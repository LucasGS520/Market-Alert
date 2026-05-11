"""
Router: comparações de preços.

Endpoints para consultar o posicionamento competitivo de um produto
monitorado. A comparação é calculada automaticamente após cada coleta
e registrada no banco.

Endpoints:
    GET /comparisons/{monitored_id}         → última comparação calculada
    GET /comparisons/{monitored_id}/history → histórico de comparações
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.comparison.comparison_schemas import ComparisonRead
from app.comparison.comparison_service import get_comparison_history, get_latest_comparison
from app.infra.database import get_session

router = APIRouter(prefix="/comparisons", tags=["comparisons"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{monitored_id}", response_model=ComparisonRead)
async def get_latest_comparison_endpoint(monitored_id: uuid.UUID, session: Session):
    """
    Retorna a comparação de preços mais recente para um produto monitorado.

    Retorna 404 se nenhuma comparação foi calculada ainda (produto recém-cadastrado).
    """
    comparacao = await get_latest_comparison(session, monitored_id)
    if not comparacao:
        raise HTTPException(status_code=404, detail="Nenhuma comparação disponível ainda para este produto")
    return comparacao


@router.get("/{monitored_id}/history", response_model=list[ComparisonRead])
async def get_comparison_history_endpoint(monitored_id: uuid.UUID, session: Session):
    """
    Retorna o histórico das últimas 100 comparações de um produto monitorado.

    Útil para acompanhar a evolução do posicionamento competitivo ao longo do tempo.
    """
    return await get_comparison_history(session, monitored_id)
