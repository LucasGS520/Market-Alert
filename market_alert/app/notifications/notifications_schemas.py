import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class NotificationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitored_id: uuid.UUID
    comparison_id: uuid.UUID | None
    event_type: str
    delivery_status: str
    message: str
    title: str | None
    error_message: str | None
    attempt_count: int
    old_price: Decimal | None
    new_price: Decimal | None
    old_status: str | None
    new_status: str | None
    old_ranking: int | None
    new_ranking: int | None
    competitor_id: uuid.UUID | None
    run_id: str | None
    run_status: str | None
    participants_count: int | None
    sent_at: datetime
