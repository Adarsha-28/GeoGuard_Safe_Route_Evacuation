# GeoGuard V6 Scenario Simulation Guide

## Overview

The **GeoGuard V6 Scenario Simulation Engine** empowers emergency command operators to model extreme precipitation events, assess network resilience, and plan adaptive evacuations before catastrophic flooding occurs.

---

## 1. Simulation Methodology

### Non-Destructive Vector Scaling
Rather than requiring model re-training or altering production database state, the simulation engine operates on input feature vectors:
1. Retrieves baseline forecast precipitation for the requested horizon ($H \in \{\text{nowcast}, 6\text{h}, 12\text{h}, 24\text{h}\}$).
2. Applies the requested precipitation multiplier:
   $$\text{Rainfall}_{sim} = \text{Rainfall}_{base} \times \text{Multiplier}$$
3. Re-computes rolling accumulations (3-day and 7-day cumulative values) reflecting sustained rainfall stress.
4. Executes empirical inference through `MLPredictionService` using the scaled feature vector.
5. Derives probability delta:
   $$\Delta P = P_{sim} - P_{base}$$
6. Classifies transitions:
   - **`DETERIORATED`**: Risk severity increases (e.g., Low $\to$ Moderate, Moderate $\to$ High, High $\to$ Severe).
   - **`IMPROVED`**: Risk severity decreases.
   - **`UNCHANGED`**: Risk severity band remains constant.

### Standard Presets
| Preset | Rainfall Multiplier | Description | Operational Use Case |
| :--- | :--- | :--- | :--- |
| `+25% Surge` | `1.25x` | Moderate monsoon intensification | Pre-monsoon drainage buffer assessment |
| `+50% Surge` | `1.50x` | Heavy convective storm band | Localized waterlogging & underpass blockages |
| `+75% Surge` | `1.75x` | Severe cyclone peripheral band | Canal overflow and low-lying sector alert |
| `+100% Surge` | `2.00x` | Extreme catastrophic rainfall | City-wide emergency evacuation & relief surge |
| `Custom` | User-defined | Fine-grained sensitivity analysis | Engineering stress test of infrastructure |

---

## 2. Spatial Propagation Modeling

Using PostGIS topological boundaries (`ST_Touches` and `ST_DWithin`), sectors under simulation are classified into three spatial propagation states:
1. **`DIRECT`**: Sector experienced direct flood risk deterioration or reached High / Severe classification under the simulated rainfall.
2. **`NEIGHBOR`**: Sector maintains Low / Moderate direct risk but directly borders one or more `DIRECT` hazard sectors. This highlights early warning buffer zones susceptible to runoff spillover.
3. **`UNAFFECTED`**: Sector has low direct risk and does not border any active hazard zones.

---

## 3. Shelter Capacity Stress Testing

To test municipal relief capacity without inventing or fabricating real-world population data, GeoGuard utilizes **Simulation Demand Factors**:
- **Baseline Allocation**: Nominal utilization estimated at 40% of rated capacity.
- **Demand Multipliers**: `1.0x` (nominal), `1.25x` (+25% surge), `1.5x` (+50% surge), `2.0x` (double demand).
- **Simulated Headroom**:
  $$\text{Capacity}_{rem} = \text{Capacity}_{total} - (\text{Occupancy}_{base} \times \text{DemandFactor})$$
- **Operational Classification**:
  - `NORMAL`: $\text{Capacity}_{rem} \ge 0.25 \times \text{Capacity}_{total}$
  - `STRESSED`: $0 \le \text{Capacity}_{rem} < 0.25 \times \text{Capacity}_{total}$
  - `OVERLOADED`: $\text{Capacity}_{rem} < 0$. When overloaded, the adaptive evacuation planner automatically redirects excess evacuees to the nearest alternative facility with spare capacity.

---

## 4. Multi-Path Evacuation Route Resilience

For high-priority sectors, the route resilience engine evaluates three alternative paths:
1. **Primary Route**: Optimal driving path to the primary shelter via OSRM.
2. **Alternative Route 1**: Evacuation path routed to the secondary backup shelter.
3. **Alternative Route 2**: Lateral offset path bypassing central urban choke points.

Each path is sampled point-by-point against simulated sector risk layers:
- **`AVAILABLE`**: $<15\%$ high-risk exposure; low average hazard.
- **`CAUTION`**: $15\% - 40\%$ exposure; moderate localized water accumulation.
- **`UNSAFE`**: $>40\%$ high-risk exposure or average hazard $\ge 0.50$.
- **`BLOCKED_BY_SIMULATION`**: $\ge 35\%$ severe exposure or average hazard $\ge 0.75$ with severe peak. *Disclaimer: Denotes simulated inundation hazard, not physical road closure.*

---

## 5. API Reference

### POST `/api/v6/scenarios/simulate`
```json
{
  "name": "Northeast Monsoon Cyclone Surge +50%",
  "rainfall_multiplier": 1.5,
  "horizon": "6h",
  "simulation_demand_factor": 1.25,
  "description": "Simulation of 6-hour convective intensification",
  "operator": "Command Center Duty Officer"
}
```

### GET `/api/v6/scenarios/{scenario_id}/compare`
Returns side-by-side metrics comparing live baseline conditions with simulated outcomes.
