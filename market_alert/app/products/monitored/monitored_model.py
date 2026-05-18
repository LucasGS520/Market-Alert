import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base

ProductStatus = Enum(
    "pending", "active", "paused", "error", "unsupported", "unavailable",
    name="product_status",
)

StabilityLevel = Enum(
    "unstable", "stable", "very_stable",
    name="stability_level",
)


class MonitoredProduct(Base):
    __tablename__ = "monitored_products"
    __table_args__ = (
        UniqueConstraint("url_normalized", name="uq_monitored_url_normalized"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url_original: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_normalized: Mapped[str] = mapped_column(String(2048), nullable=False)

    status: Mapped[str] = mapped_column(ProductStatus, nullable=False, server_default="pending")
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    consecutive_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # ── Estado de Estabilidade ─────────────────────────────────────────────
    stability_level: Mapped[str] = mapped_column(
        StabilityLevel, nullable=False, server_default="unstable"
    )
    last_price_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_significant_price_change_percent: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    last_availability_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Controle Operacional de Rodada ────────────────────────────────────
    last_scheduled_delay_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collection_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_collection_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_collection_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_collection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_check_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    competitors: Mapped[list["Competitor"]] = relationship(  # noqa: F821
        "Competitor", back_populates="monitored_product",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(  # noqa: F821
        "PriceHistory", back_populates="monitored_product",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    comparisons: Mapped[list["Comparison"]] = relationship(  # noqa: F821
        "Comparison", back_populates="monitored_product",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    notification_logs: Mapped[list["NotificationLog"]] = relationship(  # noqa: F821
        "NotificationLog", back_populates="monitored_product",
        cascade="all, delete-orphan", passive_deletes=True,
    )
