"""GeoGuard V2 — FastAPI Application Entrypoint."""

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# Ensure project root is on sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.api import (
    alerts_router,
    grids_router,
    health_router,
    intelligence_router,
    operations_router,
    predictions_v5_router,
    priorities_router,
    risk_router,
    routes_router,
    shelters_router,
    timeline_router,
    trends_router,
    v6_router,
    weather_router,
)
from backend.config import FRONTEND_DIR, ROOT_DIR as CONFIG_ROOT, logger, settings
from backend.database.connection import SessionLocal, check_db_connection
from backend.services.operational_scheduler import get_operational_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown routines."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION} (V6 Flood Scenario Simulation & Resilience Intelligence)...")
    is_connected, msg = check_db_connection()
    logger.info(f"Database connection: {msg}")

    scheduler = get_operational_scheduler()
    if is_connected:
        scheduler.start()

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")
    scheduler.stop()


# Create FastAPI application
app = FastAPI(
    title="GeoGuard V6 — Flood Scenario Simulation, Adaptive Evacuation & Resilience Platform",
    description=(
        "Flood Scenario Simulation, Adaptive Evacuation & Resilience Intelligence Platform for Chennai "
        "powered by FastAPI, PostgreSQL 18, PostGIS 3.6, scikit-learn Gradient Boosting ML, multi-horizon forecasting, "
        "rainfall stress testing, spatial risk propagation, shelter stress testing, route resilience, and decision auditing."
    ),
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Standardized Error Handling
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format request validation errors consistently without exposing internals."""
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    msg = str(first_error.get("msg", "Invalid request body or query parameters."))
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    safe_errors = [
        {
            "loc": [str(x) for x in err.get("loc", [])],
            "msg": str(err.get("msg", "")),
            "type": str(err.get("type", "")),
        }
        for err in errors
    ]
    return JSONResponse(
        status_code=422,
        content={"error": f"Validation error at '{loc}': {msg}", "detail": safe_errors},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Normalize HTTPException responses into standard error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch unexpected exceptions without leaking credentials, stack traces, or file paths."""
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "An internal server error occurred."},
    )


# Include API Routers (specific sub-routes before parameterized routes)
app.include_router(health_router)
app.include_router(grids_router)
app.include_router(risk_router)
app.include_router(intelligence_router)
app.include_router(shelters_router)
app.include_router(routes_router)
app.include_router(alerts_router)
app.include_router(weather_router)
app.include_router(operations_router)
app.include_router(predictions_v5_router)
app.include_router(trends_router)
app.include_router(priorities_router)
app.include_router(timeline_router)
app.include_router(v6_router)




# Root and frontend legacy redirects
@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def root_redirect():
    """Redirect root path to interactive Leaflet frontend."""
    return RedirectResponse(url="/frontend/index.html", status_code=301)


@app.get("/web/{rest_of_path:path}", include_in_schema=False)
def legacy_web_redirect(rest_of_path: str):
    """Redirect legacy /web/* URLs to /frontend/*."""
    return RedirectResponse(url=f"/frontend/{rest_of_path}", status_code=301)


# Mount static files for frontend dashboard
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def main() -> None:
    """Launch application via Uvicorn server."""
    import uvicorn

    os.chdir(CONFIG_ROOT)
    print("=" * 65)
    print(f"   GeoGuard - Chennai Flood Risk & Safe Evacuation Platform")
    print(f"   Version: {settings.VERSION} (FastAPI + PostgreSQL/PostGIS)")
    print("=" * 65)
    print(f"\n[READY] API Documentation: http://localhost:{settings.PORT}/docs")
    print(f"[READY] Web Dashboard:     http://localhost:{settings.PORT}/frontend/index.html\n")

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
