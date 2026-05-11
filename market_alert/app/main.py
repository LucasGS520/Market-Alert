"""
Ponto de entrada da aplicação FastAPI — market_alert.

Este arquivo inicializa o servidor web, configura os middlewares e registra
todos os routers. É o primeiro arquivo carregado pelo Uvicorn.

Para iniciar localmente (fora do Docker):
    uvicorn app.main:app --reload --port 8000

Swagger UI disponível em: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router
from app.infra.database import engine

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    startup:  loga que o servidor está pronto
    shutdown: encerra o pool de conexões com o banco de forma limpa
    """
    logger.info("market_alert_iniciando")
    yield
    # Fecha todas as conexões do pool ao desligar o servidor
    await engine.dispose()
    logger.info("market_alert_encerrado")


app = FastAPI(
    title="market_alert",
    version="0.1.0",
    description=(
        "Plataforma local de monitoramento e comparação de preços em e-commerce. "
        "Cadastre URLs de produtos, acompanhe preços de concorrentes e receba alertas."
    ),
    lifespan=lifespan,
)

# CORS permissivo para uso local (empresa na mesma rede)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra todos os endpoints sob /api/v1
app.include_router(router)


@app.get("/health", tags=["infraestrutura"])
async def health() -> dict:
    """Endpoint de verificação de saúde — usado pelo Docker healthcheck."""
    return {"status": "ok"}


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura exceções não tratadas e retorna JSON ao invés de HTML de erro."""
    logger.error("excecao_nao_tratada", caminho=request.url.path, erro=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor"})
