"""
Modelo ORM: concorrente de um produto monitorado.

Um Competitor é uma URL de produto concorrente vinculada a um MonitoredProduct.
O sistema coleta preços dos concorrentes para calcular o posicionamento
competitivo do produto principal.

Regras de negócio:
    - Máximo de 5 concorrentes por produto monitorado
    - URL do concorrente não pode ser igual à URL do produto principal
    - Unicidade garantida pelo banco: (monitored_id, url) é único
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Competitor(Base):
    """Concorrente vinculado a um produto monitorado."""

    __tablename__ = "competitors"
    __table_args__ = (
        # Garante que o mesmo concorrente não seja cadastrado duas vezes no mesmo produto
        UniqueConstraint("monitored_id", "url", name="uq_competitor_monitored_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Produto monitorado ao qual este concorrente pertence
    # ON DELETE CASCADE: se o produto for removido, todos os concorrentes são removidos junto
    monitored_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitored_products.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Estado atual do concorrente (preenchido após a primeira coleta)
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relações
    monitored_product: Mapped["MonitoredProduct"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="competitors"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(  # noqa: F821
        "PriceHistory", back_populates="competitor"
    )
