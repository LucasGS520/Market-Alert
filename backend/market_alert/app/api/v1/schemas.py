import uuid
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int


class TaskEnqueued(BaseModel):
    task_id: str
    message: str


class CreatedWithTask(BaseModel, Generic[T]):
    """Envelope para respostas 202: recurso criado + task_id da coleta enfileirada."""
    data: T
    task_id: str | None = None


class SearchResult(BaseModel):
    """Item unificado de busca: produto monitorado ou concorrente."""
    type: Literal["product", "competitor"]
    id: uuid.UUID
    monitored_id: uuid.UUID
    name: str | None
    url_normalized: str
    status: str
    current_price: Decimal | None = None
    parent_name: str | None = None
