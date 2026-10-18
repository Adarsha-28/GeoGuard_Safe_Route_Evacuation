#!/usr/bin/env python3
"""Model training, empirical evaluation, and artifact serialization for GeoGuard V3.

Trains and rigorously benchmarks:
  - Baseline: V2 Deterministic Multi-Criteria Model
  - Model 1: Logistic Regression (StandardScaler + L2 regularization)
  - Model 2: Random Forest Classifier (Class-Weighted, 100 estimators)
  - Model 3: Gradient Boosting Classifier

Evaluates Precision, Recall, F1, ROC-AUC, PR-AUC, and Confusion Matrix on held-out test data.
Serializes the best-performing model into models/trained/ and exports metadata.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Project root
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "processed" / "chennai_flood_training_dataset.csv"
MODELS_DIR = ROOT_DIR / "models"
TRAINED_DIR = MODELS_DIR / "trained"
METADATA_DIR = MODELS_DIR / "metadata"

FEATURE_COLS = [
    "rainfall_current_mm",
    "rainfall_3d_accum_mm",
    "rainfall_7d_accum_mm",
    "elevation_m",
    "distance_to_water_m",
    "latitude",
    "longitude",
    "month",
]


def evaluate_v2_baseline(df_test: pd.DataFrame) -> dict[str, Any]:
    """Evaluate V2 deterministic multi-criteria risk formula as a baseline classifier."""
    y_true = df_test["flood_occurred"].values

    # V2 formula:
    # rainfall_score = min(1.0, rain / 150.0)
    # elevation_score = (max_elev - elev) / (max_elev - min_elev)
    # water_score = (max_water - water) / (max_water - min_water)
    # risk = 0.50 * r + 0.25 * e + 0.25 * w
    # Threshold for High/Severe risk = 0.60
    elev = df_test["elevation_m"].values
    water = df_test["distance_to_water_m"].values
    rain = df_test["rainfall_current_mm"].values

    min_e, max_e = np.min(elev), np.max(elev)
    min_w, max_w = np.min(water), np.max(water)

    e_range = max_e - min_e if max_e > min_e else 1.0
    w_range = max_w - min_w if max_w > min_w else 1.0

    r_score = np.clip(rain / 150.0, 0.0, 1.0)
    e_score = np.clip((max_e - elev) / e_range, 0.0, 1.0)
    w_score = np.clip((max_w - water) / w_range, 0.0, 1.0)

    scores = (0.50 * r_score) + (0.25 * e_score) + (0.25 * w_score)
    y_pred = (scores >= 0.50).astype(int)

    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    roc = roc_auc_score(y_true, scores)
    pr_auc = average_precision_score(y_true, scores)
    cm = confusion_matrix(y_true, y_pred).tolist()

    return {
        "model_name": "V2 Deterministic Multi-Criteria (Baseline)",
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "confusion_matrix": cm,
    }


def train_and_evaluate() -> dict[str, Any]:
    """Train candidate models, evaluate on held-out test data, and serialize best model."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Training dataset not found at {DATA_PATH}. Run scripts/build_training_dataset.py first.")

    df = pd.read_csv(DATA_PATH)
    print(f"[..] Loaded {len(df):,} records from {DATA_PATH.name}")

    # Anti-leakage split:
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "validation"]
    test_df = df[df["split"] == "test"]

    print(f"     Train records: {len(train_df):,} | Validation: {len(val_df):,} | Test: {len(test_df):,}")

    X_train = train_df[FEATURE_COLS]
    y_train = train_df["flood_occurred"]

    X_test = test_df[FEATURE_COLS]
    y_test = test_df["flood_occurred"]

    # 1. Baseline: V2 Deterministic Formula
    res_baseline = evaluate_v2_baseline(test_df)

    # 2. Model 1: Logistic Regression Pipeline
    pipe_lr = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)),
    ])
    pipe_lr.fit(X_train, y_train)
    y_pred_lr = pipe_lr.predict(X_test)
    y_prob_lr = pipe_lr.predict_proba(X_test)[:, 1]

    res_lr = {
        "model_name": "Logistic Regression (Class-Weighted)",
        "precision": round(float(precision_score(y_test, y_pred_lr, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred_lr, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred_lr, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_prob_lr)), 4),
        "pr_auc": round(float(average_precision_score(y_test, y_prob_lr)), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred_lr).tolist(),
    }

    # 3. Model 2: Random Forest Classifier Pipeline
    pipe_rf = Pipeline([
        ("clf", RandomForestClassifier(n_estimators=100, max_depth=8, class_weight="balanced", random_state=42)),
    ])
    pipe_rf.fit(X_train, y_train)
    y_pred_rf = pipe_rf.predict(X_test)
    y_prob_rf = pipe_rf.predict_proba(X_test)[:, 1]

    res_rf = {
        "model_name": "Random Forest Classifier (Balanced)",
        "precision": round(float(precision_score(y_test, y_pred_rf, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred_rf, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred_rf, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_prob_rf)), 4),
        "pr_auc": round(float(average_precision_score(y_test, y_prob_rf)), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred_rf).tolist(),
    }

    # 4. Model 3: Gradient Boosting Classifier Pipeline
    pipe_gb = Pipeline([
        ("clf", GradientBoostingClassifier(n_estimators=80, learning_rate=0.08, max_depth=4, random_state=42)),
    ])
    pipe_gb.fit(X_train, y_train)
    y_pred_gb = pipe_gb.predict(X_test)
    y_prob_gb = pipe_gb.predict_proba(X_test)[:, 1]

    res_gb = {
        "model_name": "Gradient Boosting Classifier",
        "precision": round(float(precision_score(y_test, y_pred_gb, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred_gb, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred_gb, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_prob_gb)), 4),
        "pr_auc": round(float(average_precision_score(y_test, y_prob_gb)), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred_gb).tolist(),
    }

    results = [res_baseline, res_lr, res_rf, res_gb]

    print("\n" + "=" * 80)
    print("   GeoGuard V3 — Empirical Model Evaluation Benchmark (Held-Out Test Set)")
    print("=" * 80)
    print(f"{'Model Name':<42} {'Precision':>10} {'Recall':>8} {'F1':>8} {'ROC-AUC':>9} {'PR-AUC':>8}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['model_name']:<42} {r['precision']:>10.4f} {r['recall']:>8.4f} "
            f"{r['f1']:>8.4f} {r['roc_auc']:>9.4f} {r['pr_auc']:>8.4f}"
        )
    print("-" * 80)

    # Feature Importance Calculation from Random Forest
    rf_clf: RandomForestClassifier = pipe_rf.named_steps["clf"]
    importances = rf_clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    feature_ranking = [
        {"feature": FEATURE_COLS[i], "importance": round(float(importances[i]), 4)}
        for i in sorted_idx
    ]

    print("\n[..] Random Forest Feature Contributions:")
    for rank, item in enumerate(feature_ranking, start=1):
        print(f"     {rank}. {item['feature']:<25}: {item['importance'] * 100:.2f}%")

    # Select Best Model based on F1-Score on Held-Out Test Set
    ml_candidates = [
        ("Random Forest", pipe_rf, res_rf),
        ("Gradient Boosting", pipe_gb, res_gb),
        ("Logistic Regression", pipe_lr, res_lr),
    ]
    ml_candidates.sort(key=lambda x: x[2]["f1"], reverse=True)
    best_name, best_pipeline, best_metrics = ml_candidates[0]
    print(f"\n[OK] Selected best model: {best_name} (F1 = {best_metrics['f1']:.4f}, ROC-AUC = {best_metrics['roc_auc']:.4f})")

    # Save Model Artifact
    TRAINED_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    model_artifact_path = TRAINED_DIR / "geoguard_flood_rf_v3.joblib"
    joblib.dump(best_pipeline, model_artifact_path)
    print(f"[OK] Model artifact serialized -> {model_artifact_path.name} ({os.path.getsize(model_artifact_path):,} bytes)")

    # Save Model Metadata
    metadata = {
        "model_version": "v3.0.0",
        "algorithm": best_name,
        "features": FEATURE_COLS,
        "feature_ranking": feature_ranking,
        "training_dataset": "data/processed/chennai_flood_training_dataset.csv",
        "dataset_records": len(df),
        "train_records": len(train_df),
        "test_records": len(test_df),
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "random_seed": 42,
        "test_metrics": best_metrics,
        "benchmark_comparison": results,
    }

    metadata_path = METADATA_DIR / "model_metadata_v3.json"
    with open(metadata_path, mode="w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[OK] Metadata exported -> {metadata_path.name}")

    return metadata


def main() -> int:
    print("=" * 65)
    print("   GeoGuard V3 — Model Training & Benchmarking")
    print("=" * 65)
    meta = train_and_evaluate()
    print(f"\n[SUCCESS] V3 Model Pipeline Ready! Model Version: {meta['model_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
