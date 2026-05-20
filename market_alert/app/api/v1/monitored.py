import uuid
from typing import Annotated
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
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
    list_products_with_comparisons,
    pause_product,
    resume_product,
)
from app.products.url_utils import get_url_rejection_reason, is_valid_product_url, normalize_url, resolve_canonical_url
from app.api.v1.schemas import CreatedWithTask
from app.scheduling.scheduler_service import enqueue_with_lease
from app.workers.redis import (
    get_collection_attempts,
    get_redis,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/monitored", tags=["monitored"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/", response_model=CreatedWithTask[MonitoredProductRead], status_code=status.HTTP_202_ACCEPTED)
async def create_monitored(body: MonitoredProductCreate, session: Session) -> CreatedWithTask[MonitoredProductRead]:
    url_str = str(body.url)
    normalized = normalize_url(url_str)
    if not is_valid_product_url(normalized):
        resolved = await resolve_canonical_url(url_str)
        if resolved and is_valid_product_url(resolved):
            logger.info("url_resolvida_por_redirect", url_original=url_str, url_resolvida=resolved)
            url_str = resolved
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_url",
                    "message": get_url_rejection_reason(url_str),
                    "url": url_str,
                },
            )
    produto = await create_product(session, url_str, body.name)
    task_id = await enqueue_with_lease(session, produto.id)
    return CreatedWithTask(data=MonitoredProductRead.model_validate(produto), task_id=task_id)


@router.get("/", response_model=list[MonitoredProductDetail])
async def list_monitored(session: Session):
    rows = await list_products_with_comparisons(session)
    result = []
    for produto, comparacao, count in rows:
        item = MonitoredProductDetail.model_validate(produto)
        if comparacao:
            item.latest_comparison = ComparisonRead.model_validate(comparacao)
        item.competitors_count = count
        result.append(item)
    return result


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
        from app.scheduling.scheduler_service import enqueue_with_lease
        tarefa_id = await enqueue_with_lease(session, produto.id)
        if tarefa_id:
            logger.info("coleta_enfileirada_apos_resume", produto_id=str(produto.id), tarefa_id=tarefa_id)
        else:
            logger.info("coleta_pulada_lease_ativo_apos_resume", produto_id=str(produto.id))
    except Exception as exc:
        logger.warning("enfileiramento_falhou_apos_resume", produto_id=str(produto.id), erro=str(exc))
    return produto


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitored(product_id: uuid.UUID, session: Session) -> Response:
    await delete_product(session, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ProductHealth(BaseModel):
    product_id: uuid.UUID
    domain: str
    status: str
    next_check_at: str | None
    next_check_reason: str | None
    consecutive_failures: int
    last_successful_collection_at: str | None
    recent_attempts: list[dict]


@router.get("/{product_id}/health", response_model=ProductHealth)
async def get_product_health(product_id: uuid.UUID, session: Session) -> ProductHealth:
    """Diagnóstico de coleta: status atual, agendamento e histórico de tentativas."""
    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    redis = get_redis()
    dominio = urlparse(produto.url_normalized or "").netloc or "unknown"

    return ProductHealth(
        product_id=product_id,
        domain=dominio,
        status=produto.status,
        next_check_at=produto.next_check_at.isoformat() if produto.next_check_at else None,
        next_check_reason=produto.next_check_reason,
        consecutive_failures=produto.consecutive_failures or 0,
        last_successful_collection_at=(
            produto.last_successful_collection_at.isoformat()
            if produto.last_successful_collection_at
            else None
        ),
        recent_attempts=get_collection_attempts(redis, str(product_id)),
    )
