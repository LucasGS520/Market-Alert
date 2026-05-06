"""
Dispatcher: roteia uma URL para o adapter correto.

Ordem de tentativa:
  1. Verifica cada adapter registrado em _ADAPTERS (primeiro match vence)
  2. Se nenhum reconhece a URL, cai no fallback HTML (collector + parser)
"""

from decimal import Decimal

from app.adapters.base import BaseAdapter, ProductData
from app.adapters.magalu import MagaluAdapter
from app.adapters.mercadolivre import MercadoLivreAdapter
from app.adapters.shopee import ShopeeAdapter

_ADAPTERS: list[type[BaseAdapter]] = [
    MercadoLivreAdapter,
    MagaluAdapter,
    ShopeeAdapter,
]


async def dispatch(url: str) -> ProductData:
    for adapter_cls in _ADAPTERS:
        if adapter_cls.matches(url):
            return await adapter_cls().fetch(url)
    return await _html_fallback(url)


async def _html_fallback(url: str) -> ProductData:
    from app.scraping.parser import collect_and_parse

    dados = await collect_and_parse(url)
    return ProductData(
        marketplace="generic",
        price=Decimal(str(dados["price"])),
        available=bool(dados.get("is_available", True)),
        title=dados.get("name"),
        currency=dados.get("currency"),
    )
