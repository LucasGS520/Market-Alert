import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import CreatedWithTask
from app.infra.database import get_session
from app.products.competitor.competitor_schemas import CompetitorCreate, CompetitorRead
from app.products.competitor.competitor_service import create_competitor, delete_competitor, list_competitors
from app.utils.url_utils import get_url_rejection_reason, is_valid_product_url, normalize_url

logger = structlog.get_logger()

Session = Annotated[AsyncSession, Depends(get_session)]

# Router para endpoints diretos de concorrentes
router = APIRouter(prefix="/competitors", tags=["competitors"])

# Router para endpoints aninhados de concorrentes (no contexto de produtos monitorados)
router_nested = APIRouter(prefix="/monitored/{monitored_id}/competitors", tags=["competitors"])


# ── Endpoints aninhados de concorrentes ──────────────────────────────────────────

@router_nested.post(
    "",
    response_model=CreatedWithTask[CompetitorRead],
    status_code=status.HTTP_202_ACCEPTED,
)
async def add_competitor(
    monitored_id: uuid.UUID, body: CompetitorCreate, session: Session
) -> CreatedWithTask[CompetitorRead]:
    """Adicionar um concorrente a um produto monitorado."""
    url_str = str(body.url)
    normalized = normalize_url(url_str)
    if not is_valid_product_url(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_url",
                "message": get_url_rejection_reason(url_str),
                "url": url_str,
            },
        )
    concorrente = await create_competitor(session, monitored_id, normalized, body.name)

    task_id: str | None = None
    try:
        from app.workers.tasks import collector_task
        tarefa = collector_task.delay(competitor_id=str(concorrente.id))
        task_id = tarefa.id
        logger.info("coleta_concorrente_enfileirada", concorrente_id=str(concorrente.id), tarefa_id=task_id)
    except Exception as exc:
        logger.warning("enfileiramento_falhou", concorrente_id=str(concorrente.id), erro=str(exc))

    return CreatedWithTask(data=CompetitorRead.model_validate(concorrente), task_id=task_id)


@router_nested.get(
    "",
    response_model=list[CompetitorRead],
)
async def list_monitored_competitors(monitored_id: uuid.UUID, session: Session):
    """Listar concorrentes de um produto monitorado."""
    return await list_competitors(session, monitored_id)

# ── Endpoints diretos de concorrentes ────────────────────────────────────────────

@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_competitor(competitor_id: uuid.UUID, session: Session) -> Response:
    monitored_id = await delete_competitor(session, competitor_id)

    try:
        from app.workers.tasks import comparison_task
        comparison_task.delay(monitored_id=str(monitored_id))
    except Exception as exc:
        logger.warning("recalculo_falhou", monitored_id=str(monitored_id), erro=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
