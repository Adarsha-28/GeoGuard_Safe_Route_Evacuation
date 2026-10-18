# GeoGuard Model Registry

This directory contains serialized machine learning model artifacts, preprocessing pipelines, and versioned training metadata for GeoGuard V3.

---

## Directory Structure

```text
models/
├── trained/
│   └── geoguard_flood_rf_v3.joblib     # Serialized Gradient Boosting Pipeline
├── metadata/
│   └── model_metadata_v3.json          # Hyperparameters, metrics, feature ranking
└── README.md
```

---

## Active Model Metadata (`v3.0.0`)

* **Model Version**: `v3.0.0`
* **Algorithm**: Gradient Boosting Classifier
* **Library**: `scikit-learn 1.7.2`
* **Serialization**: `joblib 1.5.1`
* **Artifact Size**: 74,609 bytes
* **Features**:
  1. `rainfall_current_mm`
  2. `rainfall_3d_accum_mm`
  3. `rainfall_7d_accum_mm`
  4. `elevation_m`
  5. `distance_to_water_m`
  6. `latitude`
  7. `longitude`
  8. `month`
* **Test F1-Score**: 0.8889
* **Test ROC-AUC**: 0.9827
* **Random Seed**: 42

---

## Security Notice

Model artifacts inside `models/trained/` are trusted internal assets compiled during reproducible training runs. Inbound untrusted API data is never unpickled.
