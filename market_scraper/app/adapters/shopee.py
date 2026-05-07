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

# Shopee armazena preços como inteiros × 100.000 (ex.: 4990000 → R$49,90)
_SHOPEE_PRICE_DIVISOR = Decimal("100000")

# Extrai seller_id e item_id de URLs como /Product-i.SELLER.ITEM
_ITEM_ID_RE = re.compile(r"i\.(\d+)\.(\d+)")

# Status de item na API Shopee: 1 = normal (disponível)
_STATUS_NORMAL = 1


class ShopeeAdapter(MarketplaceAdapter):
    marketplace = "shopee"

    async def collect(self, url: str) -> CollectedPage:
        async def _wait(page: Page) -> None:
            try:
                # Aguarda especificamente a resposta da API de produto.
                # O _on_response em navigate_and_collect captura o body independentemente;
                # este wait apenas sincroniza o timing para não sair antes do API call.
                await page.wait_for_response(
                    lambda r: "/api/v4/pdp/get_pc" in r.url or "/api/v4/item/get" in r.url,
                    timeout=12000,
                )
            except Exception:
                # Fallback se o endpoint não vier (CAPTCHA, produto indisponível, etc.)
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=4000)
                except Exception:
                    pass

        return await self._browser.navigate_and_collect(
            url=url,
            marketplace=self.marketplace,
            wait_condition=_wait,
        )

    async def extract(self, page: CollectedPage) -> ScrapeResult | ScrapeError:
        if page.captcha_detected:
            return ScrapeError(
                error_code=ErrorCode.CAPTCHA_DETECTED,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="CAPTCHA detectado na página da Shopee",
            )

        if page.blocked:
            return ScrapeError(
                error_code=ErrorCode.BLOCKED,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="Acesso bloqueado (HTTP 403)",
            )

        # Estratégia 1: payload de rede /api/v4/pdp/get_pc (checado ANTES do html guard,
        # pois o interceptor de resposta captura payloads mesmo quando a navegação falha/timeout)
        payload_result = _extract_from_payload(page.network_payloads)

        if payload_result is not None:
            price, title, seller_id, item_id, available = payload_result

            if not available:
                return ScrapeError(
                    error_code=ErrorCode.UNAVAILABLE,
                    marketplace=self.marketplace,
                    url=page.url,
                    retryable=False,
                    message="Produto sem estoque na Shopee",
                )

            if price is None or price <= 0:
                return ScrapeError(
                    error_code=ErrorCode.PRICE_NOT_FOUND,
                    marketplace=self.marketplace,
                    url=page.url,
                    retryable=True,
                    message="Preço ausente no payload da Shopee",
                )

            logger.info(
                "shopee_extracao_sucesso",
                url=page.url,
                price=str(price),
                method=ExtractionMethod.NETWORK_PAYLOAD.value,
            )

            return ScrapeResult(
                marketplace=self.marketplace,
                url=page.url,
                canonical_url=None,
                title=title,
                price=price,
                currency="BRL",
                available=True,
                seller=None,
                product_id=item_id,
                extraction_method=ExtractionMethod.NETWORK_PAYLOAD,
                confidence=1.0,
            )

        if page.html is None:
            return ScrapeError(
                error_code=ErrorCode.PRICE_NOT_FOUND,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message=f"Falha na coleta da página (sem payload e sem html): {page.error}",
            )

        # Estratégia 2: DOM renderizado (seletores específicos da Shopee)
        sel = Selector(page.html)
        price, title = _extract_from_dom(sel)

        if price is None or price <= 0:
            return ScrapeError(
                error_code=ErrorCode.PRICE_NOT_FOUND,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="Preço não encontrado na página da Shopee (payload e DOM falharam)",
            )

        seller_id_url, item_id_url = _extract_ids_from_url(page.url)

        logger.info(
            "shopee_extracao_sucesso",
            url=page.url,
            price=str(price),
            method=ExtractionMethod.CSS_SELECTOR.value,
        )

        return ScrapeResult(
            marketplace=self.marketplace,
            url=page.url,
            canonical_url=None,
            title=title,
            price=price,
            currency="BRL",
            available=True,
            seller=None,
            product_id=item_id_url,
            extraction_method=ExtractionMethod.CSS_SELECTOR,
            confidence=0.7,
        )


# ---------------------------------------------------------------------------
# Extração via payload de rede
# ---------------------------------------------------------------------------

def _extract_from_payload(
    payloads: list[dict],
) -> tuple[Decimal | None, str | None, str | None, str | None, bool] | None:
    """
    Retorna (price, title, seller_id, item_id, available) ou None se nenhum
    payload relevante foi capturado.
    """
    for entry in payloads:
        body = entry.get("body", {})
        if not isinstance(body, dict):
            continue

        data = body.get("data")
        logger.debug(
            "shopee_payload_keys",
            top_keys=list(body.keys()),
            data_keys=list(data.keys()) if isinstance(data, dict) else None,
            data_item_keys=list(data["item"].keys()) if isinstance(data, dict) and isinstance(data.get("item"), dict) else None,
        )

        # Tenta todos os caminhos conhecidos da API Shopee em ordem de confiabilidade
        item = (
            _get_nested(body, "data", "item")
            or _get_nested(body, "data", "result", "item")
            or _get_nested(body, "data", "item_brief")
            or _get_nested(body, "item")
        )

        if item and isinstance(item, dict):
            price_raw = item.get("price_min") or item.get("price")
            if price_raw and isinstance(price_raw, (int, float)) and price_raw > 0:
                try:
                    price = Decimal(str(price_raw)) / _SHOPEE_PRICE_DIVISOR
                    title = item.get("name") or item.get("title")
                    item_id = str(item.get("itemid") or item.get("item_id") or "")
                    seller_id = str(item.get("shopid") or item.get("shop_id") or "")
                    status = item.get("status", _STATUS_NORMAL)
                    stock = item.get("stock", 1)
                    available = (status == _STATUS_NORMAL) and (stock > 0)
                    return price, title, seller_id, item_id or None, available
                except InvalidOperation:
                    pass

        # Caminho 2: busca recursiva fallback — tolerante a variações de estrutura da API
        price_raw = _deep_find_price_shopee(body, depth=6)
        if price_raw and price_raw > 0:
            try:
                price = Decimal(str(price_raw)) / _SHOPEE_PRICE_DIVISOR
                if price > 0:
                    _, item_id_url = _extract_ids_from_url(entry.get("url", ""))
                    logger.debug("shopee_preco_via_busca_recursiva", price=str(price))
                    return price, None, None, item_id_url, True
            except InvalidOperation:
                pass

    return None


# Chaves de preço relevantes no JSON da Shopee
_SHOPEE_PRICE_KEYS = frozenset({"price", "price_min", "current_price", "discounted_price"})
# Contextos a ignorar (parcelas, preço antigo)
_SHOPEE_EXCLUDE_KEYS = frozenset({"original_price", "price_before_discount", "slash_price", "installment"})


def _deep_find_price_shopee(obj: object, depth: int) -> float | None:
    """Busca recursiva por valor de preço inteiro (formato Shopee × 100.000) no payload."""
    if depth <= 0:
        return None

    if isinstance(obj, dict):
        for key, val in obj.items():
            key_lower = key.lower()
            if any(exc in key_lower for exc in _SHOPEE_EXCLUDE_KEYS):
                continue
            if key_lower in _SHOPEE_PRICE_KEYS and isinstance(val, (int, float)) and val > 0:
                return float(val)
        for key, val in obj.items():
            if any(exc in key.lower() for exc in _SHOPEE_EXCLUDE_KEYS):
                continue
            result = _deep_find_price_shopee(val, depth - 1)
            if result:
                return result

    elif isinstance(obj, list):
        for item in obj[:10]:
            result = _deep_find_price_shopee(item, depth - 1)
            if result:
                return result

    return None


def _get_nested(obj: dict, *keys: str) -> object | None:
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


# ---------------------------------------------------------------------------
# Extração via DOM renderizado
# ---------------------------------------------------------------------------

def _extract_from_dom(
    sel: Selector,
) -> tuple[Decimal | None, str | None]:
    # Shopee usa nomes de classes gerados/hash, então tentamos múltiplos padrões
    price_text = (
        sel.css("[class*='price-box'] [class*='current']::text").get()
        or sel.css("[class*='product-price'] [class*='price']::text").get()
        or sel.css("[class*='prd-price']::text").get()
        # Fallback: meta OG (geralmente presente em páginas de produto)
        or sel.css("meta[property='og:price:amount']::attr(content)").get()
    )

    title = (
        sel.css("[class*='product-name'] span::text").get()
        or sel.css("meta[property='og:title']::attr(content)").get()
        or sel.css("h1::text").get()
    )

    if price_text is None:
        return None, title

    price = parse_price_string(price_text)
    return price, title


def _extract_ids_from_url(url: str) -> tuple[str | None, str | None]:
    match = _ITEM_ID_RE.search(url)
    if match:
        return match.group(1), match.group(2)
    return None, None
