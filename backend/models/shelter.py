"""SQLAlchemy model for Relief Shelters with PostGIS Point Location."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, Index, Integer, String, Text, func

from backend.database.base import Base


class Shelter(Base):
    """Registered relief shelter entity with spatial location and capacity limits."""

    __tablename__ = "shelters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    address = Column(Text, nullable=False)
    capacity = Column(Integer, nullable=False)
    available_capacity = Column(Integer, nullable=False)
    risk_level = Column(String(20), nullable=False, default="Moderate")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    facilities = Column(Text, nullable=False, default="")
    contact = Column(String(50), nullable=False, default="")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("capacity >= 0", name="chk_shelter_capacity_non_negative"),
        CheckConstraint("available_capacity >= 0", name="chk_shelter_available_capacity_non_negative"),
        CheckConstraint("available_capacity <= capacity", name="chk_shelter_available_lte_capacity"),
        Index("idx_shelters_location", "location", postgresql_using="gist"),
        Index("idx_shelters_active_avail", "is_active", "available_capacity"),
    )

    def to_dict(self, distance_km: float | None = None) -> dict:
        """Convert model to dictionary compatible with V1 frontend expectations."""
        res = {
            "id": self.id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "capacity": self.capacity,
            "availableCapacity": self.available_capacity,
            "riskLevel": self.risk_level,
            "isActive": 1 if self.is_active else 0,
            "facilities": self.facilities,
            "contact": self.contact,
        }
        if distance_km is not None:
            res["distance"] = round(distance_km, 2)
        return res
