"""Política de agendamento — funções puras, sem I/O, sem estado global."""

import random
from datetime import datetime, timedelta
from typing import Literal

CheckReason = Literal[
    "success_price_changed",
    "success_price_unchanged",
    "unavailable",
    "error_backoff",
    "rate_limited",
    "lock_busy",
    "unsupported",
    "initial",
]

# Janelas de coleta por nível de estabilidade (minutos)
STABILITY_WINDOWS: dict[str, tuple[int, int]] = {
    "unstable":    (45, 90),
    "stable":      (90, 180),
    "very_stable": (180, 360),
}

# Janela de volatilidade de disponibilidade: mudança recente nas últimas 24h → instável
_AVAILABILITY_VOLATILITY_WINDOW_MINUTES = 1440

# Tolerância para anti-repetição de delay: ±15 % do último valor
_ANTI_REPEAT_TOLERANCE = 0.15


def is_significant_change(old_price: float, new_price: float, threshold_percent: float) -> bool:
    """Retorna True se a variação percentual entre preços atingir o limiar."""
    if old_price == 0:
        return False
    return abs(new_price - old_price) / old_price * 100 >= threshold_percent


def classify_stability(
    last_price_changed_at: datetime | None,
    last_availability_changed_at: datetime | None,
    now: datetime,
) -> str:
    """Classifica o nível de estabilidade do produto com base em tempo.

    Semântica temporal (substitui a anterior counter-based):
    - unstable:    preço alterado há menos de 24h, ou nunca registrado
    - stable:      preço inalterado entre 24h e 48h
    - very_stable: preço inalterado há mais de 48h

    Override: mudança de disponibilidade nas últimas 24h força "unstable"
    independentemente do histórico de preço.
    """
    if last_availability_changed_at is not None:
        age_minutes = (now - last_availability_changed_at).total_seconds() / 60
        if age_minutes < _AVAILABILITY_VOLATILITY_WINDOW_MINUTES:
            return "unstable"

    if last_price_changed_at is None:
        return "unstable"
    elapsed_hours = (now - last_price_changed_at).total_seconds() / 3600
    if elapsed_hours < 24:
        return "unstable"
    if elapsed_hours < 48:
        return "stable"
    return "very_stable"


def window_for_stability(stability_level: str) -> tuple[int, int]:
    """Retorna a janela (min, max) em minutos para o nível de estabilidade."""
    return STABILITY_WINDOWS.get(stability_level, STABILITY_WINDOWS["unstable"])


def pick_delay_in_window(min_minutes: int, max_minutes: int, last_delay: int | None) -> int:
    """Sorteia um delay dentro da janela com anti-repetição de ±15 % sobre o valor anterior."""
    delay = random.randint(min_minutes, max_minutes)
    if last_delay is not None:
        tolerance = last_delay * _ANTI_REPEAT_TOLERANCE
        if abs(delay - last_delay) <= tolerance:
            delay = random.randint(min_minutes, max_minutes)
    return delay


def backoff_delay(consecutive_failures: int, base_minutes: int, max_minutes: int) -> int:
    """Backoff exponencial com teto: base * 2^(failures-1), limitado por max."""
    exponent = max(consecutive_failures - 1, 0)
    return min(base_minutes * (2 ** exponent), max_minutes)


def compute_next_check(
    reason: CheckReason,
    now: datetime,
    stability_level: str,
    last_scheduled_delay_minutes: int | None,
    consecutive_failures: int,
    base_backoff_minutes: int,
    max_backoff_minutes: int,
    rate_limit_min: int,
    rate_limit_max: int,
    lock_busy_min: int,
    lock_busy_max: int,
) -> tuple[datetime | None, int | None]:
    """Calcula (next_check_at, delay_minutes) para cada motivo de coleta.

    Retorna (None, None) exclusivamente para 'unsupported'.
    """
    if reason == "unsupported":
        return None, None

    if reason == "rate_limited":
        delay = pick_delay_in_window(rate_limit_min, rate_limit_max, last_scheduled_delay_minutes)
    elif reason == "lock_busy":
        delay = pick_delay_in_window(lock_busy_min, lock_busy_max, last_scheduled_delay_minutes)
    elif reason == "error_backoff":
        delay = backoff_delay(consecutive_failures, base_backoff_minutes, max_backoff_minutes)
    else:
        win_min, win_max = window_for_stability(stability_level)
        delay = pick_delay_in_window(win_min, win_max, last_scheduled_delay_minutes)

    return now + timedelta(minutes=delay), delay
