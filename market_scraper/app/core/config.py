"""
Configuração do serviço market_scraper.

Define parâmetros de comportamento do scraping: timeouts, user-agent
e se o Playwright (browser headless) está habilitado.

O Playwright é mais lento e consome mais memória, mas consegue
renderizar páginas que bloqueiam bots baseados apenas em HTTP.
Habilite-o para sites com proteção anti-bot mais avançada.

Uso:
    from app.core.config import settings
    print(settings.playwright_enabled)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Habilita o fallback para Playwright quando HTTP falha
    playwright_enabled: bool = True

    # Timeout para requisições HTTP comuns (curl_cffi)
    request_timeout_seconds: int = 15

    # Timeout para operações do Playwright (navegação + carregamento)
    playwright_timeout_ms: int = 30000

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
