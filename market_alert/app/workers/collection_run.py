"""Gerenciamento de rodadas coordenadas de coleta em Redis.

Uma rodada representa a execução conjunta de um produto monitorado e seus
concorrentes elegíveis, garantindo que a comparação use preços coletados
na mesma janela de tempo.

Chave Redis: collection_run:{run_id}   (run_id é UUIDv4, único por rodada)
Tipo: Hash
  __meta__   → JSON {monitored_id, expires_at (unix float)}
  {competitor_id} → "pending" | "done" | "failed"
TTL: timeout (padrão 300 s)

Estados da rodada (get_status):
  pending       — ainda há concorrentes pendentes dentro do TTL
  complete      — todos terminaram com sucesso
  partial       — todos terminaram, mas pelo menos um falhou definitivamente
  expired       — TTL esgotou antes de todos terminarem (chave ausente)
  no_competitors — rodada iniciada sem concorrentes
"""

import json
import time

from redis import Redis

_PREFIX = "collection_run"


def start_run(
    redis: Redis,
    run_id: str,
    monitored_id: str,
    competitor_ids: list[str],
    timeout: int = 300,
) -> None:
    """Registra uma nova rodada com todos os concorrentes como 'pending'."""
    key = f"{_PREFIX}:{run_id}"
    meta = json.dumps({
        "monitored_id": monitored_id,
        "expires_at": time.time() + timeout,
    })
    mapping: dict[str, str] = {"__meta__": meta}
    mapping.update({cid: "pending" for cid in competitor_ids})
    redis.hset(key, mapping=mapping)
    redis.expire(key, timeout)


def mark_done(redis: Redis, run_id: str, competitor_id: str) -> None:
    """Marca um concorrente como concluído com sucesso."""
    key = f"{_PREFIX}:{run_id}"
    if redis.exists(key):
        redis.hset(key, competitor_id, "done")


def mark_failed(redis: Redis, run_id: str, competitor_id: str) -> None:
    """Marca um concorrente como falho de forma definitiva."""
    key = f"{_PREFIX}:{run_id}"
    if redis.exists(key):
        redis.hset(key, competitor_id, "failed")


def get_status(redis: Redis, run_id: str) -> str:
    """Retorna o estado atual da rodada.

    Returns:
        "pending"       — ainda há concorrentes pendentes
        "complete"      — todos concluíram com sucesso
        "partial"       — todos terminaram, mas pelo menos um falhou
        "expired"       — chave expirou (TTL esgotado)
        "no_competitors"— rodada sem concorrentes registrados
    """
    key = f"{_PREFIX}:{run_id}"
    if not redis.exists(key):
        return "expired"

    data = {
        k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
        for k, v in redis.hgetall(key).items()
    }
    estados = {k: v for k, v in data.items() if k != "__meta__"}

    if not estados:
        return "no_competitors"

    values = list(estados.values())

    if any(s == "pending" for s in values):
        return "pending"

    if any(s == "failed" for s in values):
        return "partial"

    return "complete"


def is_complete(redis: Redis, run_id: str) -> bool:
    """True quando a rodada não está mais pendente (qualquer estado final)."""
    return get_status(redis, run_id) != "pending"
