import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.products.competitor.competitor_schemas import CompetitorCreate, CompetitorRead
from app.products.competitor.competitor_service import create_competitor, delete_competitor, list_competitors

logger = structlog.get_logger()

router = APIRouter(prefix="/competitors", tags=["competitors"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/scrape", response_model=CompetitorRead, status_code=status.HTTP_202_ACCEPTED)
async def add_competitor(body: CompetitorCreate, session: Session):
    concorrente = await create_competitor(session, body.monitored_id, str(body.url), body.name)

    try:
        from app.workers.tasks import collector_task
        tarefa = collector_task.delay(competitor_id=str(concorrente.id))
        logger.info("coleta_concorrente_enfileirada", concorrente_id=str(concorrente.id), tarefa_id=tarefa.id)
    except Exception as exc:
        logger.warning("enfileiramento_falhou", concorrente_id=str(concorrente.id), erro=str(exc))

    return concorrente


@router.get("/", response_model=list[CompetitorRead])
async def list_competitors_endpoint(monitored_id: uuid.UUID, session: Session):
    return await list_competitors(session, monitored_id)


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_competitor(competitor_id: uuid.UUID, session: Session) -> Response:
    monitored_id = await delete_competitor(session, competitor_id)

    try:
        from app.workers.tasks import comparison_task
        comparison_task.delay(monitored_id=str(monitored_id))
    except Exception as exc:
        logger.warning("recalculo_falhou", monitored_id=str(monitored_id), erro=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
