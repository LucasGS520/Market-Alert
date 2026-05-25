import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatusLiteral = Literal["complete", "partial", "expired", "no_competitors", "manual"]


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
    variation_24h: float | None
    status: str
    thumbnail_url: str | None


class MarketSnapshotRead(ComparisonRead):
    # Indicadores temporais da oferta de referência
    variation_24h: float | None = None
    variation_all: float | None = None
    previous_price: Decimal | None = None
    sparkline: list[float] = Field(default_factory=list)
    # Indicador de mercado
    market_variation_24h: float | None = None
    # Resumo das ofertas concorrentes
    competitors: list[CompetitorSummaryRead] = Field(default_factory=list)
