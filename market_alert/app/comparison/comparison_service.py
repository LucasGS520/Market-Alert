import uuid
from decimal import Decimal

import structlog
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comparison.comparison_model import Comparison
from app.products.competitor.competitor_model import Competitor
from app.products.monitored.monitored_model import MonitoredProduct
from app.workers.redis import invalidate_comparison_cache

logger = structlog.get_logger()

_LIMITE_ATENCAO = 5.0
_LIMITE_URGENTE = 15.0


def _calcular_status(preco_produto: Decimal, preco_minimo: Decimal) -> str:
    if preco_minimo == 0:
        return "competitive"
    pct_acima = float((preco_produto - preco_minimo) / preco_minimo * 100)
    if pct_acima <= _LIMITE_ATENCAO:
        return "competitive"
    if pct_acima <= _LIMITE_URGENTE:
        return "attention"
    return "urgent"


async def calculate_comparison(
    session: AsyncSession,
    redis: Redis,
    monitored_id: uuid.UUID,
) -> Comparison | None:
    produto = await session.get(MonitoredProduct, monitored_id)
    if not produto or produto.current_price is None:
        logger.info("comparacao_pulada_sem_preco", produto_id=str(monitored_id))
        return None

    resultado = await session.execute(
        select(Competitor).where(Competitor.monitored_id == monitored_id)
    )
    concorrentes = list(resultado.scalars().all())

    todos_precos: list[Decimal] = [Decimal(str(produto.current_price))]
    for c in concorrentes:
        if c.current_price is not None:
            todos_precos.append(Decimal(str(c.current_price)))

    precos_ordenados = sorted(todos_precos)
    preco_produto = Decimal(str(produto.current_price))

    ranking = precos_ordenados.index(preco_produto) + 1
    preco_medio = sum(todos_precos) / len(todos_precos)
    preco_minimo = precos_ordenados[0]
    preco_maximo = precos_ordenados[-1]
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
