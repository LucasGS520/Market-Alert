"""
Router: notificações.

Endpoints para consultar o histórico de alertas.
Cada registro representa uma entrega, falha ou supressão de notificação —
incluindo bloqueios operacionais auditáveis.

Endpoints:
    GET /notifications                    → listagem com filtros
    GET /notifications/{notification_id}  → detalhe de uma tentativa
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.notifications.event_types import ALL_TYPES
from app.notifications.notifications_schemas import NotificationLogRead
from app.notifications.notifications_service import get_notification, list_notifications

_EVENT_TYPE_ENUM = sorted(ALL_TYPES)
DeliveryStatus = Literal["pending", "sent", "failed", "skipped"]

router = APIRouter(prefix="/notifications", tags=["notifications"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[NotificationLogRead])
async def list_notifications_endpoint(
    session: Session,
    monitored_id: uuid.UUID | None = None,
    event_type: str | None = Query(default=None, enum=_EVENT_TYPE_ENUM),
    delivery_status: DeliveryStatus | None = None,
    competitor_id: uuid.UUID | None = None,
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Lista tentativas de notificação com filtros opcionais.

    - **monitored_id**: filtra por produto monitorado.
    - **event_type**: qualquer tipo presente em `event_types.ALL_TYPES` (ativos, auditoria, inativos ou legados).
    - **delivery_status**: pending, sent, failed ou skipped.
    - **competitor_id**: filtra eventos Tier 2 de um concorrente específico.
    - **from** / **to**: intervalo de data (ISO 8601).
    - **limit**: máximo de registros retornados (padrão 50, máximo 200).
    """
    return await list_notifications(
        session,
        monitored_id=monitored_id,
        event_type=event_type,
        delivery_status=delivery_status,
        date_from=date_from,
        date_to=date_to,
        competitor_id=competitor_id,
        limit=limit,
    )


@router.get("/{notification_id}", response_model=NotificationLogRead)
async def get_notification_endpoint(notification_id: uuid.UUID, session: Session):
    """
    Retorna o detalhe de uma tentativa de notificação específica.

    Inclui comparação origem, canal, status de entrega, erro (se houver)
    e contexto completo do evento (preços, status, rodada).
    """
    notif = await get_notification(session, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    return notif
