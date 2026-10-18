# GeoGuard V5 — Command Center Operations & Decision Support Manual

## 1. Operational Philosophy: Near-Real-Time Decision Support

GeoGuard is explicitly engineered as a **near-real-time operational flood intelligence and decision support platform**. 

> [!IMPORTANT]
> **Advisory Terminology Disclaimer**:
> All risk ratings, forecast horizons, priority scores, and route assessments produced by GeoGuard are predictive advisory models designed to assist incident commanders and emergency responders. GeoGuard does not replace field observation or statutory civil defense authority.

---

## 2. Command Center Startup & Verification

### PostgreSQL 18 + PostGIS 3.6 Cluster
```powershell
# Verify running local PostgreSQL cluster
Get-Process *postgres*
netstat -ano | findstr 5433
```

### Server Execution
```powershell
python main.py
```
Expected output:
```
[INFO] Starting GeoGuard v5.0.0 (V5 Predictive Flood Intelligence)...
[INFO] Database connection: PostgreSQL 18 + PostGIS connected successfully.
[INFO] GeoGuard Operational Scheduler initialized. Periodic cycle interval: 300s.
[READY] Server operational at http://localhost:8000/
```

---

## 3. Key Operational APIs

| Operational Capability | HTTP Method & Endpoint | Primary Parameters |
| :--- | :--- | :--- |
| **Multi-Horizon Forecast** | `GET /api/predictions/forecast` | `horizon=nowcast\|6h\|12h\|24h`, `grid_id` |
| **Prediction History** | `GET /api/predictions/history/{grid_id}` | `horizon`, `limit` |
| **Temporal Risk Trends** | `GET /api/risk/trends/{grid_id}` | `hours`, `horizon` |
| **Sector Triage Prioritization**| `GET /api/priorities` | `horizon`, `risk_level`, `category` |
| **Shelter Intelligence** | `GET /api/shelters/intelligence` | `lat`, `lng`, `radius_km` |
| **Route Intelligence** | `GET /api/routes/intelligence` | `src_lat`, `src_lng`, `shelter_id` |
| **Operational Timeline** | `GET /api/operations/timeline` | `hours`, `event_type`, `grid_id`, `limit` |

---

## 4. Known Operational Limitations

1. **Near-Real-Time Weather Latency**: Open-Meteo updates global numerical models hourly. Localized flash cloudbursts under 15 minutes may experience slight ingestion latency.
2. **Census Demographics Omission**: Zone prioritization omits population counts because ward-level census statistics are not empirically available in the open-source dataset. Rather than manufacturing synthetic population numbers, prioritization relies strictly on measurable physical and spatial variables (hazard probability, deterioration velocity, rainfall accumulation, shelter accessibility deficit).
3. **OSRM Road Network Assumption**: Evacuation routing models use OpenStreetMap driving geometries. Physical obstructions (e.g. fallen trees, downed power lines) must be confirmed by field observers.
