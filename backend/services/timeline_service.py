"""Operational Event Timeline Service for GeoGuard V5.

Logs and queries operational audit events:
- weather_sync
- prediction_cycle
- risk_transition
- alert_generated
- alert_acknowledged
- alert_deactivated
- evacuation_initiated
- shelter_capacity_change
- model_fallback_activation
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.operational_event import OperationalEvent


class TimelineService:
    """Service managing the command center operational event timeline."""

    @staticmethod
    def record_event(
        db: Session,
        event_type: str,
        message: str,
        category: str = "SYSTEM",
        severity: str = "INFO",
        grid_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OperationalEvent:
        """Record an operational timeline event into PostgreSQL."""
        event = OperationalEvent(
            event_type=event_type,
            category=category,
            severity=severity,
            message=message,
            grid_id=grid_id,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        return event

    @staticmethod
    def get_timeline(
        db: Session,
        hours: int = 24,
        event_type: str | None = None,
        grid_id: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve historical timeline events with filtering."""
        since_dt = datetime.utcnow() - timedelta(hours=max(1, hours))
        query = db.query(OperationalEvent).filter(OperationalEvent.created_at >= since_dt)

        if event_type:
            query = query.filter(OperationalEvent.event_type == event_type)
        if grid_id is not None:
            query = query.filter(OperationalEvent.grid_id == grid_id)

        events = query.order_by(desc(OperationalEvent.created_at)).limit(min(200, max(1, limit))).all()
        return [e.to_dict() for e in events]


_singleton_timeline_service: TimelineService | None = None


def get_timeline_service() -> TimelineService:
    """Retrieve singleton instance of TimelineService."""
    global _singleton_timeline_service
    if _singleton_timeline_service is None:
        _singleton_timeline_service = TimelineService()
    return _singleton_timeline_service
