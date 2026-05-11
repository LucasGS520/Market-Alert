"""Classificação centralizada de erros do scraper."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScraperErrorClassification:
    """Resultado da classificação de um erro do scraper."""

    status: str        # "error" | "unavailable" | "unsupported"
    action: str        # "retry_with_backoff" | "retry_later" | "no_retry"
    domain_cooldown: bool  # True → ativar cooldown no domínio após este erro


_ERROR_MAP: dict[str, ScraperErrorClassification] = {
    "CAPTCHA_DETECTED":          ScraperErrorClassification("error",       "retry_with_backoff", True),
    "BLOCKED":                   ScraperErrorClassification("error",       "retry_with_backoff", True),
    "PRICE_NOT_FOUND":           ScraperErrorClassification("error",       "retry_later",        False),
    "LAYOUT_CHANGED":            ScraperErrorClassification("error",       "retry_later",        False),
    "TIMEOUT":                   ScraperErrorClassification("error",       "retry_with_backoff", False),
    "MARKETPLACE_NOT_SUPPORTED": ScraperErrorClassification("unsupported", "no_retry",           False),
    "UNAVAILABLE":               ScraperErrorClassification("unavailable", "retry_later",        False),
    "REDIRECT":                  ScraperErrorClassification("error",       "retry_later",        False),
}

_DEFAULT = ScraperErrorClassification("error", "retry_later", False)

# Mantidos para compatibilidade até refatoração da Fase 2
ERROS_BLOQUEIO = {"CAPTCHA_DETECTED", "BLOCKED"}
ERROS_NAO_SUPORTADO = {"MARKETPLACE_NOT_SUPPORTED"}


def classify_scraper_error(error_code: str) -> ScraperErrorClassification:
    """Retorna classificação completa: status operacional, ação e se deve aplicar domain cooldown."""
    return _ERROR_MAP.get(error_code, _DEFAULT)


def classify_error(error_code: str) -> str:
    """Retorna categoria do erro: 'BLOCKED', 'UNAVAILABLE', 'UNSUPPORTED' ou 'SEMANTIC_ERROR'.

    Mantida para compatibilidade com código legado — prefira classify_scraper_error.
    """
    cls = classify_scraper_error(error_code)
    if cls.domain_cooldown:
        return "BLOCKED"
    if cls.status == "unavailable":
        return "UNAVAILABLE"
    if cls.status == "unsupported":
        return "UNSUPPORTED"
    return "SEMANTIC_ERROR"
