"""Configuration module for GeoGuard V2."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings

# Base directories (always resolved relative to project root)
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = ROOT_DIR / "data"
FRONTEND_DIR = ROOT_DIR / "frontend"

# Data file paths
DB_PATH = DATA_DIR / "shelters.db"  # Kept for V1 SQLite data migration
GEOJSON_PATH = DATA_DIR / "processed" / "chennai_flood_risk_with_water.geojson"
PLACES_CSV_PATH = DATA_DIR / "chennai_places.csv"
RAW_BOUNDARY_PATH = DATA_DIR / "raw" / "chennai_boundary.geojson"


def _load_env_file(env_path: Path) -> None:
    """Parse .env file safely without overriding existing environment variables."""
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"[CONFIG] Warning: Failed to parse .env file: {e}")


# Load local environment configuration
_load_env_file(ROOT_DIR / ".env")


class Settings(BaseSettings):
    """Application settings validated by Pydantic."""

    APP_NAME: str = "GeoGuard"
    VERSION: str = "6.0.0"
    V4_VERSION: str = "4.0.0"
    V5_VERSION: str = "5.0.0"
    V6_VERSION: str = "6.0.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")


    # Database settings (PostgreSQL + PostGIS)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/geoguard",
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    # External service configurations
    OSRM_URL: str = os.getenv("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
    OPENMETEO_BASE_URL: str = os.getenv(
        "OPENMETEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"
    )
    HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "5.0"))
    WEATHER_SYNC_INTERVAL: int = int(os.getenv("WEATHER_SYNC_INTERVAL", "300"))
    WEATHER_SYNC_INTERVAL_SECONDS: int = int(os.getenv("WEATHER_SYNC_INTERVAL_SECONDS", os.getenv("WEATHER_SYNC_INTERVAL", "300")))
    PREDICTION_INTERVAL_SECONDS: int = int(os.getenv("PREDICTION_INTERVAL_SECONDS", "300"))

    # Operational V4 Model safety configurations
    ACTIVE_MODEL_VERSION: str = os.getenv("ACTIVE_MODEL_VERSION", "v3.0.0")
    ML_ENABLED: bool = os.getenv("ML_ENABLED", "True").lower() in ("true", "1", "yes")
    WEATHER_API_MAX_RETRIES: int = int(os.getenv("WEATHER_API_MAX_RETRIES", "3"))
    WEATHER_API_BACKOFF_FACTOR: float = float(os.getenv("WEATHER_API_BACKOFF_FACTOR", "1.5"))

    # Default Chennai Center coordinates
    CHENNAI_CENTER_LAT: float = 13.0827
    CHENNAI_CENTER_LNG: float = 80.2707

    # CORS configuration
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"extra": "ignore"}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        raw_cors = os.getenv("CORS_ORIGINS")
        if raw_cors:
            try:
                parsed = json.loads(raw_cors)
                if isinstance(parsed, list):
                    self.CORS_ORIGINS = parsed
            except Exception:
                self.CORS_ORIGINS = [o.strip() for o in raw_cors.split(",") if o.strip()]


settings = Settings()

# Module-level aliases for direct imports
HOST: str = settings.HOST
PORT: int = settings.PORT
DEBUG: bool = settings.DEBUG
DATABASE_URL: str = settings.DATABASE_URL
OSRM_URL: str = settings.OSRM_URL
OPENMETEO_BASE_URL: str = settings.OPENMETEO_BASE_URL
HTTP_TIMEOUT: float = settings.HTTP_TIMEOUT
WEATHER_SYNC_INTERVAL: int = settings.WEATHER_SYNC_INTERVAL
WEATHER_SYNC_INTERVAL_SECONDS: int = settings.WEATHER_SYNC_INTERVAL_SECONDS
PREDICTION_INTERVAL_SECONDS: int = settings.PREDICTION_INTERVAL_SECONDS
ACTIVE_MODEL_VERSION: str = settings.ACTIVE_MODEL_VERSION
ML_ENABLED: bool = settings.ML_ENABLED
WEATHER_API_MAX_RETRIES: int = settings.WEATHER_API_MAX_RETRIES
WEATHER_API_BACKOFF_FACTOR: float = settings.WEATHER_API_BACKOFF_FACTOR
CHENNAI_CENTER_LAT: float = settings.CHENNAI_CENTER_LAT
CHENNAI_CENTER_LNG: float = settings.CHENNAI_CENTER_LNG


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Configure standardized application logger without leaking credentials."""
    logger = logging.getLogger("geoguard")
    if not logger.handlers:
        logger.setLevel(log_level)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logging(logging.DEBUG if settings.DEBUG else logging.INFO)
