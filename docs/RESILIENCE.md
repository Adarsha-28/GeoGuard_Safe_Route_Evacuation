# GeoGuard V6 Municipal Resilience Scoring

## 1. Mathematical Formulation

GeoGuard V6 introduces a transparent, multi-factor municipal flood disaster resilience index ($R_{system}$) bounded on a scale of $[0, 100]$:

$$R_{system} = 0.25 R_{shelter} + 0.25 R_{route} + 0.15 R_{data} + 0.15 R_{model} + 0.20 R_{ops}$$

```
+-------------------------------------------------------------------------------+
|                      R_system = Municipal Resilience Index                    |
+-------------------+-------------------+---------------+---------------+-------+
| Shelter (25%)     | Route (25%)       | Data (15%)    | Model (15%)   | Ops (20%)
| - Capacity Headroom| - Clear Paths %   | - Freshness   | - ML Loaded   | - DB Status
| - Active Shelters | - Hazard Index    | - Retries OK  | - Fallback OK | - Scheduler Heartbeat
| - Surrounding Risk| - Exposure %      | - Bounds OK   | - Feature Val | - Error Rate
+-------------------+-------------------+---------------+---------------+-------+
```

---

## 2. Component Subscores

### 1. Shelter Network Resilience ($R_{shelter}$, Weight: 0.25)
Evaluates relief center availability and physical safety under stress:
$$R_{shelter} = 100 \times \left(0.35 \frac{S_{active}}{S_{total}} + 0.40 \frac{C_{remaining}}{C_{total}} + 0.25 \frac{S_{safe}}{S_{total}}\right)$$
- $\frac{S_{active}}{S_{total}}$: Proportion of operational relief centers.
- $\frac{C_{remaining}}{C_{total}}$: Remaining spare capacity ratio under requested demand factor.
- $\frac{S_{safe}}{S_{total}}$: Proportion of shelters located outside high/severe hazard zones.

### 2. Route Network Resilience ($R_{route}$, Weight: 0.25)
Evaluates transportation and evacuation route viability:
$$R_{route} = 100 \times \left(0.40 \frac{N_{available}}{N_{total}} + 0.35 (1 - \overline{H}_{sim}) + 0.25 (1 - \overline{E}_{severe})\right)$$
- $\frac{N_{available}}{N_{total}}$: Ratio of routes retaining `AVAILABLE` status.
- $\overline{H}_{sim}$: Mean simulated hazard exposure score along evaluated route segments.
- $\overline{E}_{severe}$: Mean percentage of route distance exposed to severe simulated hazard.

### 3. Data Ingestion Resilience ($R_{data}$, Weight: 0.15)
Evaluates telemetry reliability and meteorological data freshness:
- Freshness: $100$ if updated within 1 hour; penalized down to $40$ if $>6$ hours old.
- Ingestion Status: $100$ for healthy connection; $65$ if running on cached fallback.
- Data Completeness: Penalized for missing values or failed API retries.

### 4. Predictive Model Resilience ($R_{model}$, Weight: 0.15)
Evaluates machine learning health and deterministic fallback readiness:
- ML Model Loaded: $100$ when Gradient Boosting pipeline is verified and loaded.
- Fallback Readiness: $85$ if operating on V2 deterministic multi-criteria formula.
- Feature Attribution Completeness: Verified across all 8 empirical predictors.

### 5. Operational Infrastructure Health ($R_{ops}$, Weight: 0.20)
Evaluates backend operational continuity:
- PostgreSQL / PostGIS connection status and connection pool health.
- Background scheduler execution heartbeats and non-blocking recovery.
- Zero fatal unhandled exceptions during continuous monitoring cycles.

---

## 3. Resilience Classification Bands

| Score Range | Category | Operational Posture | Command Center Action |
| :--- | :--- | :--- | :--- |
| **80.0 – 100.0** | **Robust** | High redundancy, all shelters have surplus headroom, all routes clear. | Routine monitoring; standard readiness. |
| **60.0 – 79.9** | **Moderate** | Localized stress; isolated shelters approaching capacity; caution routes active. | Pre-position relief personnel; alert secondary shelters. |
| **40.0 – 59.9** | **Stressed** | Significant capacity deficits; alternative routes required; data degraded. | Activate emergency response centers; divert traffic corridors. |
| **0.0 – 39.9** | **Vulnerable** | Critical systemic overload; primary routes compromised; multiple facilities overloaded. | City-wide disaster protocol; mandatory evacuation routing. |

---

## 4. Controlled Failure Simulation & Verification

GeoGuard includes 6 controlled failure injection routines accessed via `POST /api/v6/resilience/failure-test`:

| Simulation Type | Component Injected | Fallback Mechanism | Degraded Status |
| :--- | :--- | :--- | :--- |
| `WEATHER_API_UNAVAILABLE` | Open-Meteo endpoint offline | Cached observation or zero-baseline | `degraded` |
| `WEATHER_DATA_STALE` | Ingestion age exceeds 6h | Conservative bounds + stale alert | `degraded_stale` |
| `ML_MODEL_UNAVAILABLE` | ML pipeline artifact corrupted | V2 Deterministic Multi-Criteria Formula | `ml_fallback_active` |
| `DATABASE_UNAVAILABLE` | PostgreSQL connection failure | Standardized HTTP 503 degraded envelope | `service_degraded` |
| `OSRM_UNAVAILABLE` | OSRM routing server timeout | Geometric straight-line estimation | `routing_degraded` |
| `SCHEDULER_FAILURE` | Periodic background task crash | Thread supervisor auto-restart & retry | `scheduler_degraded` |
