import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import structlog
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.clients.scraper import ScraperClient, ScraperParseError, ScraperUnavailableError
from app.infra.scraper_errors import classify_scraper_error
from app.products.monitored.monitored_model import MonitoredProduct
from app.products.price_history.price_model import PriceHistory
from app.scheduling.policy import CheckReason, classify_stability, compute_next_check, is_significant_change
from app.workers.redis import acquire_lock, check_rate_limit, release_lock, set_domain_cooldown

logger = structlog.get_logger()


# ── CRUD ────────────────────────────────────────────────────────────────────────

async def list_products(session: AsyncSession) -> list[MonitoredProduct]:
    resultado = await session.execute(
        select(MonitoredProduct).order_by(MonitoredProduct.created_at.desc())
    )
    return list(resultado.scalars().all())


async def list_products_with_comparisons(
    session: AsyncSession,
) -> list[tuple["MonitoredProduct", "Comparison | None", int]]:
    from sqlalchemy import func
    from app.comparison.comparison_model import Comparison
    from app.products.competitor.competitor_model import Competitor

    products_q = await session.execute(
        select(MonitoredProduct).order_by(MonitoredProduct.created_at.desc())
    )
    products = list(products_q.scalars().all())
    if not products:
        return []

    product_ids = [p.id for p in products]

    latest_calc_subq = (
        select(
            Comparison.monitored_id,
            func.max(Comparison.calculated_at).label("max_calc"),
        )
        .where(Comparison.monitored_id.in_(product_ids))
        .group_by(Comparison.monitored_id)
        .subquery()
    )
    latest_comparisons_q = await session.execute(
        select(Comparison).join(
            latest_calc_subq,
            (Comparison.monitored_id == latest_calc_subq.c.monitored_id)
            & (Comparison.calculated_at == latest_calc_subq.c.max_calc),
        )
    )
    latest_by_product = {c.monitored_id: c for c in latest_comparisons_q.scalars().all()}

    counts_q = await session.execute(
        select(Competitor.monitored_id, func.count(Competitor.id).label("cnt"))
        .where(Competitor.monitored_id.in_(product_ids))
        .group_by(Competitor.monitored_id)
    )
    competitor_counts = {row.monitored_id: row.cnt for row in counts_q}

    return [
        (p, latest_by_product.get(p.id), competitor_counts.get(p.id, 0))
        for p in products
    ]


async def create_product(session: AsyncSession, url: str, name: str | None) -> MonitoredProduct:
    from app.products.url_utils import normalize_url

    url_normalized = normalize_url(url)
    existente = await session.scalar(
        select(MonitoredProduct).where(MonitoredProduct.url_normalized == url_normalized)
    )
    if existente:
        raise HTTPException(status_code=409, detail="Esta URL já está sendo monitorada")

    produto = MonitoredProduct(
        url_original=url,
        url_normalized=url_normalized,
        name=name,
        status="pending",
        next_check_at=datetime.now(timezone.utc),
    )
    session.add(produto)
    await session.commit()
    await session.refresh(produto)
    return produto


async def pause_product(session: AsyncSession, product_id: uuid.UUID) -> MonitoredProduct:
    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")
    produto.status = "paused"
    await session.commit()
    await session.refresh(produto)
    return produto


async def resume_product(session: AsyncSession, product_id: uuid.UUID) -> MonitoredProduct:
    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")
    produto.status = "active"
    produto.next_check_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(produto)
    return produto


async def delete_product(session: AsyncSession, product_id: uuid.UUID) -> None:
    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")
    await session.delete(produto)
    await session.commit()


async def get_with_latest_comparison(
    session: AsyncSession, product_id: uuid.UUID
) -> tuple["MonitoredProduct", "Comparison | None"]:  # noqa: F821
    from app.comparison.comparison_model import Comparison  # local import avoids circular at module load

    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")

    ultima_comparacao = await session.scalar(
        select(Comparison)
        .where(Comparison.monitored_id == product_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(1)
    )
    return produto, ultima_comparacao


# ── Coleta ─────────────────────────────────────────────────────────────────────

async def collect_product(
    session: AsyncSession,
    redis: Redis,
    scraper: ScraperClient,
    product: MonitoredProduct,
) -> dict:
    """Coleta preço do produto monitorado.

    Returns:
        dict com chave "success" (bool) e campos adicionais por resultado.
    Raises:
        ScraperUnavailableError: scraper inacessível — Celery deve retentar.
        ScraperParseError: erro retryable do scraper — Celery deve retentar.
    """
    from app.infra.config import settings

    inicio = time.monotonic()

    if product.status in ("paused", "unsupported"):
        logger.info("coleta_ignorada_status", produto_id=str(product.id), status=product.status)
        return {"success": False, "reason": "ineligible_status"}

    chave_lock = f"lock:collect:{product.id}"
    lock_token = acquire_lock(redis, chave_lock, timeout=300)
    if not lock_token:
        now = datetime.now(timezone.utc)
        logger.info("coleta_pulada_lock_ativo", produto_id=str(product.id))
        next_dt, delay = compute_next_check(
            reason="lock_busy",
            now=now,
            stability_level=product.stability_level,
            last_scheduled_delay_minutes=product.last_scheduled_delay_minutes,
            consecutive_failures=product.consecutive_failures or 0,
            base_backoff_minutes=settings.collection_retry_base_delay_minutes,
            max_backoff_minutes=settings.collection_retry_max_delay_minutes,
            rate_limit_min=settings.rate_limit_reschedule_min_minutes,
            rate_limit_max=settings.rate_limit_reschedule_max_minutes,
            lock_busy_min=settings.lock_busy_reschedule_min_minutes,
            lock_busy_max=settings.lock_busy_reschedule_max_minutes,
        )
        product.next_check_at = next_dt
        product.last_scheduled_delay_minutes = delay
        product.next_check_reason = "lock_busy"
        await session.commit()
        return {"success": False, "reason": "lock_busy"}

    logger.info("lock_adquirido", produto_id=str(product.id))

    try:
        dominio = urlparse(product.url_original).netloc
        if not check_rate_limit(redis, dominio):
            now = datetime.now(timezone.utc)
            logger.info(
                "coleta_rate_limited",
                dominio=dominio,
                produto_id=str(product.id),
                ttl_s=settings.domain_rate_limit_ttl_seconds,
            )
            next_dt, delay = compute_next_check(
                reason="rate_limited",
                now=now,
                stability_level=product.stability_level,
                last_scheduled_delay_minutes=product.last_scheduled_delay_minutes,
                consecutive_failures=product.consecutive_failures or 0,
                base_backoff_minutes=settings.collection_retry_base_delay_minutes,
                max_backoff_minutes=settings.collection_retry_max_delay_minutes,
                rate_limit_min=settings.rate_limit_reschedule_min_minutes,
                rate_limit_max=settings.rate_limit_reschedule_max_minutes,
                lock_busy_min=settings.lock_busy_reschedule_min_minutes,
                lock_busy_max=settings.lock_busy_reschedule_max_minutes,
            )
            product.next_check_at = next_dt
            product.last_scheduled_delay_minutes = delay
            product.next_check_reason = "rate_limited"
            await session.commit()
            return {"success": False, "reason": "rate_limited"}

        logger.info(
            "iniciando_coleta",
            produto_id=str(product.id),
            url=product.url_original,
        )

        try:
            resultado = await scraper.parse(product.url_original)
        except ScraperUnavailableError as exc:
            now = datetime.now(timezone.utc)
            logger.warning(
                "scraper_indisponivel",
                produto_id=str(product.id),
                erro=str(exc),
                scraper_timeout_s=settings.scraper_timeout_seconds,
            )
            product.status = "error"
            product.last_checked_at = now
            product.consecutive_failures = (product.consecutive_failures or 0) + 1
            next_dt, delay = compute_next_check(
                reason="error_backoff",
                now=now,
                stability_level=product.stability_level,
                last_scheduled_delay_minutes=product.last_scheduled_delay_minutes,
                consecutive_failures=product.consecutive_failures,
                base_backoff_minutes=settings.collection_retry_base_delay_minutes,
                max_backoff_minutes=settings.collection_retry_max_delay_minutes,
                rate_limit_min=settings.rate_limit_reschedule_min_minutes,
                rate_limit_max=settings.rate_limit_reschedule_max_minutes,
                lock_busy_min=settings.lock_busy_reschedule_min_minutes,
                lock_busy_max=settings.lock_busy_reschedule_max_minutes,
            )
            product.next_check_at = next_dt
            product.last_scheduled_delay_minutes = delay
            product.next_check_reason = "error_backoff"
            await session.commit()
            raise
        except ScraperParseError as exc:
            error_code = exc.error_result.error_code
            cls = classify_scraper_error(error_code)
            now = datetime.now(timezone.utc)

            logger.warning(
                "scraper_erro_semantico",
                produto_id=str(product.id),
                error_code=error_code,
                status_resultante=cls.status,
                acao=cls.action,
                domain_cooldown=cls.domain_cooldown,
                marketplace=exc.error_result.marketplace,
            )

            if cls.domain_cooldown:
                set_domain_cooldown(redis, dominio)

            product.last_checked_at = now

            if cls.status == "unavailable":
                if product.is_available:
                    product.last_availability_changed_at = now
                product.status = "unavailable"
                product.is_available = False
                product.consecutive_failures = 0
                new_stability = classify_stability(
                    last_price_changed_at=product.last_price_changed_at,
                    last_availability_changed_at=product.last_availability_changed_at,
                    now=now,
                )
                product.stability_level = new_stability
                next_dt, delay = compute_next_check(
                    reason="unavailable",
                    now=now,
                    stability_level=new_stability,
                    last_scheduled_delay_minutes=product.last_scheduled_delay_minutes,
                    consecutive_failures=0,
                    base_backoff_minutes=settings.collection_retry_base_delay_minutes,
                    max_backoff_minutes=settings.collection_retry_max_delay_minutes,
                    rate_limit_min=settings.rate_limit_reschedule_min_minutes,
                    rate_limit_max=settings.rate_limit_reschedule_max_minutes,
                    lock_busy_min=settings.lock_busy_reschedule_min_minutes,
                    lock_busy_max=settings.lock_busy_reschedule_max_minutes,
                )
                product.check_interval_minutes = delay or product.check_interval_minutes
                product.last_scheduled_delay_minutes = delay
                product.next_check_at = next_dt
                product.next_check_reason = "unavailable"
                await session.commit()
                logger.info(
                    "produto_indisponivel_por_erro",
                    produto_id=str(product.id),
                    error_code=error_code,
                    stability_level=new_stability,
                    proximo_intervalo_min=delay,
                )
                return {"success": False, "reason": "unavailable", "retryable": False}

            if cls.status == "unsupported":
                product.status = "unsupported"
                product.next_check_at = None
                product.next_check_reason = "unsupported"
                await session.commit()
                logger.info("produto_nao_suportado", produto_id=str(product.id), error_code=error_code)
                return {"success": False, "reason": "unsupported", "retryable": False}

            # status == "error" — backoff exponencial por consecutive_failures, re-raise para Celery retry
            product.status = "error"
            product.consecutive_failures = (product.consecutive_failures or 0) + 1
            next_dt, delay = compute_next_check(
                reason="error_backoff",
                now=now,
                stability_level=product.stability_level,
                last_scheduled_delay_minutes=product.last_scheduled_delay_minutes,
                consecutive_failures=product.consecutive_failures,
                base_backoff_minutes=settings.collection_retry_base_delay_minutes,
                max_backoff_minutes=settings.collection_retry_max_delay_minutes,
                rate_limit_min=settings.rate_limit_reschedule_min_minutes,
                rate_limit_max=settings.rate_limit_reschedule_max_minutes,
                lock_busy_min=settings.lock_busy_reschedule_min_minutes,
                lock_busy_max=settings.lock_busy_reschedule_max_minutes,
            )
            product.next_check_at = next_dt
            product.last_scheduled_delay_minutes = delay
            product.next_check_reason = "error_backoff"
            await session.commit()
            raise

        # ── Sucesso do scraper ──────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        novo_preco = resultado.price

        if resultado.available and novo_preco is not None and novo_preco > 0:
            # Coleta bem-sucedida: produto disponível com preço válido
            preco_anterior = Decimal(str(product.current_price)) if product.current_price is not None else None
            preco_mudou = preco_anterior is None or novo_preco != preco_anterior

            historico = PriceHistory(
                monitored_id=product.id,
                price=novo_preco,
                is_available=True,
                title=resultado.title,
                seller=resultado.seller,
                currency=resultado.currency,
                extraction_method=resultado.extraction_method,
                confidence=resultado.confidence,
                thumbnail_url=resultado.thumbnail_url,
                canonical_url=resultado.canonical_url,
                product_id=resultado.product_id,
            )
            session.add(historico)

            disponibilidade_mudou_para_ativa = product.is_available is False
            product.current_price = float(novo_preco)
            product.is_available = True
            product.status = "active"
            product.last_checked_at = now
            product.consecutive_failures = 0

            if resultado.title and not product.name:
                product.name = resultado.title

            if preco_mudou:
                if preco_anterior is None:
                    product.last_price_changed_at = now
                elif is_significant_change(float(preco_anterior), float(novo_preco), settings.price_stability_change_threshold_percent):
                    delta_pct = abs(float(novo_preco) - float(preco_anterior)) / float(preco_anterior) * 100
                    product.last_price_changed_at = now
                    product.last_significant_price_change_percent = delta_pct
                razao: CheckReason = "success_price_changed"
            else:
                razao = "success_price_unchanged"

            if disponibilidade_mudou_para_ativa:
                product.last_availability_changed_at = now

            new_stability = classify_stability(
                last_price_changed_at=product.last_price_changed_at,
                last_availability_changed_at=product.last_availability_changed_at,
                now=now,
            )
            product.stability_level = new_stability
            next_dt, delay = compute_next_check(
                reason=razao,
                now=now,
                stability_level=new_stability,
                last_scheduled_delay_minutes=product.last_scheduled_delay_minutes,
                consecutive_failures=0,
                base_backoff_minutes=settings.collection_retry_base_delay_minutes,
                max_backoff_minutes=settings.collection_retry_max_delay_minutes,
                rate_limit_min=settings.rate_limit_reschedule_min_minutes,
                rate_limit_max=settings.rate_limit_reschedule_max_minutes,
                lock_busy_min=settings.lock_busy_reschedule_min_minutes,
                lock_busy_max=settings.lock_busy_reschedule_max_minutes,
            )
            product.check_interval_minutes = delay
            product.last_scheduled_delay_minutes = delay
            product.next_check_at = next_dt
            product.next_check_reason = razao

            await session.commit()
            await session.refresh(historico)

            # Canonicalização persistente: quando o scraper retorna uma canonical_url
            # confiável diferente da URL armazenada, atualiza o registro para que
            # próximas coletas já partam da URL canônica e robusta.
            if resultado.canonical_url and resultado.confidence >= 0.90:
                from sqlalchemy.exc import IntegrityError
                from app.products.url_utils import normalize_url
                canon_normalized = normalize_url(resultado.canonical_url)
                if canon_normalized != product.url_normalized:
                    try:
                        product.url_original = resultado.canonical_url
                        product.url_normalized = canon_normalized
                        await session.commit()
                        logger.info(
                            "url_canonicalizada",
                            produto_id=str(product.id),
                            url_anterior=product.url_normalized,
                            canonical_url=resultado.canonical_url,
                        )
                    except IntegrityError:
                        await session.rollback()
                        logger.info(
                            "url_canonical_conflito",
                            produto_id=str(product.id),
                            canonical_url=resultado.canonical_url,
                        )

            logger.info(
                "produto_coletado",
                produto_id=str(product.id),
                preco=str(novo_preco),
                preco_mudou=preco_mudou,
                stability_level=new_stability,
                proximo_intervalo_min=delay,
                next_check_reason=razao,
                extraction_method=resultado.extraction_method,
                confidence=resultado.confidence,
                duracao_s=round(time.monotonic() - inicio, 2),
            )
            return {"success": True, "price": float(novo_preco), "next_check_at": product.next_check_at}

        else:
            # Scraper retornou sucesso mas produto está indisponível
            # Grava histórico com último preço conhecido para não perder a evidência de coleta
            preco_historico = novo_preco if novo_preco is not None else (
                Decimal(str(product.current_price)) if product.current_price is not None else None
            )
            if preco_historico is not None:
                historico = PriceHistory(
                    monitored_id=product.id,
                    price=preco_historico,
                    is_available=False,
                    title=resultado.title,
                    extraction_method=resultado.extraction_method,
                    confidence=resultado.confidence,
                )
                session.add(historico)

            if product.is_available:
                product.last_availability_changed_at = now
            product.is_available = False
            product.status = "unavailable"
            product.last_checked_at = now
            product.consecutive_failures = 0

            new_stability = classify_stability(
                last_price_changed_at=product.last_price_changed_at,
                last_availability_changed_at=product.last_availability_changed_at,
                now=now,
            )
            product.stability_level = new_stability
            next_dt, delay = compute_next_check(
                reason="unavailable",
                now=now,
                stability_level=new_stability,
                last_scheduled_delay_minutes=product.last_scheduled_delay_minutes,
                consecutive_failures=0,
                base_backoff_minutes=settings.collection_retry_base_delay_minutes,
                max_backoff_minutes=settings.collection_retry_max_delay_minutes,
                rate_limit_min=settings.rate_limit_reschedule_min_minutes,
                rate_limit_max=settings.rate_limit_reschedule_max_minutes,
                lock_busy_min=settings.lock_busy_reschedule_min_minutes,
                lock_busy_max=settings.lock_busy_reschedule_max_minutes,
            )
            product.check_interval_minutes = delay or product.check_interval_minutes
            product.last_scheduled_delay_minutes = delay
            product.next_check_at = next_dt
            product.next_check_reason = "unavailable"

            await session.commit()

            logger.info(
                "produto_indisponivel",
                produto_id=str(product.id),
                stability_level=new_stability,
                proximo_intervalo_min=delay,
                duracao_s=round(time.monotonic() - inicio, 2),
            )
            return {"success": False, "reason": "unavailable"}

    finally:
        release_lock(redis, chave_lock, lock_token)
        logger.debug(
            "lock_liberado",
            produto_id=str(product.id),
            duracao_s=round(time.monotonic() - inicio, 2),
        )
