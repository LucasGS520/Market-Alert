import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import httpx
import structlog
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.config import settings
from app.infra.clients.ntfy import send_ntfy
from app.notifications.notifications_model import NotificationLog
from app.workers.redis import is_in_cooldown, set_cooldown

logger = structlog.get_logger()


class RetryableDeliveryError(Exception):
    """Propagada por send_notification quando o envio falhou com erro retryable."""


def _fmt_preco(v: Decimal | None) -> str:
    return f"R$ {v:.2f}" if v is not None else "R$ ?"


@dataclass
class NotificationPayload:
    """Contrato de um alerta consolidado derivado de uma comparação.

    Regra de negócio: notificação é consequência da comparação, não parte do
    cálculo. Ela nunca altera preço, ranking ou status competitivo.
    """

    monitored_id: uuid.UUID
    comparison_id: uuid.UUID | None
    alert_type: str
    reason_codes: list[str]
    old_price: Decimal | None
    new_price: Decimal | None
    old_status: str | None
    new_status: str | None
    old_ranking: int | None = None
    new_ranking: int | None = None
    market_min_old: Decimal | None = None
    market_min_new: Decimal | None = None
    run_id: str | None = None
    run_status: str | None = None
    participants_count: int | None = None


_STATUS_RANK = {"competitive": 0, "attention": 1, "urgent": 2}


def _montar_mensagem(
    alert_type: str,
    nome_produto: str,
    old_price: Decimal | None,
    new_price: Decimal | None,
    old_status: str | None,
    new_status: str | None,
    old_ranking: int | None = None,
    new_ranking: int | None = None,
    market_min_old: Decimal | None = None,
    market_min_new: Decimal | None = None,
    reason_codes: list[str] | None = None,
) -> tuple[str, str]:
    """Retorna (titulo, mensagem) para o alert_type dado. URL vai no header Click, não aqui."""
    reason_codes = reason_codes or []

    if alert_type == "price_drop_alert":
        titulo = f"Queda de preço — {nome_produto}"
        mensagem = f"Preço caiu de {_fmt_preco(old_price)} para {_fmt_preco(new_price)}."
        contexto = _contexto_competitivo(old_status, new_status, old_ranking, new_ranking, reason_codes)
        if contexto:
            mensagem += f"\n\nTambém houve mudança competitiva:{contexto}"

    elif alert_type == "price_rise_alert":
        titulo = f"Alta de preço — {nome_produto}"
        mensagem = f"Preço subiu de {_fmt_preco(old_price)} para {_fmt_preco(new_price)}."
        contexto = _contexto_competitivo(old_status, new_status, old_ranking, new_ranking, reason_codes)
        if contexto:
            mensagem += f"\n\nTambém houve mudança competitiva:{contexto}"

    elif alert_type == "competitive_position_alert":
        rank_anterior = _STATUS_RANK.get(old_status or "", 0)
        rank_novo = _STATUS_RANK.get(new_status or "", 0)
        direcao = "perdeu" if rank_novo > rank_anterior else "ganhou"
        titulo = f"Alerta competitivo — {nome_produto}"
        mensagem = f"O produto {direcao} competitividade."
        mensagem += _contexto_competitivo(old_status, new_status, old_ranking, new_ranking, reason_codes, market_min_old, market_min_new)

    elif alert_type == "availability_alert":
        if "product_unavailable" in reason_codes:
            titulo = f"Produto indisponível — {nome_produto}"
            mensagem = "O produto ficou indisponível."
        else:
            titulo = f"Produto disponível — {nome_produto}"
            mensagem = "O produto voltou a ficar disponível."

    elif alert_type == "error_alert":
        titulo = f"Problema com Coleta — {nome_produto}"
        mensagem = "Ocorreu um erro com a coleta do produto."

    else:
        titulo = f"Alerta — {nome_produto}"
        mensagem = f"Tipo: {alert_type}"

    return titulo, mensagem


def _contexto_competitivo(
    old_status: str | None,
    new_status: str | None,
    old_ranking: int | None,
    new_ranking: int | None,
    reason_codes: list[str],
    market_min_old: Decimal | None = None,
    market_min_new: Decimal | None = None,
) -> str:
    """Monta linhas de contexto competitivo para incluir na mensagem."""
    linhas: list[str] = []
    if "status_changed" in reason_codes and old_status and new_status and old_status != new_status:
        linhas.append(f"\nStatus: {old_status} → {new_status}")
    if "ranking_changed" in reason_codes and old_ranking is not None and new_ranking is not None:
        linhas.append(f"\nRanking: {old_ranking}º → {new_ranking}º")
    if "market_min_changed" in reason_codes and market_min_old and market_min_new:
        linhas.append(f"\nMenor preço de mercado: {_fmt_preco(market_min_old)} → {_fmt_preco(market_min_new)}")
    return "".join(linhas)


def _registrar_tentativa(
    session: AsyncSession,
    payload: NotificationPayload,
    titulo: str,
    mensagem: str,
    falhou: bool,
    erro: str | None,
) -> uuid.UUID:
    """Adiciona um NotificationLog à sessão — um registro por tentativa de entrega.

    Retorna o UUID pré-gerado para uso em logs antes do commit.
    """
    log_id = uuid.uuid4()
    log = NotificationLog(
        id=log_id,
        monitored_id=payload.monitored_id,
        comparison_id=payload.comparison_id,
        event_type=payload.alert_type,
        delivery_status="failed" if falhou else "sent",
        message=mensagem,
        title=titulo,
        error_message=erro,
        attempt_count=1,
        old_price=payload.old_price,
        new_price=payload.new_price,
        old_status=payload.old_status,
        new_status=payload.new_status,
        old_ranking=payload.old_ranking,
        new_ranking=payload.new_ranking,
        market_min_old=payload.market_min_old,
        market_min_new=payload.market_min_new,
        reason_codes=payload.reason_codes or None,
        run_id=payload.run_id,
        run_status=payload.run_status,
        participants_count=payload.participants_count,
    )
    session.add(log)
    return log_id


def _is_permanent_dns_failure(exc: httpx.ConnectError) -> bool:
    """Detecta falha DNS permanente percorrendo __cause__ e __context__ da cadeia."""
    seen: set[int] = set()
    cause: BaseException | None = exc.__cause__ or exc.__context__
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(cause, socket.gaierror) and cause.args[0] in (socket.EAI_NONAME, -2):
            return True
        if "Name or service not known" in str(cause):
            return True
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
    return False


def _is_retryable(exc: Exception) -> bool:
    """Classifica se a falha de entrega admite nova tentativa."""
    if isinstance(exc, httpx.ConnectError):
        if _is_permanent_dns_failure(exc):
            return False
        return True
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


async def _ja_entregue(
    session: AsyncSession,
    comparison_id: uuid.UUID | None,
    alert_type: str,
) -> bool:
    """Verifica se já houve entrega com sucesso para a mesma comparação e alert_type."""
    if not comparison_id:
        return False
    result = await session.scalar(
        select(NotificationLog).where(
            NotificationLog.comparison_id == comparison_id,
            NotificationLog.event_type == alert_type,
            NotificationLog.delivery_status == "sent",
        )
    )
    return result is not None


async def send_notification(
    session: AsyncSession,
    redis: Redis,
    payload: NotificationPayload,
    product_name: str | None,
    product_url: str,
) -> None:
    """Entrega o alerta consolidado via ntfy e registra a tentativa.

    Raises:
        RetryableDeliveryError: se o envio falhou com erro retryable.
    """
    if not settings.ntfy_topic:
        logger.debug(
            "notificacao_ignorada_ntfy_desabilitado",
            produto_id=str(payload.monitored_id),
            alert_type=payload.alert_type,
        )
        return

    if is_in_cooldown(redis, payload.monitored_id, payload.alert_type):
        logger.debug(
            "notificacao_cooldown_ativo",
            produto_id=str(payload.monitored_id),
            alert_type=payload.alert_type,
        )
        return

    nome_produto = product_name or product_url
    titulo, mensagem = _montar_mensagem(
        payload.alert_type, nome_produto,
        payload.old_price, payload.new_price,
        payload.old_status, payload.new_status,
        payload.old_ranking, payload.new_ranking,
        payload.market_min_old, payload.market_min_new,
        payload.reason_codes,
    )

    if await _ja_entregue(session, payload.comparison_id, payload.alert_type):
        logger.info(
            "notificacao_ja_entregue",
            produto_id=str(payload.monitored_id),
            alert_type=payload.alert_type,
            comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
        )
        return

    logger.info(
        "notificacao_envio_iniciado",
        produto_id=str(payload.monitored_id),
        alert_type=payload.alert_type,
        comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
    )

    try:
        await send_ntfy(settings.ntfy_url, settings.ntfy_topic, titulo, mensagem, click_url=product_url)

        log_id = _registrar_tentativa(session, payload, titulo, mensagem, falhou=False, erro=None)
        await session.commit()
        logger.info(
            "notificacao_enviada",
            notification_id=str(log_id),
            produto_id=str(payload.monitored_id),
            alert_type=payload.alert_type,
            comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
        )
        set_cooldown(redis, payload.monitored_id, payload.alert_type)
        logger.info(
            "notificacao_cooldown_definido",
            produto_id=str(payload.monitored_id),
            alert_type=payload.alert_type,
            ttl_minutes=settings.notification_cooldown_minutes,
        )

    except Exception as exc:
        retryable = _is_retryable(exc)
        erro = str(exc)
        status_http = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.warning(
            "notificacao_falhou",
            produto_id=str(payload.monitored_id),
            comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
            retryable=retryable,
            status_http=status_http,
            erro=erro,
        )
        _registrar_tentativa(session, payload, titulo, mensagem, falhou=True, erro=erro)
        await session.commit()
        if retryable:
            raise RetryableDeliveryError(str(exc)) from exc


# ── Consultas ──────────────────────────────────────────────────────────────────

async def list_notifications(
    session: AsyncSession,
    monitored_id: uuid.UUID | None = None,
    event_type: str | None = None,
    delivery_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    competitor_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[NotificationLog]:
    stmt = select(NotificationLog).order_by(NotificationLog.sent_at.desc())
    if monitored_id is not None:
        stmt = stmt.where(NotificationLog.monitored_id == monitored_id)
    if event_type is not None:
        stmt = stmt.where(NotificationLog.event_type == event_type)
    if delivery_status is not None:
        stmt = stmt.where(NotificationLog.delivery_status == delivery_status)
    if date_from is not None:
        stmt = stmt.where(NotificationLog.sent_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(NotificationLog.sent_at <= date_to)
    if competitor_id is not None:
        stmt = stmt.where(NotificationLog.competitor_id == competitor_id)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_notification(
    session: AsyncSession,
    notification_id: uuid.UUID,
) -> NotificationLog | None:
    return await session.get(NotificationLog, notification_id)
