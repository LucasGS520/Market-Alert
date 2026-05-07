"""
Ponto de entrada do microserviço market_scraper.

Serviço stateless que extrai preço/disponibilidade/título de qualquer URL de e-commerce.
Fluxo: coletar HTML (HTTP → Playwright fallback) → pipeline de parsing em cascata.

Endpoints:
    POST /scraper/parse → extrai dados de produto de uma URL
    GET  /health        → verifica se o serviço está rodando
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import AnyHttpUrl, BaseModel

from app.scraping.collector import CollectionError, fetch_html
from app.scraping.extractor import extract_product

# Desabilita access logs do Uvicorn (--health checks são muito verbosos)
logging.getLogger("uvicorn.access").disabled = True

logger = structlog.get_logger()

app = FastAPI(
    title="market_scraper",
    version="0.3.0",
    description="Microserviço stateless de extração de preços via pipeline genérico.",
    docs_url="/docs",
)

_MARKETPLACE_PATTERNS: dict[str, str] = {
    "mercadolivre": "mercadolivre",
    "mercadolibre": "mercadolivre",
    "shopee": "shopee",
    "magazineluiza": "magalu",
    "magalu": "magalu",
    "americanas": "americanas",
    "amazon": "amazon",
    "casasbahia": "casasbahia",
}


class ParseRequest(BaseModel):
    url: AnyHttpUrl


class ParseResponse(BaseModel):
    marketplace: str
    price: Decimal
    available: bool
    title: str | None = None
    seller: str | None = None
    currency: str | None = None
    collected_at: datetime


def _detect_marketplace(url: str) -> str:
    url_lower = url.lower()
    for pattern, name in _MARKETPLACE_PATTERNS.items():
        if pattern in url_lower:
            return name
    return "generic"


@app.get("/health", tags=["infraestrutura"])
async def health() -> dict:
    return {"status": "ok"}


@app.post("/scraper/parse", response_model=ParseResponse, tags=["scraping"])
async def parse_url(body: ParseRequest) -> ParseResponse:
    """
    Extrai preço e dados de produto de uma URL.

    Coleta o HTML (HTTP com curl_cffi, Playwright como fallback) e aplica
    4 estratégias de extração em cascata: JSON-LD → CSS → regex → OG.
    """
    url = str(body.url)
    marketplace = _detect_marketplace(url)
    logger.info("requisicao_parse", url=url, marketplace=marketplace)

    try:
        html, metodo = await fetch_html(url)
        dados = extract_product(html, url)
    except CollectionError as exc:
        logger.warning("coleta_falhou", url=url, motivo=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        logger.warning("extracao_falhou", url=url, motivo=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("erro_inesperado_parse", url=url, erro=str(exc))
        raise HTTPException(status_code=500, detail="Erro interno no scraper")

    logger.info(
        "parse_sucesso",
        url=url,
        marketplace=marketplace,
        preco=str(dados["price"]),
        metodo_coleta=metodo,
    )
    return ParseResponse(
        marketplace=marketplace,
        price=Decimal(str(dados["price"])),
        available=bool(dados.get("is_available", True)),
        title=dados.get("name"),
        seller=None,
        currency=dados.get("currency"),
        collected_at=datetime.now(timezone.utc),
    )
