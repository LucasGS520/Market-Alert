from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    PRICE_NOT_FOUND = "PRICE_NOT_FOUND"
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"
    REDIRECT = "REDIRECT"
    LAYOUT_CHANGED = "LAYOUT_CHANGED"
    TIMEOUT = "TIMEOUT"
    MARKETPLACE_NOT_SUPPORTED = "MARKETPLACE_NOT_SUPPORTED"


class ExtractionMethod(str, Enum):
    HYDRATION_JSON = "hydration_json"
    NETWORK_PAYLOAD = "network_payload"
    CSS_SELECTOR = "css_selector"
    SSR_STATE = "ssr_state"


@dataclass
class CollectedPage:
    url: str
    marketplace: str
    html: str | None = None
    network_payloads: list[dict] = field(default_factory=list)
    rendered: bool = False
    blocked: bool = False
    captcha_detected: bool = False
    status_code: int | None = None
    error: str | None = None


class ScrapeResult(BaseModel):
    marketplace: str
    url: str
    canonical_url: str | None = None
    title: str | None = None
    price: Decimal
    currency: str = "BRL"
    available: bool
    seller: str | None = None
    product_id: str | None = None
    extraction_method: ExtractionMethod
    confidence: float
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScrapeError(BaseModel):
    error_code: ErrorCode
    marketplace: str
    url: str
    retryable: bool
    message: str
