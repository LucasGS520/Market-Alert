"""
Serviço de comparação de preços.

Este serviço calcula o posicionamento competitivo de um produto monitorado
em relação aos seus concorrentes cadastrados. É executado sempre que
um novo preço é coletado.

O que é calculado:
    - ranking:             posição do produto (1 = mais barato)
    - average_price:       média entre produto + concorrentes
    - min_price:           menor preço do mercado
    - max_price:           maior preço do mercado
    - potential_adjustment: quanto o produto precisaria baixar para liderar
    - status:              classificação competitiva (ver abaixo)

Status competitivo:
    competitive → produto está no menor preço ou dentro de 5% acima do mínimo
    attention   → produto está entre 5% e 15% acima do menor preço
    urgent      → produto está mais de 15% acima do menor preço

Cache Redis:
    O resultado mais recente é invalidado no Redis após cada cálculo,
    forçando os próximos acessos à API a buscarem do banco de dados.
    Chave: cache:comparison:{monitored_id}
"""

import uuid
from decimal import Decimal

import structlog
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comparison import Comparison
from app.models.competitor import Competitor
from app.models.monitored_product import MonitoredProduct

logger = structlog.get_logger()

# Limites para classificação do status competitivo
_LIMITE_ATENCAO = 5.0   # % acima do mínimo → atenção
_LIMITE_URGENTE = 15.0  # % acima do mínimo → urgente


def _calcular_status(preco_produto: Decimal, preco_minimo: Decimal) -> str:
    """
    Classifica a posição competitiva do produto.

    Args:
        preco_produto: Preço atual do produto monitorado.
        preco_minimo:  Menor preço do mercado (produto + concorrentes).

    Returns:
        "competitive", "attention" ou "urgent".
    """
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
    """
    Calcula e persiste a comparação de preços de um produto monitorado.

    Carrega o produto e seus concorrentes, faz os cálculos de ranking
    e status, salva um novo registro de Comparison e invalida o cache.

    Args:
        session:      Sessão assíncrona do SQLAlchemy.
        redis:        Cliente Redis para invalidação de cache.
        monitored_id: ID do produto monitorado.

    Returns:
        O registro Comparison criado, ou None se o produto não tem preço ainda.
    """
    produto = await session.get(MonitoredProduct, monitored_id)
    if not produto or produto.current_price is None:
        # Sem preço ainda: nada a comparar
        logger.info("comparacao_pulada_sem_preco", produto_id=str(monitored_id))
        return None

    # Carrega todos os concorrentes do produto
    resultado = await session.execute(
        select(Competitor).where(Competitor.monitored_id == monitored_id)
    )
    concorrentes = list(resultado.scalars().all())

    # Monta a lista de preços: produto monitorado + concorrentes com preço disponível
    todos_precos: list[Decimal] = [Decimal(str(produto.current_price))]
    for c in concorrentes:
        if c.current_price is not None:
            todos_precos.append(Decimal(str(c.current_price)))

    precos_ordenados = sorted(todos_precos)
    preco_produto = Decimal(str(produto.current_price))

    # Posição do produto na lista ordenada (1 = mais barato)
    ranking = precos_ordenados.index(preco_produto) + 1
    preco_medio = sum(todos_precos) / len(todos_precos)
    preco_minimo = precos_ordenados[0]
    preco_maximo = precos_ordenados[-1]
    status = _calcular_status(preco_produto, preco_minimo)

    # Quanto o produto precisaria baixar para ficar no mínimo do mercado
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

    # Invalida o cache para que a API retorne dados frescos na próxima leitura
    redis.delete(f"cache:comparison:{monitored_id}")

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
