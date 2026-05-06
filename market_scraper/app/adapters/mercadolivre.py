"""
Adapter Mercado Livre.

Estratégia: API pública `api.mercadolibre.com/items/{id}` retorna JSON com
preço, título, disponibilidade e seller_id — sem parsing de HTML.

Extração do item ID:
    A URL sempre contém "MLB" seguido de dígitos (com ou sem hífen).
    Ex: https://www.mercadolivre.com.br/.../MLB-123456789-...
        https://produto.mercadolivre.com.br/MLB-123456789-...
        https://www.mercadolivre.com.br/p/MLB123456789
"""

import re
from decimal import Decimal

import httpx
import structlog

from app.adapters.base import BaseAdapter, ProductData
from app.scraping.collector import CollectionError

logger = structlog.get_logger()

_RE_ITEM_ID = re.compile(r"MLB-?(\d+)", re.IGNORECASE)
_API_BASE = "https://api.mercadolibre.com"
_TIMEOUT = 10


class MercadoLivreAdapter(BaseAdapter):
    @classmethod
    def matches(cls, url: str) -> bool:
        return "mercadolivre.com.br" in url or "mercadolibre.com.br" in url

    async def fetch(self, url: str) -> ProductData:
        item_id = self._extract_item_id(url)
        if not item_id:
            raise CollectionError(f"Não foi possível extrair item ID do Mercado Livre: {url}")

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            item = await self._get_item(client, item_id)
            seller = await self._get_seller_name(client, item.get("seller_id"))

        price = item.get("price")
        if price is None:
            raise CollectionError(f"API do Mercado Livre não retornou preço para {item_id}")

        return ProductData(
            marketplace="mercadolivre",
            price=Decimal(str(price)),
            available=item.get("available_quantity", 0) > 0 and item.get("status") == "active",
            title=item.get("title"),
            seller=seller,
            currency=item.get("currency_id"),
        )

    def _extract_item_id(self, url: str) -> str | None:
        match = _RE_ITEM_ID.search(url)
        if not match:
            return None
        return f"MLB{match.group(1)}"

    async def _get_item(self, client: httpx.AsyncClient, item_id: str) -> dict:
        response = await client.get(f"{_API_BASE}/items/{item_id}")
        if response.status_code != 200:
            raise CollectionError(
                f"API Mercado Livre retornou HTTP {response.status_code} para item {item_id}"
            )
        return response.json()

    async def _get_seller_name(self, client: httpx.AsyncClient, seller_id: int | None) -> str | None:
        if not seller_id:
            return None
        try:
            response = await client.get(f"{_API_BASE}/users/{seller_id}")
            if response.status_code == 200:
                return response.json().get("nickname")
        except Exception:
            pass
        return None
