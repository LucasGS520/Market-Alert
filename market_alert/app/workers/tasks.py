"""
Tarefas Celery — processamento assíncrono em background.

━━━ collector_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Coleta unitária: produto monitorado OU concorrente individual.
    Aceita exatamente um dos dois IDs.
    Orquestração de rodada (concorrentes + comparação) é responsabilidade
    de collection_orchestrator_task (app.workers.orchestrator).
    Retenta até 3 vezes em caso de falha retryable do scraper.

━━━ comparison_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Recalcula ranking, médias e status competitivo de um produto.
    Quando recebe run_id, aguarda conclusão da rodada coordenada
    (retenta até 25 × 15 s = 375 s) antes de calcular.

━━━ scheduler_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Rodado pelo Celery Beat a cada 1 minuto.
    Protegido por lock global Redis (TTL = scheduler_lock_ttl_seconds).
    Delega ao scheduler_service: consulta por prioridade temporal, lease
    atômico por produto e enqueue do collector_task.

Nota sobre async dentro do Celery:
    O Celery é síncrono por natureza. Para chamar funções async dos serviços,
    usamos run_async_task() dentro de cada task. Ele cria um event loop
    temporário e descarta conexões async no mesmo loop da execução.
"""

import time
import uuid
from decimal import Decimal

import structlog
from celery import Task
from sqlalchemy import select

from app.infra.database import AsyncSessionLocal
from app.infra.clients.scraper import ScraperClient, ScraperParseError, ScraperUnavailableError
from app.comparison.comparison_service import calculate_comparison
from app.products.competitor.competitor_model import Competitor
from app.products.competitor.competitor_service import collect_competitor
from app.products.monitored.monitored_model import MonitoredProduct
from app.products.monitored.monitored_service import collect_product
from app.workers.async_utils import run_async_task
from app.workers.celery_app import celery_app
from app.workers.collection_run import get_status, mark_deferred, mark_done, mark_failed, mark_skipped
from app.workers.redis import get_redis

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.workers.tasks.collector_task",
)
def collector_task(
    self: Task,
    product_id: str | None = None,
    competitor_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Coleta preço de um produto monitorado ou de um concorrente.

    Aceita exatamente um entre product_id e competitor_id.
    run_id identifica a rodada coordenada à qual este concorrente pertence.

    Args:
        product_id:    UUID do MonitoredProduct (string).
        competitor_id: UUID do Competitor (string).
        run_id:        UUIDv4 da rodada coordenada, quando aplicável.
    """
    redis = get_redis()
    scraper = ScraperClient()
    inicio = time.monotonic()

    if bool(product_id) == bool(competitor_id):
        logger.error(
            "collector_task_parametros_invalidos",
            product_id=product_id,
            competitor_id=competitor_id,
        )
        return

    async def _executar():
        async with AsyncSessionLocal() as session:

            # ── Coleta de produto monitorado (unitária) ─────────────────────
            if product_id:
                pid = uuid.UUID(product_id)
                produto = await session.get(MonitoredProduct, pid)

                if not produto:
                    logger.warning("produto_nao_encontrado", produto_id=product_id)
                    return
                if produto.status in ("paused", "unsupported"):
                    logger.info(
                        "produto_inelegivel_pulando",
                        produto_id=product_id,
                        status=produto.status,
                    )
                    return

                logger.info(
                    "collector_task_iniciando",
                    fase="produto",
                    produto_id=product_id,
                    task_id=self.request.id,
                    tentativa=self.request.retries,
                )

                try:
                    resultado = await collect_product(session, redis, scraper, produto)
                except ScraperUnavailableError as exc:
                    raise self.retry(exc=exc)
                except ScraperParseError as exc:
                    if exc.error_result.retryable:
                        raise self.retry(exc=exc)
                    logger.warning(
                        "coleta_permanentemente_falhada",
                        produto_id=product_id,
                        error_code=exc.error_result.error_code,
                    )
                    return

                logger.info(
                    "collector_task_concluido",
                    fase="produto",
                    produto_id=product_id,
                    sucesso=resultado.get("success", False),
                    razao=resultado.get("reason"),
                    duracao_s=round(time.monotonic() - inicio, 2),
                )

            # ── Coleta de concorrente ───────────────────────────────────────
            elif competitor_id:
                cid = uuid.UUID(competitor_id)
                concorrente = await session.get(Competitor, cid)

                if not concorrente:
                    logger.warning("concorrente_nao_encontrado", concorrente_id=competitor_id)
                    return

                monitored_id_str = str(concorrente.monitored_id)

                logger.info(
                    "collector_task_iniciando",
                    fase="concorrente",
                    concorrente_id=competitor_id,
                    run_id=run_id,
                    task_id=self.request.id,
                    tentativa=self.request.retries,
                )

                try:
                    resultado = await collect_competitor(session, redis, scraper, concorrente)
                except ScraperUnavailableError as exc:
                    # Só marca failed na última tentativa; retries intermediários ficam "pending"
                    if run_id and self.request.retries >= self.max_retries:
                        mark_failed(redis, run_id, competitor_id)
                    raise self.retry(exc=exc)
                except ScraperParseError as exc:
                    is_retryable = exc.error_result.retryable
                    is_last_attempt = self.request.retries >= self.max_retries
                    if run_id and (not is_retryable or is_last_attempt):
                        mark_failed(redis, run_id, competitor_id)
                    if is_retryable:
                        raise self.retry(exc=exc)
                    logger.warning(
                        "coleta_permanentemente_falhada",
                        concorrente_id=competitor_id,
                        error_code=exc.error_result.error_code,
                    )
                    return

                coleta_ok = resultado.get("success", False)
                razao = resultado.get("reason")

                if run_id:
                    if coleta_ok:
                        mark_done(redis, run_id, competitor_id)
                    elif razao in ("rate_limited", "lock_busy"):
                        mark_deferred(redis, run_id, competitor_id)
                    elif razao in ("ineligible_status", "unsupported"):
                        mark_skipped(redis, run_id, competitor_id)
                    elif razao == "unavailable":
                        mark_done(redis, run_id, competitor_id)
                    else:
                        mark_failed(redis, run_id, competitor_id)
                elif coleta_ok:
                    # Coleta autônoma (ex.: cadastro de novo concorrente): dispara comparação
                    comparison_task.delay(monitored_id=monitored_id_str)
                elif resultado.get("availability_changed"):
                    # Disponibilidade do concorrente mudou; recalcula posição competitiva
                    comparison_task.delay(monitored_id=monitored_id_str)

                logger.info(
                    "collector_task_concluido",
                    fase="concorrente",
                    concorrente_id=competitor_id,
                    sucesso=coleta_ok,
                    run_id=run_id,
                    duracao_s=round(time.monotonic() - inicio, 2),
                )

    run_async_task(_executar)


@celery_app.task(
    bind=True,
    max_retries=25,  # 25 × 15 s = 375 s > SLA de rodada (300 s)
    default_retry_delay=15,
    name="app.workers.tasks.comparison_task",
)
def comparison_task(
    self: Task,
    monitored_id: str,
    old_price: str | None = None,
    new_price: str | None = None,
    run_id: str | None = None,
) -> None:
    """Recalcula a comparação de preços e avalia notificações.

    Quando run_id está presente, aguarda a conclusão da rodada coordenada
    (todos os concorrentes coletados) antes de calcular, respeitando o SLA
    de collection_run_timeout_seconds.

    Args:
        monitored_id: UUID do MonitoredProduct (string).
        old_price:    Preço antes da coleta (string Decimal).
        new_price:    Preço após a coleta (string Decimal).
        run_id:       UUIDv4 da rodada coordenada, se aplicável.
    """
    redis = get_redis()

    # Aguarda ou resolve estado da rodada coordenada
    run_status: str | None = None
    if run_id:
        rodada_status = get_status(redis, run_id)
        if rodada_status == "pending":
            logger.info(
                "comparacao_aguardando_rodada",
                monitored_id=monitored_id,
                run_id=run_id,
                tentativa=self.request.retries,
            )
            raise self.retry()
        run_status = rodada_status

    async def _executar():
        nonlocal old_price, new_price
        async with AsyncSessionLocal() as session:
            from app.comparison.comparison_model import Comparison
            from app.infra.config import settings as _settings
            from app.workers.redis import is_in_cooldown

            mid = uuid.UUID(monitored_id)

            comparacao_anterior = await session.scalar(
                select(Comparison)
                .where(Comparison.monitored_id == mid)
                .order_by(Comparison.calculated_at.desc())
                .limit(1)
            )
            status_anterior = comparacao_anterior.status if comparacao_anterior else None

            comparacao = await calculate_comparison(session, redis, mid, run_id=run_id, run_status=run_status)

            if comparacao:
                produto = await session.get(MonitoredProduct, mid)
                if produto:
                    preco_anterior = Decimal(old_price) if old_price else None
                    preco_novo = Decimal(new_price) if new_price else None

                    # Evento 1: variação real do preço do produto → price_drop/price_rise
                    # Sem preço real (coleta de concorrente): variação de min_price competitivo
                    # → market_min_price_drop/rise (semântica diferente, cooldown independente)
                    evento_preco: str | None = None
                    old_price_preco = old_price
                    new_price_preco = new_price
                    if preco_anterior is not None and preco_novo is not None and preco_anterior > 0:
                        variacao_pct = float(abs(preco_novo - preco_anterior) / preco_anterior * 100)
                        if variacao_pct >= _settings.notification_delta_percent:
                            evento_preco = "price_drop" if preco_novo < preco_anterior else "price_rise"
                    elif comparacao_anterior is not None:
                        min_ant = comparacao_anterior.min_price
                        min_nov = comparacao.min_price
                        if min_ant and min_nov and min_ant != min_nov and min_ant > 0:
                            variacao_pct = float(abs(float(min_nov) - float(min_ant)) / float(min_ant) * 100)
                            if variacao_pct >= _settings.notification_delta_percent:
                                evento_preco = "market_min_price_drop" if min_nov < min_ant else "market_min_price_rise"
                                old_price_preco = str(min_ant)
                                new_price_preco = str(min_nov)

                    # Evento 2: mudança de status competitivo — cooldown próprio, independente do preço
                    evento_status: str | None = None
                    if status_anterior and comparacao.status != status_anterior:
                        evento_status = "status_change"

                    for evento, ep_old, ep_new in [
                        (evento_preco, old_price_preco, new_price_preco),
                        (evento_status, None, None),
                    ]:
                        if not evento:
                            continue
                        if is_in_cooldown(redis, mid, evento):
                            logger.debug(
                                "notificacao_cooldown_ativo",
                                produto_id=str(mid),
                                evento=evento,
                                run_status=run_status,
                            )
                            continue
                        notification_task.delay(
                            monitored_id=str(mid),
                            comparison_id=str(comparacao.id),
                            event_type=evento,
                            old_price=ep_old,
                            new_price=ep_new,
                            old_status=status_anterior,
                            new_status=comparacao.status,
                            product_url=produto.url_original,
                            product_name=produto.name,
                            run_id=run_id,
                            run_status=run_status,
                            participants_count=comparacao.participants_count,
                        )
                        logger.info(
                            "notificacao_enfileirada",
                            produto_id=str(mid),
                            evento=evento,
                            comparison_id=str(comparacao.id),
                            run_id=run_id,
                        )

                    if not evento_preco and not evento_status:
                        logger.debug(
                            "notificacao_sem_evento",
                            produto_id=str(mid),
                            run_id=run_id,
                            run_status=run_status,
                        )

    run_async_task(_executar)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.workers.tasks.notification_task",
)
def notification_task(
    self: Task,
    monitored_id: str,
    comparison_id: str | None,
    event_type: str,
    old_price: str | None,
    new_price: str | None,
    old_status: str | None,
    new_status: str | None,
    product_url: str,
    product_name: str | None = None,
    run_id: str | None = None,
    run_status: str | None = None,
    participants_count: int | None = None,
) -> None:
    """Entrega o alerta para os canais configurados com retry/backoff independente.

    Retry automático (até 3x, intervalo 60 s) para falhas retryable
    (timeout, conexão, HTTP 5xx/429). Canais já entregues com sucesso são
    idempotentes: não são reenviados em tentativas posteriores.

    Args:
        monitored_id:      UUID do MonitoredProduct (string).
        comparison_id:     UUID da Comparison que gerou o evento (string).
        event_type:        Tipo do evento: price_drop, price_rise, status_change.
        old_price:         Preço anterior (string Decimal) ou None.
        new_price:         Preço novo (string Decimal) ou None.
        old_status:        Status competitivo anterior ou None.
        new_status:        Novo status competitivo ou None.
        product_url:       URL original do produto monitorado.
        product_name:      Nome do produto (opcional).
        run_id:            ID da rodada coordenada, se aplicável.
        run_status:        Status da rodada (complete, partial, etc.), se aplicável.
        participants_count: Total de concorrentes considerados na comparação.
    """
    from app.notifications.notifications_service import (
        NotificationPayload,
        RetryableDeliveryError,
        send_notification,
    )

    redis = get_redis()

    payload = NotificationPayload(
        monitored_id=uuid.UUID(monitored_id),
        comparison_id=uuid.UUID(comparison_id) if comparison_id else None,
        event_type=event_type,
        old_price=Decimal(old_price) if old_price else None,
        new_price=Decimal(new_price) if new_price else None,
        old_status=old_status,
        new_status=new_status,
        run_id=run_id,
        run_status=run_status,
        participants_count=participants_count,
    )

    logger.info(
        "notification_task_iniciando",
        monitored_id=monitored_id,
        comparison_id=comparison_id,
        event_type=event_type,
        tentativa=self.request.retries,
    )

    async def _executar():
        async with AsyncSessionLocal() as session:
            await send_notification(session, redis, payload, product_name, product_url)

    try:
        run_async_task(_executar)
    except RetryableDeliveryError as exc:
        logger.warning(
            "notification_task_retry",
            monitored_id=monitored_id,
            comparison_id=comparison_id,
            event_type=event_type,
            tentativa=self.request.retries,
            erro=str(exc),
        )
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.scheduler_task")
def scheduler_task() -> None:
    """Verifica quais produtos estão prontos para coleta e os enfileira.

    Rodado pelo Celery Beat a cada 1 minuto. Protegido por lock global Redis
    para garantir execução única por ciclo. Delega ao scheduler_service a
    consulta, lease e enqueue, respeitando batch_size e justiça temporal.
    """
    from app.infra.config import settings
    from app.scheduling.scheduler_service import run_scheduler
    from app.workers.redis import acquire_lock, release_lock

    redis = get_redis()
    inicio = time.monotonic()

    scheduler_token = acquire_lock(redis, "lock:scheduler", timeout=settings.scheduler_lock_ttl_seconds)
    if not scheduler_token:
        logger.info("scheduler_lock_ocupado_pulando")
        return

    try:
        async def _executar():
            async with AsyncSessionLocal() as session:
                return await run_scheduler(session, redis)

        resultado = run_async_task(_executar)

        logger.info(
            "scheduler_rodou",
            total_encontrados=resultado["total_encontrados"],
            total_enfileirados=resultado["total_enfileirados"],
            skips_lease=resultado["skips"]["lease_ativo"],
            duracao_s=round(time.monotonic() - inicio, 2),
        )
    finally:
        release_lock(redis, "lock:scheduler", scheduler_token)
