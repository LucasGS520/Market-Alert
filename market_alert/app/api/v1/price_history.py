"""
Router: historico de precos coletados.

Endpoints para consultar o historico de precos de um produto monitorado
ou de um concorrente especifico. Cada entrada representa uma coleta realizada.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.products.price_history.price_model import PriceHistory
from app.products.price_history.price_schemas import PriceHistoryRead

router = APIRouter(prefix="/price-history", tags=["price-history"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/competitor/{competitor_id}", response_model=list[PriceHistoryRead])
async def get_competitor_history(competitor_id: uuid.UUID, session: Session) -> list[PriceHistory]:
    """Retorna as ultimas 200 coletas de preco de um concorrente."""
    resultado = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.competitor_id == competitor_id)
        .order_by(PriceHistory.collected_at.desc())
        .limit(200)
    )
    return list(resultado.scalars().all())


@router.get("/{monitored_id}", response_model=list[PriceHistoryRead])
async def get_product_history(monitored_id: uuid.UUID, session: Session) -> list[PriceHistory]:
    """Retorna as ultimas 200 coletas de preco de um produto monitorado."""
    resultado = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.monitored_id == monitored_id)
        .order_by(PriceHistory.collected_at.desc())
        .limit(200)
    )
    return list(resultado.scalars().all())
