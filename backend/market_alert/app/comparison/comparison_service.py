import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comparison.comparison_model import Comparison
from app.infra.config import settings
from app.products.competitor.competitor_model import Competitor
from app.products.monitored.monitored_model import MonitoredProduct

logger = structlog.get_logger()


def _calcular_status(preco_produto: Decimal, preco_minimo: Decimal) -> str:
    # "competitive": dentro da tolerância aceitável de preço.
    # "attention": acima do limiar competitivo, mas ainda recuperável.
    # "urgent": produto visivelmente mais caro que o mercado.
    if preco_minimo == 0:
        return "competitive"
    pct_acima = float((preco_produto - preco_minimo) / preco_minimo * 100)
    if pct_acima <= settings.status_threshold_competitive:
        return "competitive"
    if pct_acima <= settings.status_threshold_attention:
        return "attention"
    return "urgent"


def _snapshot_identico(anterior: Comparison, novo: dict) -> bool:
    """Retorna True se os indicadores competitivos do snapshot são idênticos.

    Inclui metadados de composição para evitar supressão quando o conjunto
    de concorrentes muda (participants_count, valid/ignored counts, run_status).
    Compara reference_available para detectar mudança de disponibilidade da referência.
    """
    return (
        anterior.status == novo["status"]
        and anterior.ranking == novo["ranking"]
        and Decimal(str(anterior.average_price)) == novo["average_price"]
        and Decimal(str(anterior.min_price)) == novo["min_price"]
        and Decimal(str(anterior.max_price)) == novo["max_price"]
        and (
            (anterior.potential_adjustment is None and novo["potential_adjustment"] is None)
            or (
                anterior.potential_adjustment is not None
                and novo["potential_adjustment"] is not None
                and Decimal(str(anterior.potential_adjustment)) == novo["potential_adjustment"]
            )
        )
        and anterior.participants_count == novo["participants_count"]
        and anterior.valid_competitors_count == novo["valid_competitors_count"]
        and anterior.ignored_competitors_count == novo["ignored_competitors_count"]
        and anterior.run_status == novo["run_status"]
        and getattr(anterior, "reference_available", True) == novo["reference_available"]
    )


async def calculate_comparison(
    session: AsyncSession,
    monitored_id: uuid.UUID,
    run_id: str | None = None,
    run_status: str | None = None,
) -> Comparison | None:
    """Calcula e persiste um snapshot de mercado para o grupo monitorado.

    Aborta apenas quando não há âncora estrutural válida (produto inexistente ou
    em paused/unsupported) ou quando zero ofertas têm preço válido.

    Quando a oferta de referência estiver indisponível (sem preço, inativa ou
    indisponível), o mercado ainda é calculado com os concorrentes válidos;
    ranking, status e potential_adjustment ficam None nesse snapshot.

    Retorna None sem persistir se o snapshot for idêntico ao anterior dentro
    da janela de deduplicação.
    """
    # ── 1. Verificar âncora estrutural ────────────────────────────────────
    produto = await session.get(MonitoredProduct, monitored_id)

    if not produto:
        logger.warning("comparacao_abortada", produto_id=str(monitored_id), razao="produto_nao_encontrado")
        return None

    if produto.status in ("paused", "unsupported"):
        logger.info(
            "comparacao_abortada",
            produto_id=str(monitored_id),
            razao="produto_status_inativo",
            status=produto.status,
        )
        return None

    # ── 2. Determinar elegibilidade da oferta de referência ───────────────
    reference_available = (
        produto.status == "active"
        and produto.is_available is True
        and produto.current_price is not None
    )

    if not reference_available:
        logger.info(
            "referencia_indisponivel",
            produto_id=str(monitored_id),
            status=produto.status,
            is_available=produto.is_available,
            current_price=str(produto.current_price) if produto.current_price is not None else None,
        )

    # ── 3. Buscar e classificar concorrentes ──────────────────────────────
    resultado = await session.execute(
        select(Competitor).where(Competitor.monitored_id == monitored_id)
    )
    todos_concorrentes = list(resultado.scalars().all())

    elegíveis: list[Competitor] = []
    ignorados: list[Competitor] = []

    for c in todos_concorrentes:
        if (
            c.status == "active"
            and c.is_available is True
            and c.current_price is not None
            and Decimal(str(c.current_price)) > 0
        ):
            elegíveis.append(c)
        else:
            ignorados.append(c)
            logger.debug(
                "concorrente_ignorado",
                concorrente_id=str(c.id),
                status=c.status,
                is_available=c.is_available,
                current_price=str(c.current_price) if c.current_price is not None else None,
            )

    valid_competitors_count = len(elegíveis)
    ignored_competitors_count = len(ignorados)

    # ── 4. Verificar se há ofertas suficientes para calcular o mercado ────
    if not reference_available and valid_competitors_count == 0:
        logger.warning("comparacao_abortada", produto_id=str(monitored_id), razao="sem_ofertas_validas")
        return None

    # run_status: sem concorrentes válidos substitui qualquer estado da rodada
    if valid_competitors_count == 0:
        run_status_final = "no_competitors"
    elif run_status is not None:
        run_status_final = run_status
    else:
        run_status_final = "manual"

    # ── 5. Montar entradas para cálculo de mercado ────────────────────────
    # Tuplas (preco, indice_original) garantem tie-breaking determinístico.
    # Índice 0 reservado para a oferta de referência.
    entradas: list[tuple[Decimal, int]] = []
    preco_referencia: Decimal | None = None

    if reference_available:
        preco_referencia = Decimal(str(produto.current_price))
        entradas.append((preco_referencia, 0))

    for i, c in enumerate(elegíveis, 1):
        entradas.append((Decimal(str(c.current_price)), i))

    entradas_ordenadas = sorted(entradas, key=lambda x: (x[0], x[1]))
    todos_precos = [p for p, _ in entradas_ordenadas]

    preco_medio = sum(todos_precos) / len(todos_precos)
    preco_minimo = todos_precos[0]
    preco_maximo = todos_precos[-1]
    participants_count = len(entradas)

    # ── 6. Calcular posição da referência (somente se disponível) ─────────
    if reference_available:
        ranking = next(i + 1 for i, (_, idx) in enumerate(entradas_ordenadas) if idx == 0)
        status = _calcular_status(preco_referencia, preco_minimo)
        ajuste_potencial = preco_referencia - preco_minimo if preco_referencia > preco_minimo else None
    else:
        ranking = None
        status = None
        ajuste_potencial = None

    novo_snapshot = {
        "status": status,
        "ranking": ranking,
        "average_price": preco_medio,
        "min_price": preco_minimo,
        "max_price": preco_maximo,
        "potential_adjustment": ajuste_potencial,
        "participants_count": participants_count,
        "valid_competitors_count": valid_competitors_count,
        "ignored_competitors_count": ignored_competitors_count,
        "run_status": run_status_final,
        "reference_available": reference_available,
    }

    # ── 4. Deduplicação ───────────────────────────────────────────────────
    # Snapshot repetido dentro da janela não é persistido para não inflar o histórico
    # nem gerar notificações redundantes quando o preço está estável.
    anterior = await session.scalar(
        select(Comparison)
        .where(Comparison.monitored_id == monitored_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(1)
    )

    if anterior is not None and _snapshot_identico(anterior, novo_snapshot):
        janela = timedelta(minutes=settings.comparison_dedup_window_minutes)
        agora = datetime.now(timezone.utc)
        calculado_em = anterior.calculated_at
        if calculado_em.tzinfo is None:
            calculado_em = calculado_em.replace(tzinfo=timezone.utc)
        if agora - calculado_em < janela:
            logger.info(
                "comparacao_deduplicada",
                produto_id=str(monitored_id),
                anterior_id=str(anterior.id),
                run_id=run_id,
                run_status=run_status_final,
            )
            return None

    # ── 5. Persistir snapshot ─────────────────────────────────────────────
    comparacao = Comparison(
        monitored_id=monitored_id,
        status=status,
        ranking=ranking,
        average_price=preco_medio,
        min_price=preco_minimo,
        max_price=preco_maximo,
        potential_adjustment=ajuste_potencial,
        run_id=run_id,
        run_status=run_status_final,
        product_price=preco_referencia,
        participants_count=participants_count,
        valid_competitors_count=valid_competitors_count,
        ignored_competitors_count=ignored_competitors_count,
        reference_available=reference_available,
    )
    session.add(comparacao)
    await session.commit()
    await session.refresh(comparacao)

    logger.info(
        "comparacao_calculada",
        produto_id=str(monitored_id),
        reference_available=reference_available,
        status=status,
        ranking=ranking,
        preco_minimo=str(preco_minimo),
        preco_referencia=str(preco_referencia) if preco_referencia is not None else None,
        participants_count=participants_count,
        valid_competitors_count=valid_competitors_count,
        ignored_competitors_count=ignored_competitors_count,
        run_id=run_id,
        run_status=run_status_final,
    )
    return comparacao


async def get_latest_comparison(
    session: AsyncSession,
    monitored_id: uuid.UUID,
) -> Comparison | None:
    return await session.scalar(
        select(Comparison)
        .where(Comparison.monitored_id == monitored_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(1)
    )


async def get_comparison_history(
    session: AsyncSession,
    monitored_id: uuid.UUID,
    limit: int = 100,
) -> list[Comparison]:
    resultado = await session.execute(
        select(Comparison)
        .where(Comparison.monitored_id == monitored_id)
        .order_by(Comparison.calculated_at.desc())
        .limit(limit)
    )
    return list(resultado.scalars().all())
