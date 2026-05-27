"""
Lógica de decisão de alerta — separada da infraestrutura Celery.

Recebe primitivos (sem modelos SQLAlchemy, sem I/O) e devolve decisões
que tasks.py usa para enfileirar notification_task.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal


def _ranking_relevante(rank_old: int | None, rank_new: int | None, status_mudou: bool) -> bool:
    """Ranking é relevante quando: ganhou/perdeu 1ª posição, diferença >=2, ou status também mudou."""
    if rank_old is None or rank_new is None:
        return False
    if 1 in (rank_old, rank_new):
        return True
    if abs(rank_new - rank_old) >= 2:
        return True
    return status_mudou


_STATUS_RANK = {"competitive": 0, "attention": 1, "urgent": 2}

# Prioridade: ameaça > oportunidade > mercado > disponibilidade da referência.
# Sinais de preço da referência (reference_price_drop/rise) são apenas contexto em
# reason_codes e não disparam alerta por conta própria.
_THREAT_SIGNALS      = frozenset({"ranking_worsened", "status_worsened", "gap_increased"})
_OPPORTUNITY_SIGNALS = frozenset({"ranking_improved", "status_improved", "market_became_less_aggressive", "gap_decreased"})
_MARKET_SIGNALS      = frozenset({"market_min_changed", "market_became_more_aggressive"})
_REFERENCE_SIGNALS   = frozenset({"reference_became_unavailable", "reference_became_available"})


def _calcular_gap(price: Decimal | None, min_price: Decimal | None) -> float | None:
    """Gap percentual entre o preço da referência e o mínimo de mercado."""
    if price and min_price and float(min_price) > 0:
        return float((price - min_price) / min_price * 100)
    return None


class AlertDecision:
    __slots__ = ("alert_type", "reason_codes")

    def __init__(self, alert_type: str, reason_codes: list[str]) -> None:
        self.alert_type = alert_type
        self.reason_codes = reason_codes


def build_signals(
    preco_anterior: Decimal | None,
    preco_novo: Decimal | None,
    status_anterior: str | None,
    status_novo: str | None,
    rank_old: int | None,
    rank_new: int | None,
    min_ant: Decimal | None,
    min_nov: Decimal | None,
    ref_ant: bool | None,
    ref_nov: bool | None,
    delta_percent: float,
) -> list[str]:
    """Constrói lista de sinais técnicos a partir de dois snapshots de comparação.

    Recebe apenas primitivos — sem acesso a banco, sem I/O.
    ref_ant=None indica que não há snapshot anterior (sem sinal de disponibilidade gerado).
    """
    sinais: list[str] = []

    # Variação de preço da referência (contexto — não dispara alerta sozinho)
    if preco_anterior is not None and preco_novo is not None and preco_anterior > 0:
        variacao_pct = float(abs(preco_novo - preco_anterior) / preco_anterior * 100)
        if variacao_pct >= delta_percent:
            sinais.append("reference_price_drop" if preco_novo < preco_anterior else "reference_price_rise")

    # Mudança direcional de status competitivo
    if (
        status_anterior is not None
        and status_novo is not None
        and status_novo != status_anterior
    ):
        rank_status_ant = _STATUS_RANK.get(status_anterior, 0)
        rank_status_nov = _STATUS_RANK.get(status_novo, 0)
        sinais.append("status_worsened" if rank_status_nov > rank_status_ant else "status_improved")

    # Mudança direcional de ranking (apenas se relevante)
    status_mudou = "status_worsened" in sinais or "status_improved" in sinais
    if rank_old != rank_new and _ranking_relevante(rank_old, rank_new, status_mudou):
        # _ranking_relevante garante que ambos não são None
        sinais.append("ranking_worsened" if rank_new > rank_old else "ranking_improved")  # type: ignore[operator]

    # Variação do mínimo de mercado (direcional)
    if min_ant and min_nov and float(min_ant) > 0:
        variacao_pct_m = float(abs(float(min_nov) - float(min_ant)) / float(min_ant) * 100)
        if variacao_pct_m >= delta_percent:
            sinais.append("market_min_changed")
            sinais.append(
                "market_became_more_aggressive" if float(min_nov) < float(min_ant)
                else "market_became_less_aggressive"
            )

    # Variação do gap referência vs mínimo de mercado
    gap_ant = _calcular_gap(preco_anterior, min_ant)
    gap_nov = _calcular_gap(preco_novo, min_nov)
    if gap_ant is not None and gap_nov is not None:
        delta_gap = gap_nov - gap_ant
        if abs(delta_gap) >= delta_percent:
            sinais.append("gap_increased" if delta_gap > 0 else "gap_decreased")

    # Mudança de disponibilidade da oferta de referência
    # ref_ant=None significa que não há snapshot anterior — nenhum sinal gerado
    if ref_ant is not None and ref_ant != ref_nov:
        sinais.append("reference_became_available" if ref_nov else "reference_became_unavailable")

    return sinais


def decide_alert(sinais: list[str]) -> AlertDecision | None:
    """N sinais técnicos → 1 decisão de alerta público (ou None para não notificar).

    Hierarquia: competitive_threat > competitive_opportunity > market_movement >
    reference_availability. Sinais de preço da referência são apenas contexto.
    """
    if not sinais:
        return None
    sinal_set = set(sinais)
    if sinal_set & _THREAT_SIGNALS:
        return AlertDecision("competitive_threat_alert", sinais)
    if sinal_set & _OPPORTUNITY_SIGNALS:
        return AlertDecision("competitive_opportunity_alert", sinais)
    if sinal_set & _MARKET_SIGNALS:
        return AlertDecision("market_movement_alert", sinais)
    if sinal_set & _REFERENCE_SIGNALS:
        return AlertDecision("reference_availability_alert", sinais)
    return None


@dataclass(slots=True)
class CompetitorSignal:
    competitor_id: uuid.UUID
    signal_type: str
    details: dict = field(default_factory=dict)


def build_competitor_signals(
    competitors_prev_prices: dict[str, Decimal | None],
    competitors_curr_prices: dict[str, Decimal | None],
    competitors_prev_avail: dict[str, bool | None],
    competitors_curr_avail: dict[str, bool | None],
    delta_percent: float,
) -> list[CompetitorSignal]:
    """Gera sinais por concorrente com base em variação de preço e mudança de disponibilidade.

    Chaves dos dicts são competitor_id como string.
    Retorna um CompetitorSignal por concorrente que cruzou o threshold.
    """
    signals: list[CompetitorSignal] = []
    all_ids = set(competitors_curr_prices) | set(competitors_prev_prices)

    for cid_str in all_ids:
        cid = uuid.UUID(cid_str)
        prev_price = competitors_prev_prices.get(cid_str)
        curr_price = competitors_curr_prices.get(cid_str)
        prev_avail = competitors_prev_avail.get(cid_str)
        curr_avail = competitors_curr_avail.get(cid_str)

        if curr_price is not None and prev_price is not None and prev_price > 0:
            variacao = float(abs(curr_price - prev_price) / prev_price * 100)
            if variacao >= delta_percent:
                signals.append(CompetitorSignal(
                    competitor_id=cid,
                    signal_type="price_movement",
                    details={
                        "old_price": float(prev_price),
                        "new_price": float(curr_price),
                        "change_pct": round(variacao, 2),
                    },
                ))

        if prev_avail is not None and curr_avail is not None and prev_avail != curr_avail:
            signals.append(CompetitorSignal(
                competitor_id=cid,
                signal_type="availability_change",
                details={"available": curr_avail},
            ))

    return signals
