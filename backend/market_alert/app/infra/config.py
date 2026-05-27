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

    # ── Notificações — ntfy ────────────────────────────────────────────────
    ntfy_url: str = "https://ntfy.sh"
    ntfy_topic: str | None = None

    # ── Notificações — e-mail (SMTP) ───────────────────────────────────────
    # smtp_host=None desativa o canal silenciosamente (mesmo padrão de ntfy_topic=None).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "Market Alert <noreply@market-alert.local>"
    smtp_to: str | None = None      # destinatário dos alertas
    smtp_use_tls: bool = True       # False para Mailpit local (porta 1025)

    # ── Regras de Negócio de Notificação ──────────────────────────────────
    notification_delta_percent: float = 5.0
    # Janela de silêncio por (produto × tipo de alerta) para evitar spam em oscilações frequentes.
    notification_cooldown_minutes: int = 30
    # Quorum mínimo de concorrentes válidos para disparar notificação.
    # Comparação persiste para auditoria, mas notificação é bloqueada abaixo do quorum.
    notification_min_quorum: int = 1

    # ── Regras de Comparação ───────────────────────────────────────────────
    status_threshold_competitive: float = 1.0   # % acima do mínimo → ainda "competitive"
    status_threshold_attention: float = 15.0    # % acima do mínimo → "attention" (acima → "urgent")
    comparison_dedup_window_minutes: int = 5    # janela de deduplicação de snapshots idênticos

    # ── Concorrentes ───────────────────────────────────────────────────────
    max_competitors_per_product: int = 5

    # ── Rate Limiting de Domínio ───────────────────────────────────────────
    domain_captcha_cooldown_seconds: int = 300  # mantido para compat; usar circuit breaker
    domain_rate_limit_ttl_seconds: int = 2

    # ── Circuit Breaker de Domínio (escalada progressiva) ─────────────────
    domain_circuit_cooldown_tier1: int = 300    # 1ª falha consecutiva: 5 min
    domain_circuit_cooldown_tier2: int = 600    # 2ª falha consecutiva: 10 min
    domain_circuit_cooldown_tier3: int = 1200   # 3ª+ falha consecutiva: 20 min
    domain_circuit_failure_ttl: int = 86400     # TTL do contador de falhas: 24h

    # ── Retry e Backoff de Coleta ──────────────────────────────────────────
    collection_retry_base_delay_minutes: int = 5
    collection_retry_max_delay_minutes: int = 60
    collection_run_timeout_seconds: int = 300  # SLA máximo de uma rodada coordenada

    # ── Política de Estabilidade ───────────────────────────────────────────
    price_stability_change_threshold_percent: float = 1.0
    # Multiplicador sobre check_interval_minutes para definir dado como obsoleto.
    # Ex.: intervalo=60min × 2.0 → stale após 120min sem coleta bem-sucedida.
    stale_multiplier: float = 2.0

    # ── Scheduler com Lease ────────────────────────────────────────────────
    scheduler_batch_size: int = 50
    scheduler_lock_ttl_seconds: int = 55
    collection_lease_ttl_seconds: int = 600
    # Limite de produtos enfileirados por domínio por ciclo do scheduler.
    # Evita burst quando vários produtos do mesmo domínio ficam vencidos ao mesmo tempo.
    scheduler_max_per_domain: int = 3

    # ── Reagendamento por Motivo ───────────────────────────────────────────
    rate_limit_reschedule_min_minutes: int = 5
    rate_limit_reschedule_max_minutes: int = 15
    lock_busy_reschedule_min_minutes: int = 2
    lock_busy_reschedule_max_minutes: int = 5

    # ── Servidor ───────────────────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
