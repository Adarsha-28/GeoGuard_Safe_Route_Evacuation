"""Unit tests for the GeoGuard V3 training dataset assembly and feature pipeline."""

from pathlib import Path
import pandas as pd
import pytest

from backend.config import ROOT_DIR

DATA_PATH = ROOT_DIR / "data" / "processed" / "chennai_flood_training_dataset.csv"


def test_training_dataset_structure():
    """Verify processed training dataset exists and adheres to required schema."""
    assert DATA_PATH.exists(), f"Dataset not found at {DATA_PATH}"
    df = pd.read_csv(DATA_PATH)

    required_columns = [
        "date", "grid_id", "place_name", "latitude", "longitude",
        "elevation_m", "distance_to_water_m", "rainfall_current_mm",
        "rainfall_3d_accum_mm", "rainfall_7d_accum_mm", "wind_speed_max_kmh",
        "month", "flood_occurred", "flood_severity", "split",
    ]
    for col in required_columns:
        assert col in df.columns, f"Missing required column: {col}"

    # Minimum dataset size
    assert len(df) >= 1000
    # Class values valid
    assert set(df["flood_occurred"].unique()).issubset({0, 1})
    # Target severity values valid
    assert set(df["flood_severity"].unique()).issubset({"Low", "Moderate", "High", "Severe"})


def test_anti_leakage_chronological_splits():
    """Verify chronological split guarantees zero future information leaks into training."""
    df = pd.read_csv(DATA_PATH)
    df["year"] = pd.to_datetime(df["date"]).dt.year

    train_years = set(df[df["split"] == "train"]["year"].unique())
    val_years = set(df[df["split"] == "validation"]["year"].unique())
    test_years = set(df[df["split"] == "test"]["year"].unique())

    # Training strictly prior to validation
    assert max(train_years) < min(val_years), "Data leakage: training years overlap validation!"
    # Validation strictly prior to test
    assert max(val_years) < min(test_years), "Data leakage: validation years overlap test!"


def test_no_missing_values():
    """Verify clean dataset contains no NaN values in features or labels."""
    df = pd.read_csv(DATA_PATH)
    features = [
        "rainfall_current_mm", "rainfall_3d_accum_mm", "rainfall_7d_accum_mm",
        "elevation_m", "distance_to_water_m", "latitude", "longitude", "month",
    ]
    assert df[features].isna().sum().sum() == 0, "Found unexpected NaN values in feature matrix"
    assert df["flood_occurred"].isna().sum() == 0, "Found NaN values in target labels"
