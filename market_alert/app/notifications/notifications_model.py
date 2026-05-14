import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base

EventType = Enum(
    "price_drop", "price_rise", "status_change",
    "ranking_change",
    "product_unavailable", "product_available",
    "market_price_drop", "market_price_rise",
    "competitor_unavailable", "competitor_available",
    name="notification_event_type",
)
DeliveryStatus = Enum("pending", "sent", "failed", "skipped", name="delivery_status")


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        Index(
            "uq_notification_comparison_event",
            "comparison_id",
            "event_type",
            unique=True,
            postgresql_where=text("comparison_id IS NOT NULL AND delivery_status = 'sent'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    monitored_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitored_products.id", ondelete="CASCADE"), nullable=False
    )
    comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comparisons.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(EventType, nullable=False)
    delivery_status: Mapped[str] = mapped_column(DeliveryStatus, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_ranking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_ranking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competitor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="SET NULL"), nullable=True
    )
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    run_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    participants_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    monitored_product: Mapped["MonitoredProduct"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="notification_logs"
    )
