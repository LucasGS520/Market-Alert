from typing import Generic, TypeVar

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
