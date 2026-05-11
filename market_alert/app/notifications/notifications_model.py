import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base

EventType = Enum("price_drop", "price_rise", "status_change", name="notification_event_type")
ChannelType = Enum("ntfy", "telert", name="notification_channel")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    monitored_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitored_products.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(EventType, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(ChannelType, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    monitored_product: Mapped["MonitoredProduct"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="notification_logs"
    )
