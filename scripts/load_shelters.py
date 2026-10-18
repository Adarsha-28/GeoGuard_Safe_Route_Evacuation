#!/usr/bin/env python3
"""Idempotent data loader for Chennai relief shelters into PostGIS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.connection import SessionLocal
from backend.models.shelter import Shelter

DEFAULT_SHELTERS = [
    {"name": "Corporation Primary School, T. Nagar", "lat": 13.0418, "lng": 80.2341, "capacity": 500, "availableCapacity": 350, "riskLevel": "Moderate", "address": "T. Nagar, Chennai", "contact": "044-2434-5678", "facilities": "Water, Food, Medical"},
    {"name": "Anna Nagar Community Hall", "lat": 13.0850, "lng": 80.2101, "capacity": 300, "availableCapacity": 180, "riskLevel": "Low", "address": "Anna Nagar, Chennai", "contact": "044-2615-4321", "facilities": "Water, Food, Toilets"},
    {"name": "Nungambakkam High School", "lat": 13.0569, "lng": 80.2425, "capacity": 400, "availableCapacity": 260, "riskLevel": "Moderate", "address": "Nungambakkam, Chennai", "contact": "044-2827-9876", "facilities": "Water, Food, Medical, Toilets"},
    {"name": "Egmore Relief Center", "lat": 13.0732, "lng": 80.2609, "capacity": 350, "availableCapacity": 220, "riskLevel": "Moderate", "address": "Egmore, Chennai", "contact": "044-2819-5432", "facilities": "Water, Food, Medical"},
    {"name": "Adyar Kalyana Mandapam", "lat": 13.0067, "lng": 80.2570, "capacity": 600, "availableCapacity": 400, "riskLevel": "High", "address": "Adyar, Chennai", "contact": "044-2441-2345", "facilities": "Water, Food, Medical, Toilets"},
    {"name": "Velachery Community Center", "lat": 12.9750, "lng": 80.2210, "capacity": 450, "availableCapacity": 280, "riskLevel": "High", "address": "Velachery, Chennai", "contact": "044-2266-7890", "facilities": "Water, Food, Toilets"},
    {"name": "Guindy Marriage Hall", "lat": 13.0067, "lng": 80.2206, "capacity": 500, "availableCapacity": 320, "riskLevel": "Moderate", "address": "Guindy, Chennai", "contact": "044-2235-4567", "facilities": "Water, Food, Medical"},
    {"name": "Mylapore Temple Hall", "lat": 13.0339, "lng": 80.2619, "capacity": 400, "availableCapacity": 240, "riskLevel": "High", "address": "Mylapore, Chennai", "contact": "044-2464-8901", "facilities": "Water, Food, Toilets"},
    {"name": "Kotturpuram School", "lat": 13.0200, "lng": 80.2450, "capacity": 300, "availableCapacity": 190, "riskLevel": "High", "address": "Kotturpuram, Chennai", "contact": "044-2441-3456", "facilities": "Water, Food"},
    {"name": "Thiruvanmiyur Relief Camp", "lat": 12.9820, "lng": 80.2590, "capacity": 350, "availableCapacity": 210, "riskLevel": "High", "address": "Thiruvanmiyur, Chennai", "contact": "044-2441-7890", "facilities": "Water, Food, Medical"},
    {"name": "Besant Nagar Community Hall", "lat": 13.0001, "lng": 80.2668, "capacity": 400, "availableCapacity": 250, "riskLevel": "Severe", "address": "Besant Nagar, Chennai", "contact": "044-2445-6789", "facilities": "Water, Food, Medical, Toilets"},
    {"name": "Sholinganallur Relief Center", "lat": 12.9010, "lng": 80.2279, "capacity": 500, "availableCapacity": 300, "riskLevel": "Severe", "address": "Sholinganallur, Chennai", "contact": "044-2450-1234", "facilities": "Water, Food, Medical"},
    {"name": "Neelankarai School", "lat": 12.9490, "lng": 80.2590, "capacity": 300, "availableCapacity": 180, "riskLevel": "Moderate", "address": "Neelankarai, Chennai", "contact": "044-2449-5678", "facilities": "Water, Food"},
    {"name": "Porur Community Center", "lat": 13.0381, "lng": 80.1570, "capacity": 400, "availableCapacity": 260, "riskLevel": "Moderate", "address": "Porur, Chennai", "contact": "044-2476-2345", "facilities": "Water, Food, Medical, Toilets"},
    {"name": "Ashok Nagar Marriage Hall", "lat": 13.0358, "lng": 80.2101, "capacity": 350, "availableCapacity": 220, "riskLevel": "Low", "address": "Ashok Nagar, Chennai", "contact": "044-2489-6789", "facilities": "Water, Food, Toilets"},
    {"name": "KK Nagar Relief Camp", "lat": 13.0381, "lng": 80.2020, "capacity": 300, "availableCapacity": 190, "riskLevel": "Low", "address": "KK Nagar, Chennai", "contact": "044-2474-3456", "facilities": "Water, Food"},
    {"name": "Vadapalani Temple Hall", "lat": 13.0504, "lng": 80.2121, "capacity": 450, "availableCapacity": 290, "riskLevel": "Moderate", "address": "Vadapalani, Chennai", "contact": "044-2480-7890", "facilities": "Water, Food, Medical"},
    {"name": "Perambur Relief Center", "lat": 13.1143, "lng": 80.2378, "capacity": 500, "availableCapacity": 320, "riskLevel": "Low", "address": "Perambur, Chennai", "contact": "044-2662-1234", "facilities": "Water, Food, Medical, Toilets"},
    {"name": "Madhavaram Community Hall", "lat": 13.1482, "lng": 80.2314, "capacity": 400, "availableCapacity": 250, "riskLevel": "Low", "address": "Madhavaram, Chennai", "contact": "044-2552-5678", "facilities": "Water, Food, Toilets"},
    {"name": "Ambattur School", "lat": 13.1143, "lng": 80.1548, "capacity": 450, "availableCapacity": 300, "riskLevel": "Low", "address": "Ambattur, Chennai", "contact": "044-2656-9012", "facilities": "Water, Food, Medical"},
    {"name": "Avadi Relief Camp", "lat": 13.1067, "lng": 80.1018, "capacity": 350, "availableCapacity": 210, "riskLevel": "Low", "address": "Avadi, Chennai", "contact": "044-2666-3456", "facilities": "Water, Food"},
    {"name": "Tambaram Corporation School", "lat": 12.9249, "lng": 80.1000, "capacity": 600, "availableCapacity": 420, "riskLevel": "Low", "address": "Tambaram, Chennai", "contact": "044-2226-7890", "facilities": "Water, Food, Medical, Toilets"},
    {"name": "Chromepet Community Center", "lat": 12.9516, "lng": 80.1462, "capacity": 400, "availableCapacity": 260, "riskLevel": "Low", "address": "Chromepet, Chennai", "contact": "044-2235-1234", "facilities": "Water, Food, Toilets"},
    {"name": "Pallikaranai Relief Center", "lat": 12.9450, "lng": 80.2050, "capacity": 350, "availableCapacity": 200, "riskLevel": "Moderate", "address": "Pallikaranai, Chennai", "contact": "044-2266-5678", "facilities": "Water, Food, Medical"},
    {"name": "Perungudi School", "lat": 12.9610, "lng": 80.2440, "capacity": 300, "availableCapacity": 170, "riskLevel": "High", "address": "Perungudi, Chennai", "contact": "044-2496-9012", "facilities": "Water, Food"},
]


def load_shelters(db: Session) -> int:
    """Load default relief shelters into PostGIS idempotently."""
    inserted = 0
    updated = 0

    for s in DEFAULT_SHELTERS:
        existing = db.query(Shelter).filter(Shelter.name == s["name"]).first()
        point_geom = ST_SetSRID(ST_MakePoint(s["lng"], s["lat"]), 4326)

        if not existing:
            new_shelter = Shelter(
                name=s["name"],
                latitude=s["lat"],
                longitude=s["lng"],
                location=point_geom,
                address=s["address"],
                capacity=s["capacity"],
                available_capacity=s["availableCapacity"],
                risk_level=s["riskLevel"],
                is_active=True,
                facilities=s["facilities"],
                contact=s["contact"],
            )
            db.add(new_shelter)
            inserted += 1
        else:
            existing.latitude = s["lat"]
            existing.longitude = s["lng"]
            existing.location = point_geom
            existing.capacity = s["capacity"]
            existing.risk_level = s["riskLevel"]
            existing.address = s["address"]
            existing.facilities = s["facilities"]
            existing.contact = s["contact"]
            updated += 1

    db.commit()
    print(f"[OK] Shelters loading complete: {inserted} inserted, {updated} updated.")
    return inserted + updated


def main() -> int:
    print("=" * 60)
    print("   GeoGuard V2 — Loading Relief Shelters into PostGIS")
    print("=" * 60)
    with SessionLocal() as db:
        count = load_shelters(db)
        print(f"[SUCCESS] Total shelters in database: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
