"""
Router principal da API v1.

Agrupa todos os sub-routers sob o prefixo /api/v1.
Cada módulo de router é responsável por um domínio específico do sistema.
"""

from fastapi import APIRouter

from app.api.v1 import comparisons, competitors, monitored, price_history

# Router central que será incluído no app FastAPI
router = APIRouter(prefix="/api/v1")

router.include_router(monitored.router)       # /api/v1/monitored/...
router.include_router(competitors.router)     # /api/v1/competitors/...
router.include_router(comparisons.router)     # /api/v1/comparisons/...
router.include_router(price_history.router)   # /api/v1/price-history/...
