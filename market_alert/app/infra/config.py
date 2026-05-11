from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Banco de Dados ─────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://market:market_pass@postgres:5432/market_alert"
    database_sync_url: str = "postgresql+psycopg2://market:market_pass@localhost:5432/market_alert"

    # ── Redis ──────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── Serviço de Scraping ────────────────────────────────────────────────
    scraper_url: str = "http://market_scraper:8001"

    # ── Notificações ───────────────────────────────────────────────────────
    ntfy_url: str = "https://ntfy.sh"
    ntfy_topic: str = "market_alert"
    telert_token: str | None = None

    # ── Regras de Negócio de Notificação ──────────────────────────────────
    notification_delta_percent: float = 5.0
    notification_cooldown_minutes: int = 30

    # ── Rate Limiting de Domínio ───────────────────────────────────────────
    domain_captcha_cooldown_seconds: int = 300

    # ── Servidor ───────────────────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
