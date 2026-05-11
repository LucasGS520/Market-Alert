import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.comparison.comparison_schemas import ComparisonRead


class MonitoredProductCreate(BaseModel):
    url: AnyHttpUrl
    name: str | None = Field(None, max_length=512)


class MonitoredProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    url_original: str
    url_normalized: str
    status: str
    current_price: Decimal | None
    is_available: bool | None
    next_check_at: datetime | None
    last_checked_at: datetime | None
    check_interval_minutes: int
    created_at: datetime


class MonitoredProductDetail(MonitoredProductRead):
    latest_comparison: ComparisonRead | None = None


class MonitoredProductPatch(BaseModel):
    status: Literal["pending", "active", "paused", "error", "unsupported", "unavailable"]
