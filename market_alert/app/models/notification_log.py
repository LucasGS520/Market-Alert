"""
Modelo ORM: registro de notificações enviadas.

Cada vez que o sistema dispara um alerta, um NotificationLog é gravado.
Serve para auditoria (o que foi enviado, quando, por qual canal) e
para evitar re-envio em caso de bug.

Tipos de evento:
    price_drop    → preço caiu mais que o delta configurado
    price_rise    → preço subiu mais que o delta configurado
    status_change → status competitivo mudou (ex: competitive → urgent)

Canais:
    ntfy   → notificação push via ntfy.sh
    telert → mensagem via telert.dev
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

EventType = Enum("price_drop", "price_rise", "status_change", name="notification_event_type")
ChannelType = Enum("ntfy", "telert", name="notification_channel")


class NotificationLog(Base):
    """Registro de um alerta enviado pelo sistema."""

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

    # Relações
    monitored_product: Mapped["MonitoredProduct"] = relationship(  # noqa: F821
        "MonitoredProduct", back_populates="notification_logs"
    )
