"""SQLAlchemy model for Weather Observations."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, Index, Integer, String, UniqueConstraint, func

from backend.database.base import Base


class WeatherObservation(Base):
    """Historical telemetry record of precipitation measurements."""

    __tablename__ = "weather_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    rainfall_mm = Column(Float, nullable=False)
    source = Column(String(50), nullable=False, default="Open-Meteo")
    observed_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    wind_speed_kmh = Column(Float, nullable=False, default=0.0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    ingested_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_weather_location", "location", postgresql_using="gist"),
        Index("idx_weather_observed_at", "observed_at"),
        UniqueConstraint("source", "observed_at", "latitude", "longitude", name="uq_weather_obs_source_time_coords"),
    )
