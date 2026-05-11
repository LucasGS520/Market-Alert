"""
Tarefas Celery — processamento assíncrono em background.

Este módulo define as três tarefas que compõem o pipeline de monitoramento:

━━━ collector_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Coleta o preço de um produto monitorado OU de um concorrente.
    Quando coleta um produto principal, automaticamente:
        1. Enfileira a coleta de todos os seus concorrentes
        2. Enfileira o recálculo da comparação
    Retenta até 3 vezes em caso de falha do scraper.

━━━ comparison_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Recalcula ranking, médias e status competitivo de um produto monitorado.
    Ao final, avalia e dispara notificações se necessário.

━━━ scheduler_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Rodado pelo Celery Beat a cada 1 minuto.
    Consulta quais produtos têm next_check_at <= agora e enfileira
    uma collector_task para cada um.

Nota sobre async dentro do Celery:
    O Celery é síncrono por natureza. Para chamar funções async dos serviços,
    usamos asyncio.run() dentro de cada task — isso cria um event loop
    temporário por execução de tarefa.
"""

import asyncio
import uuid
from decimal import Decimal

import structlog
from celery import Task
from sqlalchemy import and_, select

from app.infra.database import AsyncSessionLocal
from app.infra.clients.scraper import ScraperClient, ScraperParseError, ScraperUnavailableError
from app.comparison.comparison_service import calculate_comparison
from app.products.competitor.competitor_model import Competitor
from app.products.competitor.competitor_service import collect_competitor
from app.products.monitored.monitored_model import MonitoredProduct
from app.products.monitored.monitored_service import collect_product
from app.workers.celery_app import celery_app
from app.workers.redis import get_redis

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # aguarda 60s entre tentativas
    name="app.workers.tasks.collector_task",
)
def collector_task(
    self: Task,
    product_id: str | None = None,
    competitor_id: str | None = None,
) -> None:
    """
    Coleta o preço de um produto monitorado ou de um concorrente.

    Aceita exatamente um dos dois parâmetros. Se product_id for passado,
    após a coleta enfileira a coleta dos concorrentes e o recálculo.

    Args:
        product_id:    UUID do MonitoredProduct (como string).
        competitor_id: UUID do Competitor (como string).
    """
    redis = get_redis()
    scraper = ScraperClient()

    async def _executar():
        async with AsyncSessionLocal() as session:
            if product_id:
                pid = uuid.UUID(product_id)
                produto = await session.get(MonitoredProduct, pid)

                if not produto:
                    logger.warning("produto_nao_encontrado", produto_id=product_id)
                    return
                if produto.status == "paused":
                    logger.info("produto_pausado_pulando", produto_id=product_id)
                    return

                # Guarda preço anterior para comparação na notification
                preco_anterior = Decimal(str(produto.current_price)) if produto.current_price else None

                try:
                    await collect_product(session, redis, scraper, produto)
                except ScraperUnavailableError as exc:
                    raise self.retry(exc=exc)
                except ScraperParseError as exc:
                    if exc.error_result.retryable:
                        raise self.retry(exc=exc)
                    logger.warning(
                        "erro_permanente_sem_retry",
                        produto_id=product_id,
                        error_code=exc.error_result.error_code,
                    )

                await session.refresh(produto)
                preco_novo = Decimal(str(produto.current_price)) if produto.current_price else None

                # Enfileira coleta de cada concorrente cadastrado
                concorrentes_result = await session.execute(
                    select(Competitor).where(Competitor.monitored_id == pid)
                )
                for concorrente in concorrentes_result.scalars().all():
                    collector_task.delay(competitor_id=str(concorrente.id))

                # Enfileira recálculo da comparação passando preços para avaliação de alertas
                comparison_task.delay(
                    monitored_id=product_id,
                    old_price=str(preco_anterior) if preco_anterior else None,
                    new_price=str(preco_novo) if preco_novo else None,
                    old_status=None,  # o comparison_task determinará o status atual
                )

            elif competitor_id:
                cid = uuid.UUID(competitor_id)
                concorrente = await session.get(Competitor, cid)

                if not concorrente:
                    logger.warning("concorrente_nao_encontrado", concorrente_id=competitor_id)
                    return

                try:
                    await collect_competitor(session, redis, scraper, concorrente)
                except ScraperUnavailableError as exc:
                    raise self.retry(exc=exc)
                except ScraperParseError as exc:
                    if exc.error_result.retryable:
                        raise self.retry(exc=exc)
                    logger.warning(
                        "erro_permanente_sem_retry",
                        concorrente_id=competitor_id,
                        error_code=exc.error_result.error_code,
                    )

    asyncio.run(_executar())


@celery_app.task(bind=True, name="app.workers.tasks.comparison_task")
def comparison_task(
    self: Task,
    monitored_id: str,
    old_price: str | None = None,
    new_price: str | None = None,
    old_status: str | None = None,
) -> None:
    """
    Recalcula a comparação de preços e avalia notificações.

    Args:
        monitored_id: UUID do MonitoredProduct.
        old_price:    Preço antes da coleta (string Decimal), para detectar variação.
        new_price:    Preço após a coleta (string Decimal).
        old_status:   Status competitivo anterior, para detectar mudança de status.
    """
    redis = get_redis()

    async def _executar():
        async with AsyncSessionLocal() as session:
            mid = uuid.UUID(monitored_id)

            # Calcula e persiste a nova comparação
            comparacao = await calculate_comparison(session, redis, mid)

            if comparacao:
                # Avalia se deve enviar notificação com base na variação de preço/status
                from app.notifications.notifications_service import evaluate_and_send

                produto = await session.get(MonitoredProduct, mid)
                if produto:
                    await evaluate_and_send(
                        session=session,
                        redis=redis,
                        product=produto,
                        old_price=Decimal(old_price) if old_price else None,
                        new_price=Decimal(new_price) if new_price else None,
                        old_status=old_status,
                        new_status=comparacao.status,
                    )

    asyncio.run(_executar())


@celery_app.task(name="app.workers.tasks.scheduler_task")
def scheduler_task() -> None:
    """
    Verifica quais produtos estão prontos para coleta e os enfileira.

    Rodado pelo Celery Beat a cada 1 minuto. Consulta produtos com
    status='active' e next_check_at <= agora, enfileirando uma
    collector_task para cada um.
    """
    from datetime import datetime, timezone

    async def _executar():
        async with AsyncSessionLocal() as session:
            agora = datetime.now(timezone.utc)

            # Busca todos os produtos que já passaram do horário agendado
            resultado = await session.execute(
                select(MonitoredProduct).where(
                    and_(
                        MonitoredProduct.status == "active",
                        MonitoredProduct.next_check_at <= agora,
                    )
                )
            )
            produtos = resultado.scalars().all()

            for produto in produtos:
                collector_task.delay(product_id=str(produto.id))
                logger.debug("scheduler_enfileirou", produto_id=str(produto.id))

            if produtos:
                logger.info("scheduler_rodou", total_enfileirados=len(produtos))

    asyncio.run(_executar())
