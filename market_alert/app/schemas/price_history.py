"""
Schemas Pydantic para histórico de preços.

Define o contrato de saída da API para o endpoint /price-history.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PriceHistoryRead(BaseModel):
    """Dados de uma coleta de preço registrada no histórico."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Apenas um dos dois campos abaixo será preenchido por registro
    monitored_id: uuid.UUID | None   # Preenchido para coletas de produto monitorado
    competitor_id: uuid.UUID | None  # Preenchido para coletas de concorrente
    price: Decimal
    is_available: bool
    collected_at: datetime
