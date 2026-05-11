import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base

ComparisonStatus = Enum("competitive", "attention", "urgent", name="comparison_status")


class Comparison(Base):
    __tablename__ = "comparisons"
    __table_args__ = (
        Index("ix_comparisons_monitored_calculated", "monitored_id", "calculated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    monitored_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitored_products.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(ComparisonStatus, nullable=False)
    ranking: Mapped[int] = mapped_column(Integer, nullable=False)

    average_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    min_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    potential_adjustment: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    monitored_product: Mapped["MonitoredProduct"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="comparisons"
    )
