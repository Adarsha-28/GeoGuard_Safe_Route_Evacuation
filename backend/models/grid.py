"""SQLAlchemy model for Chennai Geospatial Risk Grids."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, Index, Integer, String, func

from backend.database.base import Base


class Grid(Base):
    """Monitored Chennai flood risk grid sector entity."""

    __tablename__ = "grids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_m = Column(Float, nullable=False)
    distance_to_water = Column(Float, nullable=False)
    rainfall_mm = Column(Float, nullable=False, default=0.0)
    flood_risk_score = Column(Float, nullable=False, default=0.0)
    flood_risk = Column(String(20), nullable=False, default="Low")

    # PostGIS geometries: Polygon boundary for ST_Contains, Point for distance
    geom = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    point_geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_grids_geom", "geom", postgresql_using="gist"),
        Index("idx_grids_point_geom", "point_geom", postgresql_using="gist"),
        Index("idx_grids_risk", "flood_risk"),
    )

    def to_geojson_feature(self) -> dict:
        """Serialize grid sector to GeoJSON Feature with point coordinates."""
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {
                "id": self.id,
                "place_name": self.name,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "elevation_m": self.elevation_m,
                "distance_to_water": self.distance_to_water,
                "rainfall_mm": self.rainfall_mm,
                "flood_risk_score": round(self.flood_risk_score, 4),
                "flood_risk": self.flood_risk,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude],
            },
        }
