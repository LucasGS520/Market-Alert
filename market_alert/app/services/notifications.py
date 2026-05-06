"""
Serviço de avaliação e disparo de notificações.

Este serviço é chamado após cada cálculo de comparação. Ele determina
se algo relevante aconteceu (mudança de preço ou de status competitivo)
e, se sim, envia a notificação pelos canais configurados.

Eventos detectados:
    price_drop    → preço caiu mais que o delta configurado (padrão: 5%)
    price_rise    → preço subiu mais que o delta configurado
    status_change → status competitivo mudou (ex: attention → urgent)

Cooldown:
    Após enviar uma notificação, o sistema aguarda o período de cooldown
    (padrão: 30 minutos) antes de notificar novamente sobre o mesmo produto.
    Isso evita spam de alertas em momentos de muita volatilidade.

    Chave Redis: ratelimit:notify:{monitored_id}
    TTL: cooldown_minutes × 60 segundos

Canais:
    ntfy.sh e Telert são chamados em paralelo (asyncio.gather).
    Falha em um canal não impede o outro de entregar.
"""

import asyncio
import uuid
from decimal import Decimal

import structlog
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ntfy import send_ntfy
from app.clients.telert import send_telert
from app.core.config import settings
from app.models.monitored_product import MonitoredProduct
from app.models.notification_log import NotificationLog

logger = structlog.get_logger()


def _chave_cooldown(monitored_id: uuid.UUID) -> str:
    """Retorna a chave Redis de cooldown para um produto."""
    return f"ratelimit:notify:{monitored_id}"


def _em_cooldown(redis: Redis, monitored_id: uuid.UUID) -> bool:
    """Verifica se o produto está no período de silêncio pós-notificação."""
    return bool(redis.exists(_chave_cooldown(monitored_id)))


def _ativar_cooldown(redis: Redis, monitored_id: uuid.UUID) -> None:
    """Ativa o cooldown após uma notificação ser enviada."""
    ttl = settings.notification_cooldown_minutes * 60
    redis.set(_chave_cooldown(monitored_id), "1", ex=ttl)


def _detectar_evento(
    preco_anterior: Decimal | None,
    preco_novo: Decimal | None,
    status_anterior: str | None,
    status_novo: str | None,
    delta_pct: float,
) -> str | None:
    """
    Determina se houve um evento relevante que justifica notificação.

    Args:
        preco_anterior: Preço antes da coleta.
        preco_novo:     Preço após a coleta.
        status_anterior: Status competitivo anterior.
        status_novo:     Status competitivo atual.
        delta_pct:       Variação mínima de preço (%) para notificar.

    Returns:
        Nome do evento ("price_drop", "price_rise", "status_change") ou None.
    """
    # Verifica variação de preço
    if preco_anterior is not None and preco_novo is not None and preco_anterior > 0:
        variacao_pct = float(abs(preco_novo - preco_anterior) / preco_anterior * 100)
        if variacao_pct >= delta_pct:
            return "price_drop" if preco_novo < preco_anterior else "price_rise"

    # Verifica mudança de status competitivo
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
    """
    Avalia se deve enviar notificação e, se sim, envia por todos os canais.

    Args:
        session:     Sessão do banco para gravar NotificationLog.
        redis:       Cliente Redis para verificar/ativar cooldown.
        product:     Produto monitorado (para nome e URL na mensagem).
        old_price:   Preço antes da última coleta.
        new_price:   Preço após a última coleta.
        old_status:  Status competitivo antes.
        new_status:  Status competitivo após o recálculo.
    """
    # Não notifica se ainda está no período de cooldown
    if _em_cooldown(redis, product.id):
        logger.debug("notificacao_cooldown_ativo", produto_id=str(product.id))
        return

    evento = _detectar_evento(old_price, new_price, old_status, new_status, settings.notification_delta_percent)
    if not evento:
        return  # Nenhuma mudança significativa detectada

    # Monta a mensagem com contexto claro para o usuário
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

    # Envia para todos os canais configurados em paralelo
    tarefas = []
    canais_enviados = []

    if settings.ntfy_topic:
        tarefas.append(send_ntfy(settings.ntfy_url, settings.ntfy_topic, titulo, mensagem))
        canais_enviados.append("ntfy")

    if settings.telert_token:
        tarefas.append(send_telert(settings.telert_token, f"{titulo}\n{mensagem}"))
        canais_enviados.append("telert")

    if tarefas:
        # return_exceptions=True: falha em um canal não cancela o outro
        await asyncio.gather(*tarefas, return_exceptions=True)

    # Ativa cooldown imediatamente após o envio
    _ativar_cooldown(redis, product.id)

    # Registra cada canal individualmente no banco para auditoria
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
