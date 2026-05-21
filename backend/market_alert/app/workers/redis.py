import json
import uuid
from datetime import datetime, timezone

import structlog
from redis import Redis

from app.infra.config import settings

logger = structlog.get_logger()

_LOCK_TTL = 60
# Libera o lock apenas se o token ainda corresponde ao adquirente original.
# Evita que uma task antiga apague o lock de outra task após expiração.
_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


# ── Locks distribuídos ─────────────────────────────────────────────────────────

def acquire_lock(redis: Redis, key: str, timeout: int = _LOCK_TTL) -> str | None:
    """Adquire lock e retorna token único, ou None se já ocupado."""
    token = str(uuid.uuid4())
    acquired = redis.set(key, token, nx=True, ex=timeout)
    return token if acquired else None


def release_lock(redis: Redis, key: str, token: str) -> None:
    """Libera lock somente se o token ainda corresponde. Seguro contra expiração."""
    released = redis.eval(_RELEASE_SCRIPT, 1, key, token)
    if not released:
        logger.warning("lock_release_ignorado", key=key, motivo="token_divergente_ou_expirado")


# ── Cooldown de notificações ───────────────────────────────────────────────────
# Granularidade: produto + tipo de evento (+ concorrente para eventos tier 2).
# Cooldown de um evento não bloqueia outros eventos do mesmo produto.

def notification_cooldown_key(
    monitored_id: uuid.UUID,
    event_type: str,
    competitor_id: uuid.UUID | None = None,
) -> str:
    if competitor_id:
        return f"cooldown:notify:{monitored_id}:{event_type}:{competitor_id}"
    return f"cooldown:notify:{monitored_id}:{event_type}"


def is_in_cooldown(
    redis: Redis,
    monitored_id: uuid.UUID,
    event_type: str,
    competitor_id: uuid.UUID | None = None,
) -> bool:
    return bool(redis.exists(notification_cooldown_key(monitored_id, event_type, competitor_id)))


def set_cooldown(
    redis: Redis,
    monitored_id: uuid.UUID,
    event_type: str,
    ttl_minutes: int | None = None,
    competitor_id: uuid.UUID | None = None,
) -> None:
    ttl = (ttl_minutes or settings.notification_cooldown_minutes) * 60
    redis.set(notification_cooldown_key(monitored_id, event_type, competitor_id), "1", ex=ttl)


# ── Tentativas de coleta (auditoria lightweight) ───────────────────────────────

_COLLECTION_ATTEMPTS_MAX = 10  # máximo de tentativas mantidas por entidade


def get_collection_attempts(redis: Redis, entity_id: str) -> list[dict]:
    """Retorna as últimas tentativas de coleta de uma entidade (produto ou concorrente).

    Returns:
        Lista de dicts com keys: ts, outcome, domain. Mais recente primeiro.
    """
    key = f"collection:attempts:{entity_id}"
    raw = redis.lrange(key, 0, _COLLECTION_ATTEMPTS_MAX - 1)
    result = []
    for entry in raw:
        try:
            result.append(json.loads(entry))
        except (ValueError, TypeError):
            continue
    return result


def record_collection_attempt(
    redis: Redis,
    entity_id: str,
    outcome: str,
    domain: str,
) -> None:
    """Registra uma tentativa de coleta como evento de primeira classe.

    Mantém as últimas _COLLECTION_ATTEMPTS_MAX tentativas por entidade (produto ou
    concorrente) como lista Redis, sem exigir migration de banco.

    Args:
        entity_id: UUID do MonitoredProduct ou Competitor.
        outcome: resultado — success | captcha | blocked | timeout | price_not_found | rate_limited | domain_circuit_open
        domain: domínio da URL coletada (ex.: www.mercadolivre.com.br).
    """
    key = f"collection:attempts:{entity_id}"
    entry = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "domain": domain,
    })
    redis.lpush(key, entry)
    redis.ltrim(key, 0, _COLLECTION_ATTEMPTS_MAX - 1)
    redis.expire(key, 86400 * 7)  # TTL 7 dias


# ── Cache ──────────────────────────────────────────────────────────────────────

def invalidate_comparison_cache(redis: Redis, monitored_id: uuid.UUID) -> None:
    redis.delete(f"cache:comparison:{monitored_id}")
