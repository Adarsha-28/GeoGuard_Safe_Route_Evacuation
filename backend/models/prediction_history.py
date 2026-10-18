"""SQLAlchemy model for Multi-Horizon Prediction History."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class PredictionHistory(Base):
    """Historical record of multi-horizon risk predictions for temporal intelligence."""

    __tablename__ = "prediction_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False, index=True)
    horizon = Column(String(20), server_default="nowcast", nullable=False, index=True)
    predicted_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    risk_level = Column(String(20), nullable=False, index=True)
    probability = Column(Float, nullable=False)
    confidence = Column(Float, server_default="0.85", nullable=False)
    confidence_category = Column(String(20), server_default="High", nullable=False)
    rainfall_mm = Column(Float, server_default="0.0", nullable=False)
    rainfall_3d_mm = Column(Float, server_default="0.0", nullable=False)
    rainfall_7d_mm = Column(Float, server_default="0.0", nullable=False)
    model_version = Column(String(50), server_default="v5.0.0", nullable=False)
    trigger_type = Column(String(20), server_default="scheduled", nullable=False)
    is_fallback = Column(Boolean, server_default="false", nullable=False)
    features_json = Column(Text, nullable=True)
    contributing_features_json = Column(Text, nullable=True)

    grid = relationship("Grid", backref="prediction_histories")

    __table_args__ = (
        Index("idx_pred_hist_grid_horizon_time", "grid_id", "horizon", "predicted_at"),
        Index("idx_pred_hist_time", "predicted_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize prediction history record to dictionary."""
        features = {}
        if self.features_json:
            try:
                features = json.loads(self.features_json)
            except Exception:
                features = {}

        contributions = []
        if self.contributing_features_json:
            try:
                contributions = json.loads(self.contributing_features_json)
            except Exception:
                contributions = []

        return {
            "id": self.id,
            "grid_id": self.grid_id,
            "horizon": self.horizon,
            "predicted_at": self.predicted_at.isoformat() if self.predicted_at else None,
            "risk_level": self.risk_level,
            "probability": round(self.probability, 4),
            "confidence": round(self.confidence, 4),
            "confidence_category": self.confidence_category,
            "rainfall_mm": round(self.rainfall_mm, 2),
            "rainfall_3d_mm": round(self.rainfall_3d_mm, 2),
            "rainfall_7d_mm": round(self.rainfall_7d_mm, 2),
            "model_version": self.model_version,
            "trigger_type": self.trigger_type,
            "is_fallback": self.is_fallback,
            "features": features,
            "contributing_features": contributions,
        }
