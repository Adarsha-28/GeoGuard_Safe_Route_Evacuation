"""Weather synchronization service communicating with Open-Meteo."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy.orm import Session

from backend.config import (
    CHENNAI_CENTER_LAT,
    CHENNAI_CENTER_LNG,
    HTTP_TIMEOUT,
    OPENMETEO_BASE_URL,
    logger,
)
from backend.models.weather import WeatherObservation
from backend.services.risk_service import RiskService, get_risk_service


class WeatherService:
    """Service for fetching live precipitation and updating geospatial risk models."""

    def __init__(self, risk_service: RiskService | None = None) -> None:
        self.risk_service = risk_service or get_risk_service()
        self.last_known_rainfall_mm: float = 0.0

    def sync_live_weather(self, db: Session) -> tuple[bool, float, str]:
        """Query live precipitation from Open-Meteo with fallback resilience.
        
        Failure Policy:
          If Open-Meteo fails, times out, or returns invalid data:
          1. Log the error warning without crashing.
          2. Preserve the last valid observation.
          3. Set status to degraded.
          4. Never generate random or fake values.
        """
        url = (
            f"{OPENMETEO_BASE_URL}?latitude={CHENNAI_CENTER_LAT}&longitude={CHENNAI_CENTER_LNG}"
            f"&current=precipitation,rain&timezone=Asia/Kolkata"
        )
        logger.info(f"Synchronizing live weather from Open-Meteo: {url}")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GeoGuard/2.0 Open-Meteo Syncer"})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        url, response.status, "Non-200 response from Open-Meteo", response.headers, None
                    )
                raw_data = response.read()
                data = json.loads(raw_data.decode("utf-8"))

            if "current" not in data or "precipitation" not in data["current"]:
                raise ValueError("Malformed Open-Meteo response structure: missing 'current.precipitation'")

            current_rain = float(data["current"]["precipitation"])
            now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            self.last_known_rainfall_mm = current_rain

            # Persist observation to PostgreSQL
            observation = WeatherObservation(
                location=ST_SetSRID(ST_MakePoint(CHENNAI_CENTER_LNG, CHENNAI_CENTER_LAT), 4326),
                rainfall_mm=current_rain,
                source="Open-Meteo",
                observed_at=datetime.utcnow(),
            )
            db.add(observation)
            db.commit()

            # Recalculate deterministic risk indices
            self.risk_service.recalculate_all_risks(db, measured_rainfall_mm=current_rain)
            self.risk_service.update_weather_status(current_rain, now_iso, status="live")

            logger.info(f"Weather synchronized successfully: {current_rain} mm precipitation recorded.")
            return True, current_rain, now_iso

        except Exception as e:
            logger.warning(
                f"Open-Meteo sync failed ({type(e).__name__}: {e}). "
                f"Preserving last known rainfall: {self.last_known_rainfall_mm} mm."
            )
            now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            self.risk_service.update_weather_status(self.last_known_rainfall_mm, now_iso, status="degraded")
            return False, self.last_known_rainfall_mm, now_iso


_singleton_weather_service: WeatherService | None = None


def get_weather_service() -> WeatherService:
    """Retrieve singleton instance of WeatherService."""
    global _singleton_weather_service
    if _singleton_weather_service is None:
        _singleton_weather_service = WeatherService()
    return _singleton_weather_service
