"""
Router: concorrentes de produtos monitorados.

Endpoints para cadastrar e remover URLs de concorrentes associados a um produto
monitorado. O cadastro dispara uma coleta imediata do preço do concorrente.

Regras de negócio aplicadas aqui:
    - Máximo de 5 concorrentes por produto
    - URL do concorrente não pode ser a mesma do produto monitorado
    - A mesma URL não pode ser cadastrada duas vezes no mesmo produto

Endpoints:
    POST   /competitors/scrape   → cadastra concorrente e enfileira coleta
    GET    /competitors/         → lista concorrentes de um produto
    DELETE /competitors/{id}     → remove concorrente e recalcula comparação
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.competitor import Competitor
from app.models.monitored_product import MonitoredProduct
from app.schemas.competitor import CompetitorCreate, CompetitorRead

logger = structlog.get_logger()

router = APIRouter(prefix="/competitors", tags=["competitors"])

Session = Annotated[AsyncSession, Depends(get_session)]

# Limite máximo de concorrentes por produto monitorado
MAX_CONCORRENTES = 5


@router.post("/scrape", response_model=CompetitorRead, status_code=status.HTTP_202_ACCEPTED)
async def add_competitor(body: CompetitorCreate, session: Session) -> Competitor:
    """
    Cadastra um concorrente para um produto monitorado e inicia coleta imediata.

    Valida: produto existe, não é auto-referência, limite não atingido, URL única.
    Retorna 202 Accepted — a coleta ocorre em background.
    """
    url = str(body.url)

    # Produto deve existir
    produto = await session.get(MonitoredProduct, body.monitored_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto monitorado não encontrado")

    # Não permitir que o concorrente seja o próprio produto
    if url == produto.url:
        raise HTTPException(
            status_code=422,
            detail="A URL do concorrente não pode ser igual à URL do produto monitorado"
        )

    # Verificar limite de concorrentes
    total = await session.scalar(
        select(func.count()).where(Competitor.monitored_id == body.monitored_id)
    )
    if total >= MAX_CONCORRENTES:
        raise HTTPException(
            status_code=422,
            detail=f"Máximo de {MAX_CONCORRENTES} concorrentes por produto atingido"
        )

    # Verificar duplicata
    existente = await session.scalar(
        select(Competitor).where(
            Competitor.monitored_id == body.monitored_id,
            Competitor.url == url,
        )
    )
    if existente:
        raise HTTPException(status_code=409, detail="Este URL já é um concorrente deste produto")

    concorrente = Competitor(monitored_id=body.monitored_id, url=url, name=body.name)
    session.add(concorrente)
    await session.commit()
    await session.refresh(concorrente)

    # Enfileira coleta imediata do concorrente
    try:
        from app.workers.tasks import collector_task
        tarefa = collector_task.delay(competitor_id=str(concorrente.id))
        logger.info("coleta_concorrente_enfileirada", concorrente_id=str(concorrente.id), tarefa_id=tarefa.id)
    except Exception as exc:
        logger.warning("enfileiramento_falhou", concorrente_id=str(concorrente.id), erro=str(exc))

    return concorrente


@router.get("/", response_model=list[CompetitorRead])
async def list_competitors(monitored_id: uuid.UUID, session: Session) -> list[Competitor]:
    """Lista todos os concorrentes de um produto monitorado, em ordem de cadastro."""
    resultado = await session.execute(
        select(Competitor)
        .where(Competitor.monitored_id == monitored_id)
        .order_by(Competitor.created_at)
    )
    return list(resultado.scalars().all())


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(competitor_id: uuid.UUID, session: Session) -> Response:
    """
    Remove um concorrente e dispara recálculo da comparação do produto principal.

    O recálculo garante que o ranking/status reflita a remoção imediatamente.
    """
    concorrente = await session.get(Competitor, competitor_id)
    if not concorrente:
        raise HTTPException(status_code=404, detail="Concorrente não encontrado")

    monitored_id = concorrente.monitored_id
    await session.delete(concorrente)
    await session.commit()

    # Recalcula a comparação sem o concorrente removido
    try:
        from app.workers.tasks import comparison_task
        comparison_task.delay(monitored_id=str(monitored_id))
    except Exception as exc:
        logger.warning("recalculo_falhou", monitored_id=str(monitored_id), erro=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
