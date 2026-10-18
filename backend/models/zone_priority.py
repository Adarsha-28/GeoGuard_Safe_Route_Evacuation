"""SQLAlchemy model for Monitored Zone Prioritization."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class ZonePriority(Base):
    """Operational priority scoring and triage ranking for monitored sectors."""

    __tablename__ = "zone_priorities"

    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="CASCADE"), primary_key=True)
    priority_score = Column(Float, server_default="0.0", nullable=False, index=True)
    priority_rank = Column(Integer, server_default="1", nullable=False)
    priority_category = Column(String(20), server_default="Low", nullable=False, index=True)
    risk_level = Column(String(20), server_default="Low", nullable=False)
    predicted_probability = Column(Float, server_default="0.0", nullable=False)
    probability_delta = Column(Float, server_default="0.0", nullable=False)
    rainfall_accumulation_mm = Column(Float, server_default="0.0", nullable=False)
    shelter_accessibility_score = Column(Float, server_default="1.0", nullable=False)
    confidence = Column(Float, server_default="0.85", nullable=False)
    calculated_at = Column(DateTime, server_default=func.now(), nullable=False)

    grid = relationship("Grid", backref="zone_priority", uselist=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize zone priority to dictionary."""
        return {
            "grid_id": self.grid_id,
            "grid_name": self.grid.name if self.grid else f"Grid {self.grid_id}",
            "priority_score": round(self.priority_score, 4),
            "priority_rank": self.priority_rank,
            "priority_category": self.priority_category,
            "risk_level": self.risk_level,
            "predicted_probability": round(self.predicted_probability, 4),
            "probability_delta": round(self.probability_delta, 4),
            "rainfall_accumulation_mm": round(self.rainfall_accumulation_mm, 2),
            "shelter_accessibility_score": round(self.shelter_accessibility_score, 4),
            "confidence": round(self.confidence, 4),
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
        }
