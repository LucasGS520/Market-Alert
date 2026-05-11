import asyncio
import uuid
from decimal import Decimal

import structlog
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.config import settings
from app.infra.clients.ntfy import send_ntfy
from app.infra.clients.telert import send_telert
from app.products.monitored.monitored_model import MonitoredProduct
from app.notifications.notifications_model import NotificationLog
from app.workers.redis import is_in_cooldown, set_cooldown

logger = structlog.get_logger()


def _detectar_evento(
    preco_anterior: Decimal | None,
    preco_novo: Decimal | None,
    status_anterior: str | None,
    status_novo: str | None,
    delta_pct: float,
) -> str | None:
    if preco_anterior is not None and preco_novo is not None and preco_anterior > 0:
        variacao_pct = float(abs(preco_novo - preco_anterior) / preco_anterior * 100)
        if variacao_pct >= delta_pct:
            return "price_drop" if preco_novo < preco_anterior else "price_rise"

    if status_anterior and status_novo and status_anterior != status_novo:
        return "status_change"

    return None


async def evaluate_and_send(
    session: AsyncSession,
    redis: Redis,
    product: MonitoredProduct,
    old_price: Decimal | None,
    new_price: Decimal | None,
    old_status: str | None,
    new_status: str | None,
) -> None:
    if is_in_cooldown(redis, product.id):
        logger.debug("notificacao_cooldown_ativo", produto_id=str(product.id))
        return

    evento = _detectar_evento(old_price, new_price, old_status, new_status, settings.notification_delta_percent)
    if not evento:
        return

    nome_produto = product.name or product.url
    if evento == "price_drop":
        titulo = f"Queda de preço — {nome_produto}"
        mensagem = f"Preço caiu de R$ {old_price:.2f} para R$ {new_price:.2f}\n{product.url}"
    elif evento == "price_rise":
        titulo = f"Alta de preço — {nome_produto}"
        mensagem = f"Preço subiu de R$ {old_price:.2f} para R$ {new_price:.2f}\n{product.url}"
    else:
        titulo = f"Mudança de status — {nome_produto}"
        mensagem = f"Status mudou de '{old_status}' para '{new_status}'\n{product.url}"

    tarefas = []
    canais_enviados = []

    if settings.ntfy_topic:
        tarefas.append(send_ntfy(settings.ntfy_url, settings.ntfy_topic, titulo, mensagem))
        canais_enviados.append("ntfy")

    if settings.telert_token:
        tarefas.append(send_telert(settings.telert_token, f"{titulo}\n{mensagem}"))
        canais_enviados.append("telert")

    if tarefas:
        await asyncio.gather(*tarefas, return_exceptions=True)

    set_cooldown(redis, product.id)

    for canal in canais_enviados:
        log = NotificationLog(
            monitored_id=product.id,
            event_type=evento,
            message=mensagem,
            channel=canal,
        )
        session.add(log)
    await session.commit()

    logger.info("notificacao_enviada", produto_id=str(product.id), evento=evento, canais=canais_enviados)
