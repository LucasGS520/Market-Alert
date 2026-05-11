import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
