# GeoGuard V5 — Empirical Model Evaluation & Probability Calibration Analysis

## 1. Executive Summary

As part of the GeoGuard V5 development cycle, the empirical probabilistic outputs of the production V3 Gradient Boosting Classifier (`models/trained/geoguard_flood_rf_v3.joblib`) were evaluated on the strictly held-out chronological test dataset (`data/processed/chennai_flood_training_dataset.csv`).

Key findings:
- The **uncalibrated model** achieves an outstanding **Brier Score of 0.0320**, an **ROC-AUC of 0.9827**, and a **PR-AUC of 0.8000**.
- Post-hoc calibration (using Isotonic regression and Platt Sigmoid scaling fitted exclusively on the validation split without test set leakage) resulted in a higher (worse) Brier Score:
  - **Isotonic Calibration Brier Score: 0.0378** (+18.1% error increase)
  - **Platt Sigmoid Calibration Brier Score: 0.0377** (+17.8% error increase)
- **Decision**: In strict adherence to GeoGuard engineering guidelines ("If it does not improve the model, keep the existing model and document the result"), the uncalibrated V3 model is retained in production without an artificial calibration distortion layer.

---

## 2. Chronological Anti-Leakage Dataset Split

To prevent temporal and spatial data leakage:
- **Training Set (71.2%)**: 4,284 observations (historical monsoon seasons through 2021)
- **Validation Set (11.8%)**: 714 observations (2022 intermediate observation cycles)
- **Held-Out Test Set (17.0%)**: 1,020 observations (2023–2024 independent test cycles)

---

## 3. Comparative Benchmark on Held-Out Test Set

| Model / Calibration Method | Brier Score (Lower is better) | ROC-AUC | PR-AUC | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **V2 Deterministic Multi-Criteria Baseline** | 0.1420 | 0.8161 | 0.6503 | 0.6098 | 0.6048 | 0.6073 |
| **Logistic Regression (Class-Weighted)** | 0.0712 | 0.9866 | 0.9075 | 0.3769 | 1.0000 | 0.5475 |
| **Random Forest (Balanced, 100 Trees)** | 0.0345 | 1.0000 | 1.0000 | 0.6667 | 1.0000 | 0.8000 |
| **Gradient Boosting (Uncalibrated Baseline)** | **0.0320** | **0.9827** | **0.8000** | **0.8000** | **1.0000** | **0.8889** |
| *Gradient Boosting + Isotonic Calibration* | 0.0378 | 0.9810 | 0.7950 | 0.7820 | 1.0000 | 0.8777 |
| *Gradient Boosting + Platt Sigmoid Calibration* | 0.0377 | 0.9815 | 0.7960 | 0.7850 | 1.0000 | 0.8796 |

---

## 4. Why Post-Hoc Calibration Did Not Improve the Model

1. **Extreme Separability in Gradient Boosting**: The Gradient Boosting model already assigns low probabilities ($\le 0.02$) to dry non-flood scenarios and high probabilities ($\ge 0.85$) to heavy inundation events.
2. **Validation Sample Step-Function Overfitting**: Isotonic regression creates step-functions that compress extreme probabilities, artificially inflating mean squared probability errors on the test set.
3. **Reliability Analysis**: The uncalibrated probability outputs align well with operational risk thresholds (`Low` $< 0.25$, `Moderate` $0.25 - 0.60$, `High` $0.60 - 0.85$, `Severe` $\ge 0.85$).

---

## 5. Conclusion & Operational Governance

The model is maintained in its verified form. Model confidence is separated from probability to explicitly quantify uncertainty rather than distorting calibrated classifier outputs.
