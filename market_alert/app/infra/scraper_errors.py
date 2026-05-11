"""Classificação centralizada de erros do scraper."""

ERROS_BLOQUEIO = {"CAPTCHA_DETECTED", "BLOCKED"}


def classify_error(error_code: str) -> str:
    """Retorna a categoria do erro: 'BLOCKED', 'UNAVAILABLE' ou 'SEMANTIC_ERROR'."""
    if error_code in ERROS_BLOQUEIO:
        return "BLOCKED"
    if error_code == "UNAVAILABLE":
        return "UNAVAILABLE"
    return "SEMANTIC_ERROR"
