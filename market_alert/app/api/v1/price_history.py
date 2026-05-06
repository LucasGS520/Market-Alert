"""
Router: histórico de preços coletados.

Endpoints para consultar o histórico de preços de um produto monitorado
ou de um concorrente específico. Cada entrada representa uma coleta realizada.

Endpoints:
    GET /price-history/{monitored_id}       → histórico do produto monitorado
    GET /price-history/competitor/{id}      → histórico de um concorrente
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.price_history import PriceHistory
from app.schemas.price_history import PriceHistoryRead

router = APIRouter(prefix="/price-history", tags=["price-history"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{monitored_id}", response_model=list[PriceHistoryRead])
async def get_product_history(monitored_id: uuid.UUID, session: Session) -> list[PriceHistory]:
    """
    Retorna as últimas 200 coletas de preço de um produto monitorado.

    Ordenado do mais recente ao mais antigo — útil para gráficos de tendência.
    """
    resultado = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.monitored_id == monitored_id)
        .order_by(PriceHistory.collected_at.desc())
        .limit(200)
    )
    return list(resultado.scalars().all())


@router.get("/competitor/{competitor_id}", response_model=list[PriceHistoryRead])
async def get_competitor_history(competitor_id: uuid.UUID, session: Session) -> list[PriceHistory]:
    """
    Retorna as últimas 200 coletas de preço de um concorrente.

    Permite comparar a evolução de preço de um concorrente específico ao longo do tempo.
    """
    resultado = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.competitor_id == competitor_id)
        .order_by(PriceHistory.collected_at.desc())
        .limit(200)
    )
    return list(resultado.scalars().all())
