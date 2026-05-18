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


# ── Rate limit por domínio (burst control) ────────────────────────────────────

def check_rate_limit(redis: Redis, domain: str) -> bool:
    """Controle de burst: True se pode prosseguir, False se requisição em andamento (2s TTL).

    Separado do circuit breaker — cobre apenas a janela de burst de 2s entre coletas.
    Para bloqueio por CAPTCHA/block use is_domain_open() / open_domain_circuit().
    """
    key = f"ratelimit:domain:{domain}"
    if redis.exists(key):
        return False
    redis.set(key, "1", ex=settings.domain_rate_limit_ttl_seconds)
    return True


# ── Circuit Breaker de domínio (estado escalável) ──────────────────────────────

def _circuit_key(domain: str) -> str:
    return f"domain:circuit:{domain}"


def _failures_key(domain: str) -> str:
    return f"domain:failures:{domain}"


def get_domain_circuit_state(redis: Redis, domain: str) -> str:
    """Retorna 'OPEN' se o circuito está aberto, 'CLOSED' se pode operar."""
    return "OPEN" if redis.exists(_circuit_key(domain)) else "CLOSED"


def is_domain_open(redis: Redis, domain: str) -> bool:
    """True se o domínio está com circuito OPEN (bloqueado)."""
    return bool(redis.exists(_circuit_key(domain)))


def open_domain_circuit(redis: Redis, domain: str) -> int:
    """Abre (ou escala) o circuit breaker do domínio após CAPTCHA/bloqueio.

    Incrementa o contador de falhas consecutivas e aplica cooldown escalonado:
    - 1ª falha: tier1 (padrão 300s)
    - 2ª falha: tier2 (padrão 600s)
    - 3ª+ falha: tier3 (padrão 1200s)

    Returns:
        cooldown_seconds aplicado.
    """
    failures_key = _failures_key(domain)
    failures = redis.incr(failures_key)
    redis.expire(failures_key, settings.domain_circuit_failure_ttl)

    if failures == 1:
        ttl = settings.domain_circuit_cooldown_tier1
    elif failures == 2:
        ttl = settings.domain_circuit_cooldown_tier2
    else:
        ttl = settings.domain_circuit_cooldown_tier3

    redis.set(_circuit_key(domain), str(failures), ex=ttl)
    logger.warning(
        "domain_circuit_opened",
        dominio=domain,
        falhas_consecutivas=failures,
        cooldown_segundos=ttl,
    )
    return ttl


def close_domain_circuit(redis: Redis, domain: str) -> None:
    """Fecha o circuit breaker após coleta bem-sucedida em domínio recuperado."""
    had_failures = redis.exists(_failures_key(domain))
    redis.delete(_circuit_key(domain), _failures_key(domain))
    if had_failures:
        logger.info("domain_circuit_closed", dominio=domain)


def get_remaining_circuit_cooldown(redis: Redis, domain: str) -> int:
    """Retorna segundos restantes do cooldown do circuito (0 se CLOSED ou expirado)."""
    ttl = redis.ttl(_circuit_key(domain))
    return max(ttl, 0)


def set_domain_cooldown(redis: Redis, domain: str) -> None:
    """Compatibilidade: abre o circuit breaker escalável. Use open_domain_circuit() diretamente."""
    open_domain_circuit(redis, domain)


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
