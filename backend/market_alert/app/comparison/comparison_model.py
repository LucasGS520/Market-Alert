import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base

ComparisonStatus = Enum("competitive", "attention", "urgent", name="comparison_status")
RunStatus = Enum(
    "complete", "partial", "expired", "no_competitors", "manual",
    name="run_status",
)


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

    # Nullable quando a oferta de referência estiver indisponível no snapshot.
    status: Mapped[str | None] = mapped_column(ComparisonStatus, nullable=True)
    ranking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    average_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    min_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    potential_adjustment: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Campos de auditoria da rodada (adicionados na migration 006)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    run_status: Mapped[str | None] = mapped_column(RunStatus, nullable=True)
    product_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    participants_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_competitors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ignored_competitors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    monitored_product: Mapped["MonitoredProduct"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="comparisons"
    )
