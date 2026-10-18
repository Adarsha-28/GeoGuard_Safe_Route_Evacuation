"""Live Weather Ingestion Service for GeoGuard V4.

Connects to Open-Meteo endpoint to collect real precipitation and antecedent
weather observations, performs strict schema & boundary validation, handles
retries with exponential backoff, prevents duplicate records, and maintains
telemetry state without manufacturing synthetic observations.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import (
    CHENNAI_CENTER_LAT,
    CHENNAI_CENTER_LNG,
    HTTP_TIMEOUT,
    OPENMETEO_BASE_URL,
    WEATHER_API_BACKOFF_FACTOR,
    WEATHER_API_MAX_RETRIES,
    logger,
)
from backend.models.weather import WeatherObservation


class WeatherIngestionResult:
    """Encapsulates the outcome of a weather ingestion attempt."""

    def __init__(
        self,
        success: bool,
        observation: WeatherObservation | None = None,
        rainfall_current_mm: float = 0.0,
        wind_speed_kmh: float = 0.0,
        daily_rainfall_history: list[float] | None = None,
        observed_at: datetime | None = None,
        is_duplicate: bool = False,
        error_message: str | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        self.success = success
        self.observation = observation
        self.rainfall_current_mm = rainfall_current_mm
        self.wind_speed_kmh = wind_speed_kmh
        self.daily_rainfall_history = daily_rainfall_history or []
        self.observed_at = observed_at
        self.is_duplicate = is_duplicate
        self.error_message = error_message
        self.latency_ms = latency_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "rainfall_current_mm": self.rainfall_current_mm,
            "wind_speed_kmh": self.wind_speed_kmh,
            "daily_history_count": len(self.daily_rainfall_history),
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "is_duplicate": self.is_duplicate,
            "error_message": self.error_message,
            "latency_ms": round(self.latency_ms, 2),
        }


class WeatherIngestionService:
    """Production service for fetching and persisting live weather observations."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = HTTP_TIMEOUT,
        max_retries: int = WEATHER_API_MAX_RETRIES,
        backoff_factor: float = WEATHER_API_BACKOFF_FACTOR,
        lat: float = CHENNAI_CENTER_LAT,
        lng: float = CHENNAI_CENTER_LNG,
    ) -> None:
        self.base_url = (base_url or OPENMETEO_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.lat = lat
        self.lng = lng
        self._lock = threading.Lock()

        # State tracking
        self.last_successful_observation: WeatherObservation | None = None
        self.last_known_rainfall_mm: float = 0.0
        self.last_known_wind_speed_kmh: float = 0.0
        self.last_known_daily_history: list[float] = []
        self.last_sync_timestamp: datetime | None = None
        self.last_sync_status: str = "initialized"  # "healthy", "degraded", "unavailable"
        self.last_error_message: str | None = None

    def build_api_url(self, lat: float | None = None, lng: float | None = None) -> str:
        """Construct parameterized Open-Meteo forecast and antecedent weather URL."""
        target_lat = lat if lat is not None else self.lat
        target_lng = lng if lng is not None else self.lng
        return (
            f"{self.base_url}?latitude={target_lat:.4f}&longitude={target_lng:.4f}"
            f"&current=precipitation,rain,wind_speed_10m"
            f"&daily=precipitation_sum&past_days=7&timezone=Asia/Kolkata"
        )

    def validate_weather_payload(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate structural integrity and physical realism of Open-Meteo payload."""
        if not isinstance(data, dict):
            return False, "Payload must be a JSON object"

        if "current" not in data or not isinstance(data["current"], dict):
            return False, "Missing or invalid 'current' object in response"

        current = data["current"]
        if "precipitation" not in current and "rain" not in current:
            return False, "Missing precipitation or rain in 'current' weather"

        # Validate current precipitation numeric bounds
        rain_val = current.get("precipitation", current.get("rain"))
        if not isinstance(rain_val, (int, float)) or rain_val < 0.0 or rain_val > 1000.0:
            return False, f"Precipitation value '{rain_val}' out of physical bounds [0, 1000] mm"

        # Validate wind speed if present
        wind_val = current.get("wind_speed_10m", 0.0)
        if not isinstance(wind_val, (int, float)) or wind_val < 0.0 or wind_val > 500.0:
            return False, f"Wind speed value '{wind_val}' out of physical bounds [0, 500] km/h"

        # Validate observation timestamp
        time_str = current.get("time")
        if not time_str or not isinstance(time_str, str):
            return False, "Missing or invalid observation timestamp in 'current.time'"

        # Validate geographic coordinates returned
        resp_lat = data.get("latitude")
        resp_lng = data.get("longitude")
        if resp_lat is not None and not (-90.0 <= resp_lat <= 90.0):
            return False, f"Latitude '{resp_lat}' out of valid geographic range [-90, 90]"
        if resp_lng is not None and not (-180.0 <= resp_lng <= 180.0):
            return False, f"Longitude '{resp_lng}' out of valid geographic range [-180, 180]"

        return True, None

    def fetch_weather_with_retry(
        self, lat: float | None = None, lng: float | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Fetch weather data with exponential backoff bounded retries."""
        url = self.build_api_url(lat, lng)
        logger.info(f"weather_sync_started: connecting to Open-Meteo endpoint {url}")

        last_error = None
        for attempt in range(self.max_retries + 1):
            start_t = time.perf_counter()
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "GeoGuard/4.0 Operational Weather Ingestion Engine"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    status_code = response.status
                    if status_code != 200:
                        raise urllib.error.HTTPError(
                            url, status_code, f"Non-200 HTTP response: {status_code}", response.headers, None
                        )
                    raw_bytes = response.read()
                    data = json.loads(raw_bytes.decode("utf-8"))
                    return data, None

            except urllib.error.HTTPError as he:
                last_error = f"HTTP error {he.code}: {he.reason}"
                logger.warning(
                    f"weather_sync_retry: attempt {attempt + 1}/{self.max_retries + 1} failed: {last_error}"
                )
            except urllib.error.URLError as ue:
                last_error = f"Network/timeout error: {ue.reason}"
                logger.warning(
                    f"weather_sync_retry: attempt {attempt + 1}/{self.max_retries + 1} failed: {last_error}"
                )
            except (json.JSONDecodeError, UnicodeDecodeError) as je:
                last_error = f"Malformed JSON response: {je}"
                logger.warning(
                    f"weather_sync_retry: attempt {attempt + 1}/{self.max_retries + 1} failed: {last_error}"
                )
            except Exception as e:
                last_error = f"Unexpected error: {type(e).__name__} ({e})"
                logger.warning(
                    f"weather_sync_retry: attempt {attempt + 1}/{self.max_retries + 1} failed: {last_error}"
                )

            if attempt < self.max_retries:
                sleep_seconds = self.backoff_factor ** attempt
                time.sleep(sleep_seconds)

        logger.error(f"weather_sync_failed: all {self.max_retries + 1} attempts exhausted. Error: {last_error}")
        return None, last_error

    def ingest_current_weather(
        self, db: Session, lat: float | None = None, lng: float | None = None
    ) -> WeatherIngestionResult:
        """Execute full ingestion workflow: fetch, validate, deduplicate, persist in DB."""
        target_lat = round(lat if lat is not None else self.lat, 4)
        target_lng = round(lng if lng is not None else self.lng, 4)

        start_time = time.perf_counter()
        data, fetch_err = self.fetch_weather_with_retry(target_lat, target_lng)
        latency = (time.perf_counter() - start_time) * 1000.0

        with self._lock:
            if data is None:
                self.last_sync_status = "degraded" if self.last_known_rainfall_mm > 0 else "unavailable"
                self.last_error_message = fetch_err
                return WeatherIngestionResult(
                    success=False,
                    observation=self.last_successful_observation,
                    rainfall_current_mm=self.last_known_rainfall_mm,
                    wind_speed_kmh=self.last_known_wind_speed_kmh,
                    daily_rainfall_history=self.last_known_daily_history,
                    observed_at=self.last_sync_timestamp,
                    error_message=fetch_err,
                    latency_ms=latency,
                )

            # Validate payload schema
            is_valid, validation_err = self.validate_weather_payload(data)
            if not is_valid:
                logger.error(f"weather_sync_failed: schema validation error: {validation_err}")
                self.last_sync_status = "degraded"
                self.last_error_message = validation_err
                return WeatherIngestionResult(
                    success=False,
                    observation=self.last_successful_observation,
                    rainfall_current_mm=self.last_known_rainfall_mm,
                    wind_speed_kmh=self.last_known_wind_speed_kmh,
                    daily_rainfall_history=self.last_known_daily_history,
                    observed_at=self.last_sync_timestamp,
                    error_message=validation_err,
                    latency_ms=latency,
                )

            current = data["current"]
            rainfall_mm = float(current.get("precipitation", current.get("rain", 0.0)))
            wind_speed_kmh = float(current.get("wind_speed_10m", 0.0))
            time_str = current["time"]

            # Parse observation timestamp
            try:
                # Open-Meteo formats as YYYY-MM-DDTHH:MM
                if "T" in time_str:
                    obs_dt = datetime.fromisoformat(time_str)
                else:
                    obs_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            except Exception:
                obs_dt = datetime.utcnow()

            # Parse daily precipitation sums
            daily_history: list[float] = []
            if "daily" in data and "precipitation_sum" in data["daily"]:
                raw_sums = data["daily"]["precipitation_sum"]
                if isinstance(raw_sums, list):
                    daily_history = [float(x) for x in raw_sums if isinstance(x, (int, float))]

            # Check for duplicate observation in database
            existing = (
                db.query(WeatherObservation)
                .filter(
                    WeatherObservation.source == "Open-Meteo",
                    WeatherObservation.observed_at == obs_dt,
                    WeatherObservation.latitude == target_lat,
                    WeatherObservation.longitude == target_lng,
                )
                .first()
            )

            if existing:
                logger.info(
                    f"weather_sync_success: observation at {obs_dt} for ({target_lat}, {target_lng}) "
                    f"already exists (deduplicated). Rainfall: {rainfall_mm} mm."
                )
                self.last_known_rainfall_mm = rainfall_mm
                self.last_known_wind_speed_kmh = wind_speed_kmh
                self.last_known_daily_history = daily_history
                self.last_sync_timestamp = obs_dt
                self.last_sync_status = "healthy"
                self.last_error_message = None
                return WeatherIngestionResult(
                    success=True,
                    observation=existing,
                    rainfall_current_mm=rainfall_mm,
                    wind_speed_kmh=wind_speed_kmh,
                    daily_rainfall_history=daily_history,
                    observed_at=obs_dt,
                    is_duplicate=True,
                    latency_ms=latency,
                )

            # Persist new valid observation in database
            obs = WeatherObservation(
                location=ST_SetSRID(ST_MakePoint(target_lng, target_lat), 4326),
                rainfall_mm=rainfall_mm,
                wind_speed_kmh=wind_speed_kmh,
                latitude=target_lat,
                longitude=target_lng,
                source="Open-Meteo",
                observed_at=obs_dt,
                ingested_at=datetime.utcnow(),
            )
            try:
                db.add(obs)
                db.commit()
                db.refresh(obs)
            except IntegrityError:
                db.rollback()
                logger.warning("Duplicate observation detected via database constraint during insert.")
                obs = (
                    db.query(WeatherObservation)
                    .filter(
                        WeatherObservation.source == "Open-Meteo",
                        WeatherObservation.observed_at == obs_dt,
                    )
                    .first()
                )

            self.last_successful_observation = obs
            self.last_known_rainfall_mm = rainfall_mm
            self.last_known_wind_speed_kmh = wind_speed_kmh
            self.last_known_daily_history = daily_history
            self.last_sync_timestamp = obs_dt
            self.last_sync_status = "healthy"
            self.last_error_message = None

            logger.info(
                f"weather_sync_success: recorded {rainfall_mm} mm rainfall, {wind_speed_kmh} km/h wind "
                f"at {obs_dt} (latency: {latency:.2f} ms)."
            )

            return WeatherIngestionResult(
                success=True,
                observation=obs,
                rainfall_current_mm=rainfall_mm,
                wind_speed_kmh=wind_speed_kmh,
                daily_rainfall_history=daily_history,
                observed_at=obs_dt,
                is_duplicate=False,
                latency_ms=latency,
            )


_singleton_weather_ingestion_service: WeatherIngestionService | None = None


def get_weather_ingestion_service() -> WeatherIngestionService:
    """Retrieve singleton instance of WeatherIngestionService."""
    global _singleton_weather_ingestion_service
    if _singleton_weather_ingestion_service is None:
        _singleton_weather_ingestion_service = WeatherIngestionService()
    return _singleton_weather_ingestion_service
