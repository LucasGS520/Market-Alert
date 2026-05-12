"""
Tarefas Celery — processamento assíncrono em background.

━━━ collector_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Coleta o preço de um produto monitorado OU de um concorrente.
    Aceita exatamente um dos dois IDs. Para produto principal:
        1. Cria rodada coordenada em Redis com concorrentes elegíveis
        2. Enfileira coleta de cada concorrente com run_id
        3. Enfileira comparison_task que aguarda conclusão da rodada
    Retenta até 3 vezes em caso de falha retryable do scraper.

━━━ comparison_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Recalcula ranking, médias e status competitivo de um produto.
    Quando recebe run_id, aguarda conclusão da rodada coordenada
    (retenta até 25 × 15 s = 375 s) antes de calcular.

━━━ scheduler_task ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Rodado pelo Celery Beat a cada 1 minuto.
    Busca produtos elegíveis (pending, active, unavailable, error)
    com next_check_at <= agora. Máximo 100 por execução.

Nota sobre async dentro do Celery:
    O Celery é síncrono por natureza. Para chamar funções async dos serviços,
    usamos asyncio.run() dentro de cada task — isso cria um event loop
    temporário por execução de tarefa.
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
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
from app.workers.collection_run import get_status, mark_done, mark_failed, start_run
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
        from app.infra.config import settings

        async with AsyncSessionLocal() as session:

            # ── Coleta de produto monitorado ────────────────────────────────
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

                preco_anterior = Decimal(str(produto.current_price)) if produto.current_price else None

                logger.info(
                    "collector_task_iniciando",
                    fase="produto",
                    produto_id=product_id,
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

                coleta_ok = resultado.get("success", False)

                if not coleta_ok:
                    logger.info(
                        "collector_task_concluido",
                        fase="produto",
                        produto_id=product_id,
                        sucesso=False,
                        razao=resultado.get("reason"),
                        duracao_s=round(time.monotonic() - inicio, 2),
                    )
                    return

                await session.refresh(produto)
                preco_novo = Decimal(str(produto.current_price)) if produto.current_price else None

                # Busca concorrentes elegíveis para compor a rodada
                concorrentes_result = await session.execute(
                    select(Competitor).where(
                        Competitor.monitored_id == pid,
                        Competitor.status.notin_(["paused", "unsupported"]),
                    )
                )
                concorrentes = concorrentes_result.scalars().all()

                rodada_id: str | None = None
                if concorrentes:
                    rodada_id = str(uuid.uuid4())
                    ids = [str(c.id) for c in concorrentes]
                    start_run(redis, rodada_id, product_id, ids, timeout=settings.collection_run_timeout_seconds)
                    for c in concorrentes:
                        collector_task.delay(competitor_id=str(c.id), run_id=rodada_id)
                    logger.info(
                        "rodada_coordenada_iniciada",
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

                logger.info(
                    "collector_task_concluido",
                    fase="produto",
                    produto_id=product_id,
                    sucesso=True,
                    total_concorrentes=len(concorrentes),
                    rodada_coordenada=rodada_id is not None,
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
                    tentativa=self.request.retries,
                )

                try:
                    resultado = await collect_competitor(session, redis, scraper, concorrente)
                except ScraperUnavailableError as exc:
                    if run_id:
                        mark_failed(redis, run_id, competitor_id)
                    raise self.retry(exc=exc)
                except ScraperParseError as exc:
                    if run_id:
                        mark_failed(redis, run_id, competitor_id)
                    if exc.error_result.retryable:
                        raise self.retry(exc=exc)
                    logger.warning(
                        "coleta_permanentemente_falhada",
                        concorrente_id=competitor_id,
                        error_code=exc.error_result.error_code,
                    )
                    return

                coleta_ok = resultado.get("success", False)

                if run_id:
                    # Parte de rodada coordenada: sinaliza conclusão (comparison já enfileirada)
                    mark_done(redis, run_id, competitor_id)
                elif coleta_ok:
                    # Coleta autônoma (ex.: cadastro de novo concorrente): dispara comparação
                    comparison_task.delay(monitored_id=monitored_id_str)

                logger.info(
                    "collector_task_concluido",
                    fase="concorrente",
                    concorrente_id=competitor_id,
                    sucesso=coleta_ok,
                    run_id=run_id,
                    duracao_s=round(time.monotonic() - inicio, 2),
                )

    asyncio.run(_executar())


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
        async with AsyncSessionLocal() as session:
            from app.comparison.comparison_model import Comparison
            from app.infra.config import settings as _settings
            from app.notifications.notifications_service import detect_notification_event
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

                    evento = detect_notification_event(
                        preco_anterior, preco_novo,
                        status_anterior, comparacao.status,
                        _settings.notification_delta_percent,
                    )

                    if evento and not is_in_cooldown(redis, mid, evento):
                        notification_task.delay(
                            monitored_id=str(mid),
                            comparison_id=str(comparacao.id),
                            event_type=evento,
                            old_price=old_price,
                            new_price=new_price,
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
                    elif not evento:
                        logger.debug(
                            "notificacao_sem_evento",
                            produto_id=str(mid),
                            run_id=run_id,
                            run_status=run_status,
                        )
                    else:
                        logger.debug(
                            "notificacao_cooldown_ativo",
                            produto_id=str(mid),
                            evento=evento,
                            run_status=run_status,
                        )

    asyncio.run(_executar())


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
        asyncio.run(_executar())
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

    Rodado pelo Celery Beat a cada 1 minuto. Busca produtos elegíveis
    (pending, active, unavailable, error) com next_check_at preenchido
    e <= agora. Limite de 100 por ciclo para evitar thundering herd.
    """
    inicio = time.monotonic()

    async def _executar():
        async with AsyncSessionLocal() as session:
            agora = datetime.now(timezone.utc)

            resultado = await session.execute(
                select(MonitoredProduct)
                .where(
                    and_(
                        MonitoredProduct.status.in_(["pending", "active", "unavailable", "error"]),
                        MonitoredProduct.next_check_at <= agora,
                        MonitoredProduct.next_check_at.isnot(None),
                    )
                )
                .limit(100)
            )
            produtos = resultado.scalars().all()

            for produto in produtos:
                collector_task.delay(product_id=str(produto.id))
                logger.debug(
                    "agendamento_enfileirado",
                    produto_id=str(produto.id),
                    status=produto.status,
                )

            logger.info(
                "scheduler_rodou",
                total_encontrados=len(produtos),
                total_enfileirados=len(produtos),
                duracao_s=round(time.monotonic() - inicio, 2),
            )

    asyncio.run(_executar())
