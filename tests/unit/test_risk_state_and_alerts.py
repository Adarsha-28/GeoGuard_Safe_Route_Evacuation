"""Unit tests for RiskStateService and AlertEngine in GeoGuard V4."""

from datetime import datetime
import pytest

from backend.database.connection import SessionLocal
from backend.models.alert import Alert
from backend.models.grid import Grid
from backend.models.risk_state import GridRiskState
from backend.services.alert_engine import AlertEngine, get_alert_engine
from backend.services.prediction_pipeline_service import SectorPredictionResult
from backend.services.risk_state_service import (
    RiskStateService,
    RiskTransition,
    get_risk_state_service,
)


@pytest.fixture
def risk_state_service():
    return get_risk_state_service()


@pytest.fixture
def alert_engine():
    return get_alert_engine()


def test_risk_transition_classification(risk_state_service):
    """Verify transition category logic."""
    assert risk_state_service.classify_transition_type("Low", "Moderate") == "escalation"
    assert risk_state_service.classify_transition_type("Moderate", "High") == "escalation"
    assert risk_state_service.classify_transition_type("High", "Severe") == "escalation"
    assert risk_state_service.classify_transition_type("Severe", "Moderate") == "de-escalation"
    assert risk_state_service.classify_transition_type("High", "Low") == "de-escalation"
    assert risk_state_service.classify_transition_type("Moderate", "Moderate") == "unchanged"
    assert risk_state_service.classify_transition_type(None, "Low") == "initial"


def test_risk_state_update_and_transition_detection(risk_state_service):
    """Verify persistence of risk state and detection of escalation."""
    with SessionLocal() as db:
        grid = db.query(Grid).first()
        assert grid is not None

        # Simulate escalation to High
        preds = [
            SectorPredictionResult(
                grid_id=grid.id,
                grid_name=grid.name,
                risk_level="High",
                probability=0.78,
                model_version="v3.0.0",
                is_fallback=False,
            )
        ]

        transitions = risk_state_service.update_grid_risk_states(db, preds)
        assert len(transitions) == 1
        t = transitions[0]
        assert t.grid_id == grid.id
        assert t.current_risk == "High"

        # Verify state in DB
        state = db.query(GridRiskState).filter(GridRiskState.grid_id == grid.id).first()
        assert state is not None
        assert state.current_risk_level == "High"
        assert state.current_probability == 0.78

        # Run identical prediction: must be UNCHANGED (no transitions returned)
        transitions2 = risk_state_service.update_grid_risk_states(db, preds)
        assert len(transitions2) == 0  # Deduplication of transition


def test_alert_engine_generation_and_deduplication(alert_engine):
    """Verify alert creation upon transition and suppression of duplicates."""
    with SessionLocal() as db:
        grid = db.query(Grid).first()
        assert grid is not None

        trans = [
            RiskTransition(
                grid_id=grid.id,
                grid_name=grid.name,
                previous_risk="Moderate",
                current_risk="High",
                probability=0.75,
                model_version="v3.0.0",
                transition_type="escalation",
                risk_changed_at=datetime.utcnow(),
            )
        ]

        # First alert generation
        alerts1 = alert_engine.evaluate_transitions_and_generate_alerts(db, trans)
        assert len(alerts1) == 1
        a1 = alerts1[0]
        assert a1["severity"] in ("Warning", "High")
        assert "High flood risk" in a1["message"]
        assert a1["grid_id"] == grid.id

        # Duplicate transition must NOT create a second alert
        alerts2 = alert_engine.evaluate_transitions_and_generate_alerts(db, trans)
        assert len(alerts2) == 0

        # Clean up test alert
        db.query(Alert).filter(Alert.id == a1["id"]).delete()
        db.commit()


def test_alert_de_escalation_deactivates_older_alerts(alert_engine):
    """Verify that de-escalation creates recovery alert and deactivates prior warnings."""
    with SessionLocal() as db:
        grid = db.query(Grid).first()
        assert grid is not None

        # Escalation
        trans_esc = [
            RiskTransition(
                grid_id=grid.id,
                grid_name=grid.name,
                previous_risk="Low",
                current_risk="Severe",
                probability=0.92,
                model_version="v3.0.0",
                transition_type="escalation",
                risk_changed_at=datetime.utcnow(),
            )
        ]
        created = alert_engine.evaluate_transitions_and_generate_alerts(db, trans_esc)
        assert len(created) == 1
        critical_id = created[0]["id"]

        # De-escalation back to Low
        trans_deesc = [
            RiskTransition(
                grid_id=grid.id,
                grid_name=grid.name,
                previous_risk="Severe",
                current_risk="Low",
                probability=0.15,
                model_version="v3.0.0",
                transition_type="de-escalation",
                risk_changed_at=datetime.utcnow(),
            )
        ]
        alert_engine.evaluate_transitions_and_generate_alerts(db, trans_deesc)

        # Verify previous critical alert was deactivated
        critical_alert = db.query(Alert).filter(Alert.id == critical_id).first()
        assert critical_alert.is_active is False

        # Clean up
        db.query(Alert).filter(Alert.grid_id == grid.id).delete()
        db.commit()
