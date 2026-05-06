"""
Adapter Shopee Brasil.

Estratégia: chama a API interna do frontend `shopee.com.br/api/v4/item/get`
com os headers que o próprio browser Shopee envia. Retorna JSON diretamente —
sem parsing de HTML nem Playwright.

Proteção anti-bot da Shopee é contornada usando curl_cffi (fingerprint TLS
idêntico ao Chrome real) combinado com os headers corretos de origem.

Extração de IDs:
    URL padrão: https://shopee.com.br/{shop_slug}/{product_slug}-i.{shop_id}.{item_id}
    Ex: https://shopee.com.br/vendedor/nome-produto-i.123456789.987654321

Preço:
    Shopee armazena preços como inteiros × 100000.
    Ex: price=19900000 → R$ 199,00
"""

import re
from decimal import Decimal

import structlog
from curl_cffi.requests import AsyncSession

from app.adapters.base import BaseAdapter, ProductData
from app.core.config import settings
from app.scraping.collector import CollectionError

logger = structlog.get_logger()

_RE_IDS = re.compile(r"-i\.(\d+)\.(\d+)")
_API_URL = "https://shopee.com.br/api/v4/item/get"
_PRICE_DIVISOR = Decimal("100000")
_TIMEOUT = 15

# Headers que o frontend Shopee envia para sua própria API
_HEADERS = {
    "Referer": "https://shopee.com.br/",
    "x-api-source": "pc",
    "x-shopee-language": "pt-BR",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


class ShopeeAdapter(BaseAdapter):
    @classmethod
    def matches(cls, url: str) -> bool:
        return "shopee.com.br" in url

    async def fetch(self, url: str) -> ProductData:
        shop_id, item_id = self._extract_ids(url)

        async with AsyncSession(impersonate="chrome120") as session:
            response = await session.get(
                _API_URL,
                params={"itemid": item_id, "shopid": shop_id},
                headers={**_HEADERS, "User-Agent": settings.user_agent},
                timeout=_TIMEOUT,
            )

        if response.status_code != 200:
            raise CollectionError(
                f"API Shopee retornou HTTP {response.status_code} "
                f"para shopid={shop_id} itemid={item_id}"
            )

        payload = response.json()
        item = payload.get("data") or payload.get("item")
        if not item:
            error_msg = payload.get("error_msg") or payload.get("msg") or "sem dados"
            raise CollectionError(f"API Shopee não retornou item ({error_msg}): {url}")

        logger.debug("shopee_api_ok", shop_id=shop_id, item_id=item_id)
        return self._parse_item(item, url)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_ids(self, url: str) -> tuple[str, str]:
        match = _RE_IDS.search(url)
        if not match:
            raise CollectionError(f"Não foi possível extrair IDs da URL Shopee: {url}")
        return match.group(1), match.group(2)  # shop_id, item_id

    def _parse_item(self, item: dict, url: str) -> ProductData:
        # Shopee expõe price_min (menor variação) e price (default)
        raw_price = item.get("price") or item.get("price_min")
        if raw_price is None:
            raise CollectionError(f"Campo de preço ausente na resposta Shopee: {url}")

        price = Decimal(str(raw_price)) / _PRICE_DIVISOR

        stock = item.get("stock", 0)
        status = item.get("status", 1)
        available = int(stock) > 0 and int(status) == 1

        # shop_name vem no payload quando o produto inclui dados do seller
        seller = item.get("shop_name") or item.get("brand") or None

        return ProductData(
            marketplace="shopee",
            price=price,
            available=available,
            title=item.get("name"),
            seller=seller,
            currency="BRL",
        )
