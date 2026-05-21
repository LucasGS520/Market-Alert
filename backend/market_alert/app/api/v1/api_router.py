"""
Router principal da API v1.

Agrupa todos os sub-routers sob o prefixo /api/v1.
Cada módulo de router é responsável por um domínio específico do sistema.
"""

from fastapi import APIRouter

from app.api.v1 import (
    comparisons_routes,
    competitors_routes,
    monitored_routes,
    notifications_routes,
    price_history_routes,
)

# Router central que será incluído no app FastAPI
router = APIRouter(prefix="/api/v1")

router.include_router(monitored_routes.router)             # /api/v1/monitored/...
router.include_router(competitors_routes.router)           # /api/v1/competitors/...
router.include_router(competitors_routes.router_nested)    # /api/v1/monitored/{monitored_id}/competitors/...
router.include_router(comparisons_routes.router)           # /api/v1/comparisons/...
router.include_router(price_history_routes.router)         # /api/v1/price-history/...
router.include_router(notifications_routes.router)         # /api/v1/notifications/...
