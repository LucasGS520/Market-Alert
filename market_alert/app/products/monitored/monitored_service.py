import random
import time
import uuid
from datetime import datetime, timedelta, timezone
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
from app.workers.redis import acquire_lock, check_rate_limit, release_lock, set_domain_cooldown

logger = structlog.get_logger()

# ── Scheduling ─────────────────────────────────────────────────────────────────


def compute_next_interval(current_interval: int, price_changed: bool, consecutive_unchanged: int) -> int:
    """Calcula o próximo intervalo base de coleta (sem jitter).

    O jitter (±20 %) deve ser aplicado pelo chamador ao calcular next_check_at,
    para evitar thundering herd sem corromper o estado armazenado.
    """
    from app.infra.config import settings

    if price_changed:
        return max(settings.min_check_interval_minutes, current_interval // 2)
    if consecutive_unchanged >= settings.consecutive_unchanged_threshold:
        return min(settings.max_check_interval_minutes, current_interval * 2)
    return current_interval


def _next_check_at(now: datetime, interval_minutes: int) -> datetime:
    """Aplica jitter de ±20 % sobre o intervalo e retorna o próximo horário de coleta."""
    jittered = random.uniform(interval_minutes * 0.8, interval_minutes * 1.2)
    return now + timedelta(minutes=jittered)


# ── CRUD ────────────────────────────────────────────────────────────────────────

async def list_products(session: AsyncSession) -> list[MonitoredProduct]:
    resultado = await session.execute(
        select(MonitoredProduct).order_by(MonitoredProduct.created_at.desc())
    )
    return list(resultado.scalars().all())


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
    if not acquire_lock(redis, chave_lock, timeout=300):
        logger.info("coleta_pulada_lock_ativo", produto_id=str(product.id))
        return {"success": False, "reason": "lock_busy"}

    logger.info("lock_adquirido", produto_id=str(product.id))

    try:
        dominio = urlparse(product.url_original).netloc
        if not check_rate_limit(redis, dominio):
            logger.info("coleta_rate_limited", dominio=dominio, produto_id=str(product.id))
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
            logger.warning("scraper_indisponivel", produto_id=str(product.id), erro=str(exc))
            product.status = "error"
            product.last_checked_at = now
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
                product.status = "unavailable"
                product.is_available = False
                proximo_intervalo = compute_next_interval(
                    current_interval=product.check_interval_minutes,
                    price_changed=False,
                    consecutive_unchanged=(product.consecutive_unchanged or 0) + 1,
                )
                product.check_interval_minutes = proximo_intervalo
                product.next_check_at = _next_check_at(now, proximo_intervalo)
                await session.commit()
                logger.info(
                    "produto_indisponivel_por_erro",
                    produto_id=str(product.id),
                    error_code=error_code,
                    proximo_intervalo_min=proximo_intervalo,
                )
                return {"success": False, "reason": "unavailable", "retryable": False}

            if cls.status == "unsupported":
                product.status = "unsupported"
                product.next_check_at = None
                await session.commit()
                logger.info("produto_nao_suportado", produto_id=str(product.id), error_code=error_code)
                return {"success": False, "reason": "unsupported", "retryable": False}

            # status == "error" — agendar backoff e re-raise para Celery retry
            product.status = "error"
            attempt = 1  # incrementado pelo Celery no retry; aqui é o primeiro erro
            delay = min(
                settings.collection_retry_base_delay_minutes * attempt,
                settings.collection_retry_max_delay_minutes,
            )
            product.next_check_at = now + timedelta(minutes=delay)
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

            product.current_price = float(novo_preco)
            product.is_available = True
            product.status = "active"
            product.last_checked_at = now

            if resultado.title and not product.name:
                product.name = resultado.title

            if preco_mudou:
                product.consecutive_unchanged = 0
            else:
                product.consecutive_unchanged = (product.consecutive_unchanged or 0) + 1

            proximo_intervalo = compute_next_interval(
                current_interval=product.check_interval_minutes,
                price_changed=preco_mudou,
                consecutive_unchanged=product.consecutive_unchanged,
            )
            product.check_interval_minutes = proximo_intervalo
            product.next_check_at = _next_check_at(now, proximo_intervalo)

            await session.commit()
            await session.refresh(historico)

            logger.info(
                "produto_coletado",
                produto_id=str(product.id),
                preco=str(novo_preco),
                preco_mudou=preco_mudou,
                proximo_intervalo_min=proximo_intervalo,
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

            product.is_available = False
            product.status = "unavailable"
            product.last_checked_at = now

            proximo_intervalo = compute_next_interval(
                current_interval=product.check_interval_minutes,
                price_changed=False,
                consecutive_unchanged=(product.consecutive_unchanged or 0) + 1,
            )
            product.check_interval_minutes = proximo_intervalo
            product.next_check_at = _next_check_at(now, proximo_intervalo)

            await session.commit()

            logger.info(
                "produto_indisponivel",
                produto_id=str(product.id),
                proximo_intervalo_min=proximo_intervalo,
                duracao_s=round(time.monotonic() - inicio, 2),
            )
            return {"success": False, "reason": "unavailable"}

    finally:
        release_lock(redis, chave_lock)
        logger.debug(
            "lock_liberado",
            produto_id=str(product.id),
            duracao_s=round(time.monotonic() - inicio, 2),
        )
