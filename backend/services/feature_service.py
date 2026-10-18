"""Feature Engineering Service for GeoGuard V4.

Generates the exact 8-feature schema used during V3 Gradient Boosting training:
1. rainfall_current_mm
2. rainfall_3d_accum_mm
3. rainfall_7d_accum_mm
4. elevation_m
5. distance_to_water_m
6. latitude
7. longitude
8. month

Guarantees feature ordering, strict numerical & boundary validation,
physical realism constraints, and explicit data-availability states.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.weather import WeatherObservation

V3_FEATURE_NAMES = [
    "rainfall_current_mm",
    "rainfall_3d_accum_mm",
    "rainfall_7d_accum_mm",
    "elevation_m",
    "distance_to_water_m",
    "latitude",
    "longitude",
    "month",
]

# Physical bounds for validation
BOUNDS = {
    "rainfall_current_mm": (0.0, 1000.0),
    "rainfall_3d_accum_mm": (0.0, 2500.0),
    "rainfall_7d_accum_mm": (0.0, 5000.0),
    "elevation_m": (-10.0, 300.0),
    "distance_to_water_m": (0.0, 50000.0),
    "latitude": (12.5, 13.5),       # Chennai Metropolitan Area
    "longitude": (79.8, 80.5),      # Chennai Metropolitan Area
    "month": (1, 12),
}


class FeatureGenerationResult:
    """Encapsulates generated feature vector and validation status."""

    def __init__(
        self,
        features: dict[str, float | int],
        ordered_feature_values: list[float | int],
        is_valid: bool,
        is_data_sufficient: bool,
        data_availability_state: str,  # "full", "degraded", "insufficient_history"
        validation_error: str | None = None,
    ) -> None:
        self.features = features
        self.ordered_feature_values = ordered_feature_values
        self.is_valid = is_valid
        self.is_data_sufficient = is_data_sufficient
        self.data_availability_state = data_availability_state
        self.validation_error = validation_error


class FeatureService:
    """Service to produce validated V3 features from live and stored geospatial data."""

    @staticmethod
    def calculate_rolling_accumulations_from_history(
        daily_history: list[float], current_rain: float
    ) -> tuple[float, float, bool]:
        """Calculate 3-day and 7-day rolling precipitation from daily history.
        
        daily_history contains past precipitation sums up to today.
        Returns: (rainfall_3d_accum_mm, rainfall_7d_accum_mm, is_sufficient)
        """
        if not daily_history or len(daily_history) < 3:
            return 0.0, 0.0, False

        # If today's current rain is higher than the today's partial daily sum, use current
        history = list(daily_history)
        if current_rain > history[-1]:
            history[-1] = current_rain

        # 3-day sum (today + 2 prior days)
        accum_3d = sum(history[-3:])

        # 7-day sum (today + 6 prior days, or as many up to 7)
        if len(history) >= 7:
            accum_7d = sum(history[-7:])
            is_sufficient = True
        else:
            accum_7d = sum(history)
            is_sufficient = False  # Degraded 7-day history

        return round(accum_3d, 2), round(accum_7d, 2), is_sufficient

    @staticmethod
    def calculate_accumulations_from_db(
        db: Session, target_lat: float, target_lng: float, current_rain: float
    ) -> tuple[float, float, bool]:
        """Query historical weather observations from PostgreSQL if API daily history is absent."""
        try:
            # Query sum of rainfall in last 3 days
            result_3d = (
                db.query(func.sum(WeatherObservation.rainfall_mm))
                .filter(WeatherObservation.observed_at >= func.now() - func.cast("3 days", func.INTERVAL))
                .scalar()
            )
            # Query sum of rainfall in last 7 days
            result_7d = (
                db.query(func.sum(WeatherObservation.rainfall_mm))
                .filter(WeatherObservation.observed_at >= func.now() - func.cast("7 days", func.INTERVAL))
                .scalar()
            )

            val_3d = float(result_3d or current_rain)
            val_7d = float(result_7d or current_rain)

            # Check if we have at least some observations
            count = (
                db.query(func.count(WeatherObservation.id))
                .filter(WeatherObservation.observed_at >= func.now() - func.cast("3 days", func.INTERVAL))
                .scalar()
            )
            is_sufficient = bool(count and count >= 3)
            return round(val_3d, 2), round(val_7d, 2), is_sufficient
        except Exception as e:
            logger.warning(f"Database accumulation query fallback: {e}")
            return current_rain, current_rain, False

    def validate_features(self, features: dict[str, Any]) -> tuple[bool, str | None]:
        """Verify that every feature is present, numeric, non-null, and within physical bounds."""
        for feat_name in V3_FEATURE_NAMES:
            if feat_name not in features:
                return False, f"Missing required feature: '{feat_name}'"

            val = features[feat_name]
            if val is None:
                return False, f"Feature '{feat_name}' is None (null value not allowed)"

            if not isinstance(val, (int, float)):
                return False, f"Feature '{feat_name}' is not numeric (type: {type(val).__name__})"

            min_bound, max_bound = BOUNDS[feat_name]
            if not (min_bound <= float(val) <= max_bound):
                return False, (
                    f"Feature '{feat_name}' with value {val} is outside valid physical "
                    f"bounds [{min_bound}, {max_bound}]"
                )

        return True, None

    def generate_sector_features(
        self,
        grid: Grid,
        rainfall_current_mm: float,
        rainfall_3d_accum_mm: float,
        rainfall_7d_accum_mm: float,
        observation_dt: datetime | None = None,
        is_data_sufficient: bool = True,
    ) -> FeatureGenerationResult:
        """Construct and validate feature vector for a specific monitored grid sector."""
        obs_time = observation_dt or datetime.utcnow()
        month = obs_time.month

        features_dict: dict[str, float | int] = {
            "rainfall_current_mm": float(rainfall_current_mm),
            "rainfall_3d_accum_mm": float(rainfall_3d_accum_mm),
            "rainfall_7d_accum_mm": float(rainfall_7d_accum_mm),
            "elevation_m": float(grid.elevation_m),
            "distance_to_water_m": float(grid.distance_to_water),
            "latitude": float(grid.latitude),
            "longitude": float(grid.longitude),
            "month": int(month),
        }

        # Build strictly ordered list
        ordered_values = [features_dict[name] for name in V3_FEATURE_NAMES]

        # Validate features
        is_valid, err = self.validate_features(features_dict)

        data_state = "full" if (is_valid and is_data_sufficient) else "insufficient_history" if not is_data_sufficient else "invalid_features"

        return FeatureGenerationResult(
            features=features_dict,
            ordered_feature_values=ordered_values,
            is_valid=is_valid,
            is_data_sufficient=is_data_sufficient,
            data_availability_state=data_state,
            validation_error=err,
        )


_singleton_feature_service: FeatureService | None = None


def get_feature_service() -> FeatureService:
    """Retrieve singleton instance of FeatureService."""
    global _singleton_feature_service
    if _singleton_feature_service is None:
        _singleton_feature_service = FeatureService()
    return _singleton_feature_service
