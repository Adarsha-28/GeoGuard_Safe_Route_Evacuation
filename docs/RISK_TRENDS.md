# GeoGuard V5 — Temporal Risk Tracking & Prediction Change Detection

## 1. Overview

Flooding in coastal deltas like Chennai is dynamic: risks do not manifest instantaneously, but evolve over cumulative rainfall cycles. GeoGuard V5 implements **Temporal Intelligence** and a **Cycle-over-Cycle Prediction-Delta Engine** to detect changes before severe inundation occurs.

---

## 2. Prediction Delta Engine

Every prediction cycle compares cycle $N$ with cycle $N-1$ for each sector and horizon:

$$\Delta P = P_N - P_{N-1}$$
$$\Delta R = R_N - R_{N-1} \quad \text{(Rainfall)}$$
$$\Delta C = C_N - C_{N-1} \quad \text{(Confidence)}$$

### Trend State Machine

```
              +-------------------------+
              |         STABLE          |
              +-------------------------+
                /          |          \
 +-------------+           |           +-------------+
 |                         |                         |
 v                         v                         v
[DETERIORATING]  [SUDDEN_DETERIORATION]   [IMPROVING] / [RECOVERY]
(ΔP >= +0.10 or   (ΔP >= +0.35 or          (ΔP <= -0.10 or
 Rank jump +1)     Rank jump >= +2)         Severe -> Low)
```

| Trend Classification | Trigger Criteria | Advisory Implication |
| :--- | :--- | :--- |
| **`SUDDEN_DETERIORATION`** | Risk rank jumps $\ge +2$ levels (e.g. Low $\to$ High) OR $\Delta P \ge +0.35$ | Immediate critical alert; rapid drainage failure likely. |
| **`DETERIORATING`** | Risk rank increases by $+1$ level OR $\Delta P \ge +0.10$ | Warning escalation; prepare relief shelters. |
| **`STABLE`** | Risk rank unchanged and $|\Delta P| < 0.10$ | Normal monitoring posture; routine cycle. |
| **`IMPROVING`** | Risk rank drops by $\ge 1$ level OR $\Delta P \le -0.10$ | Informational bulletin; road drainage succeeding. |
| **`RECOVERY_DETECTED`** | Previous risk was Severe/High, current is Moderate/Low with $\Delta P \le -0.20$ | De-escalate active alerts; confirm road clearance. |

---

## 3. Database Persistence

Transitions are persisted to PostgreSQL tables:
- **`prediction_history`**: Every snapshot across horizons (`nowcast`, `6h`, `12h`, `24h`).
- **`risk_transitions`**: Audited ledger of every non-stable transition with timestamps and deltas.

---

## 4. REST API

```http
GET /api/risk/trends/{grid_id}?hours=24&horizon=nowcast
```

Example response:
```json
{
  "grid_id": 1,
  "grid_name": "Velachery",
  "horizon": "nowcast",
  "query_window_hours": 24,
  "data_points_count": 12,
  "current_risk_level": "High",
  "current_probability": 0.78,
  "current_confidence": 0.88,
  "overall_trend": "DETERIORATING",
  "overall_probability_delta": 0.32,
  "history": [...]
}
```
