import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

RunStatusLiteral = Literal["complete", "partial", "expired", "no_competitors", "manual"]


class ComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitored_id: uuid.UUID
    status: str
    ranking: int
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
