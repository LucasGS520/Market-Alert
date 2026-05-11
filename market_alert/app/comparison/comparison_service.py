import uuid
from decimal import Decimal

import structlog
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comparison.comparison_model import Comparison
from app.infra.config import settings
from app.products.competitor.competitor_model import Competitor
from app.products.monitored.monitored_model import MonitoredProduct
from app.workers.redis import invalidate_comparison_cache

logger = structlog.get_logger()


def _calcular_status(preco_produto: Decimal, preco_minimo: Decimal) -> str:
    if preco_minimo == 0:
        return "competitive"
    pct_acima = float((preco_produto - preco_minimo) / preco_minimo * 100)
    if pct_acima <= settings.status_threshold_competitive:
        return "competitive"
    if pct_acima <= settings.status_threshold_attention:
        return "attention"
    return "urgent"


async def calculate_comparison(
    session: AsyncSession,
    redis: Redis,
    monitored_id: uuid.UUID,
) -> Comparison | None:
    produto = await session.get(MonitoredProduct, monitored_id)
    if not produto or produto.current_price is None:
        logger.warning(
            "comparacao_abortada_produto_sem_preco",
            produto_id=str(monitored_id),
            razao="produto_sem_preco_atual",
        )
        return None

    resultado = await session.execute(
        select(Competitor).where(Competitor.monitored_id == monitored_id)
    )
    concorrentes = list(resultado.scalars().all())

    # Tuplas (preco, indice_original) garantem tie-breaking determinístico por ordem de inserção
    entradas: list[tuple[Decimal, int]] = [(Decimal(str(produto.current_price)), 0)]
    for i, c in enumerate(concorrentes, 1):
        if c.current_price is not None:
            entradas.append((Decimal(str(c.current_price)), i))
        else:
            logger.info("concorrente_excluido_sem_preco", concorrente_id=str(c.id))

    entradas_ordenadas = sorted(entradas, key=lambda x: (x[0], x[1]))
    todos_precos = [p for p, _ in entradas_ordenadas]

    preco_produto = Decimal(str(produto.current_price))
    ranking = next(i + 1 for i, (_, idx) in enumerate(entradas_ordenadas) if idx == 0)
    preco_medio = sum(todos_precos) / len(todos_precos)
    preco_minimo = todos_precos[0]
    preco_maximo = todos_precos[-1]
    status = _calcular_status(preco_produto, preco_minimo)
    ajuste_potencial = preco_produto - preco_minimo if preco_produto > preco_minimo else None

    comparacao = Comparison(
        monitored_id=monitored_id,
        status=status,
        ranking=ranking,
        average_price=preco_medio,
        min_price=preco_minimo,
        max_price=preco_maximo,
        potential_adjustment=ajuste_potencial,
    )
    session.add(comparacao)
    await session.commit()
    await session.refresh(comparacao)

    invalidate_comparison_cache(redis, monitored_id)

    logger.info(
        "comparacao_calculada",
        produto_id=str(monitored_id),
        status=status,
        ranking=ranking,
        preco_minimo=str(preco_minimo),
        preco_produto=str(preco_produto),
        total_precos=len(todos_precos),
    )
    return comparacao


async def get_latest_comparison(
    session: AsyncSession,
    monitored_id: uuid.UUID,
) -> Comparison | None:
    return await session.scalar(
        select(Comparison)
        .where(Comparison.monitored_id == monitored_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(1)
    )


async def get_comparison_history(
    session: AsyncSession,
    monitored_id: uuid.UUID,
    limit: int = 100,
) -> list[Comparison]:
    resultado = await session.execute(
        select(Comparison)
        .where(Comparison.monitored_id == monitored_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(limit)
    )
    return list(resultado.scalars().all())
