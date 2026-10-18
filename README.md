# 🛡️ GeoGuard: Flood Scenario Simulation, Adaptive Evacuation & Resilience Intelligence

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2F18-336791.svg)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4%2F3.6-5B8C00.svg)](https://postgis.net/)
[![Tests](https://img.shields.io/badge/Tests-117%20Passed%20(100%25)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

**GeoGuard** is an enterprise-grade predictive geospatial disaster management, scenario simulation, and evacuation resilience platform designed for Chennai, Tamil Nadu. It couples real-time meteorological synchronization, empirical Gradient-Boosted machine learning flood prediction, PostGIS topological spatial queries, and multi-path safe evacuation routing into an interactive operational command dashboard.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Interactive Command Dashboards                       │
│   HTML5 / Vanilla CSS3 / JavaScript (ES6) / Leaflet.js / Chart.js      │
│   • Map Dashboard:    /frontend/index.html                             │
│   • Command Center:   /frontend/admin.html (Auth: admin / admin123)    │
│   • Emergency Guide:  /frontend/emergency.html                         │
│   • Sector Catalog:   /frontend/areas.html                             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP REST (JSON / GeoJSON)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Application Layer                        │
│   - Unified Exception Handlers & Standard Error Envelope               │
│   - Lifespan Context Manager (Background Weather Synchronization)      │
│   - Interactive OpenAPI Swagger UI (/docs) & ReDoc (/redoc)            │
├────────────────────────────────────────────────────────────────────────┤
│   API Routers (/backend/api/):                                         │
│   ├── health.py        -> GET  /api/health                             │
│   ├── grids.py         -> GET  /api/grids, GET /api/grids/{id}         │
│   ├── risk.py          -> GET  /api/risk/{id}, GET /api/risk/point     │
│   ├── shelters.py      -> GET  /api/shelters, GET /api/shelters/nearby │
│   ├── routes.py        -> POST /api/routes/safe, /api/evacuation/start │
│   ├── alerts.py        -> GET  /api/alerts, POST /api/alerts           │
│   ├── weather.py       -> POST /api/weather/sync                       │
│   ├── predictions.py   -> POST /api/predictions/flood                  │
│   ├── trends.py        -> GET  /api/trends/risk                        │
│   ├── priorities.py    -> GET  /api/priorities/zones                   │
│   ├── timeline.py      -> GET  /api/operations/timeline                │
│   └── v6.py            -> POST /api/v6/simulate, GET /api/v6/resilience│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Pydantic v2 Schemas & Validation
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Service Business Logic                          │
│   ├── scenario_simulation_service.py -> Multi-horizon rainfall surge   │
│   ├── spatial_propagation_service.py -> PostGIS ST_Touches/ST_DWithin  │
│   ├── adaptive_evacuation_service.py -> Dynamic shelter stress tests   │
│   ├── route_resilience_service.py    -> Multi-path alternative paths   │
│   ├── resilience_scoring_service.py  -> 5-Factor municipal index       │
│   ├── failure_simulation_service.py  -> 6 Controlled fallback doubles  │
│   ├── ml_prediction_service.py       -> Gradient Boosting ML inference │
│   ├── routing_service.py             -> OSRM road graph & hazard cost  │
│   └── operational_scheduler.py       -> Non-blocking concurrency worker│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQLAlchemy 2.0 / GeoAlchemy2
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 16/18 + PostGIS 3.4/3.6                  │
│   - Spatial GiST Indexes (idx_shelters_location, idx_grids_geom)       │
│   - Connection Pool (pool_size=10, max_overflow=20, pre_ping=True)    │
│   - Alembic Schema Migrations & Atomic Check Constraints               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Capabilities

1. **Flood Scenario Simulation Engine**: Multi-horizon rainfall surge stress testing (+25%, +50%, +75%, +100%, custom multiplier) modifying feature vectors with zero model retraining; outputs $\Delta P$, risk category transitions, and mandatory disclaimer `"SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA"`.
2. **PostGIS Spatial Risk Propagation**: Distinguishes direct flood hazards from neighbor-influenced buffer hazards using topological spatial boundaries (`ST_Touches` and `ST_DWithin`).
3. **Adaptive Evacuation Planner**: Triage prioritization and dynamic allocation of primary and backup relief shelters.
4. **Shelter Capacity Stress Testing**: Evaluates facility headroom under surge demand factors (1.0x to 2.0x), classifying facilities into `NORMAL`, `STRESSED`, or `OVERLOADED` and discovering alternative relief facilities.
5. **Route Resilience & Alternatives**: Evaluates multi-path route alternatives (Primary, Alternative 1, Alternative 2) with status indicators (`AVAILABLE`, `CAUTION`, `UNSAFE`, `BLOCKED_BY_SIMULATION`).
6. **Mathematical Resilience Index ($R_{system}$)**: Quantifies municipal disaster resilience on a transparent $[0, 100]$ scale across shelter, route, data, model, and operational dimensions:
   $$R_{system} = 0.25 R_s + 0.25 R_r + 0.15 R_d + 0.15 R_m + 0.20 R_o$$
7. **Empirical ML Flood Prediction**: Pre-trained Gradient-Boosted classifier trained on Chennai inundation surveys and meteorological reanalysis data with automatic deterministic fallback.
8. **100% Automated Test Suite**: 117 automated unit, API, and integration tests passing with 0 regressions.

---

## ⚡ Quickstart & How to Run

### Prerequisites
- **Python 3.10+**
- **PostgreSQL 16+ with PostGIS** (or use the automated local setup script / Docker)

---

### Step 1: Install Python Dependencies
```powershell
cd C:\Users\ADARSHA\Desktop\GeoGuard\GeoGuard_Safe_Evacuation
pip install -r requirements.txt
```

---

### Step 2: Configure Environment & Start Database

Create `.env` from template:
```powershell
copy .env.example .env
```

Start PostgreSQL + PostGIS:

- **Option A — Automated Local Setup (Windows Standalone, Port 5433):**
  ```powershell
  python scripts/setup_local_postgres.py
  ```
  *(Starts the isolated user-space PostgreSQL instance, verifies PostGIS, and updates `.env` automatically).*

- **Option B — Docker Compose:**
  ```powershell
  docker compose up -d
  ```

---

### Step 3: Run Database Migrations & Initial Data Loading
Execute schema migrations and load all 34 Chennai sectors, 25 relief shelters, and baseline alerts:
```powershell
python scripts/init_db.py
```
*(You will see: `[SUCCESS] GeoGuard V2 database setup completed successfully!`)*

---

### Step 4: Start the GeoGuard Application
```powershell
python main.py
```
*(Or alternatively: `python -m uvicorn backend.main:app --port 8000 --reload`)*

---

### Step 5: Open in Your Browser

| Interface | URL | Description |
|---|---|---|
| **Interactive Map Dashboard** | [http://localhost:8000/frontend/index.html](http://localhost:8000/frontend/index.html) | Live Chennai flood risk grid, shelter discovery & safe evacuation routes |
| **Administrative Command Center** | [http://localhost:8000/frontend/admin.html](http://localhost:8000/frontend/admin.html) | What-If Scenario Lab, Resilience Scoring, and Incident Timeline *(Login: `admin` / `admin123`)* |
| **Emergency Guide & Contacts** | [http://localhost:8000/frontend/emergency.html](http://localhost:8000/frontend/emergency.html) | Critical helplines, zonal officers, and safety checklists |
| **Sector Directory** | [http://localhost:8000/frontend/areas.html](http://localhost:8000/frontend/areas.html) | Comprehensive sector catalog with historical risk levels |
| **OpenAPI Swagger UI** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API exploration and test client |
| **ReDoc Documentation** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean technical API specification |

---

## 🧪 Testing

Execute the complete 117-test automated test suite across unit, API, and integration tiers:
```powershell
python -m pytest tests/ -v
```

Run spatial query performance benchmarks:
```powershell
python scripts/benchmark_spatial.py
```

Run simulation & resilience benchmarks:
```powershell
python scripts/benchmark_v6.py
```

---

## 📡 REST API Reference

| Method | Endpoint | Parameters / Body | Description |
|---|---|---|---|
| `GET` | `/api/health` | None | System status, database health, and active risk breakdown |
| `GET` | `/api/grids` | `?model=ml` / `deterministic` | GeoJSON FeatureCollection of all 34 monitored sectors |
| `GET` | `/api/grids/{id}` | `id: int` | GeoJSON Feature for specific monitored sector |
| `GET` | `/api/risk/point` | `lat, lng` | PostGIS polygon containment & nearest sector lookup |
| `GET` | `/api/risk/{id}` | `id: int` | Stored risk indicators for sector |
| `POST` | `/api/predictions/flood` | `{"latitude", "longitude", "rainfall_mm"}` | ML flood probability & 8-feature attribution |
| `GET` | `/api/predictions/forecast`| `?horizon=nowcast\|6h\|12h\|24h` | Multi-horizon risk predictions across all sectors |
| `GET` | `/api/trends/risk` | `?sector_id=int` | Prediction change detection & delta trends |
| `GET` | `/api/priorities/zones` | None | Operational sector triage prioritization ranking |
| `GET` | `/api/shelters` | None | All active relief shelters with available capacity |
| `GET` | `/api/shelters/nearby` | `lat, lng, radius, limit` | PostGIS `ST_DWithin` spatial shelter discovery |
| `POST` | `/api/routes/safe` | `{"latitude", "longitude"}` | OSRM road polyline with PostGIS flood hazard penalty |
| `POST` | `/api/evacuation/start` | `{"shelter_id": int}` | Atomic transaction decrementing shelter capacity |
| `GET` | `/api/alerts` | None | Active emergency advisory bulletins |
| `POST` | `/api/alerts` | `{"title", "severity", "zone", "message"}` | Publish administrative emergency bulletin |
| `POST` | `/api/v6/simulate` | `{"multiplier": 1.5, "rainfall_mm": 50}` | Non-destructive rainfall stress simulation |
| `GET` | `/api/v6/resilience` | None | Composite 5-factor municipal resilience score |
| `GET` | `/api/v6/decision-log` | None | Chronological operational decision audit ledger |
| `POST` | `/api/v6/simulate-failure` | `{"mode": "weather_api_outage"}` | Controlled test double failure verification |

---

## 📁 Repository Structure

```text
GeoGuard_Safe_Evacuation/
├── alembic/                # Alembic database migrations
├── backend/                # FastAPI application
│   ├── api/                # REST API endpoint routers
│   ├── database/           # PostgreSQL connection pool & session manager
│   ├── models/             # SQLAlchemy ORM models with GeoAlchemy2 geometries
│   ├── schemas/            # Pydantic v2 request/response schemas
│   └── services/           # Business logic, ML pipelines, and schedulers
├── data/
│   ├── raw/                # Historical survey KML & GeoJSON boundaries
│   ├── processed/          # Training datasets
│   └── chennai_places.csv  # 34 monitored Chennai sectors with elevation & water proximity
├── docs/                   # Architectural & technical documentation
├── frontend/               # Interactive Leaflet & Chart.js dashboard
├── models/
│   └── trained/            # Serialized Gradient Boosting ML models (.joblib)
├── scripts/                # Database initialization, loaders, and benchmarks
├── tests/                  # 117 automated unit, API, and integration tests
├── .env.example            # Environment configuration template
├── .gitignore              # Production-grade gitignore
├── docker-compose.yml      # PostGIS Docker Compose specification
├── main.py                 # Application root entrypoint launcher
└── requirements.txt        # Production dependencies
```

---

## 📜 License
This project is open-source under the MIT License.
