"""
Cliente HTTP para o microserviço market_scraper.

O market_scraper roda como um container Docker separado e expõe uma API REST.
Este módulo encapsula toda comunicação com ele — a lógica de negócio
(o que fazer com o resultado) fica nos serviços, não aqui.

Fluxo de comunicação:
    market_alert (este cliente) ──POST /scraper/parse──→ market_scraper
    market_alert (este cliente) ←── { price, is_available, name } ──────

Erros tratados:
    ScraperUnavailableError → scraper está fora do ar ou deu timeout
    ScraperParseError       → scraper rodou mas não extraiu dados; carrega
                              ScraperErrorResult com error_code e retryable
"""

import httpx
import structlog

from app.core.config import settings
from app.schemas.common import ScraperErrorResult, ScraperResult

logger = structlog.get_logger()


class ScraperUnavailableError(Exception):
    """Erro de conectividade: o scraper não respondeu ou deu timeout."""
    pass


class ScraperParseError(Exception):
    """
    Erro semântico: o scraper rodou mas não extraiu preço da página.

    Carrega o contrato completo do scraper para que a camada de negócio
    possa distinguir erros retentáveis de permanentes via error_result.retryable.
    """

    def __init__(self, error_result: ScraperErrorResult) -> None:
        self.error_result = error_result
        super().__init__(error_result.message)


class ScraperClient:
    """
    Cliente HTTP que chama o microserviço market_scraper.

    Responsabilidade única: fazer a requisição HTTP e transformar
    a resposta em um ScraperResult. Qualquer erro de rede ou parsing
    é convertido em uma exceção tipada.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        """
        Args:
            base_url: URL base do scraper. Se None, usa settings.scraper_url.
            timeout:  Segundos máximos para aguardar resposta.
        """
        self.base_url = (base_url or settings.scraper_url).rstrip("/")
        self.timeout = timeout

    async def parse(self, url: str) -> ScraperResult:
        """
        Pede ao market_scraper que extraia preço e disponibilidade de uma URL.

        Args:
            url: URL do produto a ser raspado.

        Returns:
            ScraperResult com preço, disponibilidade, nome e moeda.

        Raises:
            ScraperUnavailableError: scraper inacessível ou timeout.
            ScraperParseError: scraper acessível mas não extraiu dados.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/scraper/parse",
                    json={"url": url},
                )
            except httpx.ConnectError as exc:
                raise ScraperUnavailableError(f"Scraper inacessível: {exc}") from exc
            except httpx.TimeoutException as exc:
                raise ScraperUnavailableError(f"Timeout ao chamar scraper: {exc}") from exc

            # HTTP 422: scraper rodou mas falhou semanticamente (preço não encontrado,
            # CAPTCHA, bloqueio etc.). O corpo contém o contrato ScrapeError completo.
            if response.status_code == 422:
                data = response.json()
                try:
                    error_result = ScraperErrorResult(**data)
                except Exception:
                    # Fallback para respostas inesperadas do scraper
                    error_result = ScraperErrorResult(
                        error_code="PRICE_NOT_FOUND",
                        marketplace="unknown",
                        url=url,
                        retryable=True,
                        message=data.get("detail", "Não foi possível extrair dados da URL"),
                    )
                raise ScraperParseError(error_result)

            if response.status_code != 200:
                raise ScraperUnavailableError(f"Scraper retornou HTTP {response.status_code}")

            data = response.json()
            logger.debug("resultado_scraper", url=url, preco=data.get("price"), marketplace=data.get("marketplace"))
            return ScraperResult(**data)


# Instância compartilhada — usada pelos workers e serviços
_cliente_padrao: ScraperClient | None = None


def get_scraper_client() -> ScraperClient:
    """Retorna a instância padrão do cliente (cria na primeira chamada)."""
    global _cliente_padrao
    if _cliente_padrao is None:
        _cliente_padrao = ScraperClient()
    return _cliente_padrao
