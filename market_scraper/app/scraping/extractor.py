"""
Extrator de dados de produto a partir de HTML.

Aplica 5 estratégias em cascata, todas independentes de marketplace:
    1. Dados estruturados via extruct (JSON-LD, microdata)
    2. JSON embutido em <script> tags (padrão SSR/React — ML, etc.)
    3. Seletores CSS via parsel
    4. Regex em texto livre via BeautifulSoup
    5. OpenGraph como fallback de nome

Levanta ValueError se preço não for encontrado por nenhuma estratégia.
"""

import json
import re
from decimal import Decimal

import extruct
import structlog
from bs4 import BeautifulSoup
from parsel import Selector
from price_parser import Price

logger = structlog.get_logger()

_REGEX_PRECO = re.compile(r"[\d]+(?:[.,]\d{3})*[.,]\d{2}")

_SELETORES_PRECO = [
    "meta[itemprop='price']",
    "[itemprop='price']",
    "[itemProp='price']",
    ".price",
    "#price",
    "[class*='price']",
    "[class*='Price']",
    "[class*='amount']",
    "[data-price]",
    "[data-amount]",
    ".product-price",
    ".offer-price",
]

_SCRIPT_PRECO_RE = re.compile(
    r'"(?:price|preco|valor|amount|currentPrice|salePrice|sale_price)"\s*:\s*(?:"([^"]{1,40})"|([\d]+(?:[.,]\d+)*))',
    re.IGNORECASE,
)
_SCRIPT_NOME_RE = re.compile(
    r'"(?:title|name|productName|product_name)":\s*"([^"]{5,200})"',
    re.IGNORECASE,
)

_SELETORES_DISPONIBILIDADE = [
    "[itemprop='availability']",
    ".stock",
    ".availability",
    "[class*='stock']",
    "[class*='avail']",
]

_TERMOS_EM_ESTOQUE = {"instock", "in stock", "disponível", "disponivel", "em estoque", "add to cart"}


def _extract_structured(html: str, url: str) -> dict:
    resultado: dict = {}
    try:
        dados = extruct.extract(
            html,
            base_url=url,
            syntaxes=["json-ld", "microdata", "opengraph"],
            uniform=True,
        )

        for item in dados.get("json-ld", []):
            tipo = item.get("@type")
            if isinstance(tipo, list):
                tipo = tipo[0] if tipo else None
            if tipo in ("Product", "https://schema.org/Product"):
                resultado["name"] = item.get("name")
                oferta = item.get("offers") or item.get("offer")
                if isinstance(oferta, list):
                    oferta = oferta[0]
                if isinstance(oferta, dict):
                    preco_bruto = oferta.get("price") or oferta.get("lowPrice")
                    if preco_bruto:
                        resultado["price"] = Price.fromstring(str(preco_bruto)).amount
                    disponibilidade = oferta.get("availability", "")
                    resultado["is_available"] = (
                        "InStock" in disponibilidade or "instock" in disponibilidade.lower()
                    )
                    resultado["currency"] = oferta.get("priceCurrency")
                break

        if "price" not in resultado:
            for item in dados.get("microdata", []):
                if "Product" in str(item.get("type", "")):
                    props = item.get("properties", {})
                    resultado.setdefault("name", (props.get("name") or [None])[0])
                    ofertas = props.get("offers", [])
                    if ofertas:
                        props_oferta = ofertas[0].get("properties", {})
                        preco_bruto = (props_oferta.get("price") or [None])[0]
                        if preco_bruto:
                            resultado.setdefault("price", Price.fromstring(str(preco_bruto)).amount)
                    break

        og = dados.get("opengraph", [{}])[0] if dados.get("opengraph") else {}
        resultado.setdefault("name", og.get("og:title"))

    except Exception as exc:
        logger.warning("extracao_estruturada_falhou", erro=str(exc))

    return resultado


def _find_price_in_json(data, depth: int = 0) -> "Decimal | None":
    _PRICE_KEYS = frozenset({"price", "preco", "valor", "amount", "saleprice", "currentprice", "sale_price"})
    if depth > 6:
        return None
    if isinstance(data, dict):
        for k, v in data.items():
            if k.lower() in _PRICE_KEYS:
                raw = str(v) if isinstance(v, (int, float)) else (v if isinstance(v, str) else None)
                if raw:
                    p = Price.fromstring(raw).amount
                    if p and p > Decimal("0.99"):
                        return p
            if isinstance(v, (dict, list)):
                r = _find_price_in_json(v, depth + 1)
                if r:
                    return r
    elif isinstance(data, list):
        for item in data[:10]:
            r = _find_price_in_json(item, depth + 1)
            if r:
                return r
    return None


def _extract_script_json(html: str) -> dict:
    """Extrai preço de JSON embutido em <script> tags (SSR/React apps como Mercado Livre)."""
    resultado: dict = {}
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script"):
        src = script.string
        if not src or len(src) < 20:
            continue

        if script.get("type") == "application/json":
            try:
                data = json.loads(src)
                preco = _find_price_in_json(data)
                if preco:
                    resultado["price"] = preco
                    return resultado
            except Exception:
                pass
            continue

        if "price" not in src.lower() and "preco" not in src.lower():
            continue

        for m in _SCRIPT_PRECO_RE.finditer(src):
            bruto = m.group(1) or m.group(2) or ""
            preco = Price.fromstring(bruto).amount
            if preco and preco > Decimal("0.99"):
                resultado["price"] = preco
                break

        if "price" in resultado:
            m_nome = _SCRIPT_NOME_RE.search(src)
            if m_nome:
                resultado["name"] = m_nome.group(1)
            return resultado

    return resultado


def _extract_css(html: str) -> dict:
    resultado: dict = {}
    sel = Selector(text=html)

    for css in _SELETORES_PRECO:
        for no in sel.css(css):
            bruto = (
                no.attrib.get("content")
                or no.attrib.get("data-price")
                or no.css("::text").get("")
            )
            preco = Price.fromstring(bruto or "").amount
            if preco and preco > 0:
                resultado["price"] = preco
                break
        if "price" in resultado:
            break

    for css in _SELETORES_DISPONIBILIDADE:
        no = sel.css(css).get("")
        if no:
            texto = re.sub(r"<[^>]+>", "", no).lower()
            conteudo = sel.css(f"{css}::attr(content)").get("").lower()
            combinado = texto + conteudo
            resultado["is_available"] = any(t in combinado for t in _TERMOS_EM_ESTOQUE)
            break

    return resultado


def _extract_regex(html: str) -> dict:
    resultado: dict = {}
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.find("h1")
    if h1:
        resultado["name"] = h1.get_text(strip=True)

    for no_texto in soup.find_all(string=_REGEX_PRECO):
        pai = no_texto.parent
        if pai and pai.name not in ("script", "style", "noscript"):
            for m in _REGEX_PRECO.findall(no_texto):
                preco = Price.fromstring(m).amount
                if preco and preco > Decimal("0.99"):
                    resultado["price"] = preco
                    break
        if "price" in resultado:
            break

    return resultado


def extract_product(html: str, url: str) -> dict:
    """
    Extrai dados de produto do HTML usando 5 estratégias em cascata.

    Returns:
        dict com: price (Decimal), is_available (bool), name, currency

    Raises:
        ValueError: se preço não for encontrado por nenhuma estratégia.
    """
    resultado: dict = {"currency": None, "name": None, "price": None, "is_available": None}
    estrategia: str | None = None

    dados = _extract_structured(html, url)
    resultado.update({k: v for k, v in dados.items() if v is not None})
    if resultado["price"] is not None:
        estrategia = "json-ld"

    if resultado["price"] is None:
        dados = _extract_script_json(html)
        resultado.update({k: v for k, v in dados.items() if v is not None and resultado.get(k) is None})
        if resultado["price"] is not None:
            estrategia = "script-json"

    if resultado["price"] is None:
        dados = _extract_css(html)
        resultado.update({k: v for k, v in dados.items() if v is not None and resultado.get(k) is None})
        if resultado["price"] is not None:
            estrategia = "css"

    if resultado["price"] is None:
        dados = _extract_regex(html)
        resultado.update({k: v for k, v in dados.items() if v is not None and resultado.get(k) is None})
        if resultado["price"] is not None:
            estrategia = "regex"

    if resultado["price"] is None:
        logger.warning("todas_estrategias_falharam", url=url)
        raise ValueError(f"Não foi possível extrair preço de {url}")

    if resultado["is_available"] is None:
        resultado["is_available"] = True

    logger.info(
        "extracao_sucesso",
        url=url,
        price=str(resultado["price"]),
        name=resultado.get("name"),
        estrategia=estrategia,
    )
    return resultado
