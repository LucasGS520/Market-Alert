import uuid

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


# ── Rate limit por domínio ─────────────────────────────────────────────────────

def check_rate_limit(redis: Redis, domain: str) -> bool:
    """Returns True se pode prosseguir, False se está em cooldown."""
    key = f"ratelimit:domain:{domain}"
    if redis.exists(key):
        return False
    redis.set(key, "1", ex=settings.domain_rate_limit_ttl_seconds)
    return True


def set_domain_cooldown(redis: Redis, domain: str) -> None:
    ttl = settings.domain_captcha_cooldown_seconds
    redis.set(f"ratelimit:domain:{domain}", "1", ex=ttl)
    logger.warning("dominio_cooldown_bloqueio", dominio=domain, cooldown_segundos=ttl)


# ── Cooldown de notificações ───────────────────────────────────────────────────
# Granularidade: produto + tipo de evento.
# Cooldown de um evento não bloqueia outros eventos do mesmo produto.

def notification_cooldown_key(monitored_id: uuid.UUID, event_type: str) -> str:
    return f"cooldown:notify:{monitored_id}:{event_type}"


def is_in_cooldown(redis: Redis, monitored_id: uuid.UUID, event_type: str) -> bool:
    return bool(redis.exists(notification_cooldown_key(monitored_id, event_type)))


def set_cooldown(redis: Redis, monitored_id: uuid.UUID, event_type: str) -> None:
    ttl = settings.notification_cooldown_minutes * 60
    redis.set(notification_cooldown_key(monitored_id, event_type), "1", ex=ttl)


# ── Cache ──────────────────────────────────────────────────────────────────────

def invalidate_comparison_cache(redis: Redis, monitored_id: uuid.UUID) -> None:
    redis.delete(f"cache:comparison:{monitored_id}")
