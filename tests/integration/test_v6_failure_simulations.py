"""Integration tests for GeoGuard V6 Controlled Failure & Fallback Simulations."""

import pytest
from backend.database.connection import SessionLocal
from backend.models.scenario import FailureSimulation
from backend.services.failure_simulation_service import FailureSimulationService


def test_all_six_failure_modes_and_fallbacks():
    """Verify each of the 6 controlled failure modes activates fallback and persists audit records."""
    service = FailureSimulationService()

    with SessionLocal() as db:
        for sim_type in service.VALID_SIMULATIONS:
            res = service.execute_failure_test(db, sim_type)

            assert res["simulation_type"] == sim_type
            assert res["detected"] is True
            assert res["fallback_activated"] is True
            assert res["fallback_type"] is not None
            assert res["degraded_status"] is not None
            assert res["response_time_ms"] >= 0.0
            assert res["audit_record_created"] is True
            assert "details" in res

            # Verify audit entry was written to database
            record_id = res.get("record_id")
            assert record_id is not None
            rec = db.query(FailureSimulation).filter(FailureSimulation.id == record_id).first()
            assert rec is not None
            assert rec.simulation_type == sim_type
            assert rec.fallback_activated is True


def test_invalid_failure_mode_rejection():
    """Verify unknown failure mode raises ValueError."""
    service = FailureSimulationService()
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="Unknown simulation type"):
            service.execute_failure_test(db, "INVALID_FAILURE_TYPE")
