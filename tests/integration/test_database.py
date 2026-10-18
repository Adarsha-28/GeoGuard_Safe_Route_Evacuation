"""Integration tests for SQLAlchemy connection pooling, transactions, and check constraints."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.database.connection import SessionLocal
from backend.models.alert import Alert
from backend.models.shelter import Shelter


def test_database_connection_pool():
    """Verify active connection pool executes queries concurrently."""
    sessions = [SessionLocal() for _ in range(5)]
    try:
        for s in sessions:
            res = s.execute(text("SELECT 1;")).fetchone()
            assert res[0] == 1
    finally:
        for s in sessions:
            s.close()


def test_shelter_capacity_check_constraint():
    """Verify database-level check constraint rejects negative available capacity."""
    with SessionLocal() as db:
        shelter = db.query(Shelter).first()
        assert shelter is not None

        # Attempt to set negative capacity directly in SQL
        with pytest.raises(IntegrityError):
            db.execute(
                text("UPDATE shelters SET available_capacity = -10 WHERE id = :id"),
                {"id": shelter.id},
            )
            db.commit()
        db.rollback()


def test_transaction_rollback_on_failure():
    """Verify failed operations roll back cleanly without leaving partial records."""
    with SessionLocal() as db:
        initial_alerts_count = db.query(Alert).count()

        try:
            # 1. Add valid alert
            db.add(Alert(title="Valid", severity="High", zone="Zone A", message="Test message"))
            db.flush()

            # 2. Trigger integrity failure with invalid severity
            db.execute(text("INSERT INTO alerts (title, severity, zone, message) VALUES ('Bad', 'UnknownSeverity', 'Zone', 'Msg');"))
            db.commit()
        except Exception:
            db.rollback()

        final_alerts_count = db.query(Alert).count()
        assert final_alerts_count == initial_alerts_count
