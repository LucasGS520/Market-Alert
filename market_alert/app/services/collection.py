"""
Serviço de coleta de preços.

Este é o serviço central do sistema — ele orquestra a coleta de preços
de um produto monitorado ou de um concorrente. O fluxo é:

    1. Adquire lock Redis → garante que não há coleta duplicada em paralelo
    2. Verifica rate limit por domínio → respeita o site alvo
    3. Chama o ScraperClient → delega ao microserviço market_scraper
    4. Persiste o histórico de preço no PostgreSQL
    5. Atualiza o estado atual do produto/concorrente
    6. Recalcula o intervalo adaptativo de coleta (apenas para produtos)
    7. Libera o lock Redis

Locks Redis:
    Chave: lock:collect:{id} com TTL de 60 segundos.
    Se o lock já existe, a coleta é pulada silenciosamente.

Rate limiting por domínio:
    Chave: ratelimit:domain:{dominio} com TTL de 5 segundos.
    Evita múltiplas requisições simultâneas ao mesmo site.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse

import structlog
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.scraper import ScraperClient, ScraperParseError, ScraperUnavailableError
from app.models.competitor import Competitor
from app.models.monitored_product import MonitoredProduct
from app.models.price_history import PriceHistory
from app.services.scheduling import compute_next_interval

logger = structlog.get_logger()

# Tempo máximo que o lock fica ativo (evita deadlocks se o worker travar)
_LOCK_TTL_SEGUNDOS = 60
# Intervalo mínimo entre requisições ao mesmo domínio (rate limit)
_RATE_LIMIT_TTL_SEGUNDOS = 5


def _dominio_da_url(url: str) -> str:
    """Extrai o domínio de uma URL. Ex: 'amazon.com.br' de 'https://amazon.com.br/dp/...'"""
    return urlparse(url).netloc


def _adquirir_lock(redis: Redis, chave_lock: str) -> bool:
    """
    Tenta adquirir um lock Redis (SET NX).

    Returns:
        True se o lock foi adquirido, False se já estava ativo.
    """
    return bool(redis.set(chave_lock, "1", nx=True, ex=_LOCK_TTL_SEGUNDOS))


def _liberar_lock(redis: Redis, chave_lock: str) -> None:
    """Remove o lock Redis, liberando para a próxima coleta."""
    redis.delete(chave_lock)


def _verificar_rate_limit(redis: Redis, dominio: str) -> bool:
    """
    Verifica se o domínio pode ser acessado agora.

    Returns:
        True se pode prosseguir, False se está em cooldown.
    """
    chave = f"ratelimit:domain:{dominio}"
    if redis.exists(chave):
        return False  # Ainda em cooldown
    redis.set(chave, "1", ex=_RATE_LIMIT_TTL_SEGUNDOS)
    return True


async def collect_product(
    session: AsyncSession,
    redis: Redis,
    scraper: ScraperClient,
    product: MonitoredProduct,
) -> PriceHistory | None:
    """
    Coleta o preço atual de um produto monitorado.

    Orquestra lock, rate limit, chamada ao scraper e persistência.
    Ao final, atualiza o intervalo adaptativo de coleta do produto.

    Args:
        session: Sessão assíncrona do SQLAlchemy.
        redis:   Cliente Redis para locks e rate limiting.
        scraper: Cliente HTTP do microserviço market_scraper.
        product: Produto monitorado a ser coletado.

    Returns:
        Registro de PriceHistory criado, ou None se a coleta foi pulada.

    Raises:
        ScraperUnavailableError: scraper indisponível (propaga para retry no Celery).
        ScraperParseError:       scraper não conseguiu extrair preço.
    """
    chave_lock = f"lock:collect:{product.id}"
    if not _adquirir_lock(redis, chave_lock):
        logger.info("coleta_pulada_lock_ativo", produto_id=str(product.id))
        return None

    try:
        dominio = _dominio_da_url(product.url)
        if not _verificar_rate_limit(redis, dominio):
            logger.info("coleta_rate_limited", dominio=dominio, produto_id=str(product.id))
            return None

        try:
            resultado = await scraper.parse(product.url)
        except (ScraperUnavailableError, ScraperParseError) as exc:
            # Marca o produto como erro e propaga para retry no Celery
            logger.warning("scraper_falhou", produto_id=str(product.id), erro=str(exc))
            product.status = "error"
            await session.commit()
            raise

        novo_preco = resultado.price
        preco_anterior = Decimal(str(product.current_price)) if product.current_price is not None else None
        preco_mudou = preco_anterior is None or novo_preco != preco_anterior

        # Registra o preço coletado no histórico
        historico = PriceHistory(
            monitored_id=product.id,
            price=novo_preco,
            is_available=resultado.available,
        )
        session.add(historico)

        # Atualiza o estado atual do produto
        product.current_price = float(novo_preco)
        product.is_available = resultado.available
        product.last_checked_at = datetime.now(timezone.utc)
        product.status = "active"

        # Preenche o nome se ainda não tinha (extraído pelo scraper)
        if resultado.title and not product.name:
            product.name = resultado.title

        # Atualiza contador de coletas sem mudança de preço
        if preco_mudou:
            product.consecutive_unchanged = 0
        else:
            product.consecutive_unchanged = (product.consecutive_unchanged or 0) + 1

        # Recalcula quando deve ocorrer a próxima coleta
        proximo_intervalo = compute_next_interval(
            current_interval=product.check_interval_minutes,
            price_changed=preco_mudou,
            consecutive_unchanged=product.consecutive_unchanged,
        )
        product.check_interval_minutes = proximo_intervalo
        product.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=proximo_intervalo)

        await session.commit()
        await session.refresh(historico)

        logger.info(
            "produto_coletado",
            produto_id=str(product.id),
            preco=str(novo_preco),
            preco_mudou=preco_mudou,
            proximo_intervalo_min=proximo_intervalo,
        )
        return historico

    finally:
        # Garante que o lock é liberado mesmo em caso de erro
        _liberar_lock(redis, chave_lock)


async def collect_competitor(
    session: AsyncSession,
    redis: Redis,
    scraper: ScraperClient,
    competitor: Competitor,
) -> PriceHistory | None:
    """
    Coleta o preço atual de um concorrente.

    Mesmo fluxo que collect_product, mas sem intervalo adaptativo
    (concorrentes são coletados sob demanda após a coleta do produto principal).

    Args:
        session:    Sessão assíncrona do SQLAlchemy.
        redis:      Cliente Redis para locks e rate limiting.
        scraper:    Cliente HTTP do microserviço market_scraper.
        competitor: Concorrente a ser coletado.

    Returns:
        Registro de PriceHistory criado, ou None se a coleta foi pulada.
    """
    chave_lock = f"lock:collect:{competitor.id}"
    if not _adquirir_lock(redis, chave_lock):
        logger.info("coleta_pulada_lock_ativo", concorrente_id=str(competitor.id))
        return None

    try:
        dominio = _dominio_da_url(competitor.url)
        if not _verificar_rate_limit(redis, dominio):
            logger.info("coleta_rate_limited", dominio=dominio, concorrente_id=str(competitor.id))
            return None

        try:
            resultado = await scraper.parse(competitor.url)
        except (ScraperUnavailableError, ScraperParseError) as exc:
            logger.warning("scraper_falhou_concorrente", concorrente_id=str(competitor.id), erro=str(exc))
            raise

        historico = PriceHistory(
            competitor_id=competitor.id,
            price=resultado.price,
            is_available=resultado.available,
        )
        session.add(historico)

        competitor.current_price = float(resultado.price)
        competitor.is_available = resultado.available
        competitor.last_checked_at = datetime.now(timezone.utc)

        if resultado.title and not competitor.name:
            competitor.name = resultado.title

        await session.commit()
        await session.refresh(historico)

        logger.info("concorrente_coletado", concorrente_id=str(competitor.id), preco=str(resultado.price))
        return historico

    finally:
        _liberar_lock(redis, chave_lock)
