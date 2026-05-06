"""
Ponto de entrada do microserviço market_scraper.

Este serviço é responsável exclusivamente por extrair dados de produto
(preço, disponibilidade, título, seller) de qualquer URL de e-commerce.
É stateless: não persiste nada, não conhece o banco de dados principal.

Fluxo de uma requisição:
    POST /scraper/parse { "url": "https://..." }
        ↓
    adapters/dispatcher.py → seleciona adapter por marketplace
        ↓
    adapter específico (ex: MercadoLivreAdapter) → API JSON interna
        ↓
    fallback: scraping/collector + parser (HTML) para URLs genéricas
        ↓
    Retorna { marketplace, price, available, title, seller, currency, collected_at }

Endpoints:
    POST /scraper/parse → extrai dados de produto de uma URL
    GET  /health        → verifica se o serviço está rodando
"""

import dataclasses
from datetime import datetime
from decimal import Decimal

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import AnyHttpUrl, BaseModel

from app.adapters.dispatcher import dispatch
from app.scraping.collector import CollectionError

logger = structlog.get_logger()

app = FastAPI(
    title="market_scraper",
    version="0.2.0",
    description="Microserviço stateless de extração de preços via adapters de marketplace.",
    docs_url="/docs",
)


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


@app.get("/health", tags=["infraestrutura"])
async def health() -> dict:
    return {"status": "ok"}


@app.post("/scraper/parse", response_model=ParseResponse, tags=["scraping"])
async def parse_url(body: ParseRequest) -> ParseResponse:
    """
    Extrai preço e dados de produto de uma URL.

    Para Mercado Livre usa a API pública `api.mercadolibre.com`.
    Para URLs genéricas faz fallback para HTML parsing.
    """
    url = str(body.url)
    logger.info("requisicao_parse", url=url)

    try:
        dados = await dispatch(url)
    except CollectionError as exc:
        logger.warning("parse_falhou", url=url, motivo=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("erro_inesperado_parse", url=url, erro=str(exc))
        raise HTTPException(status_code=500, detail="Erro interno no scraper")

    logger.info(
        "parse_sucesso",
        url=url,
        marketplace=dados.marketplace,
        preco=str(dados.price),
    )
    return ParseResponse(**dataclasses.asdict(dados))
