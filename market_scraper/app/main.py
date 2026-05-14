import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
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


async def _start_browser_until_ready(app: FastAPI, browser: BrowserSession) -> None:
    attempt = 0
    while True:
        attempt += 1
        app.state.browser_status = "starting"
        app.state.browser_error = None
        logger.info("browser_startup_iniciado", tentativa=attempt)

        try:
            await browser.start()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            app.state.browser_status = "failed"
            app.state.browser_error = str(exc)
            logger.error("browser_startup_falhou", tentativa=attempt, erro=str(exc))
            await browser.close_all()
            await asyncio.sleep(settings.browser_startup_retry_seconds)
            continue

        app.state.browser_status = "ready"
        app.state.browser_error = None
        logger.info("market_scraper_pronto", tentativa=attempt)
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    browser = BrowserSession()
    app.state.browser = browser
    app.state.browser_status = "starting"
    app.state.browser_error = None
    browser_startup_task = asyncio.create_task(_start_browser_until_ready(app, browser))
    app.state.browser_startup_task = browser_startup_task
    logger.info("market_scraper_api_iniciado")
    yield
    browser_startup_task.cancel()
    with suppress(asyncio.CancelledError):
        await browser_startup_task
    await browser.close_all()
    logger.info("market_scraper_encerrado")


app = FastAPI(
    title="market_scraper",
    version="1.0.0",
    description="Microserviço de extração de preços por adapters de marketplace.",
    docs_url="/docs",
    lifespan=lifespan,
)


def _ready_response(request: Request) -> dict[str, Any] | JSONResponse:
    browser: BrowserSession = request.app.state.browser
    if browser.is_ready():
        return {"status": "ok", "browser": "ready"}

    return JSONResponse(
        status_code=503,
        content={
            "status": request.app.state.browser_status,
            "browser": "not_ready",
            "reason": request.app.state.browser_error or "browser not initialized",
        },
    )


@app.get("/live", tags=["infraestrutura"])
async def live() -> dict:
    return {"status": "ok"}


@app.get("/ready", tags=["infraestrutura"], response_model=None)
async def ready(request: Request) -> dict[str, Any] | JSONResponse:
    return _ready_response(request)


@app.get("/health", tags=["infraestrutura"], response_model=None)
async def health(request: Request) -> dict[str, Any] | JSONResponse:
    return _ready_response(request)


@app.post("/scraper/parse", response_model=ScrapeResult, tags=["scraping"])
async def parse_url(body: ParseRequest, request: Request) -> ScrapeResult:
    """
    Extrai preço e dados de produto de uma URL de marketplace suportado.

    Marketplace suportado: mercadolivre.
    URLs fora desse domínio retornam 422 com MARKETPLACE_NOT_SUPPORTED.
    """
    url = str(body.url)
    marketplace = _router.detect(url)
    browser: BrowserSession = request.app.state.browser

    if not browser.is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "SCRAPER_NOT_READY",
                "retryable": True,
                "message": "Scraper ainda inicializando o browser",
            },
        )

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
        adapter = _router.get_adapter(marketplace, browser)
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
