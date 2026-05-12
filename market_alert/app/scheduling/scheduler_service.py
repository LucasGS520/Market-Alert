"""Scheduler service: consulta produtos elegíveis, adquire lease durável e enfileira coleta."""

from datetime import datetime, timedelta, timezone

import structlog
from redis import Redis
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.config import settings
from app.products.monitored.monitored_model import MonitoredProduct

logger = structlog.get_logger()

_ELIGIBLE_STATUSES = ("pending", "active", "unavailable", "error")


async def run_scheduler(session: AsyncSession, redis: Redis) -> dict:
    """Consulta produtos elegíveis, adquire lease durável e enfileira coleta.

    Ordenação por next_check_at asc garante justiça temporal (vencidos mais
    antigos têm prioridade). Lease atômico via UPDATE com guarda evita enqueue
    duplicado quando o scheduler executa em janelas sobrepostas.

    Returns:
        dict com total_encontrados, total_enfileirados e skips por motivo.
    """
    agora = datetime.now(timezone.utc)
    lease_expiry = agora + timedelta(seconds=settings.collection_lease_ttl_seconds)

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
    skips: dict[str, int] = {"lease_ativo": 0, "enqueue_falhou": 0}

    for row in candidatos:
        pid = row.id
        pid_str = str(pid)

        # Adquire lease atomicamente: avança somente se lease estiver ausente ou vencido
        lease_result = await session.execute(
            update(MonitoredProduct)
            .where(
                and_(
                    MonitoredProduct.id == pid,
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
            logger.info(
                "scheduler_skip_lease_ativo",
                produto_id=pid_str,
                next_check_at=row.next_check_at.isoformat() if row.next_check_at else None,
            )
            skips["lease_ativo"] += 1
            continue

        try:
            from app.workers.orchestrator import collection_orchestrator_task
            collection_orchestrator_task.delay(product_id=pid_str)
        except Exception as exc:
            # Reverte lease para permitir reenqueue na próxima rodada
            await session.execute(
                update(MonitoredProduct)
                .where(MonitoredProduct.id == pid)
                .values(collection_lease_until=None, last_collection_started_at=None)
            )
            await session.commit()
            logger.warning("scheduler_enqueue_falhou", produto_id=pid_str, erro=str(exc))
            skips["enqueue_falhou"] += 1
            continue

        total_enfileirados += 1
        logger.debug(
            "scheduler_enfileirado",
            produto_id=pid_str,
            status=row.status,
            next_check_at=row.next_check_at.isoformat() if row.next_check_at else None,
            lease_until=lease_expiry.isoformat(),
        )

    return {
        "total_encontrados": total_encontrados,
        "total_enfileirados": total_enfileirados,
        "skips": skips,
    }
