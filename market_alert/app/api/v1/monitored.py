"""
Router: produtos monitorados.

Endpoints para cadastrar, consultar, pausar e remover produtos que o sistema
deve acompanhar. O cadastro via POST /scrape dispara a primeira coleta
de preço imediatamente (de forma assíncrona via Celery).

Endpoints:
    POST   /monitored/scrape      → cadastra produto e enfileira coleta
    GET    /monitored/            → lista todos os produtos
    GET    /monitored/{id}        → detalhe com última comparação
    PATCH  /monitored/{id}/pause  → pausa o monitoramento
    PATCH  /monitored/{id}/resume → retoma o monitoramento
    DELETE /monitored/{id}        → remove o produto e todo seu histórico
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.comparison import Comparison
from app.models.monitored_product import MonitoredProduct
from app.schemas.comparison import ComparisonRead
from app.schemas.monitored_product import MonitoredProductCreate, MonitoredProductDetail, MonitoredProductRead

logger = structlog.get_logger()

router = APIRouter(prefix="/monitored", tags=["monitored"])

# Tipo anotado para injeção de dependência da sessão de banco
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/scrape", response_model=MonitoredProductRead, status_code=status.HTTP_202_ACCEPTED)
async def create_and_scrape(body: MonitoredProductCreate, session: Session) -> MonitoredProduct:
    """
    Cadastra um novo produto para monitoramento e inicia a primeira coleta.

    Retorna 202 Accepted imediatamente — a coleta ocorre em background.
    Retorna 409 se a URL já está sendo monitorada.
    """
    url = str(body.url)

    # Verifica se a URL já está cadastrada
    existente = await session.scalar(select(MonitoredProduct).where(MonitoredProduct.url == url))
    if existente:
        raise HTTPException(status_code=409, detail="Esta URL já está sendo monitorada")

    produto = MonitoredProduct(url=url, name=body.name)
    session.add(produto)
    await session.commit()
    await session.refresh(produto)

    # Enfileira a coleta inicial — importação lazy evita circular import com workers
    try:
        from app.workers.tasks import collector_task
        tarefa = collector_task.delay(product_id=str(produto.id))
        logger.info("coleta_enfileirada", produto_id=str(produto.id), tarefa_id=tarefa.id)
    except Exception as exc:
        # Falha na fila não deve impedir o cadastro do produto
        logger.warning("enfileiramento_falhou", produto_id=str(produto.id), erro=str(exc))

    return produto


@router.get("/", response_model=list[MonitoredProductRead])
async def list_monitored(session: Session) -> list[MonitoredProduct]:
    """Lista todos os produtos monitorados, ordenados do mais recente ao mais antigo."""
    resultado = await session.execute(
        select(MonitoredProduct).order_by(MonitoredProduct.created_at.desc())
    )
    return list(resultado.scalars().all())


@router.get("/{product_id}", response_model=MonitoredProductDetail)
async def get_monitored(product_id: uuid.UUID, session: Session) -> MonitoredProductDetail:
    """
    Retorna o detalhe de um produto monitorado, incluindo a última comparação calculada.

    A comparação pode ser None se a primeira coleta ainda não ocorreu.
    """
    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")

    # Busca a comparação mais recente (pode não existir na primeira coleta)
    ultima_comparacao = await session.scalar(
        select(Comparison)
        .where(Comparison.monitored_id == product_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(1)
    )

    detalhe = MonitoredProductDetail.model_validate(produto)
    if ultima_comparacao:
        detalhe.latest_comparison = ComparisonRead.model_validate(ultima_comparacao)
    return detalhe


@router.patch("/{product_id}/pause", response_model=MonitoredProductRead)
async def pause_monitored(product_id: uuid.UUID, session: Session) -> MonitoredProduct:
    """Pausa o monitoramento de um produto. O histórico é preservado."""
    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")
    produto.status = "paused"
    await session.commit()
    await session.refresh(produto)
    return produto


@router.patch("/{product_id}/resume", response_model=MonitoredProductRead)
async def resume_monitored(product_id: uuid.UUID, session: Session) -> MonitoredProduct:
    """Retoma o monitoramento de um produto pausado. Agenda coleta imediata."""
    from datetime import datetime, timezone

    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")

    produto.status = "active"
    # next_check_at = agora → o scheduler vai enfileirar na próxima rodada (≤1 min)
    produto.next_check_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(produto)
    return produto


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitored(product_id: uuid.UUID, session: Session) -> Response:
    """
    Remove um produto monitorado e todo seu histórico (cascade).

    Remove também: concorrentes, price_history, comparações e notification_logs.
    """
    produto = await session.get(MonitoredProduct, product_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")
    await session.delete(produto)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
