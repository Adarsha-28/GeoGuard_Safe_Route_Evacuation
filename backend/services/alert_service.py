"""Alert service managing administrative emergency broadcasts."""

from __future__ import annotations

from typing import Any
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.alert import Alert


class AlertService:
    """Service providing transactional alert operations."""

    def get_all_alerts(
        self,
        db: Session,
        limit: int = 50,
        active_only: bool = False,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve recent alerts ordered by ID descending with optional filtering."""
        query = db.query(Alert)
        if active_only:
            query = query.filter(Alert.is_active == True)
        if severity:
            query = query.filter(Alert.severity == severity.strip())
        records = query.order_by(desc(Alert.id)).limit(max(1, min(limit, 200))).all()
        return [a.to_dict() for a in records]

    def get_alert_by_id(self, db: Session, alert_id: int) -> dict[str, Any] | None:
        """Fetch an alert record by primary key."""
        record = db.query(Alert).filter(Alert.id == alert_id).first()
        return record.to_dict() if record else None

    def acknowledge_alert(self, db: Session, alert_id: int) -> dict[str, Any] | None:
        """Mark an alert as acknowledged / inactive in PostgreSQL."""
        record = db.query(Alert).filter(Alert.id == alert_id).first()
        if not record:
            return None
        record.is_active = False
        db.commit()
        db.refresh(record)
        logger.info(f"alert_acknowledged: Alert {alert_id} ({record.title}) deactivated.")
        return record.to_dict()

    def create_alert(
        self, db: Session, title: str, severity: str, zone: str, message: str
    ) -> dict[str, Any]:
        """Insert and commit a new emergency alert in a safe database transaction."""
        new_alert = Alert(
            title=title.strip(),
            severity=severity.strip(),
            zone=zone.strip(),
            message=message.strip(),
            is_active=True,
        )
        try:
            db.add(new_alert)
            db.commit()
            db.refresh(new_alert)
            logger.info(f"Published emergency alert [ID {new_alert.id}]: {new_alert.title} ({new_alert.severity})")
            return new_alert.to_dict()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create alert: {e}")
            raise


_singleton_alert_service: AlertService | None = None


def get_alert_service() -> AlertService:
    """Retrieve singleton instance of AlertService."""
    global _singleton_alert_service
    if _singleton_alert_service is None:
        _singleton_alert_service = AlertService()
    return _singleton_alert_service
