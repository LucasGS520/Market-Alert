"""
Schemas Pydantic para comparações de preço.

Define os contratos de entrada/saída da API para o endpoint /comparisons.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ComparisonRead(BaseModel):
    """Dados de uma comparação de preços calculada pelo sistema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitored_id: uuid.UUID
    # Classificação competitiva: competitive | attention | urgent
    status: str
    # Posição do produto no ranking de preços (1 = mais barato)
    ranking: int
    average_price: Decimal
    min_price: Decimal
    max_price: Decimal
    # Quanto precisaria baixar para ser o mais barato (None se já é o mais barato)
    potential_adjustment: Decimal | None
    calculated_at: datetime
