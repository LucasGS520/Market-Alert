import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base

ProductStatus = Enum("active", "paused", "error", name="product_status")


class MonitoredProduct(Base):
    __tablename__ = "monitored_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)

    status: Mapped[str] = mapped_column(ProductStatus, nullable=False, server_default="active")
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    consecutive_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    competitors: Mapped[list["Competitor"]] = relationship(  # noqa: F821
        "Competitor", back_populates="monitored_product", cascade="all, delete-orphan"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(  # noqa: F821
        "PriceHistory", back_populates="monitored_product"
    )
    comparisons: Mapped[list["Comparison"]] = relationship(  # noqa: F821
        "Comparison", back_populates="monitored_product", cascade="all, delete-orphan"
    )
    notification_logs: Mapped[list["NotificationLog"]] = relationship(  # noqa: F821
        "NotificationLog", back_populates="monitored_product", cascade="all, delete-orphan"
    )
