"""
Schemas Pydantic para produtos monitorados.

Define os contratos de entrada/saída da API para o endpoint /monitored.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.schemas.comparison import ComparisonRead


class MonitoredProductCreate(BaseModel):
    """Dados necessários para cadastrar um novo produto para monitoramento."""

    url: AnyHttpUrl                             # URL da página de produto a monitorar
    name: str | None = Field(None, max_length=512)  # Nome descritivo (opcional; scraper preenche se ausente)


class MonitoredProductRead(BaseModel):
    """Dados de um produto monitorado retornados pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    url: str
    status: str                          # active | paused | error
    current_price: Decimal | None        # None até a primeira coleta
    is_available: bool | None
    next_check_at: datetime | None       # Quando ocorrerá a próxima coleta
    last_checked_at: datetime | None     # Quando ocorreu a última coleta
    check_interval_minutes: int          # Intervalo atual (adaptativo: 15-240 min)
    created_at: datetime


class MonitoredProductDetail(MonitoredProductRead):
    """Detalhe completo incluindo a última comparação de preços calculada."""

    latest_comparison: ComparisonRead | None = None


class MonitoredProductPatch(BaseModel):
    """Dados para atualizar o status de um produto monitorado."""

    status: Literal["active", "paused"]
