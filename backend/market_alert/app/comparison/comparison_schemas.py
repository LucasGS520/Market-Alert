import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatusLiteral = Literal["complete", "partial", "expired", "no_competitors", "manual"]


class PricePoint(BaseModel):
    t: datetime
    v: float


class ComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitored_id: uuid.UUID
    # None quando a oferta de referência estava indisponível no snapshot.
    status: str | None
    ranking: int | None
    reference_available: bool
    average_price: Decimal
    min_price: Decimal
    max_price: Decimal
    potential_adjustment: Decimal | None
    calculated_at: datetime

    # Campos de auditoria da rodada
    run_id: str | None
    run_status: RunStatusLiteral | None
    product_price: Decimal | None
    participants_count: int | None
    valid_competitors_count: int | None
    ignored_competitors_count: int | None


class CompetitorSummaryRead(BaseModel):
    id: uuid.UUID
    name: str | None
    current_price: Decimal | None
    initial_price: Decimal | None = None
    variation_since_start: float | None = None
    gap_vs_product: Decimal | None = None
    gap_vs_product_percent: float | None = None
    status: str | None
    thumbnail_url: str | None


class MarketSnapshotRead(ComparisonRead):
    # Séries temporais de mercado (histórico de Comparison)
    market_min_series: list[PricePoint] = Field(default_factory=list)
    market_avg_series: list[PricePoint] = Field(default_factory=list)
    # Indicadores de mercado "desde o início"
    market_min_current: Decimal | None = None
    market_min_initial: Decimal | None = None
    market_min_variation_since_start: float | None = None
    market_avg_current: Decimal | None = None
    market_avg_initial: Decimal | None = None
    market_avg_variation_since_start: float | None = None
    # Resumo das ofertas concorrentes
    competitors: list[CompetitorSummaryRead] = Field(default_factory=list)
