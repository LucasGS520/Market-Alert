import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comparison.comparison_model import Comparison
from app.comparison.comparison_service import get_comparison_history
from app.infra.config import settings
from app.products.competitor.competitor_model import Competitor
from app.products.price_history.price_history_service import get_product_price_history
from app.products.price_history.price_model import PriceHistory


def _variacao_24h(
    precos_asc: list[tuple[Decimal, datetime]],
) -> float | None:
    """Variação percentual do preço atual em relação às últimas 24h.

    Replica a lógica de enrichWithHistory() do frontend: se houver >= 2 registros
    dentro das últimas 24h, compara o mais antigo deles ao atual; caso contrário,
    usa o penúltimo registro geral como base.
    """
    if not precos_asc:
        return None

    agora = datetime.now(timezone.utc)
    corte = agora - timedelta(hours=24)

    preco_atual = precos_asc[-1][0]

    recentes = [
        (p, ts)
        for p, ts in precos_asc
        if (ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts) >= corte
    ]

    if len(recentes) >= 2:
        base = recentes[0][0]
    elif len(precos_asc) >= 2:
        base = precos_asc[-2][0]
    else:
        return None

    if base == 0:
        return None

    return float((preco_atual - base) / base * 100)


async def compute_reference_indicators(
    session: AsyncSession,
    monitored_id: uuid.UUID,
) -> dict:
    """Indicadores temporais da oferta de referência derivados do PriceHistory.

    Retorna variation_24h, variation_all, previous_price e sparkline (últimos 30 pontos).
    Todos os campos ficam None/[] quando não há histórico suficiente.
    """
    registros = await get_product_price_history(session, monitored_id, limit=200)

    if not registros:
        return {"variation_24h": None, "variation_all": None, "previous_price": None, "sparkline": []}

    # Registros chegam em DESC — inverter para ordem cronológica
    precos_asc: list[tuple[Decimal, datetime]] = [
        (Decimal(str(r.price)), r.collected_at)
        for r in reversed(registros)
        if r.price is not None and r.is_available
    ]

    if not precos_asc:
        return {"variation_24h": None, "variation_all": None, "previous_price": None, "sparkline": []}

    preco_atual = precos_asc[-1][0]
    primeiro = precos_asc[0][0]

    variation_24h = _variacao_24h(precos_asc)
    variation_all = float((preco_atual - primeiro) / primeiro * 100) if primeiro > 0 else None
    previous_price = precos_asc[-2][0] if len(precos_asc) >= 2 else None
    sparkline = [float(p) for p, _ in precos_asc[-30:]]

    return {
        "variation_24h": variation_24h,
        "variation_all": variation_all,
        "previous_price": previous_price,
        "sparkline": sparkline,
    }


async def batch_reference_indicators(
    session: AsyncSession,
    monitored_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict]:
    """Indicadores de referência para múltiplos produtos em 1 query (elimina N+1 na listagem)."""
    if not monitored_ids:
        return {}

    resultado = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.monitored_id.in_(monitored_ids))
        .where(PriceHistory.is_available == True)  # noqa: E712
        .order_by(PriceHistory.monitored_id, PriceHistory.collected_at.desc())
    )
    todos_registros = list(resultado.scalars().all())

    agrupados: dict = defaultdict(list)
    for r in todos_registros:
        if len(agrupados[r.monitored_id]) < 200:
            agrupados[r.monitored_id].append(r)

    _empty: dict = {"variation_24h": None, "variation_all": None, "previous_price": None, "sparkline": []}
    out: dict[uuid.UUID, dict] = {}

    for mid in monitored_ids:
        recs = agrupados.get(mid, [])
        if not recs:
            out[mid] = _empty.copy()
            continue

        # recs chegam em DESC por collected_at — inverter para ordem cronológica
        precos_asc: list[tuple[Decimal, datetime]] = [
            (Decimal(str(r.price)), r.collected_at)
            for r in reversed(recs)
        ]

        if not precos_asc:
            out[mid] = _empty.copy()
            continue

        preco_atual = precos_asc[-1][0]
        primeiro = precos_asc[0][0]

        out[mid] = {
            "variation_24h": _variacao_24h(precos_asc),
            "variation_all": float((preco_atual - primeiro) / primeiro * 100) if primeiro > 0 else None,
            "previous_price": precos_asc[-2][0] if len(precos_asc) >= 2 else None,
            "sparkline": [float(p) for p, _ in precos_asc[-30:]],
        }

    return out


async def batch_market_variation_24h(
    session: AsyncSession,
    monitored_ids: list[uuid.UUID],
) -> dict[uuid.UUID, float | None]:
    """Variação do min_price de mercado (24h) para múltiplos produtos em 1 query."""
    if not monitored_ids:
        return {}

    agora = datetime.now(timezone.utc)
    corte_busca = agora - timedelta(hours=48)
    corte_24h = agora - timedelta(hours=24)

    resultado = await session.execute(
        select(Comparison)
        .where(Comparison.monitored_id.in_(monitored_ids))
        .where(Comparison.calculated_at >= corte_busca)
        .order_by(Comparison.monitored_id, Comparison.calculated_at.desc())
    )
    todos = list(resultado.scalars().all())

    agrupados: dict = defaultdict(list)
    for s in todos:
        if len(agrupados[s.monitored_id]) < 50:
            agrupados[s.monitored_id].append(s)

    out: dict[uuid.UUID, float | None] = {}

    for mid in monitored_ids:
        snapshots = agrupados.get(mid, [])
        if len(snapshots) < 2:
            out[mid] = None
            continue

        snapshot_atual = snapshots[0]
        snapshot_24h = None
        for s in snapshots[1:]:
            ts = s.calculated_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts <= corte_24h:
                snapshot_24h = s
                break

        if snapshot_24h is None:
            out[mid] = None
            continue

        min_atual = Decimal(str(snapshot_atual.min_price))
        min_base = Decimal(str(snapshot_24h.min_price))
        out[mid] = float((min_atual - min_base) / min_base * 100) if min_base != 0 else None

    return out


async def compute_competitor_summaries(
    session: AsyncSession,
    monitored_id: uuid.UUID,
    reference_price: Decimal | None = None,
) -> list[dict]:
    """Resumo de cada concorrente com variação desde o início e gap competitivo.

    2 queries fixas independente do número de concorrentes.
    """
    resultado = await session.execute(
        select(Competitor).where(Competitor.monitored_id == monitored_id)
    )
    concorrentes = list(resultado.scalars().all())

    if not concorrentes:
        return []

    competitor_ids = [c.id for c in concorrentes]

    historicos_res = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.competitor_id.in_(competitor_ids))
        .order_by(PriceHistory.competitor_id, PriceHistory.collected_at.desc())
    )
    todos_historicos = list(historicos_res.scalars().all())

    historicos_por_competidor: dict = defaultdict(list)
    for r in todos_historicos:
        if len(historicos_por_competidor[r.competitor_id]) < 100:
            historicos_por_competidor[r.competitor_id].append(r)

    summaries = []
    for c in concorrentes:
        registros = historicos_por_competidor.get(c.id, [])

        precos_asc: list[tuple[Decimal, datetime]] = [
            (Decimal(str(r.price)), r.collected_at)
            for r in reversed(registros)
            if r.price is not None and r.is_available
        ]

        initial_price: Decimal | None = precos_asc[0][0] if precos_asc else None
        current_price: Decimal | None = (
            Decimal(str(c.current_price)) if c.current_price is not None else None
        )

        variation_since_start: float | None = None
        if initial_price is not None and current_price is not None and len(precos_asc) >= 2 and initial_price > 0:
            variation_since_start = float((current_price - initial_price) / initial_price * 100)

        gap_vs_product: Decimal | None = None
        gap_vs_product_percent: float | None = None
        if current_price is not None and reference_price is not None and reference_price > 0:
            gap_vs_product = current_price - reference_price
            gap_vs_product_percent = float(gap_vs_product / reference_price * 100)

        thumbnail_url = next(
            (r.thumbnail_url for r in registros if r.thumbnail_url),
            None,
        )

        summaries.append({
            "id": c.id,
            "name": c.name,
            "current_price": current_price,
            "initial_price": initial_price,
            "variation_since_start": variation_since_start,
            "gap_vs_product": gap_vs_product,
            "gap_vs_product_percent": gap_vs_product_percent,
            "status": c.status,
            "thumbnail_url": thumbnail_url,
        })

    return summaries


async def compute_market_variation_24h(
    session: AsyncSession,
    monitored_id: uuid.UUID,
) -> float | None:
    """Variação percentual do preço mínimo de mercado nas últimas 24h.

    Compara o min_price do snapshot mais recente com o snapshot mais próximo de 24h atrás.
    Retorna None quando não há snapshots suficientes ou o snapshot de referência é zero.
    """
    historico = await get_comparison_history(session, monitored_id, limit=50)

    if len(historico) < 2:
        return None

    agora = datetime.now(timezone.utc)
    corte = agora - timedelta(hours=24)

    # historico vem DESC — índice 0 é o mais recente
    snapshot_atual = historico[0]

    snapshot_24h = None
    for s in historico[1:]:
        ts = s.calculated_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts <= corte:
            snapshot_24h = s
            break

    if snapshot_24h is None:
        return None

    min_atual = Decimal(str(snapshot_atual.min_price))
    min_base = Decimal(str(snapshot_24h.min_price))

    if min_base == 0:
        return None

    return float((min_atual - min_base) / min_base * 100)


# ── Funções para contrato de detalhe (séries temporais + indicadores "desde o início") ──


def _trend_direction(variation: float | None) -> str:
    threshold = float(settings.price_stability_change_threshold_percent)
    if variation is None:
        return "insufficient_data"
    if variation >= threshold:
        return "up"
    if variation <= -threshold:
        return "down"
    return "flat"


async def compute_reference_series(
    session: AsyncSession,
    monitored_id: uuid.UUID,
) -> dict:
    """Série temporal e indicadores 'desde o início' da oferta de referência.

    Retorna product_series (ASC), initial_price, previous_price,
    variation_since_start, variation_since_previous e trend_since_start.
    """
    registros = await get_product_price_history(session, monitored_id, limit=200)

    empty: dict = {
        "product_series": [],
        "initial_price": None,
        "previous_price": None,
        "variation_since_start": None,
        "variation_since_previous": None,
        "trend_since_start": "insufficient_data",
    }

    if not registros:
        return empty

    precos_asc: list[tuple[Decimal, datetime]] = [
        (Decimal(str(r.price)), r.collected_at)
        for r in reversed(registros)
        if r.price is not None and r.is_available
    ]

    if not precos_asc:
        return empty

    product_series = [{"t": ts, "v": float(p)} for p, ts in precos_asc]

    initial_price = precos_asc[0][0]
    current_price = precos_asc[-1][0]
    previous_price = precos_asc[-2][0] if len(precos_asc) >= 2 else None

    variation_since_start: float | None = None
    if len(precos_asc) >= 2 and initial_price > 0:
        variation_since_start = float((current_price - initial_price) / initial_price * 100)

    variation_since_previous: float | None = None
    if previous_price is not None and previous_price > 0:
        variation_since_previous = float((current_price - previous_price) / previous_price * 100)

    return {
        "product_series": product_series,
        "initial_price": initial_price,
        "previous_price": previous_price,
        "variation_since_start": variation_since_start,
        "variation_since_previous": variation_since_previous,
        "trend_since_start": _trend_direction(variation_since_start),
    }


async def compute_market_series(
    session: AsyncSession,
    monitored_id: uuid.UUID,
) -> dict:
    """Séries temporais e indicadores 'desde o início' do mercado monitorado.

    Usa histórico de Comparison (min_price, average_price) em ordem ASC.
    """
    historico = await get_comparison_history(session, monitored_id, limit=200)

    empty: dict = {
        "market_min_series": [],
        "market_avg_series": [],
        "market_min_current": None,
        "market_min_initial": None,
        "market_min_variation_since_start": None,
        "market_avg_current": None,
        "market_avg_initial": None,
        "market_avg_variation_since_start": None,
    }

    if not historico:
        return empty

    # historico vem DESC — inverter para ordem cronológica
    snapshots_asc = list(reversed(historico))

    market_min_series = [
        {"t": s.calculated_at, "v": float(s.min_price)}
        for s in snapshots_asc
    ]
    market_avg_series = [
        {"t": s.calculated_at, "v": float(s.average_price)}
        for s in snapshots_asc
    ]

    min_initial = Decimal(str(snapshots_asc[0].min_price))
    min_current = Decimal(str(snapshots_asc[-1].min_price))
    avg_initial = Decimal(str(snapshots_asc[0].average_price))
    avg_current = Decimal(str(snapshots_asc[-1].average_price))

    min_variation: float | None = None
    if len(snapshots_asc) >= 2 and min_initial > 0:
        min_variation = float((min_current - min_initial) / min_initial * 100)

    avg_variation: float | None = None
    if len(snapshots_asc) >= 2 and avg_initial > 0:
        avg_variation = float((avg_current - avg_initial) / avg_initial * 100)

    return {
        "market_min_series": market_min_series,
        "market_avg_series": market_avg_series,
        "market_min_current": min_current,
        "market_min_initial": min_initial,
        "market_min_variation_since_start": min_variation,
        "market_avg_current": avg_current,
        "market_avg_initial": avg_initial,
        "market_avg_variation_since_start": avg_variation,
    }
