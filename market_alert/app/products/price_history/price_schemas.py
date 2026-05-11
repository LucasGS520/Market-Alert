import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PriceHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitored_id: uuid.UUID | None
    competitor_id: uuid.UUID | None
    price: Decimal
    is_available: bool
    collected_at: datetime
    title: str | None = None
    seller: str | None = None
    thumbnail_url: str | None = None
    extraction_method: str | None = None
    confidence: float | None = None
