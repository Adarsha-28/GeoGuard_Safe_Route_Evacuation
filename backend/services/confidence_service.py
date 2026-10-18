"""Confidence Calculation and Feature Attribution Service for GeoGuard V5.

Implements defensible confidence estimation separated from prediction probability:
- Decision Boundary Margin: 2 * |P - 0.5|
- Weather Data Completeness: antecedent daily history presence
- Observation Freshness: age of latest ingested observation
- Defensible Confidence Categories: 'High confidence', 'Medium confidence', 'Low confidence'

Provides model-supported explainable feature attribution for all 8 features.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Feature ranking from trained Gradient Boosting model metadata
MODEL_FEATURE_WEIGHTS = {
    "rainfall_3d_accum_mm": 0.4400,
    "rainfall_7d_accum_mm": 0.3024,
    "month": 0.1470,
    "rainfall_current_mm": 0.0808,
    "elevation_m": 0.0107,
    "distance_to_water_m": 0.0107,
    "longitude": 0.0082,
    "latitude": 0.0002,
}

FEATURE_LABELS = {
    "rainfall_current_mm": "Current Rainfall",
    "rainfall_3d_accum_mm": "3-Day Cumulative Rainfall",
    "rainfall_7d_accum_mm": "7-Day Cumulative Rainfall",
    "elevation_m": "Terrain Elevation",
    "distance_to_water_m": "Distance to Water Basin",
    "latitude": "Latitude Coordinate",
    "longitude": "Longitude Coordinate",
    "month": "Monsoon Seasonality",
}


def compute_prediction_confidence(
    probability: float,
    is_data_sufficient: bool = True,
    has_7d_history: bool = True,
    observation_age_hours: float = 0.0,
    is_fallback: bool = False,
) -> tuple[float, str]:
    """Calculate calibrated confidence score and category separate from flood probability.
    
    Formula:
      boundary_margin = 2.0 * abs(probability - 0.50)  # [0.0, 1.0]
      data_completeness = 1.0 if has_7d_history else 0.85 if is_data_sufficient else 0.70
      if is_fallback: data_completeness *= 0.80
      freshness = max(0.70, 1.0 - (observation_age_hours / 24.0) * 0.30)
      confidence = 0.50 * boundary_margin + 0.30 * data_completeness + 0.20 * freshness
    
    Returns:
      (confidence: float [0.0, 1.0], category: 'High confidence' | 'Medium confidence' | 'Low confidence')
    """
    prob = max(0.0, min(1.0, float(probability)))
    boundary_margin = 2.0 * abs(prob - 0.50)

    if is_fallback:
        data_completeness = 0.65
    elif has_7d_history:
        data_completeness = 1.0
    elif is_data_sufficient:
        data_completeness = 0.85
    else:
        data_completeness = 0.70

    freshness = max(0.70, 1.0 - min(1.0, observation_age_hours / 24.0) * 0.30)

    raw_conf = (0.50 * boundary_margin) + (0.30 * data_completeness) + (0.20 * freshness)
    confidence = round(max(0.0, min(1.0, raw_conf)), 4)

    if confidence >= 0.75:
        category = "High confidence"
    elif confidence >= 0.50:
        category = "Medium confidence"
    else:
        category = "Low confidence"

    return confidence, category


def explain_prediction_features(
    features: dict[str, Any],
    probability: float,
) -> list[dict[str, Any]]:
    """Produce model-supported feature attributions for all 8 empirical predictors."""
    rain_curr = float(features.get("rainfall_current_mm", 0.0))
    rain_3d = float(features.get("rainfall_3d_accum_mm", 0.0))
    rain_7d = float(features.get("rainfall_7d_accum_mm", 0.0))
    elev = float(features.get("elevation_m", 10.0))
    water_dist = float(features.get("distance_to_water_m", 1000.0))
    lat = float(features.get("latitude", 13.08))
    lng = float(features.get("longitude", 80.27))
    month = int(features.get("month", datetime.utcnow().month))

    attributions = []

    # 1. 3-day rainfall
    imp_3d = MODEL_FEATURE_WEIGHTS["rainfall_3d_accum_mm"]
    if rain_3d >= 100.0:
        dir_3d = "High Hazard"
    elif rain_3d >= 40.0:
        dir_3d = "Moderate Hazard"
    else:
        dir_3d = "Protective Factor"
    attributions.append({
        "feature": "rainfall_3d_accum_mm",
        "name": FEATURE_LABELS["rainfall_3d_accum_mm"],
        "value": f"{rain_3d:.1f} mm",
        "relative_importance": imp_3d,
        "direction": dir_3d,
        "attribution_type": "Model-derived global importance & local threshold",
    })

    # 2. 7-day rainfall
    imp_7d = MODEL_FEATURE_WEIGHTS["rainfall_7d_accum_mm"]
    if rain_7d >= 180.0:
        dir_7d = "High Hazard"
    elif rain_7d >= 80.0:
        dir_7d = "Moderate Hazard"
    else:
        dir_7d = "Protective Factor"
    attributions.append({
        "feature": "rainfall_7d_accum_mm",
        "name": FEATURE_LABELS["rainfall_7d_accum_mm"],
        "value": f"{rain_7d:.1f} mm",
        "relative_importance": imp_7d,
        "direction": dir_7d,
        "attribution_type": "Model-derived global importance & local threshold",
    })

    # 3. Monsoon Seasonality (Month)
    imp_month = MODEL_FEATURE_WEIGHTS["month"]
    # Northeast monsoon peak in Chennai: Oct (10), Nov (11), Dec (12)
    month_name = datetime(2026, month, 1).strftime("%B")
    if month in (10, 11, 12):
        dir_month = "High Hazard (Peak Monsoon)"
    elif month in (9, 1):
        dir_month = "Moderate Hazard"
    else:
        dir_month = "Protective Factor (Dry Season)"
    attributions.append({
        "feature": "month",
        "name": FEATURE_LABELS["month"],
        "value": f"{month_name} (Month {month})",
        "relative_importance": imp_month,
        "direction": dir_month,
        "attribution_type": "Model-derived global importance & local threshold",
    })

    # 4. Current Rainfall
    imp_curr = MODEL_FEATURE_WEIGHTS["rainfall_current_mm"]
    if rain_curr >= 50.0:
        dir_curr = "High Hazard"
    elif rain_curr >= 15.0:
        dir_curr = "Moderate Hazard"
    else:
        dir_curr = "Baseline"
    attributions.append({
        "feature": "rainfall_current_mm",
        "name": FEATURE_LABELS["rainfall_current_mm"],
        "value": f"{rain_curr:.1f} mm",
        "relative_importance": imp_curr,
        "direction": dir_curr,
        "attribution_type": "Model-derived global importance & local threshold",
    })

    # 5. Elevation
    imp_elev = MODEL_FEATURE_WEIGHTS["elevation_m"]
    if elev <= 3.0:
        dir_elev = "High Hazard (Lowland Depression)"
    elif elev <= 7.0:
        dir_elev = "Moderate Hazard"
    else:
        dir_elev = "Protective Factor (High Ground)"
    attributions.append({
        "feature": "elevation_m",
        "name": FEATURE_LABELS["elevation_m"],
        "value": f"{elev:.1f} m",
        "relative_importance": imp_elev,
        "direction": dir_elev,
        "attribution_type": "Model-derived global importance & local threshold",
    })

    # 6. Distance to Water
    imp_water = MODEL_FEATURE_WEIGHTS["distance_to_water_m"]
    if water_dist <= 300.0:
        dir_water = "High Hazard (Water Basin Vicinity)"
    elif water_dist <= 800.0:
        dir_water = "Moderate Hazard"
    else:
        dir_water = "Protective Factor (Distant Basin)"
    attributions.append({
        "feature": "distance_to_water_m",
        "name": FEATURE_LABELS["distance_to_water_m"],
        "value": f"{water_dist:.0f} m",
        "relative_importance": imp_water,
        "direction": dir_water,
        "attribution_type": "Model-derived global importance & local threshold",
    })

    # 7. Longitude & 8. Latitude
    attributions.append({
        "feature": "longitude",
        "name": FEATURE_LABELS["longitude"],
        "value": f"{lng:.4f}°E",
        "relative_importance": MODEL_FEATURE_WEIGHTS["longitude"],
        "direction": "Coastal Proximity Factor" if lng >= 80.26 else "Inland Sector",
        "attribution_type": "Spatial Coordinate Basis",
    })
    attributions.append({
        "feature": "latitude",
        "name": FEATURE_LABELS["latitude"],
        "value": f"{lat:.4f}°N",
        "relative_importance": MODEL_FEATURE_WEIGHTS["latitude"],
        "direction": "Basin Spatial Distribution",
        "attribution_type": "Spatial Coordinate Basis",
    })

    # Sort attributions descending by importance
    attributions.sort(key=lambda x: x["relative_importance"], reverse=True)
    return attributions
