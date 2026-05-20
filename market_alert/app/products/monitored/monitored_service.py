import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse

import structlog
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.clients.scraper import ScraperClient, ScraperParseError, ScraperUnavailableError
from app.products.monitored.monitored_model import MonitoredProduct
from app.products.price_history.price_model import PriceHistory
from app.scheduling.policy import CheckReason, classify_stability, compute_next_check, is_significant_change
from app.workers.redis import (
    acquire_lock,
    record_collection_attempt,
    release_lock,
)

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
        ScraperUnavailableError: scraper inacessível — erro registrado, lease liberado pelo orquestrador.
    """
    from app.infra.config import settings

    inicio = time.monotonic()
    _pid_str = str(product.id)

    if product.status in ("paused", "unsupported"):
        logger.info("coleta_ignorada_status", produto_id=_pid_str, status=product.status)
        return {"success": False, "reason": "ineligible_status"}

    dominio = urlparse(product.url_normalized).netloc

    chave_lock = f"lock:collect:{product.id}"
    lock_token = acquire_lock(redis, chave_lock, timeout=300)
    if not lock_token:
        logger.info("coleta_pulada_lock_ativo", produto_id=str(product.id))
        return {"success": False, "reason": "lock_busy"}

    logger.info("lock_adquirido", produto_id=str(product.id))

    try:
        logger.info("iniciando_coleta", produto_id=str(product.id), url=product.url_normalized)

        try:
            resultado = await scraper.parse(product.url_normalized)
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
            product.next_check_at = now + timedelta(minutes=product.check_interval_minutes)
            product.last_scheduled_delay_minutes = product.check_interval_minutes
            product.next_check_reason = "error_backoff"
            try:
                await session.commit()
            except StaleDataError:
                await session.rollback()
                logger.warning("stale_data_no_commit_scraper_unavailable", produto_id=_pid_str)
            record_collection_attempt(redis, _pid_str, "scraper_unavailable", dominio)
            raise
        except ScraperParseError as exc:
            error_code = exc.error_result.error_code
            now = datetime.now(timezone.utc)

            logger.warning(
                "scraper_erro_semantico",
                produto_id=str(product.id),
                error_code=error_code,
                marketplace=exc.error_result.marketplace,
                retryable=exc.error_result.retryable,
            )

            product.last_checked_at = now
            record_collection_attempt(redis, _pid_str, error_code.lower(), dominio)

            if error_code == "UNAVAILABLE":
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
                return {"success": False, "reason": "unavailable"}

            if error_code == "MARKETPLACE_NOT_SUPPORTED":
                product.status = "unsupported"
                product.next_check_at = None
                product.next_check_reason = "unsupported"
                await session.commit()
                logger.info("produto_nao_suportado", produto_id=str(product.id))
                return {"success": False, "reason": "unsupported"}

            if error_code in ("BLOCKED", "CAPTCHA_DETECTED"):
                product.status = "error"
                product.consecutive_failures = (product.consecutive_failures or 0) + 1
                product.next_check_at = now + timedelta(minutes=product.check_interval_minutes)
                product.last_scheduled_delay_minutes = product.check_interval_minutes
                product.next_check_reason = "error_backoff"
                try:
                    await session.commit()
                except StaleDataError:
                    await session.rollback()
                    logger.warning("stale_data_no_commit_parse_error", produto_id=_pid_str)
                logger.warning("coleta_bloqueada", produto_id=str(product.id), error_code=error_code)
                return {"success": False, "reason": "blocked", "error_code": error_code}

            # Qualquer outro erro de parse: status=error, intervalo normal, sem retry
            product.status = "error"
            product.consecutive_failures = (product.consecutive_failures or 0) + 1
            product.next_check_at = now + timedelta(minutes=product.check_interval_minutes)
            product.last_scheduled_delay_minutes = product.check_interval_minutes
            product.next_check_reason = "error_backoff"
            try:
                await session.commit()
            except StaleDataError:
                await session.rollback()
                logger.warning("stale_data_no_commit_parse_error", produto_id=_pid_str)
            return {"success": False, "reason": "error", "error_code": error_code}

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
            product.last_successful_collection_at = now
            record_collection_attempt(redis, str(product.id), "success", dominio)

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
            )
            product.check_interval_minutes = delay
            product.last_scheduled_delay_minutes = delay
            product.next_check_at = next_dt
            product.next_check_reason = razao

            try:
                await session.commit()
                await session.refresh(historico)
            except StaleDataError:
                await session.rollback()
                logger.warning("produto_deletado_durante_coleta", produto_id=_pid_str)
                return {"success": False, "reason": "product_deleted"}

            # Canonicalização persistente
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
            produto_id=_pid_str,
            duracao_s=round(time.monotonic() - inicio, 2),
        )
