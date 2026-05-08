"""
Modelo ORM: histórico de preços coletados.

Cada registro representa uma coleta realizada: o preço e a disponibilidade
capturados em um determinado momento para um produto monitorado OU para
um concorrente.

Invariante garantida pelo banco:
    Exatamente um dos campos (monitored_id, competitor_id) deve ser não-nulo.
    Nunca ambos preenchidos, nunca nenhum preenchido.
    → CheckConstraint no banco garante isso em nível de SQL.

Índices para performance:
    As consultas de histórico sempre filtram por produto/concorrente + período,
    então os índices compostos (monitored_id + collected_at) são essenciais.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PriceHistory(Base):
    """Registro de uma coleta de preço (produto monitorado ou concorrente)."""

    __tablename__ = "price_history"
    __table_args__ = (
        # Garante que cada registro pertence a exatamente um dono
        CheckConstraint(
            "(monitored_id IS NOT NULL)::int + (competitor_id IS NOT NULL)::int = 1",
            name="ck_price_history_single_owner",
        ),
        # Índice para buscas rápidas de histórico por produto + período
        Index("ix_price_history_monitored_collected", "monitored_id", "collected_at"),
        # Índice para buscas rápidas de histórico por concorrente + período
        Index("ix_price_history_competitor_collected", "competitor_id", "collected_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # Apenas um destes dois será preenchido por registro
    # ON DELETE SET NULL: mantém o histórico mesmo se o produto/concorrente for removido
    monitored_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitored_products.id", ondelete="SET NULL"), nullable=True
    )
    competitor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="SET NULL"), nullable=True
    )

    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Campos de auditoria: preservam o contexto técnico de cada coleta para diagnóstico
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    seller: Mapped[str | None] = mapped_column(String(512), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relações
    monitored_product: Mapped["MonitoredProduct | None"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="price_history"
    )
    competitor: Mapped["Competitor | None"] = relationship(  # noqa: F821
        "Competitor", back_populates="price_history"
    )
