"""Prediction Horizon Engine for GeoGuard V5.

Extends the V3/V4 prediction system to support multiple operational horizons:
- nowcast: Immediate observed precipitation
- 6h: 6-hour cumulative rainfall forecast
- 12h: 12-hour cumulative rainfall forecast
- 24h: 24-hour cumulative rainfall forecast

Uses real weather forecast ingestion from Open-Meteo hourly endpoints.
Computes calibrated confidence and model-supported feature attributions for each horizon.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.config import (
    CHENNAI_CENTER_LAT,
    CHENNAI_CENTER_LNG,
    HTTP_TIMEOUT,
    OPENMETEO_BASE_URL,
    logger,
    settings,
)
from backend.models.grid import Grid
from backend.services.confidence_service import compute_prediction_confidence, explain_prediction_features
from backend.services.feature_service import FeatureService, get_feature_service
from backend.services.ml_prediction_service import MLPredictionService, get_ml_prediction_service
from backend.services.weather_ingestion_service import (
    WeatherIngestionResult,
    WeatherIngestionService,
    get_weather_ingestion_service,
)

VALID_HORIZONS = ("nowcast", "6h", "12h", "24h")


class HorizonForecastData:
    """Encapsulates real forecast precipitation accumulations across horizons."""

    def __init__(
        self,
        nowcast_mm: float = 0.0,
        h6_mm: float = 0.0,
        h12_mm: float = 0.0,
        h24_mm: float = 0.0,
        daily_history: list[float] | None = None,
        fetched_at: datetime | None = None,
        source: str = "open-meteo",
    ) -> None:
        self.nowcast_mm = max(0.0, float(nowcast_mm))
        self.h6_mm = max(0.0, float(h6_mm))
        self.h12_mm = max(0.0, float(h12_mm))
        self.h24_mm = max(0.0, float(h24_mm))
        self.daily_history = daily_history or []
        self.fetched_at = fetched_at or datetime.utcnow()
        self.source = source

    def get_rainfall_for_horizon(self, horizon: str) -> float:
        """Retrieve estimated cumulative rainfall for target operational horizon."""
        norm = horizon.lower().strip()
        if norm in ("nowcast", "current"):
            return self.nowcast_mm
        elif norm == "6h":
            return self.h6_mm
        elif norm == "12h":
            return self.h12_mm
        elif norm == "24h":
            return self.h24_mm
        raise ValueError(f"Invalid forecast horizon '{horizon}'. Must be one of {VALID_HORIZONS}.")


class ForecastService:
    """Service orchestrating multi-horizon flood risk predictions."""

    def __init__(
        self,
        weather_service: WeatherIngestionService | None = None,
        feature_service: FeatureService | None = None,
        ml_service: MLPredictionService | None = None,
        base_url: str | None = None,
        timeout: float = HTTP_TIMEOUT,
    ) -> None:
        self.weather_service = weather_service or get_weather_ingestion_service()
        self.feature_service = feature_service or get_feature_service()
        self.ml_service = ml_service or get_ml_prediction_service()
        self.base_url = (base_url or OPENMETEO_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._cached_forecast: HorizonForecastData | None = None
        self._last_fetch_time: float = 0.0

    def fetch_real_hourly_forecast(self, lat: float = CHENNAI_CENTER_LAT, lng: float = CHENNAI_CENTER_LNG) -> HorizonForecastData:
        """Fetch legitimate hourly precipitation forecast from Open-Meteo."""
        with self._lock:
            now = time.time()
            # Cache for 10 minutes to avoid rate limits
            if self._cached_forecast and (now - self._last_fetch_time < 600):
                return self._cached_forecast

            url = (
                f"{self.base_url}?latitude={lat:.4f}&longitude={lng:.4f}"
                f"&current=precipitation,rain,wind_speed_10m"
                f"&hourly=precipitation,precipitation_probability"
                f"&daily=precipitation_sum&past_days=7&forecast_days=2&timezone=Asia/Kolkata"
            )

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GeoGuard/5.0 Operational Forecast Engine"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))

                current_rain = float(payload.get("current", {}).get("precipitation", payload.get("current", {}).get("rain", 0.0)))
                daily_hist = payload.get("daily", {}).get("precipitation_sum", [])
                # Filter None
                daily_clean = [float(v) for v in daily_hist if v is not None]

                hourly_precip = payload.get("hourly", {}).get("precipitation", [])
                h_vals = [float(v) if v is not None else 0.0 for v in hourly_precip]

                # Compute cumulative amounts for upcoming slices
                # 6 hours ahead
                h6_accum = round(float(sum(h_vals[:6])), 2) if len(h_vals) >= 6 else current_rain * 6.0
                # 12 hours ahead
                h12_accum = round(float(sum(h_vals[:12])), 2) if len(h_vals) >= 12 else current_rain * 12.0
                # 24 hours ahead
                h24_accum = round(float(sum(h_vals[:24])), 2) if len(h_vals) >= 24 else current_rain * 24.0

                forecast_data = HorizonForecastData(
                    nowcast_mm=current_rain,
                    h6_mm=h6_accum,
                    h12_mm=h12_accum,
                    h24_mm=h24_accum,
                    daily_history=daily_clean,
                    fetched_at=datetime.utcnow(),
                    source="open-meteo",
                )
                self._cached_forecast = forecast_data
                self._last_fetch_time = now
                logger.info(
                    f"forecast_sync_success: nowcast={current_rain}mm, 6h={h6_accum}mm, "
                    f"12h={h12_accum}mm, 24h={h24_accum}mm"
                )
                return forecast_data

            except Exception as e:
                logger.warning(f"Failed to fetch hourly forecast from Open-Meteo: {e}. Utilizing cached or safe fallback.")
                if self._cached_forecast:
                    return self._cached_forecast

                # Graceful fallback using last known weather from weather ingestion service
                known_rain = self.weather_service.last_known_rainfall_mm
                known_history = self.weather_service.last_known_daily_history
                return HorizonForecastData(
                    nowcast_mm=known_rain,
                    h6_mm=round(known_rain * 6.0, 2),
                    h12_mm=round(known_rain * 12.0, 2),
                    h24_mm=round(known_rain * 24.0, 2),
                    daily_history=known_history,
                    fetched_at=datetime.utcnow(),
                    source="telemetry_fallback",
                )

    def predict_for_horizon(
        self,
        db: Session,
        horizon: str,
        grid_id: int | None = None,
        forecast_data: HorizonForecastData | None = None,
    ) -> list[dict[str, Any]]:
        """Perform flood risk prediction for all grids (or single grid) at target operational horizon."""
        horizon_norm = horizon.lower().strip()
        if horizon_norm not in VALID_HORIZONS:
            raise ValueError(f"Invalid horizon '{horizon}'. Must be one of {VALID_HORIZONS}.")

        fdata = forecast_data or self.fetch_real_hourly_forecast()
        target_rain = fdata.get_rainfall_for_horizon(horizon_norm)
        daily_history = fdata.daily_history

        # Query grids
        query = db.query(Grid)
        if grid_id is not None:
            query = query.filter(Grid.id == grid_id)
        grids = query.order_by(Grid.id.asc()).all()

        if not grids:
            return []

        # Antecedent accumulation
        if daily_history and len(daily_history) >= 3:
            accum_3d, accum_7d, is_data_sufficient = (
                self.feature_service.calculate_rolling_accumulations_from_history(daily_history, target_rain)
            )
        else:
            accum_3d, accum_7d, is_data_sufficient = (
                self.feature_service.calculate_accumulations_from_db(
                    db, grids[0].latitude, grids[0].longitude, target_rain
                )
            )

        now_dt = datetime.utcnow()
        results = []

        for g in grids:
            feat_result = self.feature_service.generate_sector_features(
                grid=g,
                rainfall_current_mm=target_rain,
                rainfall_3d_accum_mm=accum_3d,
                rainfall_7d_accum_mm=accum_7d,
                observation_dt=now_dt,
                is_data_sufficient=is_data_sufficient,
            )

            is_fallback = False
            fallback_reason = None

            if not feat_result.is_valid or not feat_result.is_data_sufficient or not self.ml_service.is_available:
                is_fallback = True
                fallback_reason = (
                    feat_result.validation_error
                    if not feat_result.is_valid
                    else "Insufficient weather history for empirical ML prediction"
                    if not feat_result.is_data_sufficient
                    else self.ml_service.fallback_reason or "ML service unavailable"
                )
                pred_dict = self.ml_service._deterministic_fallback(
                    rainfall_mm=target_rain,
                    elevation_m=g.elevation_m,
                    distance_to_water_m=g.distance_to_water,
                )
            else:
                try:
                    pred_dict = self.ml_service.predict_sector_risk(
                        rainfall_current_mm=target_rain,
                        rainfall_3d_accum_mm=accum_3d,
                        rainfall_7d_accum_mm=accum_7d,
                        elevation_m=g.elevation_m,
                        distance_to_water_m=g.distance_to_water,
                        latitude=g.latitude,
                        longitude=g.longitude,
                        month=now_dt.month,
                    )
                except Exception as ex:
                    is_fallback = True
                    fallback_reason = f"ML inference exception: {ex}"
                    pred_dict = self.ml_service._deterministic_fallback(
                        rainfall_mm=target_rain,
                        elevation_m=g.elevation_m,
                        distance_to_water_m=g.distance_to_water,
                    )

            prob = float(pred_dict.get("probability", 0.0))
            risk_level = str(pred_dict.get("prediction", "Low"))
            model_ver = "v5.0.0" if not is_fallback else "v2.0-deterministic-fallback"

            # Confidence calculation
            confidence, conf_category = compute_prediction_confidence(
                probability=prob,
                is_data_sufficient=is_data_sufficient,
                has_7d_history=len(daily_history) >= 7,
                observation_age_hours=0.1,
                is_fallback=is_fallback,
            )

            # Contributing features
            attributions = explain_prediction_features(feat_result.features, prob)

            results.append({
                "grid_id": g.id,
                "grid_name": g.name,
                "prediction": risk_level,
                "probability": round(prob, 4),
                "risk_level": risk_level,
                "confidence": confidence,
                "confidence_category": conf_category,
                "model_version": model_ver,
                "horizon": horizon_norm,
                "prediction_time": now_dt.isoformat() + "Z",
                "rainfall_mm": round(target_rain, 2),
                "rainfall_3d_mm": round(accum_3d, 2),
                "rainfall_7d_mm": round(accum_7d, 2),
                "elevation_m": round(g.elevation_m, 1),
                "distance_to_water_m": round(g.distance_to_water, 0),
                "is_fallback": is_fallback,
                "fallback_reason": fallback_reason,
                "features": feat_result.features,
                "contributing_features": attributions,
            })

        return results


_singleton_forecast_service: ForecastService | None = None


def get_forecast_service() -> ForecastService:
    """Retrieve singleton instance of ForecastService."""
    global _singleton_forecast_service
    if _singleton_forecast_service is None:
        _singleton_forecast_service = ForecastService()
    return _singleton_forecast_service
