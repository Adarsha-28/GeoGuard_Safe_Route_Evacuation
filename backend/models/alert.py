"""SQLAlchemy model for Administrative Emergency Alerts."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func

from backend.database.base import Base

VALID_SEVERITIES = ("Low", "Moderate", "High", "Critical", "Warning", "Informational")


class Alert(Base):
    """Emergency administrative advisory bulletin."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    severity = Column(String(20), nullable=False)
    zone = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    previous_risk = Column(String(20), nullable=True)
    current_risk = Column(String(20), nullable=True)
    probability = Column(Float, nullable=True)
    model_version = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint(
            f"severity IN {tuple(VALID_SEVERITIES)}",
            name="chk_alert_severity_valid",
        ),
        Index("idx_alerts_timestamp", "timestamp"),
    )

    def to_dict(self) -> dict:
        """Convert alert to dictionary for API response."""
        return {
            "id": self.id,
            "grid_id": self.grid_id,
            "title": self.title,
            "severity": self.severity,
            "zone": self.zone,
            "message": self.message,
            "previous_risk": self.previous_risk,
            "current_risk": self.current_risk,
            "probability": round(self.probability, 4) if self.probability is not None else None,
            "model_version": self.model_version,
            "is_active": self.is_active,
            "isActive": 1 if self.is_active else 0,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "",
            "created_at": self.timestamp.isoformat() if self.timestamp else None,
        }
