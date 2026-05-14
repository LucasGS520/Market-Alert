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
    # Deve ser maior que max_total_request_seconds do market_scraper.
    scraper_timeout_seconds: float = 270.0

    # ── Notificações ───────────────────────────────────────────────────────
    ntfy_url: str = "https://ntfy.sh"
    ntfy_topic: str | None = None
    telert_token: str | None = None

    # ── Regras de Negócio de Notificação ──────────────────────────────────
    notification_delta_percent: float = 5.0
    notification_cooldown_minutes: int = 30

    # ── Regras de Comparação ───────────────────────────────────────────────
    status_threshold_competitive: float = 5.0   # % acima do mínimo → ainda "competitive"
    status_threshold_attention: float = 15.0    # % acima do mínimo → "attention" (acima → "urgent")
    comparison_dedup_window_minutes: int = 5    # janela de deduplicação de snapshots idênticos

    # ── Concorrentes ───────────────────────────────────────────────────────
    max_competitors_per_product: int = 5

    # ── Rate Limiting de Domínio ───────────────────────────────────────────
    domain_captcha_cooldown_seconds: int = 300
    domain_rate_limit_ttl_seconds: int = 2

    # ── Retry e Backoff de Coleta ──────────────────────────────────────────
    collection_retry_base_delay_minutes: int = 5
    collection_retry_max_delay_minutes: int = 60
    collection_run_timeout_seconds: int = 300  # SLA máximo de uma rodada coordenada

    # ── Política de Estabilidade ───────────────────────────────────────────
    price_stability_change_threshold_percent: float = 1.0

    # ── Scheduler com Lease ────────────────────────────────────────────────
    scheduler_batch_size: int = 50
    scheduler_lock_ttl_seconds: int = 55
    collection_lease_ttl_seconds: int = 600

    # ── Reagendamento por Motivo ───────────────────────────────────────────
    rate_limit_reschedule_min_minutes: int = 5
    rate_limit_reschedule_max_minutes: int = 15
    lock_busy_reschedule_min_minutes: int = 2
    lock_busy_reschedule_max_minutes: int = 5

    # ── Servidor ───────────────────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
