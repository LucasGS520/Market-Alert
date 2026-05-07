import json
import re
from decimal import Decimal, InvalidOperation

import structlog
from parsel import Selector
from playwright.async_api import Page

from app.adapters.base import MarketplaceAdapter
from app.core.config import settings
from app.scraping.extractor import parse_price_string
from app.schemas import (
    CollectedPage,
    ErrorCode,
    ExtractionMethod,
    ScrapeError,
    ScrapeResult,
)

logger = structlog.get_logger()

_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)
_PRODUCT_ID_RE = re.compile(r"/p/([A-Z0-9]+)", re.IGNORECASE)

# Caminhos conhecidos do preço no __NEXT_DATA__ do Magalu (tentados em ordem)
_PRICE_PATHS: list[list[str]] = [
    ["props", "pageProps", "product", "price"],
    ["props", "pageProps", "product", "bestPrice"],
    ["props", "pageProps", "product", "priceValue"],
    ["props", "pageProps", "data", "product", "price"],
    ["props", "pageProps", "data", "product", "priceValue"],
]

_AVAILABILITY_PATHS: list[list[str]] = [
    ["props", "pageProps", "product", "available"],
    ["props", "pageProps", "product", "inStock"],
    ["props", "pageProps", "data", "product", "available"],
]

_TITLE_PATHS: list[list[str]] = [
    ["props", "pageProps", "product", "title"],
    ["props", "pageProps", "product", "name"],
    ["props", "pageProps", "data", "product", "title"],
]

_SELLER_PATHS: list[list[str]] = [
    ["props", "pageProps", "product", "seller", "name"],
    ["props", "pageProps", "product", "sellerName"],
]


class MagaluAdapter(MarketplaceAdapter):
    marketplace = "magalu"

    async def collect(self, url: str) -> CollectedPage:
        # Estratégia 1: HTTP (SSR) — falha rápido em 403, usa browser como fallback
        http_page = await self._try_http(url)
        if http_page is not None:
            return http_page

        # Estratégia 2: browser com intercepção de /_next/data/
        logger.debug("magalu_ssr_incompleto_ativando_browser", url=url)
        return await self._try_browser(url)

    async def _try_http(self, url: str) -> CollectedPage | None:
        from app.scraping.collector import CollectionError, clean_url, fetch_with_http

        url_clean = clean_url(url)
        try:
            html = await fetch_with_http(url_clean)
            return CollectedPage(
                url=url_clean,
                marketplace=self.marketplace,
                html=html,
                rendered=False,
            )
        except CollectionError as exc:
            logger.info("magalu_http_falhou", url=url_clean, motivo=str(exc))
            return None
        except Exception as exc:
            logger.warning("magalu_http_erro_infra", url=url_clean, erro=str(exc))
            return None

    async def _try_browser(self, url: str) -> CollectedPage:
        async def _wait(page: Page) -> None:
            try:
                await page.wait_for_selector(
                    "[data-testid='price-value'], [class*='price']",
                    state="visible",
                    timeout=settings.playwright_timeout_ms,
                )
            except Exception:
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=settings.playwright_timeout_ms,
                    )
                except Exception:
                    pass

        return await self._browser.navigate_and_collect(
            url=url,
            marketplace=self.marketplace,
            wait_condition=_wait,
        )

    async def extract(self, page: CollectedPage) -> ScrapeResult | ScrapeError:
        if page.blocked:
            return ScrapeError(
                error_code=ErrorCode.BLOCKED,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="Acesso bloqueado (HTTP 403)",
            )

        if page.captcha_detected:
            return ScrapeError(
                error_code=ErrorCode.CAPTCHA_DETECTED,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="CAPTCHA detectado na página do Magalu",
            )

        if page.html is None:
            return ScrapeError(
                error_code=ErrorCode.PRICE_NOT_FOUND,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message=f"Falha na coleta da página: {page.error}",
            )

        next_data = _parse_next_data(page.html)

        # Verifica disponibilidade antes de tentar o preço
        if next_data and _is_unavailable(next_data):
            return ScrapeError(
                error_code=ErrorCode.UNAVAILABLE,
                marketplace=self.marketplace,
                url=page.url,
                retryable=False,
                message="Produto indisponível no Magalu",
            )

        sel = Selector(page.html)

        # Estratégia 1: __NEXT_DATA__ SSR (confidence=0.95)
        price, method, confidence = _extract_from_next_data(next_data)

        # Estratégia 2: payload de rede /_next/data/ (confidence=1.0)
        if price is None and page.network_payloads:
            price, method, confidence = _extract_from_payloads(page.network_payloads)

        # Estratégia 3: DOM renderizado (confidence=0.8)
        if price is None:
            price, method, confidence = _extract_from_dom(sel)

        if price is None or price <= 0:
            return ScrapeError(
                error_code=ErrorCode.PRICE_NOT_FOUND,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="Preço não encontrado (SSR, payload e DOM falharam)",
            )

        title = _extract_title(next_data, sel)
        seller = _extract_seller(next_data, sel)
        product_id = _extract_product_id(page.url)

        logger.info(
            "magalu_extracao_sucesso",
            url=page.url,
            price=str(price),
            method=method.value,
            confidence=confidence,
        )

        return ScrapeResult(
            marketplace=self.marketplace,
            url=page.url,
            canonical_url=sel.css("link[rel='canonical']::attr(href)").get(),
            title=title,
            price=price,
            currency="BRL",
            available=True,
            seller=seller,
            product_id=product_id,
            extraction_method=method,
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# Parsing do __NEXT_DATA__
# ---------------------------------------------------------------------------

def _parse_next_data(html: str) -> dict | None:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


def _get_at_path(obj: object, *paths: list[str]) -> object | None:
    """Tenta cada caminho em ordem e retorna o primeiro valor não-None encontrado."""
    for path in paths:
        current = obj
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current is not None:
            return current
    return None


def _is_unavailable(next_data: dict) -> bool:
    val = _get_at_path(next_data, *_AVAILABILITY_PATHS)
    # Se o campo existe e é explicitamente False, está indisponível
    if isinstance(val, bool):
        return not val
    return False


# ---------------------------------------------------------------------------
# Extração de preço
# ---------------------------------------------------------------------------

def _extract_from_next_data(
    next_data: dict | None,
) -> tuple[Decimal | None, ExtractionMethod, float]:
    if not next_data:
        return None, ExtractionMethod.SSR_STATE, 0.0

    raw = _get_at_path(next_data, *_PRICE_PATHS)
    if raw is None:
        return None, ExtractionMethod.SSR_STATE, 0.0

    try:
        price = Decimal(str(raw))
        return price, ExtractionMethod.SSR_STATE, 0.95
    except InvalidOperation:
        return None, ExtractionMethod.SSR_STATE, 0.0


def _extract_from_payloads(
    payloads: list[dict],
) -> tuple[Decimal | None, ExtractionMethod, float]:
    for entry in payloads:
        body = entry.get("body", {})
        raw = _get_at_path(body, *_PRICE_PATHS)
        if raw is not None:
            try:
                price = Decimal(str(raw))
                if price > 0:
                    return price, ExtractionMethod.NETWORK_PAYLOAD, 1.0
            except InvalidOperation:
                continue
    return None, ExtractionMethod.NETWORK_PAYLOAD, 0.0


def _extract_from_dom(
    sel: Selector,
) -> tuple[Decimal | None, ExtractionMethod, float]:
    price_text = (
        sel.css("[data-testid='price-value']::text").get()
        or sel.css("[data-testid='price-value'] ::text").get()
        or sel.css("[class*='price-template'] [class*='value']::text").get()
        or sel.css("meta[property='product:price:amount']::attr(content)").get()
    )

    if price_text is None:
        return None, ExtractionMethod.CSS_SELECTOR, 0.0

    price = parse_price_string(price_text)
    if price is None:
        return None, ExtractionMethod.CSS_SELECTOR, 0.0
    return price, ExtractionMethod.CSS_SELECTOR, 0.8


# ---------------------------------------------------------------------------
# Extração de metadados
# ---------------------------------------------------------------------------

def _extract_title(next_data: dict | None, sel: Selector) -> str | None:
    if next_data:
        val = _get_at_path(next_data, *_TITLE_PATHS)
        if isinstance(val, str) and val:
            return val
    return (
        sel.css("[data-testid='heading-product-title']::text").get()
        or sel.css("h1::text").get()
    )


def _extract_seller(next_data: dict | None, sel: Selector) -> str | None:
    if next_data:
        val = _get_at_path(next_data, *_SELLER_PATHS)
        if isinstance(val, str) and val:
            return val
    return sel.css("[data-testid='seller-name']::text").get()


def _extract_product_id(url: str) -> str | None:
    match = _PRODUCT_ID_RE.search(url)
    return match.group(1).upper() if match else None
