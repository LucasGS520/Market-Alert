"""
Adapter Magazine Luiza (Magalu).

Estratégia: extrai o bloco __NEXT_DATA__ (JSON serializado pelo Next.js)
do HTML da página. Evita DOM parsing — os dados chegam estruturados no script
de hidratação. Não há API pública oficial, mas o __NEXT_DATA__ é estável
enquanto o frontend usa Next.js.

URL padrão: https://www.magazineluiza.com.br/{slug}/p/{sku}/
"""

import json
import re
from decimal import Decimal, InvalidOperation

import structlog

from app.adapters.base import BaseAdapter, ProductData
from app.scraping.collector import CollectionError, fetch_with_http

logger = structlog.get_logger()

_RE_NEXT_DATA = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


class MagaluAdapter(BaseAdapter):
    @classmethod
    def matches(cls, url: str) -> bool:
        return "magazineluiza.com.br" in url or "magalu.com.br" in url

    async def fetch(self, url: str) -> ProductData:
        html = await fetch_with_http(url)
        next_data = self._extract_next_data(html, url)
        return self._parse_product(next_data, url)

    # ------------------------------------------------------------------
    # Extração do bloco __NEXT_DATA__
    # ------------------------------------------------------------------

    def _extract_next_data(self, html: str, url: str) -> dict:
        match = _RE_NEXT_DATA.search(html)
        if not match:
            raise CollectionError(f"__NEXT_DATA__ não encontrado em {url}")
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise CollectionError(f"__NEXT_DATA__ inválido em {url}: {exc}") from exc

    # ------------------------------------------------------------------
    # Navegação no JSON → ProductData
    # ------------------------------------------------------------------

    def _parse_product(self, data: dict, url: str) -> ProductData:
        page_props = data.get("props", {}).get("pageProps", {})

        # Magalu usa dois layouts conhecidos; tenta ambos
        product = (
            page_props.get("product")
            or page_props.get("data", {}).get("product")
            or page_props.get("initialData", {}).get("product")
            or {}
        )

        price = self._extract_price(product, page_props)
        if price is None:
            raise CollectionError(f"Preço não encontrado no __NEXT_DATA__ de {url}")

        logger.debug("magalu_parse", url=url, preco=str(price))

        return ProductData(
            marketplace="magalu",
            price=price,
            available=self._extract_availability(product, page_props),
            title=self._extract_title(product, page_props),
            seller=self._extract_seller(product, page_props),
            currency="BRL",
        )

    # ------------------------------------------------------------------
    # Helpers — tentam múltiplos caminhos para resilência a refactors
    # ------------------------------------------------------------------

    def _extract_price(self, product: dict, page_props: dict) -> Decimal | None:
        raw_price_obj = (
            product.get("price")
            or page_props.get("price")
            or {}
        )

        candidates: list = []

        if isinstance(raw_price_obj, dict):
            candidates += [
                raw_price_obj.get("sellingPrice"),
                raw_price_obj.get("bestPrice"),
                raw_price_obj.get("promotionalPrice"),
                raw_price_obj.get("originalPrice"),
            ]
        else:
            candidates.append(raw_price_obj)

        # Caminhos diretos no produto
        candidates += [
            product.get("sellingPrice"),
            product.get("bestPrice"),
        ]

        for val in candidates:
            if val is None:
                continue
            try:
                price = Decimal(str(val))
                if price > 0:
                    return price
            except InvalidOperation:
                continue

        return None

    def _extract_availability(self, product: dict, page_props: dict) -> bool:
        for key in ("available", "inStock", "isAvailable", "stock"):
            val = product.get(key)
            if val is not None:
                if isinstance(val, bool):
                    return val
                if isinstance(val, (int, float)):
                    return val > 0
                if isinstance(val, str):
                    return val.lower() not in ("false", "0", "unavailable", "out_of_stock")
        return True

    def _extract_title(self, product: dict, page_props: dict) -> str | None:
        return (
            product.get("title")
            or product.get("name")
            or product.get("description")
            or page_props.get("title")
        )

    def _extract_seller(self, product: dict, page_props: dict) -> str | None:
        seller = (
            product.get("seller")
            or product.get("sellerName")
            or page_props.get("seller")
        )
        if isinstance(seller, dict):
            return seller.get("name") or seller.get("id") or seller.get("sellerName")
        if isinstance(seller, str):
            return seller
        return None
