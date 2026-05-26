import uuid
from typing import Annotated
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.comparison.comparison_schemas import CompetitorSummaryRead, MarketSnapshotRead
from app.comparison.comparison_schemas import PricePoint
from app.comparison.market_indicators_service import (
    batch_market_avg_sparkline,
    batch_reference_indicators,
    compute_competitor_summaries,
    compute_market_series,
    compute_reference_series,
)

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
    list_products_with_comparisons,
    pause_product,
    resume_product,
)
from app.utils.url_utils import get_url_rejection_reason, is_valid_product_url, normalize_url
from app.api.v1.schemas import CreatedWithTask, SearchResult
from app.products.competitor.competitor_model import Competitor
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_url",
                "message": get_url_rejection_reason(url_str),
                "url": url_str,
            },
        )
    produto = await create_product(session, normalized, body.name)
    task_id = await enqueue_with_lease(session, produto.id)
    return CreatedWithTask(data=MonitoredProductRead.model_validate(produto), task_id=task_id)


@router.get("/", response_model=list[MonitoredProductDetail])
async def list_monitored(session: Session):
    rows = await list_products_with_comparisons(session)
    ids = [produto.id for produto, _, _ in rows]
    indicadores = await batch_reference_indicators(session, ids)
    market_sparklines = await batch_market_avg_sparkline(session, ids)

    result = []
    for produto, comparacao, count in rows:
        item = MonitoredProductDetail.model_validate(produto)
        if comparacao:
            snapshot = MarketSnapshotRead.model_validate(comparacao)
            item.latest_comparison = snapshot
        item.competitors_count = count

        ref = indicadores.get(produto.id, {})
        item.thumbnail_url = ref.get("thumbnail_url")
        item.variation_24h = ref.get("variation_24h")
        item.variation_all = ref.get("variation_all")
        item.previous_price = ref.get("previous_price")
        item.sparkline = ref.get("sparkline", [])
        item.market_avg_sparkline = market_sparklines.get(produto.id, [])

        result.append(item)
    return result


@router.get("/search", response_model=list[SearchResult])
async def search_monitored(q: str, session: Session) -> list[SearchResult]:
    """Busca produtos monitorados e concorrentes por nome ou URL (mínimo 2 caracteres)."""
    term = q.strip()
    if len(term) < 2:
        return []

    pattern = f"%{term}%"

    products_q = await session.execute(
        select(MonitoredProduct)
        .where(or_(
            MonitoredProduct.name.ilike(pattern),
            MonitoredProduct.url_normalized.ilike(pattern),
        ))
        .limit(5)
    )
    products = list(products_q.scalars().all())

    competitors_q = await session.execute(
        select(Competitor, MonitoredProduct)
        .join(MonitoredProduct, Competitor.monitored_id == MonitoredProduct.id)
        .where(or_(
            Competitor.name.ilike(pattern),
            Competitor.url_normalized.ilike(pattern),
        ))
        .limit(5)
    )
    competitors = list(competitors_q.all())

    results: list[SearchResult] = []
    for p in products:
        results.append(SearchResult(
            type="product",
            id=p.id,
            monitored_id=p.id,
            name=p.name,
            url_normalized=p.url_normalized,
            status=p.status,
            current_price=p.current_price,
        ))
    for comp, parent in competitors:
        results.append(SearchResult(
            type="competitor",
            id=comp.id,
            monitored_id=comp.monitored_id,
            name=comp.name,
            url_normalized=comp.url_normalized,
            status=comp.status,
            current_price=comp.current_price,
            parent_name=parent.name,
        ))

    return results[:10]


@router.get("/{product_id}", response_model=MonitoredProductDetail)
async def get_monitored(product_id: uuid.UUID, session: Session) -> MonitoredProductDetail:
    produto, ultima_comparacao = await get_with_latest_comparison(session, product_id)

    detalhe = MonitoredProductDetail.model_validate(produto)

    ref = await compute_reference_series(session, product_id)
    detalhe.product_series = [PricePoint(**p) for p in ref.get("product_series", [])]
    detalhe.initial_price = ref.get("initial_price")
    detalhe.previous_price = ref.get("previous_price")
    detalhe.variation_since_start = ref.get("variation_since_start")
    detalhe.variation_since_previous = ref.get("variation_since_previous")
    detalhe.trend_since_start = ref.get("trend_since_start", "insufficient_data")

    if ultima_comparacao:
        market = await compute_market_series(session, product_id)
        competitors = await compute_competitor_summaries(
            session, product_id, reference_price=produto.current_price
        )

        snapshot = MarketSnapshotRead.model_validate(ultima_comparacao)
        snapshot.market_min_series = [PricePoint(**p) for p in market.get("market_min_series", [])]
        snapshot.market_avg_series = [PricePoint(**p) for p in market.get("market_avg_series", [])]
        snapshot.market_min_current = market.get("market_min_current")
        snapshot.market_min_initial = market.get("market_min_initial")
        snapshot.market_min_variation_since_start = market.get("market_min_variation_since_start")
        snapshot.market_avg_current = market.get("market_avg_current")
        snapshot.market_avg_initial = market.get("market_avg_initial")
        snapshot.market_avg_variation_since_start = market.get("market_avg_variation_since_start")
        snapshot.competitors = [
            CompetitorSummaryRead(
                id=c["id"],
                name=c.get("name"),
                current_price=c.get("current_price"),
                initial_price=c.get("initial_price"),
                variation_since_start=c.get("variation_since_start"),
                gap_vs_product=c.get("gap_vs_product"),
                gap_vs_product_percent=c.get("gap_vs_product_percent"),
                status=c.get("status"),
                thumbnail_url=c.get("thumbnail_url"),
            )
            for c in competitors
        ]
        detalhe.latest_comparison = snapshot

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
