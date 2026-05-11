"""Gerenciamento de rodadas coordenadas de coleta em Redis.

Uma rodada representa a execução conjunta de um produto monitorado e seus
concorrentes elegíveis, garantindo que a comparação use preços coletados
na mesma janela de tempo.

Chave Redis: collection_run:{product_id}
Tipo: Hash  {competitor_id: "pending" | "done"}
TTL: collection_run_timeout_seconds (padrão 300 s)
"""

from redis import Redis

_PREFIX = "collection_run"


def start_run(redis: Redis, product_id: str, competitor_ids: list[str], timeout: int = 300) -> None:
    """Registra uma nova rodada com todos os concorrentes como 'pending'."""
    key = f"{_PREFIX}:{product_id}"
    mapping = {cid: "pending" for cid in competitor_ids}
    if mapping:
        redis.hset(key, mapping=mapping)
        redis.expire(key, timeout)


def mark_done(redis: Redis, product_id: str, competitor_id: str) -> None:
    """Marca um concorrente como concluído na rodada ativa do produto."""
    key = f"{_PREFIX}:{product_id}"
    if redis.exists(key):
        redis.hset(key, competitor_id, "done")


def is_complete(redis: Redis, product_id: str) -> bool:
    """True se todos os concorrentes terminaram ou se a rodada expirou/não existe."""
    key = f"{_PREFIX}:{product_id}"
    if not redis.exists(key):
        return True  # rodada expirou ou nunca existiu — pode prosseguir
    statuses = redis.hvals(key)
    return all(s == "done" for s in statuses)
