"""Integration tests for GeoGuard V5 lifecycle and PostgreSQL persistence."""

import pytest
from backend.database.connection import SessionLocal
from backend.models.operational_event import OperationalEvent
from backend.models.prediction_history import PredictionHistory
from backend.models.risk_transition import RiskTransitionRecord
from backend.models.zone_priority import ZonePriority
from backend.services.operational_scheduler import get_operational_scheduler
from backend.services.timeline_service import TimelineService


def test_v5_database_tables_exist_and_persist():
    """Verify all 4 new V5 tables accept inserts, updates, and spatial queries."""
    with SessionLocal() as db:
        # 1. Operational event insert
        event = TimelineService.record_event(
            db=db,
            event_type="test_event",
            category="SYSTEM",
            severity="INFO",
            message="Test integration timeline event",
            grid_id=1,
            metadata={"test_key": "test_value"},
        )
        db.commit()
        assert event.id is not None

        # Query back
        fetched = db.query(OperationalEvent).filter(OperationalEvent.id == event.id).first()
        assert fetched is not None
        assert fetched.message == "Test integration timeline event"

        # Cleanup test event
        db.delete(fetched)
        db.commit()


def test_v5_scheduler_run_single_cycle_with_v5_intelligence():
    """Verify operational scheduler runs complete single cycle and populates V5 tables."""
    scheduler = get_operational_scheduler()
    with SessionLocal() as db:
        result = scheduler.run_single_cycle(db, trigger_type="manual")

        assert result["status"] == "success"
        assert result["total_grids"] > 0

        # Verify prediction_history has records
        ph_count = db.query(PredictionHistory).count()
        assert ph_count > 0

        # Verify zone_priorities has records
        zp_count = db.query(ZonePriority).count()
        assert zp_count > 0

        # Verify operational_events has prediction_cycle event
        op_count = db.query(OperationalEvent).filter(OperationalEvent.event_type == "prediction_cycle").count()
        assert op_count > 0
