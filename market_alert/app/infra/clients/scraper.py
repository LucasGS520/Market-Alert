import json
from datetime import datetime
from decimal import Decimal
from typing import Literal

import httpx
import structlog
from pydantic import BaseModel

from app.infra.config import settings

logger = structlog.get_logger()


class ScraperErrorResult(BaseModel):
    error_code: Literal[
        "PRICE_NOT_FOUND",
        "CAPTCHA_DETECTED",
        "BLOCKED",
        "UNAVAILABLE",
        "REDIRECT_TO_SEARCH",
        "LAYOUT_CHANGED",
        "TIMEOUT",
        "MARKETPLACE_NOT_SUPPORTED",
    ]
    marketplace: str
    url: str
    retryable: bool
    message: str


class ScraperResult(BaseModel):
    marketplace: str
    price: Decimal | None = None
    available: bool
    title: str | None = None
    seller: str | None = None
    thumbnail_url: str | None = None
    currency: str | None = None
    collected_at: datetime
    url: str | None = None
    canonical_url: str | None = None
    product_id: str | None = None
    extraction_method: str | None = None
    confidence: float | None = None


class ScraperUnavailableError(Exception):
    pass


class ScraperParseError(Exception):
    def __init__(self, error_result: ScraperErrorResult) -> None:
        self.error_result = error_result
        super().__init__(error_result.message)


def _build_error_result(payload: object, url: str) -> ScraperErrorResult | None:
    data = payload.get("detail", payload) if isinstance(payload, dict) else payload
    if not isinstance(data, dict) or "error_code" not in data:
        return None

    message = data.get("message", "Nao foi possivel extrair dados da URL")
    if not isinstance(message, str):
        message = json.dumps(message, ensure_ascii=False)

    return ScraperErrorResult(
        error_code=str(data.get("error_code", "PRICE_NOT_FOUND")),
        marketplace=str(data.get("marketplace", "unknown")),
        url=str(data.get("url", url)),
        retryable=bool(data.get("retryable", True)),
        message=message,
    )


class ScraperClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.scraper_url).rstrip("/")
        self.timeout = timeout or settings.scraper_timeout_seconds

    async def parse(self, url: str) -> ScraperResult:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/scraper/parse",
                    json={"url": url},
                )
            except httpx.ConnectError as exc:
                raise ScraperUnavailableError(f"Scraper inacessivel: {exc}") from exc
            except httpx.TimeoutException as exc:
                raise ScraperUnavailableError(f"Timeout ao chamar scraper: {exc}") from exc

            if response.status_code in (422, 504):
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ScraperUnavailableError(f"Scraper retornou HTTP {response.status_code}") from exc
                error_result = _build_error_result(payload, url)
                if error_result is None:
                    raise ScraperUnavailableError(f"Scraper retornou HTTP {response.status_code}")
                raise ScraperParseError(error_result)

            if response.status_code != 200:
                raise ScraperUnavailableError(f"Scraper retornou HTTP {response.status_code}")

            data = response.json()
            logger.debug("resultado_scraper", url=url, preco=data.get("price"), marketplace=data.get("marketplace"))
            return ScraperResult(**data)


_cliente_padrao: ScraperClient | None = None


def get_scraper_client() -> ScraperClient:
    global _cliente_padrao
    if _cliente_padrao is None:
        _cliente_padrao = ScraperClient()
    return _cliente_padrao
