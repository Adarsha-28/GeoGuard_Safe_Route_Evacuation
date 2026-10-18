"""GeoGuard API Routers Package."""

from backend.api.alerts import router as alerts_router
from backend.api.grids import router as grids_router
from backend.api.health import router as health_router
from backend.api.intelligence import router as intelligence_router
from backend.api.operations import router as operations_router
from backend.api.predictions_v5 import router as predictions_v5_router
from backend.api.priorities import router as priorities_router
from backend.api.risk import router as risk_router
from backend.api.routes import router as routes_router
from backend.api.shelters import router as shelters_router
from backend.api.timeline import router as timeline_router
from backend.api.trends import router as trends_router
from backend.api.v6 import router as v6_router
from backend.api.weather import router as weather_router

__all__ = [
    "alerts_router",
    "grids_router",
    "health_router",
    "intelligence_router",
    "operations_router",
    "predictions_v5_router",
    "priorities_router",
    "risk_router",
    "routes_router",
    "shelters_router",
    "timeline_router",
    "trends_router",
    "v6_router",
    "weather_router",
]

