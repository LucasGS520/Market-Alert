"""
Parser de HTML — extrai dados estruturados de páginas de produto.

Estratégia em três camadas (aplicadas em cascata):

    1ª — Dados estruturados (extruct):
        Extrai JSON-LD, microdata e OpenGraph do HTML.
        Sites modernos publicam dados de produto em schema.org/Product —
        este é o método mais confiável e preciso.

    2ª — Seletores CSS (parsel):
        Busca elementos com atributos semânticos comuns em e-commerces:
        [itemprop="price"], .price, #price, [data-price], etc.
        Mais frágil que dados estruturados, mas cobre muitos casos.

    3ª — BeautifulSoup + regex:
        Fallback heurístico: varre nós de texto em busca de padrões
        numéricos de preço (ex: "1.234,56" ou "1,234.56").
        Menos preciso, mas captura quando os outros métodos falham.

Normalização de preço:
    Suporta formatos brasileiro (1.234,56) e americano (1,234.56).
    Remove símbolos de moeda e espaços antes de converter para Decimal.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Literal

import extruct
import structlog
from bs4 import BeautifulSoup
from parsel import Selector

from app.scraping.collector import CollectionError, fetch_html

logger = structlog.get_logger()

# Regex para encontrar padrões de preço em texto livre
_REGEX_PRECO = re.compile(r"[\d]+(?:[.,]\d{3})*[.,]\d{2}")

# Seletores CSS comuns para elementos de preço em e-commerces
_SELETORES_PRECO = [
    "[itemprop='price']",
    "[itemProp='price']",
    ".price",
    "#price",
    "[class*='price']",
    "[class*='Price']",
    "[data-price]",
    ".product-price",
    ".offer-price",
]

# Seletores CSS para elementos de disponibilidade
_SELETORES_DISPONIBILIDADE = [
    "[itemprop='availability']",
    ".stock",
    ".availability",
    "[class*='stock']",
    "[class*='avail']",
]

# Termos que indicam "em estoque" (presença no texto = disponível)
_TERMOS_EM_ESTOQUE = {"instock", "in stock", "disponível", "disponivel", "em estoque", "add to cart"}


def _normalizar_preco(bruto: str) -> Decimal | None:
    """
    Converte uma string de preço para Decimal.

    Suporta:
        "R$ 1.234,56" → Decimal("1234.56")  (formato brasileiro)
        "1,234.56"    → Decimal("1234.56")  (formato americano)
        "99,90"       → Decimal("99.90")    (sem separador de milhar)

    Returns:
        Decimal com o valor, ou None se não for possível converter.
    """
    bruto = bruto.strip().replace("\xa0", "").replace(" ", "")
    # Remove símbolos de moeda
    bruto = re.sub(r"[R$€£¥₹]", "", bruto).strip()
    if not bruto:
        return None

    # Formato BR: "1.234,56" → "1234.56"
    if re.search(r"\.\d{3},\d{2}$", bruto):
        bruto = bruto.replace(".", "").replace(",", ".")
    # Formato US: "1,234.56" → "1234.56"
    elif re.search(r",\d{3}\.\d{2}$", bruto):
        bruto = bruto.replace(",", "")
    # Sem separador de milhar: "1234,56" → "1234.56"
    elif re.search(r",\d{2}$", bruto):
        bruto = bruto.replace(",", ".")

    try:
        return Decimal(bruto)
    except InvalidOperation:
        return None


def _extrair_dados_estruturados(html: str, url_base: str) -> dict:
    """
    Tenta extrair preço/disponibilidade de dados estruturados (JSON-LD, microdata, OpenGraph).

    Sites modernos incluem schema.org/Product com todas as informações de produto.
    Esta é a fonte mais confiável quando disponível.

    Args:
        html:     HTML completo da página.
        url_base: URL original da página (usado pelo extruct para resolver URLs relativas).

    Returns:
        Dicionário parcial com os campos encontrados (pode estar incompleto).
    """
    resultado: dict = {}
    try:
        dados = extruct.extract(
            html,
            base_url=url_base,
            syntaxes=["json-ld", "microdata", "opengraph"],
            uniform=True,
        )

        # 1ª prioridade: JSON-LD com schema.org/Product
        for item in dados.get("json-ld", []):
            if item.get("@type") in ("Product", "https://schema.org/Product"):
                resultado["name"] = item.get("name")
                oferta = item.get("offers") or item.get("offer")
                if isinstance(oferta, list):
                    oferta = oferta[0]
                if isinstance(oferta, dict):
                    preco_bruto = oferta.get("price") or oferta.get("lowPrice")
                    if preco_bruto:
                        resultado["price"] = _normalizar_preco(str(preco_bruto))
                    disponibilidade = oferta.get("availability", "")
                    resultado["is_available"] = (
                        "InStock" in disponibilidade or "instock" in disponibilidade.lower()
                    )
                    resultado["currency"] = oferta.get("priceCurrency")
                break

        # 2ª prioridade: microdata se JSON-LD não trouxe preço
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
                            resultado.setdefault("price", _normalizar_preco(str(preco_bruto)))
                    break

        # OpenGraph como fallback apenas para o nome
        og = dados.get("opengraph", [{}])[0] if dados.get("opengraph") else {}
        resultado.setdefault("name", og.get("og:title"))

    except Exception as exc:
        logger.warning("extracao_estruturada_falhou", erro=str(exc))

    return resultado


def _extrair_com_css(html: str) -> dict:
    """
    Tenta extrair preço/disponibilidade usando seletores CSS comuns.

    Args:
        html: HTML da página.

    Returns:
        Dicionário parcial com os campos encontrados.
    """
    resultado: dict = {}
    sel = Selector(text=html)

    # Tenta cada seletor de preço em ordem de confiabilidade
    for css in _SELETORES_PRECO:
        nos = sel.css(css)
        for no in nos:
            # Alguns elementos usam atributo content= (ex: itemprop="price" content="99.90")
            bruto = (
                no.attrib.get("content")
                or no.attrib.get("data-price")
                or no.css("::text").get("")
            )
            preco = _normalizar_preco(bruto or "")
            if preco and preco > 0:
                resultado["price"] = preco
                break
        if "price" in resultado:
            break

    # Verifica disponibilidade pelos seletores comuns
    for css in _SELETORES_DISPONIBILIDADE:
        no = sel.css(css).get("")
        if no:
            # Remove tags HTML e verifica o texto/atributo
            texto = re.sub(r"<[^>]+>", "", no).lower()
            conteudo = sel.css(f"{css}::attr(content)").get("").lower()
            combinado = texto + conteudo
            resultado["is_available"] = any(t in combinado for t in _TERMOS_EM_ESTOQUE)
            break

    return resultado


def _extrair_com_bs4(html: str) -> dict:
    """
    Extração heurística usando BeautifulSoup + regex — último recurso.

    Args:
        html: HTML da página.

    Returns:
        Dicionário parcial com os campos encontrados.
    """
    resultado: dict = {}
    soup = BeautifulSoup(html, "lxml")

    # Tenta extrair o nome do produto do primeiro H1
    if not resultado.get("name"):
        h1 = soup.find("h1")
        if h1:
            resultado["name"] = h1.get_text(strip=True)

    # Busca padrões de preço em nós de texto visíveis
    if "price" not in resultado:
        for no_texto in soup.find_all(string=_REGEX_PRECO):
            pai = no_texto.parent
            # Ignora scripts e estilos
            if pai and pai.name not in ("script", "style", "noscript"):
                matches = _REGEX_PRECO.findall(no_texto)
                for m in matches:
                    preco = _normalizar_preco(m)
                    # Filtra preços implausíveis (< R$ 1,00)
                    if preco and preco > Decimal("0.99"):
                        resultado["price"] = preco
                        break
            if "price" in resultado:
                break

    return resultado


async def collect_and_parse(url: str) -> dict:
    """
    Ponto de entrada principal do parser: coleta o HTML e extrai dados do produto.

    Aplica as três estratégias em cascata:
        dados estruturados → CSS → BeautifulSoup

    Args:
        url: URL do produto a ser analisado.

    Returns:
        Dicionário com: price, is_available, name, currency, method

    Raises:
        CollectionError: Se não for possível extrair preço por nenhum método.
    """
    html, metodo = await fetch_html(url)

    # Estado inicial vazio — cada camada preenche o que encontrar
    resultado: dict = {"method": metodo, "currency": None, "name": None, "price": None, "is_available": None}

    # Camada 1: dados estruturados (mais confiável)
    dados_estruturados = _extrair_dados_estruturados(html, url)
    resultado.update({k: v for k, v in dados_estruturados.items() if v is not None})

    # Camada 2: seletores CSS (se ainda falta preço)
    if resultado.get("price") is None:
        dados_css = _extrair_com_css(html)
        resultado.update({k: v for k, v in dados_css.items() if v is not None and resultado.get(k) is None})

    # Camada 3: heurística BS4 (se ainda falta preço)
    if resultado.get("price") is None:
        dados_bs4 = _extrair_com_bs4(html)
        resultado.update({k: v for k, v in dados_bs4.items() if v is not None and resultado.get(k) is None})

    if resultado.get("price") is None:
        raise CollectionError(f"Não foi possível extrair preço de {url}")

    # Se não detectou disponibilidade, assume disponível (conservador)
    if resultado.get("is_available") is None:
        resultado["is_available"] = True

    return resultado
