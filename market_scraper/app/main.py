import asyncio
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from pydantic import AnyHttpUrl, BaseModel

from app.core.config import settings
from app.router import MarketplaceRouter
from app.schemas import ErrorCode, ScrapeError, ScrapeResult
from app.scraping.browser import BrowserSession

# Suprime access logs do Uvicorn (health checks são muito frequentes)
logging.getLogger("uvicorn.access").disabled = True

logger = structlog.get_logger()

_router = MarketplaceRouter()


class ParseRequest(BaseModel):
    url: AnyHttpUrl


@asynccontextmanager
async def lifespan(app: FastAPI):
    browser = BrowserSession()
    await browser.start()
    app.state.browser = browser
    logger.info("market_scraper_iniciado")
    yield
    await browser.close_all()
    logger.info("market_scraper_encerrado")


app = FastAPI(
    title="market_scraper",
    version="1.0.0",
    description="Microserviço de extração de preços por adapters de marketplace.",
    docs_url="/docs",
    lifespan=lifespan,
)


@app.get("/health", tags=["infraestrutura"])
async def health(request: Request) -> dict:
    browser: BrowserSession = request.app.state.browser
    if browser._browser is None or not browser._browser.is_connected():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "reason": "browser not initialized"},
        )
    return {"status": "ok", "browser": "ready"}


@app.post("/scraper/parse", response_model=ScrapeResult, tags=["scraping"])
async def parse_url(body: ParseRequest, request: Request) -> ScrapeResult:
    """
    Extrai preço e dados de produto de uma URL de marketplace suportado.

    Marketplace suportado: mercadolivre.
    URLs fora desse domínio retornam 422 com MARKETPLACE_NOT_SUPPORTED.
    """
    url = str(body.url)
    marketplace = _router.detect(url)

    if marketplace is None:
        logger.warning("marketplace_nao_suportado", url=url)
        raise HTTPException(
            status_code=422,
            detail=ScrapeError(
                error_code=ErrorCode.MARKETPLACE_NOT_SUPPORTED,
                marketplace="unknown",
                url=url,
                retryable=False,
                message="Marketplace não suportado. Suportado: mercadolivre",
            ).model_dump(),
        )

    logger.info("requisicao_parse", url=url, marketplace=marketplace)

    try:
        adapter = _router.get_adapter(marketplace, request.app.state.browser)
        result = await asyncio.wait_for(
            adapter.scrape(url),
            timeout=settings.max_total_request_seconds,
        )
    except asyncio.TimeoutError:
        logger.error(
            "timeout_global_parse",
            url=url,
            marketplace=marketplace,
            timeout=settings.max_total_request_seconds,
        )
        raise HTTPException(
            status_code=504,
            detail=ScrapeError(
                error_code=ErrorCode.TIMEOUT,
                marketplace=marketplace,
                url=url,
                retryable=True,
                message="Scraper timeout: operação excedeu o limite de tempo",
            ).model_dump(),
        )
    except Exception as exc:
        logger.error("erro_inesperado_parse", url=url, marketplace=marketplace, erro=str(exc))
        raise HTTPException(status_code=500, detail="Erro interno no scraper")

    if isinstance(result, ScrapeError):
        logger.warning(
            "parse_com_erro",
            url=url,
            marketplace=marketplace,
            error_code=result.error_code.value,
        )
        raise HTTPException(status_code=422, detail=result.model_dump())

    logger.info(
        "parse_sucesso",
        url=url,
        marketplace=marketplace,
        price=str(result.price),
        method=result.extraction_method.value,
        confidence=result.confidence,
    )
    return result
