"""Unit tests for OperationalScheduler with Concurrency Guard in GeoGuard V4."""

import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from backend.database.connection import SessionLocal
from backend.services.operational_scheduler import (
    OperationalScheduler,
    get_operational_scheduler,
)


@pytest.fixture
def scheduler():
    return OperationalScheduler()


def test_scheduler_run_single_cycle_success(scheduler):
    """Verify clean execution of a single operational cycle."""
    with SessionLocal() as db:
        res = scheduler.run_single_cycle(db, trigger_type="test_single_cycle")

    assert res["status"] == "success"
    assert res["total_grids"] > 0
    assert "latency_ms" in res
    assert scheduler.last_cycle_status == "success"
    assert scheduler.cycles_completed_count >= 1


def test_scheduler_concurrency_guard(scheduler):
    """Verify that concurrent cycle requests are skipped via threading lock."""
    # Acquire the lock manually to simulate an in-progress cycle
    scheduler._cycle_lock.acquire()
    try:
        with SessionLocal() as db:
            result = scheduler.run_single_cycle(db, trigger_type="overlapping_test")
        assert result["status"] == "skipped"
        assert "Previous prediction cycle is still active" in result["reason"]
        assert scheduler.cycles_skipped_count >= 1
    finally:
        scheduler._cycle_lock.release()


def test_scheduler_error_recovery(scheduler):
    """Verify that an exception during a cycle is caught, logged, and does not kill scheduler."""
    with patch.object(
        scheduler.pipeline_service,
        "run_prediction_pipeline",
        side_effect=RuntimeError("Pipeline crash simulation"),
    ):
        with SessionLocal() as db:
            res = scheduler.run_single_cycle(db, trigger_type="error_test")

        assert res["status"] == "failed"
        assert "Pipeline crash simulation" in res["error"]
        assert scheduler.last_cycle_status == "failed"
        assert scheduler.cycles_failed_count >= 1

    # Ensure lock was released and next cycle can run normally
    assert scheduler._cycle_lock.locked() is False


def test_operational_status_telemetry(scheduler):
    """Verify telemetry values returned by get_operational_status."""
    with SessionLocal() as db:
        status = scheduler.get_operational_status(db)

    assert "weather_status" in status
    assert "model_version" in status
    assert "active_model" in status
    assert "fallback_active" in status
    assert "active_alerts" in status
    assert "high_risk_grids" in status
    assert "prediction_latency_ms" in status
    assert status["scheduler_status"] in ("running", "stopped")
