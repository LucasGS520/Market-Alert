import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import structlog
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.clients.scraper import ScraperClient, ScraperParseError, ScraperUnavailableError
from app.infra.scraper_errors import classify_scraper_error
from app.products.competitor.competitor_model import Competitor
from app.products.monitored.monitored_model import MonitoredProduct
from app.products.price_history.price_model import PriceHistory
from app.workers.redis import acquire_lock, check_rate_limit, release_lock, set_domain_cooldown

logger = structlog.get_logger()


# ── CRUD ────────────────────────────────────────────────────────────────────────

async def create_competitor(
    session: AsyncSession, monitored_id: uuid.UUID, url: str, name: str | None
) -> Competitor:
    from app.infra.config import settings
    from app.products.url_utils import normalize_url

    produto = await session.get(MonitoredProduct, monitored_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")

    url_normalized = normalize_url(url)

    if url_normalized == produto.url_normalized:
        raise HTTPException(
            status_code=422,
            detail="A URL do concorrente não pode ser igual à URL do produto monitorado",
        )

    total = await session.scalar(
        select(func.count()).where(Competitor.monitored_id == monitored_id)
    )
    if total >= settings.max_competitors_per_product:
        raise HTTPException(
            status_code=422,
            detail=f"Máximo de {settings.max_competitors_per_product} concorrentes por produto atingido",
        )

    existente = await session.scalar(
        select(Competitor).where(
            Competitor.monitored_id == monitored_id,
            Competitor.url_normalized == url_normalized,
        )
    )
    if existente:
        raise HTTPException(status_code=409, detail="Esta URL já é um concorrente deste produto")

    concorrente = Competitor(
        monitored_id=monitored_id,
        url_original=url,
        url_normalized=url_normalized,
        name=name,
        status="pending",
    )
    session.add(concorrente)
    await session.commit()
    await session.refresh(concorrente)
    return concorrente


async def list_competitors(session: AsyncSession, monitored_id: uuid.UUID) -> list[Competitor]:
    resultado = await session.execute(
        select(Competitor)
        .where(Competitor.monitored_id == monitored_id)
        .order_by(Competitor.created_at)
    )
    return list(resultado.scalars().all())


async def delete_competitor(session: AsyncSession, competitor_id: uuid.UUID) -> uuid.UUID:
    """Deleta o concorrente e retorna o monitored_id para re-enfileirar comparação."""
    concorrente = await session.get(Competitor, competitor_id)
    if not concorrente:
        raise HTTPException(status_code=404, detail="Concorrente não encontrado")

    monitored_id = concorrente.monitored_id
    await session.delete(concorrente)
    await session.commit()
    return monitored_id


# ── Coleta ─────────────────────────────────────────────────────────────────────

async def collect_competitor(
    session: AsyncSession,
    redis: Redis,
    scraper: ScraperClient,
    competitor: Competitor,
) -> dict:
    """Coleta preço do concorrente.

    Returns:
        dict com chave "success" (bool) e campos adicionais por resultado.
    Raises:
        ScraperUnavailableError: scraper inacessível — Celery deve retentar.
        ScraperParseError: erro retryable do scraper — Celery deve retentar.
    """
    inicio = time.monotonic()

    if competitor.status in ("paused", "unsupported"):
        logger.info("coleta_ignorada_status", concorrente_id=str(competitor.id), status=competitor.status)
        return {"success": False, "reason": "ineligible_status"}

    chave_lock = f"lock:collect:{competitor.id}"
    lock_token = acquire_lock(redis, chave_lock, timeout=300)
    if not lock_token:
        logger.info("coleta_pulada_lock_ativo", concorrente_id=str(competitor.id))
        return {"success": False, "reason": "lock_busy"}

    logger.info("lock_adquirido_concorrente", concorrente_id=str(competitor.id))

    try:
        dominio = urlparse(competitor.url_original).netloc
        if not check_rate_limit(redis, dominio):
            from app.infra.config import settings

            logger.info(
                "coleta_rate_limited",
                dominio=dominio,
                concorrente_id=str(competitor.id),
                ttl_s=settings.domain_rate_limit_ttl_seconds,
            )
            return {"success": False, "reason": "rate_limited"}

        logger.info(
            "iniciando_coleta_concorrente",
            concorrente_id=str(competitor.id),
            url=competitor.url_original,
        )

        previous_is_available = competitor.is_available
        try:
            resultado = await scraper.parse(competitor.url_original)
        except ScraperUnavailableError as exc:
            from app.infra.config import settings

            now = datetime.now(timezone.utc)
            logger.warning(
                "scraper_indisponivel_concorrente",
                concorrente_id=str(competitor.id),
                erro=str(exc),
                scraper_timeout_s=settings.scraper_timeout_seconds,
            )
            competitor.status = "error"
            competitor.last_checked_at = now
            await session.commit()
            raise
        except ScraperParseError as exc:
            error_code = exc.error_result.error_code
            cls = classify_scraper_error(error_code)
            now = datetime.now(timezone.utc)

            logger.warning(
                "scraper_erro_semantico_concorrente",
                concorrente_id=str(competitor.id),
                error_code=error_code,
                status_resultante=cls.status,
                acao=cls.action,
                domain_cooldown=cls.domain_cooldown,
            )

            if cls.domain_cooldown:
                set_domain_cooldown(redis, dominio)

            competitor.last_checked_at = now

            if cls.status == "unavailable":
                availability_changed = previous_is_available is not False
                competitor.status = "unavailable"
                competitor.is_available = False
                await session.commit()
                return {"success": False, "reason": "unavailable", "retryable": False, "availability_changed": availability_changed}

            if cls.status == "unsupported":
                competitor.status = "unsupported"
                await session.commit()
                return {"success": False, "reason": "unsupported", "retryable": False}

            # status == "error" — re-raise para Celery retry
            competitor.status = "error"
            await session.commit()
            raise

        # ── Sucesso do scraper ──────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        novo_preco = resultado.price

        if resultado.available and novo_preco is not None and novo_preco > 0:
            historico = PriceHistory(
                competitor_id=competitor.id,
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

            competitor.status = "active"
            competitor.current_price = float(novo_preco)
            competitor.is_available = True
            competitor.last_checked_at = now

            if resultado.title and not competitor.name:
                competitor.name = resultado.title

            await session.commit()
            await session.refresh(historico)

            # Canonicalização persistente: atualiza url_original/url_normalized quando
            # o scraper devolve uma canonical_url confiável diferente da URL armazenada.
            if resultado.canonical_url and resultado.confidence >= 0.90:
                from sqlalchemy.exc import IntegrityError
                from app.products.url_utils import normalize_url
                canon_normalized = normalize_url(resultado.canonical_url)
                if canon_normalized != competitor.url_normalized:
                    try:
                        competitor.url_original = resultado.canonical_url
                        competitor.url_normalized = canon_normalized
                        await session.commit()
                        logger.info(
                            "url_canonicalizada_concorrente",
                            concorrente_id=str(competitor.id),
                            canonical_url=resultado.canonical_url,
                        )
                    except IntegrityError:
                        await session.rollback()
                        logger.info(
                            "url_canonical_conflito_concorrente",
                            concorrente_id=str(competitor.id),
                            canonical_url=resultado.canonical_url,
                        )

            logger.info(
                "concorrente_coletado",
                concorrente_id=str(competitor.id),
                preco=str(novo_preco),
                extraction_method=resultado.extraction_method,
                confidence=resultado.confidence,
                duracao_s=round(time.monotonic() - inicio, 2),
            )
            return {"success": True, "price": float(novo_preco)}

        else:
            # Concorrente indisponível — registra histórico com último preço conhecido
            preco_historico = novo_preco if novo_preco is not None else (
                Decimal(str(competitor.current_price)) if competitor.current_price is not None else None
            )
            if preco_historico is not None:
                historico = PriceHistory(
                    competitor_id=competitor.id,
                    price=preco_historico,
                    is_available=False,
                    title=resultado.title,
                    extraction_method=resultado.extraction_method,
                    confidence=resultado.confidence,
                )
                session.add(historico)

            availability_changed = previous_is_available is not False
            competitor.status = "unavailable"
            competitor.is_available = False
            competitor.last_checked_at = now

            await session.commit()

            logger.info(
                "concorrente_indisponivel",
                concorrente_id=str(competitor.id),
                duracao_s=round(time.monotonic() - inicio, 2),
            )
            return {"success": False, "reason": "unavailable", "availability_changed": availability_changed}

    finally:
        release_lock(redis, chave_lock, lock_token)
        logger.debug(
            "lock_liberado_concorrente",
            concorrente_id=str(competitor.id),
            duracao_s=round(time.monotonic() - inicio, 2),
        )
