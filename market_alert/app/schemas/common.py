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


class ScraperErrorResult(BaseModel):
    """
    Erro estruturado retornado pelo market_scraper (HTTP 422).

    Espelha o contrato ScrapeError do scraper, preservando error_code e retryable
    para que a lógica de negócio decida se retenta ou apenas registra a falha.
    """
    error_code: str  # PRICE_NOT_FOUND | CAPTCHA_DETECTED | BLOCKED | UNAVAILABLE | REDIRECT | LAYOUT_CHANGED | TIMEOUT | MARKETPLACE_NOT_SUPPORTED
    marketplace: str
    url: str
    retryable: bool
    message: str


class ScraperResult(BaseModel):
    """
    Resultado de sucesso retornado pelo microserviço market_scraper (contrato v1).

    Campos obrigatórios: marketplace, available, extraction_method, collected_at.
    price: não-nulo e > 0 quando available=True; None quando available=False.
    """
    marketplace: str
    price: Decimal | None = None
    available: bool
    title: str | None = None
    seller: str | None = None
    thumbnail_url: str | None = None
    currency: str | None = None
    collected_at: datetime
    url: str | None = None
    canonical_url: str | None = None
    product_id: str | None = None
    extraction_method: str | None = None  # network_payload | ssr_state | hydration_json | css_selector
    confidence: float | None = None       # qualidade técnica da extração (0.0–1.0)


class TaskEnqueued(BaseModel):
    """Resposta de sucesso ao enfileirar uma tarefa Celery."""
    task_id: str
    message: str
