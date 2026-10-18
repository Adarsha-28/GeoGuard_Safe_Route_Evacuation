# GeoGuard V5 — Predictive Flood Intelligence & Decision Support Architecture

## 1. System Vision & Evolution

GeoGuard V5 transforms GeoGuard from a reactive near-real-time flood monitoring dashboard into a **Predictive Flood Intelligence & Decision Support Platform** for Chennai Municipal Disaster Operations.

| Version | Focus | Primary Capabilities |
| :--- | :--- | :--- |
| **V1** | Geospatial Baseline | 34 Chennai sectors, 25 relief shelters, Leaflet UI, PostGIS storage |
| **V2** | Multi-Criteria Hydrology | Multi-criteria deterministic formula, OSRM safe evacuation routing |
| **V3** | Empirical ML Forecasting | 8-feature Gradient Boosting classifier, chronological anti-leakage evaluation, V2 fallback |
| **V4** | Near-Real-Time Operations | Open-Meteo live sync, state transition engine, automated scheduler, advisory deduplication |
| **V5** | **Predictive Intelligence & Decision Support** | **Multi-horizon forecasting (`nowcast`, `6h`, `12h`, `24h`), prediction change detection, temporal trend intelligence, calibrated confidence reporting, sector triage prioritization, shelter suitability, route hazard exposure, operational event timeline** |

---

## 2. Core Architectural Pillars

```
+-----------------------------------------------------------------------------------+
|                        GeoGuard V5 Operational Platform                           |
+-----------------------------------------------------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
        v                                 v                                 v
[Ingestion & Horizons]          [Predictive Engines]            [Decision Support]
- Open-Meteo Hourly Forecasts    - Gradient Boosting (v3.0.0)    - Sector Triage Prioritization
- Antecedent 3d/7d Rolling Sums - V2 Deterministic Fallback     - Shelter Intelligence
- Nowcast, 6h, 12h, 24h          - Calibrated Confidence Engine  - Route Risk & Safety Score
                                - Delta & Trend Detection       - Timeline Ledger & Advisories
                                          |
                                          v
                              [PostgreSQL 18 + PostGIS 3.6]
                              - prediction_history
                              - risk_transitions
                              - operational_events
                              - zone_priorities
                              - grid_risk_states, alerts, shelters
```

---

## 3. Data Flow & Execution Sequence

1. **Weather & Forecast Ingestion**:
   - `WeatherIngestionService` and `ForecastService` query Open-Meteo for live precipitation and hourly forecast slices (6h, 12h, 24h).
   - Antecedent precipitation history is computed without synthetic manufacture.
2. **Batch Prediction & Multi-Horizon Inference**:
   - For each monitored sector, `FeatureService` extracts the exact 8 empirical features.
   - `MLPredictionService` runs inference using the trained Gradient Boosting model.
   - If feature validation fails or data is insufficient, V2 deterministic fallback is invoked seamlessly.
3. **Calibrated Confidence & Feature Attribution**:
   - `compute_prediction_confidence` calculates a defensible confidence metric based on decision boundary distance, weather completeness, and freshness.
   - `explain_prediction_features` provides direction of impact and model-derived relative importance for all 8 predictors.
4. **Prediction Change Detection & Temporal Tracking**:
   - `RiskTrendService` records each prediction into `prediction_history`.
   - Cycle-over-cycle deltas ($\Delta P$, level shifts) are computed and classified into `DETERIORATING`, `IMPROVING`, `STABLE`, `SUDDEN_DETERIORATION`, or `RECOVERY_DETECTED`.
5. **Operational Triage Prioritization**:
   - `PriorityService` calculates a composite score combining predicted flood probability (40%), deterioration velocity (20%), rainfall accumulation (15%), shelter accessibility deficit (15%), and confidence (10%).
   - Triage ranking: `Critical`, `High`, `Medium`, `Low`.
6. **Command Center Event Ledger**:
   - `TimelineService` records `prediction_cycle`, `weather_sync`, `risk_transition`, `alert_generated`, and `model_fallback_activation` in `operational_events`.

---

## 4. Database Schema (Alembic Migration 004)

- **`prediction_history`**: Audit trail of all multi-horizon predictions with features, attributions, confidence, and rainfall.
- **`risk_transitions`**: Log of risk level transitions, probability deltas, and trend classifications.
- **`operational_events`**: Chronological command center timeline ledger.
- **`zone_priorities`**: Sector triage rankings, composite priority scores, and recommended actions.
