"""
Configuração central da aplicação via variáveis de ambiente.

Usa pydantic-settings para ler automaticamente o arquivo .env ou variáveis
de ambiente do sistema. Todas as configurações do projeto estão aqui — bancos,
Redis, URLs de serviços externos, e parâmetros de regras de negócio.

Uso:
    from app.core.config import settings
    print(settings.scraper_url)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Banco de Dados ─────────────────────────────────────────────────────
    # URL assíncrona usada pela API e pelos workers em runtime
    database_url: str = "postgresql+asyncpg://market:market_pass@postgres:5432/market_alert"
    # URL síncrona usada pelo Alembic CLI para rodar migrations
    database_sync_url: str = "postgresql+psycopg2://market:market_pass@localhost:5432/market_alert"

    # ── Redis ──────────────────────────────────────────────────────────────
    # db=0: cache geral e locks distribuídos
    redis_url: str = "redis://redis:6379/0"
    # db=1: fila de tarefas do Celery
    celery_broker_url: str = "redis://redis:6379/1"
    # db=2: resultados de tarefas Celery
    celery_result_backend: str = "redis://redis:6379/2"

    # ── Serviço de Scraping ────────────────────────────────────────────────
    # URL do microserviço market_scraper (outro container Docker)
    scraper_url: str = "http://market_scraper:8001"

    # ── Notificações ───────────────────────────────────────────────────────
    # ntfy.sh: serviço de push notification open source (auto-hospedável)
    ntfy_url: str = "https://ntfy.sh"
    ntfy_topic: str = "market_alert"
    # Telert: serviço de alertas via token Bearer (opcional)
    telert_token: str | None = None

    # ── Regras de Negócio de Notificação ──────────────────────────────────
    # Variação mínima de preço (%) para disparar uma notificação
    notification_delta_percent: float = 5.0
    # Intervalo mínimo entre notificações do mesmo produto (minutos)
    notification_cooldown_minutes: int = 30

    # ── Servidor ───────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # Lê do arquivo .env na raiz do projeto; ignora variáveis desconhecidas
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Instância global — importar esta variável, nunca instanciar Settings diretamente
settings = Settings()
