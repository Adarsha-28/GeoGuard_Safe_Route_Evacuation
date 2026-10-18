"""Shelter business logic and PostGIS spatial distance calculations."""

from __future__ import annotations

import math
from typing import Any
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, desc, text
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.shelter import Shelter


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two geographic coordinates in kilometers."""
    earth_radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(earth_radius_km * c, 3)


def validate_coordinates(lat: float, lng: float) -> tuple[bool, str | None]:
    """Validate latitude and longitude against standard geographic bounds."""
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return False, "Latitude and longitude must be numbers."
    if math.isnan(lat) or math.isnan(lng) or math.isinf(lat) or math.isinf(lng):
        return False, "Coordinates cannot be NaN or Infinite."
    if not (-90.0 <= lat <= 90.0):
        return False, f"Latitude {lat} out of valid range [-90.0, 90.0]."
    if not (-180.0 <= lng <= 180.0):
        return False, f"Longitude {lng} out of valid range [-180.0, 180.0]."
    return True, None


class ShelterService:
    """Service providing relief shelter management and database-side PostGIS spatial queries."""

    def get_all_shelters(self, db: Session, active_only: bool = True) -> list[dict[str, Any]]:
        """Retrieve all shelters ordered alphabetically by name."""
        query = db.query(Shelter)
        if active_only:
            query = query.filter(Shelter.is_active == True)
        shelters = query.order_by(Shelter.name.asc()).all()
        return [s.to_dict() for s in shelters]

    def get_shelter(self, db: Session, shelter_id: int) -> dict[str, Any] | None:
        """Retrieve a single shelter by primary key ID."""
        shelter = db.query(Shelter).filter(Shelter.id == shelter_id).first()
        return shelter.to_dict() if shelter else None

    def find_nearby_shelters(
        self,
        db: Session,
        lat: float,
        lng: float,
        radius_km: float = 25.0,
        limit: int = 10,
        available_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Query nearest active shelters within radius_km using PostGIS database-side spatial logic.
        
        Uses ST_DWithin and ST_Distance on geography types with GiST indexing for fast retrieval,
        ordering directly in PostgreSQL without pulling all shelters into Python memory.
        """
        is_valid, err = validate_coordinates(lat, lng)
        if not is_valid:
            raise ValueError(err)

        radius_meters = radius_km * 1000.0

        # PostGIS query: database-side distance calculation and spatial index pruning
        sql = text("""
            SELECT 
                id, name, latitude, longitude, address, capacity, available_capacity,
                risk_level, is_active, facilities, contact,
                ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) / 1000.0 AS dist_km
            FROM shelters
            WHERE is_active = true
              AND (:available_only = false OR available_capacity > 0)
              AND ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_meters)
            ORDER BY dist_km ASC
            LIMIT :limit;
        """)

        try:
            result = db.execute(
                sql,
                {
                    "lat": lat,
                    "lng": lng,
                    "radius_meters": radius_meters,
                    "available_only": available_only,
                    "limit": limit,
                },
            )
            rows = result.fetchall()

            nearby = []
            for row in rows:
                nearby.append({
                    "id": row.id,
                    "name": row.name,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "address": row.address,
                    "capacity": row.capacity,
                    "availableCapacity": row.available_capacity,
                    "riskLevel": row.risk_level,
                    "isActive": 1 if row.is_active else 0,
                    "facilities": row.facilities,
                    "contact": row.contact,
                    "distance": round(float(row.dist_km), 2),
                })
            return nearby

        except Exception as e:
            # Fallback to application-level calculation if PostGIS extension is detached
            logger.warning(f"PostGIS spatial query failed, falling back to in-memory evaluation: {e}")
            all_shelters = self.get_all_shelters(db, active_only=True)
            fallback_nearby = []
            for s in all_shelters:
                if available_only and s["availableCapacity"] <= 0:
                    continue
                d = haversine_distance(lat, lng, s["latitude"], s["longitude"])
                if d <= radius_km:
                    sc = dict(s)
                    sc["distance"] = d
                    fallback_nearby.append(sc)
            fallback_nearby.sort(key=lambda x: x["distance"])
            return fallback_nearby[:limit]

    def decrement_shelter_capacity(
        self, db: Session, shelter_id: int
    ) -> tuple[bool, dict[str, Any] | str]:
        """Atomically reserve a spot at the designated shelter in a database transaction."""
        try:
            # Lock the row for update to prevent concurrent race conditions
            shelter = (
                db.query(Shelter)
                .filter(Shelter.id == shelter_id, Shelter.is_active == True)
                .with_for_update()
                .first()
            )

            if not shelter:
                db.rollback()
                return False, "Shelter not found or is inactive."

            if shelter.available_capacity <= 0:
                db.rollback()
                return False, "Shelter is already at full capacity."

            shelter.available_capacity -= 1
            db.commit()
            db.refresh(shelter)
            logger.info(
                f"Decremented capacity for shelter {shelter.id} ({shelter.name}): "
                f"{shelter.available_capacity} left"
            )
            return True, shelter.to_dict()

        except Exception as e:
            db.rollback()
            logger.error(f"Transaction error decrementing shelter capacity: {e}")
            return False, f"Database transaction failed: {e}"


_singleton_shelter_service: ShelterService | None = None


def get_shelter_service() -> ShelterService:
    """Retrieve singleton instance of ShelterService."""
    global _singleton_shelter_service
    if _singleton_shelter_service is None:
        _singleton_shelter_service = ShelterService()
    return _singleton_shelter_service
