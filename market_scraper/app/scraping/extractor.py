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
    # CAPTCHA clássico
    "recaptcha",
    "hcaptcha",
    "areyouhuman",
    "robot-detection",
    # Cloudflare
    "cf-challenge",
    "challenge-running",
    "cf_chl_",
    "cf-browser-verification",
    "cloudflare ray id",
    "__cf_bm",
    # DataDome
    "datadome",
    # PerimeterX
    "px_captcha",
    "_pximg",
    # Imperva / Incapsula
    "incapsula",
)

_CAPTCHA_TITLES = (
    "just a moment",
    "acesso negado",
    "access denied",
    "security check",
    "verificação de segurança",
    "verificacao de seguranca",
)

# Padrões exclusivos de páginas de produto renderizadas — presença garante que não é CAPTCHA.
# Strings do design system ML que nunca aparecem em telas de bloqueio.
_PRODUCT_CONTENT_INDICATORS = (
    "ui-pdp-title",
    "poly-component__price",
    "andes-money-amount",
    '"@type":"product"',
    '"@type": "product"',
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
    """Retorna True se o HTML contém indicadores conhecidos de CAPTCHA ou challenge."""
    if not html:
        return False
    html_lower = html.lower()
    # Short-circuit: conteúdo inequívoco de produto descarta qualquer indicador de CAPTCHA.
    # Scripts de monitoramento (Cloudflare BM, PerimeterX) aparecem em páginas normais do ML;
    # elementos do design system ML nunca aparecem em telas de bloqueio reais.
    if any(ind in html_lower for ind in _PRODUCT_CONTENT_INDICATORS):
        return False
    if any(ind in html_lower for ind in _CAPTCHA_INDICATORS):
        return True
    # Verifica <title> — sistemas como Cloudflare retornam 200 com título de challenge
    title_match = re.search(r"<title[^>]*>([^<]{1,120})</title>", html, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).lower()
        if any(t in title for t in _CAPTCHA_TITLES):
            return True
    return False
