"""Scheduler service: consulta produtos elegíveis, adquire lease durável e enfileira coleta."""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from redis import Redis
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.config import settings
from app.products.monitored.monitored_model import MonitoredProduct

logger = structlog.get_logger()

_ELIGIBLE_STATUSES = ("pending", "active", "unavailable", "error")


async def enqueue_with_lease(session: AsyncSession, product_id: uuid.UUID) -> str | None:
    """Adquire lease atômico e enfileira coleta para um produto.

    Ponto único de enqueue usado pela API (criação) e pelo scheduler, garantindo
    que ambos passem pelo mesmo controle de lease e não gerem enqueue duplicado.

    Returns:
        task_id (str) se enfileirado, None se lease já ativo.
    """
    agora = datetime.now(timezone.utc)
    lease_expiry = agora + timedelta(seconds=settings.collection_lease_ttl_seconds)

    lease_result = await session.execute(
        update(MonitoredProduct)
        .where(
            and_(
                MonitoredProduct.id == product_id,
                or_(
                    MonitoredProduct.collection_lease_until.is_(None),
                    MonitoredProduct.collection_lease_until <= agora,
                ),
            )
        )
        .values(
            collection_lease_until=lease_expiry,
            last_collection_started_at=agora,
        )
    )
    await session.commit()

    if lease_result.rowcount == 0:
        logger.debug("enqueue_pulado_lease_ativo", produto_id=str(product_id))
        return None

    try:
        from app.workers.orchestrator import collection_orchestrator_task
        tarefa = collection_orchestrator_task.delay(product_id=str(product_id))
        logger.info("coleta_enfileirada", produto_id=str(product_id), tarefa_id=tarefa.id)
        return tarefa.id
    except Exception as exc:
        # Reverte lease para permitir reenqueue na próxima rodada
        await session.execute(
            update(MonitoredProduct)
            .where(MonitoredProduct.id == product_id)
            .values(collection_lease_until=None, last_collection_started_at=None)
        )
        await session.commit()
        logger.warning("enqueue_falhou", produto_id=str(product_id), erro=str(exc))
        return None


async def run_scheduler(session: AsyncSession, redis: Redis) -> dict:
    """Consulta produtos elegíveis, adquire lease durável e enfileira coleta.

    Ordenação por next_check_at asc garante justiça temporal (vencidos mais
    antigos têm prioridade). Lease atômico via UPDATE com guarda evita enqueue
    duplicado quando o scheduler executa em janelas sobrepostas.

    Returns:
        dict com total_encontrados, total_enfileirados e skips por motivo.
    """
    agora = datetime.now(timezone.utc)

    # Seleciona apenas os campos necessários, ordenado por prioridade temporal
    id_result = await session.execute(
        select(MonitoredProduct.id, MonitoredProduct.status, MonitoredProduct.next_check_at)
        .where(
            and_(
                MonitoredProduct.status.in_(_ELIGIBLE_STATUSES),
                MonitoredProduct.next_check_at.isnot(None),
                MonitoredProduct.next_check_at <= agora,
            )
        )
        .order_by(MonitoredProduct.next_check_at.asc())
        .limit(settings.scheduler_batch_size)
    )
    candidatos = id_result.all()

    total_encontrados = len(candidatos)
    total_enfileirados = 0
    skips: dict[str, int] = {"lease_ativo": 0}

    for row in candidatos:
        pid = row.id
        pid_str = str(pid)

        task_id = await enqueue_with_lease(session, pid)

        if task_id is None:
            logger.info(
                "scheduler_skip_lease_ativo",
                produto_id=pid_str,
                next_check_at=row.next_check_at.isoformat() if row.next_check_at else None,
            )
            skips["lease_ativo"] += 1
            continue

        total_enfileirados += 1
        logger.debug(
            "scheduler_enfileirado",
            produto_id=pid_str,
            status=row.status,
            next_check_at=row.next_check_at.isoformat() if row.next_check_at else None,
            tarefa_id=task_id,
        )

    return {
        "total_encontrados": total_encontrados,
        "total_enfileirados": total_enfileirados,
        "skips": skips,
    }
