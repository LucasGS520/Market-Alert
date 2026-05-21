import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.base import MarketplaceAdapter
    from app.scraping.browser import BrowserSession

SUPPORTED_MARKETPLACES: dict[str, list[str]] = {
    "mercadolivre": [r"mercadolivre\.com\.br", r"mercadolibre\.com"],
}


class MarketplaceRouter:
    def detect(self, url: str) -> str | None:
        for marketplace, patterns in SUPPORTED_MARKETPLACES.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return marketplace
        return None

    def get_adapter(self, marketplace: str, browser: "BrowserSession") -> "MarketplaceAdapter":
        from app.adapters.mercadolivre import MercadoLivreAdapter

        adapters = {
            "mercadolivre": MercadoLivreAdapter,
        }
        cls = adapters.get(marketplace)
        if cls is None:
            raise ValueError(f"Adapter não disponível para marketplace: {marketplace}")
        return cls(browser=browser)
