import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import structlog
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.clients.scraper import ScraperClient, ScraperParseError, ScraperUnavailableError
from app.infra.scraper_errors import ERROS_BLOQUEIO, ERROS_NAO_SUPORTADO
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
) -> PriceHistory | None:
    chave_lock = f"lock:collect:{competitor.id}"
    if not acquire_lock(redis, chave_lock):
        logger.info("coleta_pulada_lock_ativo", concorrente_id=str(competitor.id))
        return None

    try:
        dominio = urlparse(competitor.url_original).netloc
        if not check_rate_limit(redis, dominio):
            logger.info("coleta_rate_limited", dominio=dominio, concorrente_id=str(competitor.id))
            return None

        try:
            resultado = await scraper.parse(competitor.url_original)
        except ScraperUnavailableError as exc:
            logger.warning("scraper_indisponivel_concorrente", concorrente_id=str(competitor.id), erro=str(exc))
            competitor.status = "error"
            competitor.last_checked_at = datetime.now(timezone.utc)
            await session.commit()
            raise
        except ScraperParseError as exc:
            error_code = exc.error_result.error_code
            logger.warning(
                "scraper_erro_semantico_concorrente",
                concorrente_id=str(competitor.id),
                error_code=error_code,
                retryable=exc.error_result.retryable,
            )
            if error_code == "UNAVAILABLE":
                competitor.status = "unavailable"
                competitor.is_available = False
                competitor.last_checked_at = datetime.now(timezone.utc)
                await session.commit()
                return None
            if error_code in ERROS_NAO_SUPORTADO:
                competitor.status = "unsupported"
                competitor.last_checked_at = datetime.now(timezone.utc)
                await session.commit()
                return None
            if error_code in ERROS_BLOQUEIO:
                set_domain_cooldown(redis, dominio)
            competitor.status = "error"
            competitor.last_checked_at = datetime.now(timezone.utc)
            await session.commit()
            raise

        historico = PriceHistory(
            competitor_id=competitor.id,
            price=resultado.price,
            is_available=resultado.available,
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
        competitor.current_price = float(resultado.price)
        competitor.is_available = resultado.available
        competitor.last_checked_at = datetime.now(timezone.utc)

        if resultado.title and not competitor.name:
            competitor.name = resultado.title

        await session.commit()
        await session.refresh(historico)

        logger.info(
            "concorrente_coletado",
            concorrente_id=str(competitor.id),
            preco=str(resultado.price),
            extraction_method=resultado.extraction_method,
            confidence=resultado.confidence,
        )
        return historico

    finally:
        release_lock(redis, chave_lock)
