import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse, urlunparse

import structlog
from parsel import Selector
from playwright.async_api import Page

from app.adapters.base import MarketplaceAdapter
from app.core.config import settings
from app.scraping.extractor import extract_jsonld, extract_script_json
from app.schemas import (
    CONFIDENCE_MIN,
    CollectedPage,
    ErrorCode,
    ExtractionMethod,
    ScrapeError,
    ScrapeResult,
)

logger = structlog.get_logger()

_PRODUCT_ID_RE = re.compile(r"MLB[A-Z]?-?\d+", re.IGNORECASE)


def _normalize_ml_url(url: str) -> str:
    """Redireciona produto.mercadolivre.com.br para www — o subdomínio de anúncios tem proteção mais agressiva."""
    parsed = urlparse(url)
    if parsed.netloc == "produto.mercadolivre.com.br":
        parsed = parsed._replace(netloc="www.mercadolivre.com.br")
        return urlunparse(parsed)
    return url

# Chaves de preço a buscar no JSON de hidratação
_PRICE_KEYS = frozenset({"price", "sale_price", "amount", "value", "currentprice"})
# Contextos de parcela — descartados na busca recursiva
_INSTALLMENT_KEYS = frozenset({"installment", "installments", "parcela", "parcelas", "monthly"})


class MercadoLivreAdapter(MarketplaceAdapter):
    marketplace = "mercadolivre"

    async def collect(self, url: str) -> CollectedPage:
        url = _normalize_ml_url(url)

        async def _wait(page: Page) -> None:
            try:
                # Cobre layout normal (/MLB-, /p/) e produto universal (/up/ com .poly-*)
                await page.wait_for_selector(
                    (
                        ".ui-pdp-title, .andes-money-amount__fraction, .ui-pdp-container,"
                        " .poly-component__price, .poly-price__current,"
                        " .ui-pdp-buybox__offers-item"
                    ),
                    state="visible",
                    timeout=min(settings.playwright_timeout_ms, 15000),
                )
            except Exception:
                # Prossegue mesmo sem confirmar carregamento; extract() classifica a falha
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
                message="CAPTCHA detectado na página do Mercado Livre",
            )

        if page.blocked:
            return ScrapeError(
                error_code=ErrorCode.BLOCKED,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="Acesso bloqueado (HTTP 403)",
            )

        if page.status_code == 404:
            return ScrapeError(
                error_code=ErrorCode.REDIRECT,
                marketplace=self.marketplace,
                url=page.url,
                retryable=False,
                message="Produto não encontrado (HTTP 404)",
            )

        if page.html is None:
            return ScrapeError(
                error_code=ErrorCode.PRICE_NOT_FOUND,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message=f"Falha na coleta da página: {page.error}",
            )

        sel = Selector(page.html)

        if _is_search_page(sel):
            return ScrapeError(
                error_code=ErrorCode.REDIRECT,
                marketplace=self.marketplace,
                url=page.url,
                retryable=False,
                message="URL redirecionou para página de busca ou categoria",
            )

        if _is_unavailable(sel):
            return ScrapeError(
                error_code=ErrorCode.UNAVAILABLE,
                marketplace=self.marketplace,
                url=page.url,
                retryable=False,
                message="Produto indisponível no Mercado Livre",
            )

        title = _extract_title(sel)

        # Estratégia 1: payload de rede (maior confiança)
        price, method, confidence = _extract_price_from_payloads(page.network_payloads)

        # Estratégia 1.5: JSON hidratação em <script type="application/json">
        if price is None:
            price, method, confidence = _extract_price_from_script_json(page.html)

        # Estratégia 1.7: JSON-LD schema.org/Product
        if price is None:
            price, method, confidence = _extract_price_from_jsonld(page.html)

        # Estratégia 2: DOM renderizado
        if price is None:
            price, method, confidence = _extract_price_from_dom(sel)

        if price is None or price <= 0:
            if page.html and _is_challenge_page(sel):
                await self._browser.reset_context(self.marketplace)
                return ScrapeError(
                    error_code=ErrorCode.CAPTCHA_DETECTED,
                    marketplace=self.marketplace,
                    url=page.url,
                    retryable=True,
                    message="Página sem estrutura de produto ML — possível soft-block",
                )
            return ScrapeError(
                error_code=ErrorCode.PRICE_NOT_FOUND,
                marketplace=self.marketplace,
                url=page.url,
                retryable=True,
                message="Preço não encontrado na página",
            )

        seller = _extract_seller(sel, page.html)
        thumbnail_url = _extract_thumbnail(sel, page.html)

        conf_min = CONFIDENCE_MIN.get(method, 0.70)
        if confidence < conf_min:
            logger.warning(
                "ml_confidence_abaixo_limiar",
                url=page.url,
                method=method.value,
                confidence=confidence,
                confidence_min=conf_min,
            )

        logger.info(
            "ml_extracao_sucesso",
            url=page.url,
            price=str(price),
            method=method.value,
            confidence=confidence,
            seller_missing=seller is None,
            thumbnail_missing=thumbnail_url is None,
        )

        return ScrapeResult(
            marketplace=self.marketplace,
            url=page.url,
            canonical_url=_extract_canonical(sel),
            title=title,
            price=price,
            currency="BRL",
            available=True,
            seller=seller,
            product_id=_extract_product_id(page.url),
            thumbnail_url=thumbnail_url,
            extraction_method=method,
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# Funções auxiliares de detecção
# ---------------------------------------------------------------------------

def _is_search_page(sel: Selector) -> bool:
    return bool(
        sel.css(".ui-search-results, .ui-search-layout, #search-results").get()
    )


def _is_challenge_page(sel: Selector) -> bool:
    """Página sem nenhum marker de produto ML indica soft-block ou challenge."""
    return not bool(
        sel.css(".ui-pdp-container, .andes-money-amount, .poly-card__portals, .ui-pdp-title").get()
    )


def _is_unavailable(sel: Selector) -> bool:
    buybox_html = sel.css(".ui-pdp-buybox").get() or ""
    unavail_keywords = ("indisponível", "indisponivel", "esgotado", "sem estoque")
    if any(kw in buybox_html.lower() for kw in unavail_keywords):
        return True
    return bool(sel.css(".ui-pdp-unavailable, .ui-pdp-buybox--unavailable").get())


# ---------------------------------------------------------------------------
# Extração de campos
# ---------------------------------------------------------------------------

def _extract_title(sel: Selector) -> str | None:
    return (
        sel.css(".ui-pdp-title::text").get()
        or sel.css("h1.ui-pdp-title::text").get()
        or sel.css("h1::text").get()
    )


def _extract_canonical(sel: Selector) -> str | None:
    return sel.css("link[rel='canonical']::attr(href)").get()


def _extract_seller(sel: Selector, html: str | None = None) -> str | None:
    candidate = (
        sel.css(".ui-pdp-seller__header-title::text").get()
        or sel.css(".ui-pdp-seller__info-title::text").get()
        or sel.css("[class*='seller'] [class*='title']::text").get()
        or sel.css(".ui-pdp-seller .ui-pdp-media__title::text").get()
        or sel.css("[data-testid='seller-info'] strong::text").get()
    )
    if candidate:
        return candidate.strip() or None

    if not html:
        return None
    for obj in extract_jsonld(html, url=""):
        offers = obj.get("offers")
        targets = [offers] if isinstance(offers, dict) else (offers if isinstance(offers, list) else [])
        for offer in targets:
            if not isinstance(offer, dict):
                continue
            seller = offer.get("seller")
            if isinstance(seller, dict) and seller.get("name"):
                return str(seller["name"])
    return None


def _extract_product_id(url: str) -> str | None:
    match = _PRODUCT_ID_RE.search(url)
    return match.group(0).upper().replace("-", "") if match else None


def _extract_thumbnail(sel: Selector, html: str | None = None) -> str | None:
    # Source 1: OG image — confiável e alta qualidade
    og_image = sel.css("meta[property='og:image']::attr(content)").get()
    if og_image and og_image.startswith("http"):
        return og_image

    # Source 2: JSON-LD image field
    if html:
        for obj in extract_jsonld(html, url=""):
            image = obj.get("image")
            if isinstance(image, str) and image.startswith("http"):
                return image
            if isinstance(image, list) and image:
                first = image[0]
                if isinstance(first, str) and first.startswith("http"):
                    return first
                if isinstance(first, dict) and str(first.get("url", "")).startswith("http"):
                    return str(first["url"])

    # Source 3: seletores CSS (layout padrão e universal)
    css_img = (
        sel.css(".ui-pdp-gallery__figure img::attr(src)").get()
        or sel.css(".ui-pdp-image::attr(src)").get()
        or sel.css(".poly-card__image img::attr(src)").get()
        or sel.css(".poly-component__picture img::attr(src)").get()
    )
    return css_img if css_img and css_img.startswith("http") else None


# ---------------------------------------------------------------------------
# Extração de preço — payload de rede
# ---------------------------------------------------------------------------

def _extract_price_from_payloads(
    payloads: list[dict],
) -> tuple[Decimal | None, ExtractionMethod, float]:
    for entry in payloads:
        val = _deep_find_price(entry.get("body", {}), depth=8)
        if val and val > 0:
            logger.debug("ml_preco_via_payload", price=val)
            return Decimal(str(round(val, 2))), ExtractionMethod.NETWORK_PAYLOAD, 1.0
    return None, ExtractionMethod.NETWORK_PAYLOAD, 0.0


def _deep_find_price(obj: object, depth: int) -> float | None:
    """Busca recursiva por valor de preço em JSON de hidratação do ML."""
    if depth <= 0:
        return None

    if isinstance(obj, dict):
        for key, val in obj.items():
            key_lower = key.lower()
            if any(exc in key_lower for exc in _INSTALLMENT_KEYS):
                continue
            if key_lower in _PRICE_KEYS:
                if isinstance(val, (int, float)) and val > 0:
                    return float(val)
                if isinstance(val, str):
                    try:
                        parsed = float(val.replace(",", "."))
                        if parsed > 0:
                            return parsed
                    except ValueError:
                        pass
        for key, val in obj.items():
            if any(exc in key.lower() for exc in _INSTALLMENT_KEYS):
                continue
            result = _deep_find_price(val, depth - 1)
            if result:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = _deep_find_price(item, depth - 1)
            if result:
                return result

    return None


# ---------------------------------------------------------------------------
# Extração de preço — DOM renderizado
# ---------------------------------------------------------------------------

def _extract_price_from_dom(
    sel: Selector,
) -> tuple[Decimal | None, ExtractionMethod, float]:
    # Layout padrão (/MLB-, /p/): containers específicos sem fallback global
    # — evita captura de valor de parcela fora do contexto de preço principal.
    for zone_sel in (".ui-pdp-price__second-line", ".ui-pdp-price__main-container"):
        zone = sel.css(zone_sel)
        if not zone:
            continue
        fraction = zone.css(".andes-money-amount__fraction::text").get()
        if fraction is None:
            continue
        cents_text = zone.css(".andes-money-amount__cents::text").get()
        try:
            # ML usa ponto como separador de milhar: "1.234" → 1234
            integer_part = int(fraction.replace(".", "").replace(",", ""))
            cents_part = int(cents_text) if cents_text and cents_text.isdigit() else 0
            price = Decimal(f"{integer_part}.{cents_part:02d}")
            return price, ExtractionMethod.CSS_SELECTOR, 0.85
        except (ValueError, InvalidOperation):
            pass

    # Layout produto universal (/up/MLBU): componentes poly-* com preço em texto corrido
    poly_text = (
        sel.css(".poly-price__current .andes-money-amount__fraction::text").get()
        or sel.css(".poly-component__price .andes-money-amount__fraction::text").get()
    )
    if poly_text is not None:
        poly_cents = (
            sel.css(".poly-price__current .andes-money-amount__cents::text").get()
            or sel.css(".poly-component__price .andes-money-amount__cents::text").get()
        )
        try:
            integer_part = int(poly_text.replace(".", "").replace(",", ""))
            cents_part = int(poly_cents) if poly_cents and poly_cents.isdigit() else 0
            price = Decimal(f"{integer_part}.{cents_part:02d}")
            return price, ExtractionMethod.CSS_SELECTOR, 0.80
        except (ValueError, InvalidOperation):
            pass

    return None, ExtractionMethod.CSS_SELECTOR, 0.0


# ---------------------------------------------------------------------------
# Extração de preço — JSON hidratação em script tags
# ---------------------------------------------------------------------------

def _extract_price_from_script_json(
    html: str | None,
) -> tuple[Decimal | None, ExtractionMethod, float]:
    if not html:
        return None, ExtractionMethod.HYDRATION_JSON, 0.0
    for blob in extract_script_json(html):
        val = _deep_find_price(blob, depth=10)
        if val and val > 0:
            logger.debug("ml_preco_via_script_json", price=val)
            return Decimal(str(round(val, 2))), ExtractionMethod.HYDRATION_JSON, 0.95
    return None, ExtractionMethod.HYDRATION_JSON, 0.0


# ---------------------------------------------------------------------------
# Extração de preço — JSON-LD schema.org/Product
# ---------------------------------------------------------------------------

def _extract_price_from_jsonld(
    html: str | None,
) -> tuple[Decimal | None, ExtractionMethod, float]:
    if not html:
        return None, ExtractionMethod.SSR_STATE, 0.0
    for obj in extract_jsonld(html, url=""):
        offers = obj.get("offers") or obj.get("Offers")
        if isinstance(offers, dict):
            price_raw = offers.get("price") or offers.get("lowPrice")
        elif isinstance(offers, list) and offers:
            price_raw = offers[0].get("price")
        else:
            price_raw = obj.get("price")
        if price_raw is not None:
            try:
                val = float(str(price_raw).replace(",", "."))
                if val > 0:
                    logger.debug("ml_preco_via_jsonld", price=val)
                    return Decimal(str(round(val, 2))), ExtractionMethod.SSR_STATE, 0.92
            except (ValueError, TypeError):
                continue
    return None, ExtractionMethod.SSR_STATE, 0.0
