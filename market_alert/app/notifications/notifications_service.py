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
from app.infra.clients.telert import send_telert
from app.notifications.notifications_model import NotificationLog
from app.workers.redis import set_cooldown

logger = structlog.get_logger()


class RetryableDeliveryError(Exception):
    """Propagada por send_notification quando ao menos um canal falhou com erro retryable."""


@dataclass
class NotificationPayload:
    """Contrato mínimo de uma notificação derivada de uma comparação.

    Regra de negócio: notificação é consequência da comparação, não parte do
    cálculo. Ela nunca altera preço, ranking ou status competitivo.
    """

    monitored_id: uuid.UUID
    comparison_id: uuid.UUID | None
    event_type: str
    old_price: Decimal | None
    new_price: Decimal | None
    old_status: str | None
    new_status: str | None
    run_id: str | None
    run_status: str | None
    participants_count: int | None


def detect_notification_event(
    preco_anterior: Decimal | None,
    preco_novo: Decimal | None,
    status_anterior: str | None,
    status_novo: str | None,
    delta_pct: float,
) -> str | None:
    """Detecta o tipo de evento notificável a partir de uma comparação.

    Prioridade explícita: variação de preço (price_drop / price_rise) tem
    precedência sobre mudança de status competitivo (status_change).
    Um único evento é gerado por comparação.
    """
    if preco_anterior is not None and preco_novo is not None and preco_anterior > 0:
        variacao_pct = float(abs(preco_novo - preco_anterior) / preco_anterior * 100)
        if variacao_pct >= delta_pct:
            return "price_drop" if preco_novo < preco_anterior else "price_rise"

    if status_anterior and status_novo and status_anterior != status_novo:
        return "status_change"

    return None


def _montar_mensagem(
    evento: str,
    nome_produto: str,
    url_original: str,
    old_price: Decimal | None,
    new_price: Decimal | None,
    old_status: str | None,
    new_status: str | None,
) -> tuple[str, str]:
    """Retorna (titulo, mensagem) para o evento dado."""
    if evento == "price_drop":
        titulo = f"Queda de preço — {nome_produto}"
        mensagem = f"Preço caiu de R$ {old_price:.2f} para R$ {new_price:.2f}\n{url_original}"
    elif evento == "price_rise":
        titulo = f"Alta de preço — {nome_produto}"
        mensagem = f"Preço subiu de R$ {old_price:.2f} para R$ {new_price:.2f}\n{url_original}"
    elif evento == "market_min_price_drop":
        titulo = f"Novo mínimo de mercado — {nome_produto}"
        mensagem = f"Menor preço do mercado caiu de R$ {old_price:.2f} para R$ {new_price:.2f}\n{url_original}"
    elif evento == "market_min_price_rise":
        titulo = f"Alta no mínimo de mercado — {nome_produto}"
        mensagem = f"Menor preço do mercado subiu de R$ {old_price:.2f} para R$ {new_price:.2f}\n{url_original}"
    else:
        titulo = f"Mudança de status — {nome_produto}"
        mensagem = f"Status mudou de '{old_status}' para '{new_status}'\n{url_original}"
    return titulo, mensagem


def _canais_habilitados() -> list[str]:
    """Retorna nomes dos canais com configuração presente."""
    canais = []
    if settings.ntfy_topic:
        canais.append("ntfy")
    if settings.telert_token:
        canais.append("telert")
    return canais


def _registrar_tentativa(
    session: AsyncSession,
    payload: NotificationPayload,
    canal: str,
    titulo: str,
    mensagem: str,
    falhou: bool,
    erro: str | None,
) -> None:
    """Adiciona um NotificationLog à sessão — um registro por tentativa de canal."""
    log = NotificationLog(
        monitored_id=payload.monitored_id,
        comparison_id=payload.comparison_id,
        event_type=payload.event_type,
        channel=canal,
        delivery_status="failed" if falhou else "sent",
        message=mensagem,
        title=titulo,
        error_message=erro,
        attempt_count=1,
        old_price=payload.old_price,
        new_price=payload.new_price,
        old_status=payload.old_status,
        new_status=payload.new_status,
        run_id=payload.run_id,
        run_status=payload.run_status,
        participants_count=payload.participants_count,
    )
    session.add(log)


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


async def _canal_ja_entregue(
    session: AsyncSession,
    comparison_id: uuid.UUID | None,
    event_type: str,
    canal: str,
) -> bool:
    """Verifica se este canal já recebeu entrega com sucesso para a mesma comparação."""
    if not comparison_id:
        return False
    result = await session.scalar(
        select(NotificationLog).where(
            NotificationLog.comparison_id == comparison_id,
            NotificationLog.event_type == event_type,
            NotificationLog.channel == canal,
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
    """Entrega o alerta para todos os canais habilitados e registra a tentativa por canal.

    Raises:
        RetryableDeliveryError: se ao menos um canal falhou com erro retryable.
            Canais já entregues com sucesso são idempotentes na próxima tentativa.
    """
    nome_produto = product_name or product_url
    titulo, mensagem = _montar_mensagem(
        payload.event_type, nome_produto, product_url,
        payload.old_price, payload.new_price,
        payload.old_status, payload.new_status,
    )

    canais = _canais_habilitados()
    if not canais:
        logger.info(
            "notificacao_sem_canal",
            produto_id=str(payload.monitored_id),
            evento=payload.event_type,
            comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
        )
        # Evento detectado mas sem canais; registra skipped para auditabilidade completa
        log = NotificationLog(
            monitored_id=payload.monitored_id,
            comparison_id=payload.comparison_id,
            event_type=payload.event_type,
            channel=None,
            delivery_status="skipped",
            message=mensagem,
            title=titulo,
            attempt_count=1,
            old_price=payload.old_price,
            new_price=payload.new_price,
            old_status=payload.old_status,
            new_status=payload.new_status,
            run_id=payload.run_id,
            run_status=payload.run_status,
            participants_count=payload.participants_count,
        )
        session.add(log)
        await session.commit()
        return

    logger.info(
        "notificacao_envio_iniciado",
        produto_id=str(payload.monitored_id),
        evento=payload.event_type,
        comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
        canais=canais,
    )

    algum_sucesso = False
    retryable_exc: Exception | None = None

    for canal in canais:
        if await _canal_ja_entregue(session, payload.comparison_id, payload.event_type, canal):
            logger.info(
                "notificacao_canal_ja_entregue",
                canal=canal,
                comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
            )
            algum_sucesso = True
            continue

        try:
            if canal == "ntfy":
                await send_ntfy(settings.ntfy_url, settings.ntfy_topic, titulo, mensagem)
            elif canal == "telert":
                await send_telert(settings.telert_token, f"{titulo}\n{mensagem}")

            algum_sucesso = True
            logger.info(
                "notificacao_enviada",
                canal=canal,
                produto_id=str(payload.monitored_id),
                evento=payload.event_type,
                comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
            )
            _registrar_tentativa(session, payload, canal, titulo, mensagem, falhou=False, erro=None)

        except Exception as exc:
            retryable = _is_retryable(exc)
            erro = str(exc)
            logger.warning(
                "notificacao_falhou",
                canal=canal,
                produto_id=str(payload.monitored_id),
                comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
                retryable=retryable,
                erro=erro,
            )
            _registrar_tentativa(session, payload, canal, titulo, mensagem, falhou=True, erro=erro)
            if retryable and retryable_exc is None:
                retryable_exc = exc

    await session.commit()
    logger.info(
        "notificacao_log_registrado",
        comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
    )

    if algum_sucesso:
        set_cooldown(redis, payload.monitored_id, payload.event_type)
        logger.info(
            "notificacao_cooldown_definido",
            produto_id=str(payload.monitored_id),
            evento=payload.event_type,
        )
    else:
        logger.warning(
            "notificacao_todos_canais_falharam",
            produto_id=str(payload.monitored_id),
            evento=payload.event_type,
            comparison_id=str(payload.comparison_id) if payload.comparison_id else None,
        )

    if retryable_exc and not algum_sucesso:
        raise RetryableDeliveryError(str(retryable_exc)) from retryable_exc


# ── Consultas ──────────────────────────────────────────────────────────────────

async def list_notifications(
    session: AsyncSession,
    monitored_id: uuid.UUID | None = None,
    event_type: str | None = None,
    channel: str | None = None,
    delivery_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
) -> list[NotificationLog]:
    stmt = select(NotificationLog).order_by(NotificationLog.sent_at.desc())
    if monitored_id is not None:
        stmt = stmt.where(NotificationLog.monitored_id == monitored_id)
    if event_type is not None:
        stmt = stmt.where(NotificationLog.event_type == event_type)
    if channel is not None:
        stmt = stmt.where(NotificationLog.channel == channel)
    if delivery_status is not None:
        stmt = stmt.where(NotificationLog.delivery_status == delivery_status)
    if date_from is not None:
        stmt = stmt.where(NotificationLog.sent_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(NotificationLog.sent_at <= date_to)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_notification(
    session: AsyncSession,
    notification_id: uuid.UUID,
) -> NotificationLog | None:
    return await session.get(NotificationLog, notification_id)
