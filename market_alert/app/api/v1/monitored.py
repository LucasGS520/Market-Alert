import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.comparison.comparison_schemas import ComparisonRead

from app.products.monitored.monitored_model import MonitoredProduct
from app.products.monitored.monitored_schemas import (
    MonitoredProductCreate,
    MonitoredProductDetail,
    MonitoredProductRead,
)
from app.products.monitored.monitored_service import (
    create_product,
    delete_product,
    get_with_latest_comparison,
    list_products,
    pause_product,
    resume_product,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/monitored", tags=["monitored"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/", response_model=MonitoredProductRead, status_code=status.HTTP_202_ACCEPTED)
async def create_monitored(body: MonitoredProductCreate, session: Session) -> MonitoredProduct:
    produto = await create_product(session, str(body.url), body.name)

    try:
        from app.workers.orchestrator import collection_orchestrator_task
        tarefa = collection_orchestrator_task.delay(product_id=str(produto.id))
        logger.info("coleta_enfileirada", produto_id=str(produto.id), tarefa_id=tarefa.id)
    except Exception as exc:
        logger.warning("enfileiramento_falhou", produto_id=str(produto.id), erro=str(exc))

    return produto


@router.get("/", response_model=list[MonitoredProductRead])
async def list_monitored(session: Session):
    return await list_products(session)


@router.get("/{product_id}", response_model=MonitoredProductDetail)
async def get_monitored(product_id: uuid.UUID, session: Session) -> MonitoredProductDetail:
    produto, ultima_comparacao = await get_with_latest_comparison(session, product_id)

    detalhe = MonitoredProductDetail.model_validate(produto)
    if ultima_comparacao:
        detalhe.latest_comparison = ComparisonRead.model_validate(ultima_comparacao)
    return detalhe


@router.patch("/{product_id}/pause", response_model=MonitoredProductRead)
async def pause_monitored(product_id: uuid.UUID, session: Session) -> MonitoredProduct:
    return await pause_product(session, product_id)


@router.patch("/{product_id}/resume", response_model=MonitoredProductRead)
async def resume_monitored(product_id: uuid.UUID, session: Session) -> MonitoredProduct:
    produto = await resume_product(session, product_id)
    try:
        from app.workers.orchestrator import collection_orchestrator_task
        tarefa = collection_orchestrator_task.delay(product_id=str(produto.id))
        logger.info("coleta_enfileirada_apos_resume", produto_id=str(produto.id), tarefa_id=tarefa.id)
    except Exception as exc:
        logger.warning("enfileiramento_falhou_apos_resume", produto_id=str(produto.id), erro=str(exc))
    return produto


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitored(product_id: uuid.UUID, session: Session) -> Response:
    await delete_product(session, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
