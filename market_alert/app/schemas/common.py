"""
Schemas Pydantic compartilhados entre múltiplos módulos da API.

Contém tipos genéricos e contratos de comunicação interna que não
pertencem a um domínio específico (monitored, competitors, etc.).
"""

from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Wrapper genérico para respostas paginadas da API.

    Uso: PaginatedResponse[MonitoredProductRead]
    """
    items: list[T]
    total: int


class ScraperResult(BaseModel):
    """
    Resultado retornado pelo microserviço market_scraper.

    Representa os dados extraídos de uma página de produto após o scraping.
    """
    marketplace: str
    price: Decimal
    available: bool
    title: str | None = None
    seller: str | None = None
    currency: str | None = None
    collected_at: datetime


class TaskEnqueued(BaseModel):
    """Resposta de sucesso ao enfileirar uma tarefa Celery."""
    task_id: str
    message: str
