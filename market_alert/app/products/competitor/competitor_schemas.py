import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class CompetitorCreate(BaseModel):
    monitored_id: uuid.UUID
    url: AnyHttpUrl
    name: str | None = Field(None, max_length=512)


class CompetitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitored_id: uuid.UUID
    url: str
    name: str | None
    current_price: Decimal | None
    is_available: bool | None
    last_checked_at: datetime | None
    created_at: datetime
