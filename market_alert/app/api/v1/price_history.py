"""
Router: historico de precos coletados.

Endpoints para consultar o historico de precos de um produto monitorado
ou de um concorrente especifico. Cada entrada representa uma coleta realizada.
"""

"""
Router: historico de precos coletados.

Endpoints para consultar o historico de precos de um produto monitorado
ou de um concorrente especifico. Cada entrada representa uma coleta realizada.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.products.price_history.price_history_service import (
    get_competitor_price_history,
    get_product_price_history,
)
from app.products.price_history.price_schemas import PriceHistoryRead

router = APIRouter(prefix="/price-history", tags=["price-history"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/competitor/{competitor_id}", response_model=list[PriceHistoryRead])
async def get_competitor_history(competitor_id: uuid.UUID, session: Session):
    """Retorna as ultimas 200 coletas de preco de um concorrente."""
    return await get_competitor_price_history(session, competitor_id)


@router.get("/{monitored_id}", response_model=list[PriceHistoryRead])
async def get_product_history(monitored_id: uuid.UUID, session: Session):
    """Retorna as ultimas 200 coletas de preco de um produto monitorado."""
    return await get_product_price_history(session, monitored_id)
