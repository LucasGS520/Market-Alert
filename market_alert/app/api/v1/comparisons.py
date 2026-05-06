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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.comparison import Comparison
from app.schemas.comparison import ComparisonRead

router = APIRouter(prefix="/comparisons", tags=["comparisons"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{monitored_id}", response_model=ComparisonRead)
async def get_latest_comparison(monitored_id: uuid.UUID, session: Session) -> Comparison:
    """
    Retorna a comparação de preços mais recente para um produto monitorado.

    Retorna 404 se nenhuma comparação foi calculada ainda (produto recém-cadastrado).
    """
    comparacao = await session.scalar(
        select(Comparison)
        .where(Comparison.monitored_id == monitored_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(1)
    )
    if not comparacao:
        raise HTTPException(status_code=404, detail="Nenhuma comparação disponível ainda para este produto")
    return comparacao


@router.get("/{monitored_id}/history", response_model=list[ComparisonRead])
async def get_comparison_history(monitored_id: uuid.UUID, session: Session) -> list[Comparison]:
    """
    Retorna o histórico das últimas 100 comparações de um produto monitorado.

    Útil para acompanhar a evolução do posicionamento competitivo ao longo do tempo.
    """
    resultado = await session.execute(
        select(Comparison)
        .where(Comparison.monitored_id == monitored_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(100)
    )
    return list(resultado.scalars().all())
