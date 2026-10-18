"""SQLAlchemy model for Operational Event Timeline."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class OperationalEvent(Base):
    """Event ledger for command center audit trail and timeline view."""

    __tablename__ = "operational_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True)
    category = Column(String(30), server_default="SYSTEM", nullable=False)
    severity = Column(String(20), server_default="INFO", nullable=False)
    message = Column(Text, nullable=False)
    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="SET NULL"), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    grid = relationship("Grid", backref="operational_events")

    __table_args__ = (
        Index("idx_op_events_time", "created_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize operational event to dictionary."""
        meta = {}
        if self.metadata_json:
            try:
                meta = json.loads(self.metadata_json)
            except Exception:
                meta = {}

        return {
            "id": self.id,
            "event_type": self.event_type,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "grid_id": self.grid_id,
            "grid_name": self.grid.name if self.grid else None,
            "metadata": meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
