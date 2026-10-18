"""SQLAlchemy model for Historical Risk Predictions and Multi-Criteria Components."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class RiskPrediction(Base):
    """Calculated flood risk snapshot per sector (ML forecast or deterministic baseline)."""

    __tablename__ = "risk_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)
    rainfall_score = Column(Float, nullable=False)
    elevation_score = Column(Float, nullable=False)
    water_proximity_score = Column(Float, nullable=False)
    model_version = Column(String(50), server_default="v2.0.0-deterministic", nullable=False)
    probability = Column(Float, nullable=True)
    prediction_horizon = Column(String(50), server_default="24-Hour Hazard", nullable=True)
    is_fallback = Column(Boolean, server_default="false", nullable=False)
    trigger_type = Column(String(20), server_default="manual", nullable=False, index=True)
    calculated_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    grid = relationship("Grid", backref="risk_predictions")
