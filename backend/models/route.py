"""SQLAlchemy model for Route Evaluations."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class RouteEvaluation(Base):
    """Historical audit log of calculated safe evacuation paths."""

    __tablename__ = "route_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_lat = Column(Float, nullable=False)
    source_lng = Column(Float, nullable=False)
    shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="SET NULL"), nullable=True)
    distance_m = Column(Float, nullable=False)
    duration_s = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    safety_score = Column(Float, nullable=False)
    max_risk = Column(String(20), nullable=False)
    evaluated_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    shelter = relationship("Shelter", backref="route_evaluations")
