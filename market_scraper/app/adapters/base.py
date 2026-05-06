from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


@dataclass
class ProductData:
    marketplace: str
    price: Decimal
    available: bool
    title: str | None = None
    seller: str | None = None
    currency: str | None = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseAdapter(ABC):
    @classmethod
    @abstractmethod
    def matches(cls, url: str) -> bool: ...

    @abstractmethod
    async def fetch(self, url: str) -> ProductData: ...
