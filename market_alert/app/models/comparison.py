"""
Modelo ORM: resultado de comparação de preços.

Um Comparison é calculado sempre que um novo preço é coletado.
Ele representa um snapshot do posicionamento competitivo do produto
em relação aos concorrentes naquele momento.

Status competitivo:
    competitive → produto está com o menor preço ou até 5% acima do mínimo
    attention   → produto está entre 5% e 15% acima do menor preço
    urgent      → produto está mais de 15% acima do menor preço

O campo potential_adjustment indica quanto o preço do produto precisaria
baixar para ficar igual ao menor preço do mercado.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Enum do PostgreSQL para classificação competitiva
ComparisonStatus = Enum("competitive", "attention", "urgent", name="comparison_status")


class Comparison(Base):
    """Snapshot do posicionamento competitivo de um produto monitorado."""

    __tablename__ = "comparisons"
    __table_args__ = (
        # Índice para buscar rapidamente a comparação mais recente de um produto
        Index("ix_comparisons_monitored_calculated", "monitored_id", "calculated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Produto ao qual esta comparação pertence
    monitored_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitored_products.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(ComparisonStatus, nullable=False)
    # 1 = mais barato; N = mais caro (entre produto + todos os concorrentes)
    ranking: Mapped[int] = mapped_column(Integer, nullable=False)

    # Estatísticas de preço (produto + concorrentes)
    average_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    min_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Quanto o produto precisaria baixar para ser o mais barato (None se já é o mais barato)
    potential_adjustment: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relações
    monitored_product: Mapped["MonitoredProduct"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="comparisons"
    )
