"""SQLAlchemy model for Monitored Grid Risk State and Transition Tracking."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class GridRiskState(Base):
    """Persistent state tracking current operational flood hazard level per grid."""

    __tablename__ = "grid_risk_states"

    grid_id = Column(
        Integer,
        ForeignKey("grids.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_risk_level = Column(String(20), nullable=False, default="Low", server_default="Low")
    current_probability = Column(Float, nullable=False, default=0.0, server_default="0.0")
    previous_risk_level = Column(String(20), nullable=True)
    model_version = Column(String(50), nullable=False, default="v3.0.0", server_default="v3.0.0")
    risk_changed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    grid = relationship("Grid", backref="risk_state", uselist=False)

    __table_args__ = (
        Index("idx_grid_risk_states_level", "current_risk_level"),
        Index("idx_grid_risk_states_updated", "updated_at"),
    )

    def to_dict(self) -> dict:
        """Serialize state representation for operational APIs."""
        return {
            "grid_id": self.grid_id,
            "current_risk_level": self.current_risk_level,
            "current_probability": round(self.current_probability, 4),
            "previous_risk_level": self.previous_risk_level,
            "model_version": self.model_version,
            "risk_changed_at": self.risk_changed_at.isoformat() if self.risk_changed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
