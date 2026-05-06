"""
Cliente Redis — fornece acesso ao Redis para toda a aplicação.

O Redis é usado em três contextos neste projeto:
    1. Locks distribuídos: impede coleta simultânea do mesmo produto
    2. Rate limiting: respeita intervalos mínimos por domínio web
    3. Cooldown de notificações: evita spam de alertas

Por que Redis síncrono nos workers?
    O Celery executa em um ambiente síncrono (não-assíncrono). Usar
    o cliente Redis síncrono (redis-py) dentro das tasks é a abordagem
    mais simples e correta. O cliente assíncrono (redis.asyncio) seria
    necessário apenas dentro de corrotinas async.

Uso:
    from app.core.redis_client import get_redis
    redis = get_redis()
    redis.set("minha_chave", "valor", ex=60)
"""

from redis import Redis

from app.core.config import settings


def get_redis() -> Redis:
    """
    Cria e retorna um cliente Redis síncrono.

    Retorna um novo cliente a cada chamada (não é singleton), pois
    o Celery pode rodar múltiplos workers em paralelo e cada um
    precisa de sua própria conexão.
    """
    return Redis.from_url(settings.redis_url, decode_responses=True)
