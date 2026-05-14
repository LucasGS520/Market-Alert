"""
Configuração do serviço market_scraper.

Uso:
    from app.core.config import settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Habilita o fallback para Playwright quando HTTP falha (usado pelo pipeline legado)
    playwright_enabled: bool = True

    # False = abre o browser visível na tela (ideal para uso local com IP residencial).
    # True  = headless (necessário em Docker sem display).
    # Setar PLAYWRIGHT_HEADLESS=false no .env para rodar localmente.
    playwright_headless: bool = True

    # Timeout para requisições HTTP comuns (curl_cffi)
    request_timeout_seconds: int = 15

    # Timeout para operações do Playwright (navegação + condição de espera)
    playwright_timeout_ms: int = 60000

    # Timeout global por requisição /scraper/parse (deve ser < scraper_timeout_seconds do caller).
    # Garante que o scraper responde antes do caller desistir, evitando trabalho órfão.
    max_total_request_seconds: int = 240

    # Intervalo entre tentativas de inicializar o Chromium em background.
    browser_startup_retry_seconds: int = 30

    # Número máximo de payloads de rede interceptados por requisição
    max_intercepted_payloads: int = 10

    # Diretório para persistir cookies/sessão por marketplace entre reinicializações.
    # Montar como volume no docker-compose para não perder entre restarts do container.
    session_state_dir: str = ".session_state"

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
