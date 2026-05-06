"""
Schemas Pydantic para concorrentes.

Define os contratos de entrada/saída da API para o endpoint /competitors.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class CompetitorCreate(BaseModel):
    """Dados necessários para cadastrar um novo concorrente."""

    monitored_id: uuid.UUID   # Produto monitorado ao qual o concorrente pertence
    url: AnyHttpUrl           # URL da página de produto do concorrente
    name: str | None = Field(None, max_length=512)  # Nome opcional (preenchido pelo scraper se ausente)


class CompetitorRead(BaseModel):
    """Dados de um concorrente retornados pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitored_id: uuid.UUID
    url: str
    name: str | None
    current_price: Decimal | None    # None até a primeira coleta
    is_available: bool | None
    last_checked_at: datetime | None # None até a primeira coleta
    created_at: datetime
