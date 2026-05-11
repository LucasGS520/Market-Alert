import uuid

import structlog
from redis import Redis

from app.infra.config import settings

logger = structlog.get_logger()

_LOCK_TTL = 60
_RATE_LIMIT_TTL = 5


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


# ── Locks distribuídos ─────────────────────────────────────────────────────────

def acquire_lock(redis: Redis, key: str, timeout: int = _LOCK_TTL) -> bool:
    return bool(redis.set(key, "1", nx=True, ex=timeout))


def release_lock(redis: Redis, key: str) -> None:
    redis.delete(key)


# ── Rate limit por domínio ─────────────────────────────────────────────────────

def check_rate_limit(redis: Redis, domain: str) -> bool:
    """Returns True se pode prosseguir, False se está em cooldown."""
    key = f"ratelimit:domain:{domain}"
    if redis.exists(key):
        return False
    redis.set(key, "1", ex=_RATE_LIMIT_TTL)
    return True


def set_domain_cooldown(redis: Redis, domain: str) -> None:
    ttl = settings.domain_captcha_cooldown_seconds
    redis.set(f"ratelimit:domain:{domain}", "1", ex=ttl)
    logger.warning("dominio_cooldown_bloqueio", dominio=domain, cooldown_segundos=ttl)


# ── Cooldown de notificações ───────────────────────────────────────────────────

def notification_cooldown_key(monitored_id: uuid.UUID) -> str:
    return f"ratelimit:notify:{monitored_id}"


def is_in_cooldown(redis: Redis, monitored_id: uuid.UUID) -> bool:
    return bool(redis.exists(notification_cooldown_key(monitored_id)))


def set_cooldown(redis: Redis, monitored_id: uuid.UUID) -> None:
    ttl = settings.notification_cooldown_minutes * 60
    redis.set(notification_cooldown_key(monitored_id), "1", ex=ttl)


# ── Cache ──────────────────────────────────────────────────────────────────────

def invalidate_comparison_cache(redis: Redis, monitored_id: uuid.UUID) -> None:
    redis.delete(f"cache:comparison:{monitored_id}")
