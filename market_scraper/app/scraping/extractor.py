"""
Utilitários de parsing compartilhados entre adapters.

Estas funções operam sobre HTML ou texto bruto e retornam dados não processados —
nenhuma delas toma decisões de negócio ou classifica falhas.
"""

import json
import re
from decimal import Decimal, InvalidOperation

import extruct
import structlog
from bs4 import BeautifulSoup
from price_parser import Price

logger = structlog.get_logger()

_CAPTCHA_INDICATORS = (
    "recaptcha",
    "hcaptcha",
    "cf-challenge",
    "areyouhuman",
    "robot-detection",
    "challenge-running",
)


def parse_price_string(text: str) -> Decimal | None:
    """Normaliza uma string de preço para Decimal, suportando formatos BR e EN."""
    if not text:
        return None
    amount = Price.fromstring(text).amount
    if amount is None or amount <= 0:
        return None
    try:
        return Decimal(str(amount))
    except InvalidOperation:
        return None


def extract_jsonld(html: str, url: str = "") -> list[dict]:
    """
    Extrai todos os itens JSON-LD do HTML.

    Returns:
        Lista de dicts com os objetos JSON-LD encontrados (pode ser vazia).
    """
    try:
        data = extruct.extract(
            html,
            base_url=url,
            syntaxes=["json-ld"],
            uniform=True,
        )
        return data.get("json-ld", [])
    except Exception as exc:
        logger.debug("extract_jsonld_falhou", erro=str(exc))
        return []


def extract_script_json(html: str) -> list[dict]:
    """
    Extrai objetos JSON de todas as tags <script type="application/json">.

    Returns:
        Lista de dicts com os objetos JSON encontrados (pode ser vazia).
    """
    results: list[dict] = []
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", type="application/json"):
        src = tag.string
        if not src or len(src) < 10:
            continue
        try:
            obj = json.loads(src)
            if isinstance(obj, dict):
                results.append(obj)
        except (json.JSONDecodeError, ValueError):
            continue
    return results


def detect_captcha(html: str) -> bool:
    """Retorna True se o HTML contém indicadores conhecidos de CAPTCHA."""
    if not html:
        return False
    html_lower = html.lower()
    return any(ind in html_lower for ind in _CAPTCHA_INDICATORS)
