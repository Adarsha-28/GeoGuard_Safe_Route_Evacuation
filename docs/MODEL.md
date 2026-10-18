# GeoGuard V3: Machine Learning Model Specification

---

## 1. Model Overview

* **Model Name**: GeoGuard Empirical Flood Risk Forecaster
* **Model Version**: `v3.0.0`
* **Production Algorithm**: Gradient Boosting Classifier (`sklearn.ensemble.GradientBoostingClassifier`)
* **Serialization Format**: Joblib pipeline (`models/trained/geoguard_flood_rf_v3.joblib`)
* **Prediction Horizon**: 24-Hour Flood Inundation Hazard
* **Task Type**: Binary Flood Occurrence Probability & Multi-Class Risk Mapping

---

## 2. Input Features Vector

The model ingests 8 numerical features in strict sequence:

| Index | Feature Name | Data Type | Physical Meaning & Range |
|---|---|---|---|
| 0 | `rainfall_current_mm` | Float | 24-hour daily precipitation ($0\text{--}350+\text{ mm}$) |
| 1 | `rainfall_3d_accum_mm` | Float | 3-day antecedent rolling precipitation sum ($0\text{--}600+\text{ mm}$) |
| 2 | `rainfall_7d_accum_mm` | Float | 7-day cumulative precipitation ($0\text{--}1000+\text{ mm}$) |
| 3 | `elevation_m` | Float | Sector terrain elevation above sea level ($1.0\text{--}16.0\text{ m}$) |
| 4 | `distance_to_water_m` | Float | Distance to nearest river/canal/lake ($100\text{--}5000\text{ m}$) |
| 5 | `latitude` | Float | Geographic latitude coordinate ($12.85\text{--}13.20^\circ\text{N}$) |
| 6 | `longitude` | Float | Geographic longitude coordinate ($80.10\text{--}80.30^\circ\text{E}$) |
| 7 | `month` | Integer | Calendar month indicator ($1\text{--}12$) |

---

## 3. Algorithm & Hyperparameters

Selected best model: **Gradient Boosting Classifier**
* `n_estimators`: 80
* `learning_rate`: 0.08
* `max_depth`: 4
* `subsample`: 1.0
* `random_state`: 42 (fixed seed for deterministic reproducibility)

---

## 4. Probability to Categorical Risk Mapping

The model outputs continuous class probability $P(\text{Flood} \mid X) \in [0.0, 1.0]$. The probability is mapped to operational risk categories as follows:

| Probability Range | Categorical Stance | Recommended Operational Action |
|---|---|---|
| $0.00 \le P < 0.25$ | **Low** | Routine municipal monitoring |
| $0.25 \le P < 0.60$ | **Moderate** | Close watch; clear street drains |
| $0.60 \le P < 0.85$ | **High** | Prepare relief shelters; issue warnings |
| $0.85 \le P \le 1.00$ | **Severe** | Activate emergency evacuations |

---

## 5. Inference Service & Graceful Fallback

Inference is encapsulated in `backend.services.ml_prediction_service.MLPredictionService`:
1. Model and metadata are loaded once into memory on server boot.
2. Inbound requests pass coordinate boundary checks via Pydantic.
3. If the model artifact is missing or corrupted, the service **automatically falls back** to the V2 deterministic multi-criteria formula:
   $$\text{Score} = (0.50 \cdot \text{RainScore}) + (0.25 \cdot \text{ElevScore}) + (0.25 \cdot \text{WaterScore})$$
4. The response explicitly sets `is_fallback: true` and `model_version: "v2.0-deterministic-fallback"`.
