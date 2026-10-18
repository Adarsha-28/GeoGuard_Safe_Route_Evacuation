# GeoGuard V3: Empirical Model Evaluation & Comparative Benchmark

This document presents the objective, empirical performance evaluation of candidate Machine Learning models against the V2 deterministic baseline on the strictly held-out test dataset (1,020 records from 2022–2023).

---

## 1. Candidate Models Benchmark Table

Evaluated on held-out test set ($N = 1,020$):

| Model Architecture | Precision | Recall | F1-Score | ROC-AUC | PR-AUC | Selection Stance |
|---|---|---|---|---|---|---|
| **V2 Deterministic Formula (Baseline)** | 0.6098 | 0.6048 | 0.6073 | 0.8161 | 0.6503 | Retained as Comparative Baseline |
| **Logistic Regression (Class-Weighted)** | 0.3769 | 1.0000 | 0.5475 | 0.9866 | 0.9075 | High false positive rate |
| **Random Forest Classifier (Balanced)** | 0.6667 | 1.0000 | 0.8000 | 1.0000 | 1.0000 | Strong non-linear boundary |
| **Gradient Boosting Classifier (Best)** | **0.8000** | **1.0000** | **0.8889** | **0.9827** | **0.8000** | **Selected Production Model** |

---

## 2. Confusion Matrices (Held-Out Test Set)

### Selected Best Model: Gradient Boosting Classifier
```text
                  Predicted Negative    Predicted Positive
Actual Negative          865                   31
Actual Positive            0                  124
```
* **True Negatives (TN)**: 865 (Correctly predicted safe non-flood conditions)
* **False Positives (FP)**: 31 (Cautious false alarms)
* **False Negatives (FN)**: 0 (Zero missed disaster events)
* **True Positives (TP)**: 124 (Accurately flagged flood inundation events)

### Baseline Model: V2 Deterministic Multi-Criteria Formula
```text
                  Predicted Negative    Predicted Positive
Actual Negative          848                   48
Actual Positive           49                   75
```
* The V2 baseline missed 49 actual flood incidents ($\text{Recall} = 60.5\%$). The V3 Gradient Boosting model achieved $100\%$ Recall with an F1 score improvement from $0.6073 \to 0.8889$ ($+46.4\%$ increase).

---

## 3. Feature Importance & Attributions

Measured relative feature importances (Gini Impurity & Tree Splitting):

| Rank | Feature | Importance | Physical Interpretation |
|---|---|---|---|
| 1 | `rainfall_3d_accum_mm` | **44.00%** | Soil saturation & stormwater system capacity overload |
| 2 | `rainfall_7d_accum_mm` | **30.24%** | Prolonged basin catchment accumulation |
| 3 | `month` | **14.70%** | North-East Monsoon seasonality (Oct–Dec) |
| 4 | `rainfall_current_mm` | **8.08%** | Immediate flash precipitation rate |
| 5 | `elevation_m` | **1.07%** | Topographic depression & low-lying pooling |
| 6 | `distance_to_water_m` | **1.07%** | River backwater & canal overflow vulnerability |
| 7 | `longitude` | **0.82%** | East-west spatial gradient (coastal vs inland) |
| 8 | `latitude` | **0.02%** | North-south spatial distribution |

---

## 4. Key Takeaways & Scientific Integrity Notice

> [!NOTE]
> **Performance Disclosure:**
> - The model's metrics reflect performance on the held-out 2022–2023 Chennai evaluation test set under historical storm events (including Cyclone Michaung).
> - This performance is **dataset-dependent** and does **NOT** establish operational flood-warning infallibility under extreme climate shifts or unobserved micro-drainage failures.
> - GeoGuard preserves the V2 deterministic multi-criteria model as an active fallback.
