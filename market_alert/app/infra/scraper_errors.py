"""Classificação centralizada de erros do scraper."""

ERROS_BLOQUEIO = {"CAPTCHA_DETECTED", "BLOCKED"}
ERROS_NAO_SUPORTADO = {"MARKETPLACE_NOT_SUPPORTED"}


def classify_error(error_code: str) -> str:
    """Retorna a categoria do erro: 'BLOCKED', 'UNAVAILABLE', 'UNSUPPORTED' ou 'SEMANTIC_ERROR'."""
    if error_code in ERROS_BLOQUEIO:
        return "BLOCKED"
    if error_code == "UNAVAILABLE":
        return "UNAVAILABLE"
    if error_code in ERROS_NAO_SUPORTADO:
        return "UNSUPPORTED"
    return "SEMANTIC_ERROR"
