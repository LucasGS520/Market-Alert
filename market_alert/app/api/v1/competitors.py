import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.products.competitor.competitor_service import delete_competitor

logger = structlog.get_logger()

router = APIRouter(prefix="/competitors", tags=["competitors"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_competitor(competitor_id: uuid.UUID, session: Session) -> Response:
    monitored_id = await delete_competitor(session, competitor_id)

    try:
        from app.workers.tasks import comparison_task
        comparison_task.delay(monitored_id=str(monitored_id))
    except Exception as exc:
        logger.warning("recalculo_falhou", monitored_id=str(monitored_id), erro=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
