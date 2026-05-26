"""Tarefa de orquestração de rodada de coleta.

Responsável por coordenar a sequência completa:
    1. Tentar coletar a oferta de referência (MonitoredProduct) via collect_product.
    2. Selecionar concorrentes elegíveis.
    3. Criar rodada coordenada no Redis.
    4. Enfileirar coletas de concorrentes (collector_task).
    5. Enfileirar comparação (comparison_task).
    6. Liberar o lease (collection_lease_until) ao encerrar.

Falha na coleta da referência não aborta a rodada de mercado — apenas torna
a posição da referência indisponível no snapshot (ver comparison_service.py).
A rodada só é abortada por: produto inexistente, paused/unsupported,
scraper completamente indisponível, ou produto deletado durante a coleta.

Separada do collector_task, que fica responsável pela coleta unitária.
"""

import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from celery import Task
from sqlalchemy import select

from app.infra.clients.scraper import ScraperClient, ScraperUnavailableError
from app.infra.database import AsyncSessionLocal
from app.products.competitor.competitor_model import Competitor
from app.products.monitored.monitored_model import MonitoredProduct
from app.products.monitored.monitored_service import collect_product
from app.utils.async_utils import run_async_task
from app.workers.celery_app import celery_app
from app.workers.collection_run import start_run
from app.workers.redis import get_redis

logger = structlog.get_logger()


def _liberar_lease(produto: MonitoredProduct) -> None:
    """Libera o lease de coleta e registra o horário de término da rodada.

    Deve ser chamada em todos os caminhos de encerramento — inclusive os de erro.
    Sem liberação, o produto fica bloqueado para o scheduler até o TTL do lease expirar.
    """
    produto.collection_lease_until = None
    produto.last_collection_finished_at = datetime.now(timezone.utc)


@celery_app.task(
    bind=True,
    name="app.workers.orchestrator.collection_orchestrator_task",
)
def collection_orchestrator_task(self: Task, product_id: str) -> None:
    """Orquestra a rodada de mercado: referência → concorrentes → comparação.

    Falha na coleta da referência não encerra a rodada — apenas torna sua
    posição indisponível no snapshot. Libera collection_lease_until em todo
    desfecho não-retryable para que o scheduler possa reenfileirar.

    Args:
        product_id: UUID do MonitoredProduct (string).
    """
    from app.workers.tasks import collector_task, comparison_task  # late — evita circular

    redis = get_redis()
    scraper = ScraperClient()
    inicio = time.monotonic()

    async def _executar():
        from app.infra.config import settings

        async with AsyncSessionLocal() as session:
            pid = uuid.UUID(product_id)
            produto = await session.get(MonitoredProduct, pid)

            if not produto:
                logger.warning("orquestrador_produto_nao_encontrado", produto_id=product_id)
                return

            if produto.status in ("paused", "unsupported"):
                logger.info(
                    "orquestrador_produto_inelegivel",
                    produto_id=product_id,
                    status=produto.status,
                )
                _liberar_lease(produto)
                await session.commit()
                return

            preco_anterior = Decimal(str(produto.current_price)) if produto.current_price else None

            logger.info(
                "orquestrador_iniciando",
                produto_id=product_id,
                task_id=self.request.id,
                tentativa=self.request.retries,
            )

            try:
                resultado = await collect_product(session, redis, scraper, produto)
            except ScraperUnavailableError:
                # service already recorded the error; release lease so scheduler can re-enqueue
                _liberar_lease(produto)
                await session.commit()
                logger.warning(
                    "orquestrador_scraper_indisponivel_lease_liberado",
                    produto_id=product_id,
                )
                return

            coleta_ok = resultado.get("success", False)
            reason = resultado.get("reason")

            if not coleta_ok and reason == "product_deleted":
                # Produto removido durante a rodada: sem âncora estrutural, abort total.
                logger.info(
                    "orquestrador_produto_deletado",
                    produto_id=product_id,
                    duracao_s=round(time.monotonic() - inicio, 2),
                )
                return

            if not coleta_ok:
                logger.info(
                    "orquestrador_referencia_falhou",
                    produto_id=product_id,
                    razao=reason,
                    duracao_s=round(time.monotonic() - inicio, 2),
                )
                # Referência indisponível; o mercado continua com os concorrentes.
                # comparison_service abortará apenas se não houver nenhuma oferta válida.

            # ── Orquestrar rodada de mercado (com ou sem referência) ──────────
            await session.refresh(produto)
            preco_novo = Decimal(str(produto.current_price)) if produto.current_price else None

            concorrentes_result = await session.execute(
                select(Competitor).where(
                    Competitor.monitored_id == pid,
                    Competitor.status.notin_(["paused", "unsupported"]),
                )
            )
            concorrentes = list(concorrentes_result.scalars().all())

            # Sem concorrentes elegíveis: comparação é disparada imediatamente sem esperar rodada.
            # com run_id=None, comparison_task não aguarda coordenação e usa apenas o produto principal.
            rodada_id: str | None = None
            if concorrentes:
                rodada_id = str(uuid.uuid4())
                ids = [str(c.id) for c in concorrentes]
                start_run(
                    redis, rodada_id, product_id, ids,
                    timeout=settings.collection_run_timeout_seconds,
                )
                for c in concorrentes:
                    collector_task.delay(competitor_id=str(c.id), run_id=rodada_id)
                logger.info(
                    "orquestrador_rodada_iniciada",
                    produto_id=product_id,
                    run_id=rodada_id,
                    total_concorrentes=len(concorrentes),
                )

            comparison_task.delay(
                monitored_id=product_id,
                old_price=str(preco_anterior) if preco_anterior else None,
                new_price=str(preco_novo) if preco_novo else None,
                run_id=rodada_id,
            )

            _liberar_lease(produto)
            await session.commit()

            logger.info(
                "orquestrador_concluido",
                produto_id=product_id,
                referencia_coletada=coleta_ok,
                total_concorrentes=len(concorrentes),
                rodada_coordenada=rodada_id is not None,
                duracao_s=round(time.monotonic() - inicio, 2),
            )

    run_async_task(_executar)
