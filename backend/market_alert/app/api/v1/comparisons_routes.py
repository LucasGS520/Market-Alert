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

from app.comparison.comparison_schemas import ComparisonRead, CompetitorSummaryRead, MarketSnapshotRead
from app.comparison.comparison_service import get_comparison_history, get_latest_comparison
from app.comparison.market_indicators_service import (
    compute_competitor_summaries,
    compute_market_variation_24h,
    compute_reference_indicators,
)
from app.infra.database import get_session

router = APIRouter(prefix="/comparisons", tags=["comparisons"])

Session = Annotated[AsyncSession, Depends(get_session)]


def _build_competitor_summary(data: dict) -> CompetitorSummaryRead:
    return CompetitorSummaryRead(
        id=data["id"],
        name=data.get("name"),
        current_price=data.get("current_price"),
        variation_24h=data.get("variation_24h"),
        status=data["status"],
        thumbnail_url=data.get("thumbnail_url"),
    )


@router.get("/{monitored_id}", response_model=MarketSnapshotRead)
async def get_latest_comparison_endpoint(monitored_id: uuid.UUID, session: Session):
    """
    Retorna o snapshot de mercado mais recente para um produto monitorado.

    Inclui indicadores da oferta de referência (variation_24h, variation_all, sparkline)
    e resumo dos concorrentes. Retorna 404 se nenhuma comparação foi calculada ainda.
    """
    comparacao = await get_latest_comparison(session, monitored_id)
    if not comparacao:
        raise HTTPException(status_code=404, detail="Nenhuma comparação disponível ainda para este produto")

    ref = await compute_reference_indicators(session, monitored_id)
    competitors = await compute_competitor_summaries(session, monitored_id)
    market_var = await compute_market_variation_24h(session, monitored_id)

    snapshot = MarketSnapshotRead.model_validate(comparacao)
    snapshot.variation_24h = ref.get("variation_24h")
    snapshot.variation_all = ref.get("variation_all")
    snapshot.previous_price = ref.get("previous_price")
    snapshot.sparkline = ref.get("sparkline", [])
    snapshot.market_variation_24h = market_var
    snapshot.competitors = [
        _build_competitor_summary(c) for c in competitors
    ]
    return snapshot


@router.get("/{monitored_id}/history", response_model=list[ComparisonRead])
async def get_comparison_history_endpoint(monitored_id: uuid.UUID, session: Session):
    """
    Retorna o histórico das últimas 100 comparações de um produto monitorado.

    Útil para acompanhar a evolução do posicionamento competitivo ao longo do tempo.
    """
    return await get_comparison_history(session, monitored_id)
