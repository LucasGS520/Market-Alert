from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ErrorCode(str, Enum):
    PRICE_NOT_FOUND = "PRICE_NOT_FOUND"
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"
    REDIRECT = "REDIRECT"
    REDIRECT_TO_SEARCH = "REDIRECT_TO_SEARCH"
    LAYOUT_CHANGED = "LAYOUT_CHANGED"
    TIMEOUT = "TIMEOUT"
    MARKETPLACE_NOT_SUPPORTED = "MARKETPLACE_NOT_SUPPORTED"


# Matriz error_code → retryable: define se o worker deve re-enfileirar após esse erro.
# True  = erro transitório; nova tentativa pode resolver.
# False = erro semântico/estrutural; retentativa imediata não ajuda.
RETRYABLE_BY_ERROR_CODE: dict[ErrorCode, bool] = {
    ErrorCode.CAPTCHA_DETECTED: True,
    ErrorCode.BLOCKED: True,
    ErrorCode.TIMEOUT: True,
    ErrorCode.REDIRECT: True,
    ErrorCode.REDIRECT_TO_SEARCH: False,
    ErrorCode.PRICE_NOT_FOUND: False,
    ErrorCode.LAYOUT_CHANGED: False,
    ErrorCode.UNAVAILABLE: False,
    ErrorCode.MARKETPLACE_NOT_SUPPORTED: False,
}


class ExtractionMethod(str, Enum):
    HYDRATION_JSON = "hydration_json"
    NETWORK_PAYLOAD = "network_payload"
    CSS_SELECTOR = "css_selector"
    SSR_STATE = "ssr_state"


# Confidence mínima aceitável por método de extração.
# Valores abaixo do limiar indicam extração degradada: rejeitar ou re-coletar.
CONFIDENCE_MIN: dict[ExtractionMethod, float] = {
    ExtractionMethod.HYDRATION_JSON: 0.90,
    ExtractionMethod.NETWORK_PAYLOAD: 0.85,
    ExtractionMethod.SSR_STATE: 0.80,
    ExtractionMethod.CSS_SELECTOR: 0.70,
}


@dataclass
class CollectedPage:
    url: str
    marketplace: str
    final_url: str | None = None
    html: str | None = None
    network_payloads: list[dict] = field(default_factory=list)
    rendered: bool = False
    blocked: bool = False
    captcha_detected: bool = False
    status_code: int | None = None
    error: str | None = None


class ScrapeResult(BaseModel):
    """Contrato v1 de resposta de sucesso do scraper — marketplace: mercadolivre.

    Campos obrigatórios: marketplace, url, price (quando available=True), currency,
    available, extraction_method, confidence, collected_at.
    Campos opcionais: canonical_url, title, seller, product_id, thumbnail_url.

    Regra de preço: quando available=True, price deve ser > 0 em BRL.
    Quando available=False, price deve ser None.
    """

    marketplace: str
    url: str
    canonical_url: str | None = None
    title: str | None = None
    price: Decimal | None = None
    currency: str = "BRL"
    available: bool
    seller: str | None = None
    product_id: str | None = None
    thumbnail_url: str | None = None
    extraction_method: ExtractionMethod
    confidence: float
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_price_rule(self) -> "ScrapeResult":
        if self.available:
            if self.price is None or self.price <= 0:
                raise ValueError(
                    "price deve ser > 0 quando available=True. "
                    "Sem preço válido, use ScrapeError com PRICE_NOT_FOUND."
                )
        else:
            if self.price is not None and self.price != Decimal(0):
                raise ValueError(
                    "price deve ser None quando available=False."
                )
        return self


class ScrapeError(BaseModel):
    error_code: ErrorCode
    marketplace: str
    url: str
    retryable: bool
    message: str
