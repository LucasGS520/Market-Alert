from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.schemas import CollectedPage, ScrapeError, ScrapeResult

if TYPE_CHECKING:
    from app.scraping.browser import BrowserSession


class MarketplaceAdapter(ABC):
    marketplace: str

    def __init__(self, browser: "BrowserSession") -> None:
        self._browser = browser

    @abstractmethod
    async def collect(self, url: str) -> CollectedPage:
        """Coleta a página e retorna CollectedPage com html, payloads e metadados."""

    @abstractmethod
    async def extract(self, page: CollectedPage) -> ScrapeResult | ScrapeError:
        """Extrai dados estruturados de uma CollectedPage já coletada."""

    async def scrape(self, url: str) -> ScrapeResult | ScrapeError:
        page = await self.collect(url)
        return await self.extract(page)
