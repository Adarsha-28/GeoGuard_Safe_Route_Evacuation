"""SQLAlchemy model for Persistent Risk Transitions and Trends."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class RiskTransitionRecord(Base):
    """Historical audit of risk level state transitions, probability deltas, and trends."""

    __tablename__ = "risk_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_risk = Column(String(20), nullable=True)
    current_risk = Column(String(20), nullable=False)
    previous_probability = Column(Float, nullable=True)
    current_probability = Column(Float, nullable=False)
    probability_delta = Column(Float, server_default="0.0", nullable=False)
    trend = Column(String(30), server_default="STABLE", nullable=False, index=True)
    horizon = Column(String(20), server_default="nowcast", nullable=False)
    detected_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    grid = relationship("Grid", backref="risk_transition_records")

    __table_args__ = (
        Index("idx_risk_trans_grid_time", "grid_id", "detected_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize risk transition to dictionary."""
        return {
            "id": self.id,
            "grid_id": self.grid_id,
            "previous_risk": self.previous_risk,
            "current_risk": self.current_risk,
            "previous_probability": round(self.previous_probability, 4) if self.previous_probability is not None else None,
            "current_probability": round(self.current_probability, 4),
            "probability_delta": round(self.probability_delta, 4),
            "trend": self.trend,
            "horizon": self.horizon,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }
