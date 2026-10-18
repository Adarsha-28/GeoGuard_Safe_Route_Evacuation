# GeoGuard V6 System Architecture

## Flood Scenario Simulation, Adaptive Evacuation & Resilience Intelligence

GeoGuard V6 elevates the municipal flood management platform from purely predictive multi-horizon forecasting into an **interactive stress simulation, spatial propagation modeling, adaptive evacuation management, and transparent resilience quantification engine**.

---

## 1. High-Level Architectural Flow

```mermaid
flowchart TD
    subgraph Weather_and_Hydrology [Weather & Hydrological Ingestion]
        OM[Open-Meteo API] --> WS[WeatherIngestionService]
        WS --> FS[ForecastService (Nowcast, 6h, 12h, 24h)]
    end

    subgraph V6_Simulation_Engine [V6 Scenario Simulation Engine]
        UI[V6 Scenario Lab UI] -->|Multiplier & Demand Factor| V6API[/api/v6/scenarios/simulate]
        V6API --> SIM[ScenarioSimulationService]
        FS -->|Baseline Rainfall Vectors| SIM
        SIM -->|Scale Rainfall Vector| ML[MLPredictionService (Zero Retraining)]
        ML -->|Simulated Probabilities| SIM
    end

    subgraph Spatial_and_Network_Resilience [Spatial & Network Intelligence]
        SIM --> SP[SpatialPropagationService (PostGIS ST_Touches)]
        SIM --> EVAC[AdaptiveEvacuationService]
        SIM --> ROUTE[RouteResilienceService (Multi-Path OSRM)]
        EVAC -->|Demand Factors 1.0x - 2.0x| SH[Shelter Capacity Stress]
        ROUTE -->|Primary / Alt 1 / Alt 2| RT[Route Hazard Exposure]
    end

    subgraph Scoring_and_Persistence [Resilience & Audit Ledger]
        SIM --> RS[ResilienceScoringService]
        RS -->|5-Factor System Index| SCORES[(resilience_assessments)]
        SIM --> AUDIT[(decision_audit_log)]
        SIM --> DB[(scenarios, scenario_sector_results, scenario_shelter_results, scenario_route_results)]
    end
```

---

## 2. Core Architectural Pillars

### A. Non-Destructive Scenario Simulation
- **No Retraining Overhead**: Simulates rainfall surges (+25%, +50%, +75%, +100%, custom) directly across the 8-feature input vector without re-fitting the underlying Gradient Boosting model.
- **Multi-Horizon Propagation**: Applies scaled precipitation vectors across Nowcast, 6h, 12h, and 24h operational forecast horizons.
- **Delta Probability ($\Delta P$)**: Calculates exact probability deltas ($P_{sim} - P_{base}$) and classifies risk transitions (e.g., `DETERIORATED`, `UNCHANGED`, `IMPROVED`).
- **Strict Integrity Disclaimer**: All simulation outputs and database records are explicitly tagged with `"SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA"`.

### B. PostGIS Spatial Risk Propagation
- Evaluates topological adjacency between Chennai's 34 monitored zones using PostGIS `ST_Touches` and `ST_DWithin`.
- Disaggregates simulated risk into:
  - **Direct Flood Hazard**: Saturated or severe risk originating directly within the sector.
  - **Neighbor-Influenced Hazard**: Moderate or low risk sectors directly adjacent to high/severe zones.
  - **Spatial Concentration Index**: Geographic clustering density of flood stress across municipal zones.

### C. Adaptive Evacuation & Shelter Stress Engine
- Evaluates shelter capacity stress using simulation demand factors (1.0x, 1.25x, 1.5x, 2.0x) without fabricating census populations.
- Categorizes facilities into operational states:
  - `NORMAL`: Headroom $\ge 25\%$.
  - `STRESSED`: Headroom $< 25\%$ but $> 0\%$.
  - `OVERLOADED`: Simulated demand exceeds capacity; automatically activates nearest alternative relief center with surplus headroom.
- Computes dynamic suitability scores penalizing facilities near high flood hazard zones.

### D. Route Resilience & Multi-Path Alternatives
- Computes three independent path alternatives per priority sector:
  - **Primary Route**: Direct path to primary designated shelter.
  - **Alternative Route 1**: Evacuation path redirected to backup shelter facility.
  - **Alternative Route 2**: Lateral waypoint diversion avoiding central hazard corridors.
- Traverses route geometries point-by-point, evaluating simulated flood hazard exposure.
- Assigns definitive status badges: `AVAILABLE`, `CAUTION`, `UNSAFE`, and `BLOCKED_BY_SIMULATION`.

### E. Mathematical Resilience Index ($R_{system}$)
- Quantifies municipal operational posture on a deterministic $[0, 100]$ scale:
  $$R_{system} = 0.25 R_{shelter} + 0.25 R_{route} + 0.15 R_{data} + 0.15 R_{model} + 0.20 R_{ops}$$
- Transparent subscores ensure decision-makers understand exactly which municipal subsystems are stressed.

### F. Controlled Failure & Fallback Simulation
- 6 isolated test doubles enable incident response validation without modifying operational configurations:
  1. `WEATHER_API_UNAVAILABLE`: Fallback to cached observations or zero-baseline.
  2. `WEATHER_DATA_STALE`: Stale observation (>6h) detection with degraded operational alert.
  3. `ML_MODEL_UNAVAILABLE`: Instantaneous fallback to V2 multi-criteria deterministic model.
  4. `DATABASE_UNAVAILABLE`: Standardized 503 degraded error envelope.
  5. `OSRM_UNAVAILABLE`: Geometric straight-line estimation fallback.
  6. `SCHEDULER_FAILURE`: Thread supervisor auto-recovery without service interruption.

### G. Operational Decision Audit Trail
- Every scenario run, parameter adjustment, and failure injection is recorded into `decision_audit_log` with operator identity, JSON parameters, and impact summaries for post-incident review.

---

## 3. Database Schema (V6 Extension)

| Table Name | Primary Role |
| :--- | :--- |
| `scenarios` | Stores scenario configuration, multiplier, horizon, summary counts, and resilience scores. |
| `scenario_sector_results` | Sector-by-sector comparative risk, $\Delta P$, spatial propagation classification, and triage priority. |
| `scenario_shelter_results` | Shelter capacity stress metrics, demand factors, remaining capacity, and backup assignments. |
| `scenario_route_results` | Primary and alternative route trajectories, hazard scores, exposure %, and status badges. |
| `resilience_assessments` | Historical snapshots of system and subcomponent resilience scores. |
| `failure_simulations` | Audit ledger for controlled failure injections and fallback verification. |
| `decision_audit_log` | Immutable chronological operational event log for disaster command coordination. |
