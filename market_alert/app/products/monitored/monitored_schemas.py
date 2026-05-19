import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, computed_field

from app.comparison.comparison_schemas import ComparisonRead
from app.infra.config import settings


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
    next_check_reason: str | None
    last_checked_at: datetime | None
    last_successful_collection_at: datetime | None
    last_collection_started_at: datetime | None
    last_collection_finished_at: datetime | None
    collection_lease_until: datetime | None
    consecutive_failures: int
    check_interval_minutes: int
    created_at: datetime

    @computed_field
    @property
    def is_price_stale(self) -> bool:
        if self.current_price is None:
            return False
        if not self.last_successful_collection_at:
            return True
        now = datetime.now(timezone.utc)
        last = self.last_successful_collection_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_minutes = (now - last).total_seconds() / 60
        threshold = self.check_interval_minutes * settings.stale_multiplier
        return age_minutes > threshold


class MonitoredProductDetail(MonitoredProductRead):
    latest_comparison: ComparisonRead | None = None
    competitors_count: int = 0


class MonitoredProductPatch(BaseModel):
    status: Literal["pending", "active", "paused", "error", "unsupported", "unavailable"]
