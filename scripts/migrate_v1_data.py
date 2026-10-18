#!/usr/bin/env python3
"""Migration script importing existing V1 SQLite records into V2 PostgreSQL/PostGIS."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy.orm import Session

from backend.config import DB_PATH
from backend.database.connection import SessionLocal
from backend.models.alert import Alert
from backend.models.shelter import Shelter
from backend.services.shelter_service import validate_coordinates


def migrate_shelters(sqlite_conn: sqlite3.Connection, db: Session) -> dict[str, int]:
    """Import shelters from SQLite into PostGIS."""
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT * FROM shelters")
    rows = cursor.fetchall()

    stats = {"imported": 0, "skipped": 0, "failed": 0}

    for row in rows:
        r = dict(row)
        name = r.get("name", "").strip()
        lat = r.get("latitude")
        lng = r.get("longitude")
        cap = r.get("capacity")
        avail = r.get("availableCapacity")

        # Validate coordinates
        is_valid, err = validate_coordinates(lat, lng)
        if not is_valid or not name or cap is None or avail is None or avail < 0 or cap < 0:
            stats["failed"] += 1
            print(f"[WARN] Skipping malformed shelter record {r.get('id')}: {err or 'invalid capacity'}")
            continue

        existing = db.query(Shelter).filter(Shelter.name == name).first()
        if existing:
            stats["skipped"] += 1
            continue

        point_geom = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        shelter = Shelter(
            name=name,
            latitude=lat,
            longitude=lng,
            location=point_geom,
            address=r.get("address", ""),
            capacity=cap,
            available_capacity=avail,
            risk_level=r.get("riskLevel", "Moderate"),
            is_active=bool(r.get("isActive", 1)),
            facilities=r.get("facilities", ""),
            contact=r.get("contact", ""),
        )
        db.add(shelter)
        stats["imported"] += 1

    db.commit()
    return stats


def migrate_alerts(sqlite_conn: sqlite3.Connection, db: Session) -> dict[str, int]:
    """Import alerts from SQLite into PostgreSQL."""
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT * FROM alerts")
    rows = cursor.fetchall()

    stats = {"imported": 0, "skipped": 0, "failed": 0}
    valid_severities = {"Low", "Moderate", "High", "Critical", "Warning"}

    for row in rows:
        r = dict(row)
        title = str(r.get("title", "")).strip()
        severity = str(r.get("severity", "")).strip()
        zone = str(r.get("zone", "")).strip()
        message = str(r.get("message", "")).strip()

        if not title or severity not in valid_severities or not message:
            stats["failed"] += 1
            print(f"[WARN] Skipping malformed alert record: {title} ({severity})")
            continue

        # Check existing alert by title and zone
        existing = db.query(Alert).filter(Alert.title == title, Alert.zone == zone).first()
        if existing:
            stats["skipped"] += 1
            continue

        alert = Alert(
            title=title,
            severity=severity,
            zone=zone,
            message=message,
            is_active=True,
        )
        db.add(alert)
        stats["imported"] += 1

    db.commit()
    return stats


def main() -> int:
    print("=" * 65)
    print("   GeoGuard V2 — V1 SQLite to V2 PostgreSQL/PostGIS Migration")
    print("=" * 65)

    if not DB_PATH.exists():
        print(f"[INFO] No V1 SQLite database found at {DB_PATH}. Skipping migration.")
        return 0

    print(f"[..] Reading SQLite database from {DB_PATH}...")
    sqlite_conn = sqlite3.connect(DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    with SessionLocal() as db:
        print("[..] Migrating shelters...")
        shelter_stats = migrate_shelters(sqlite_conn, db)
        print(
            f"[OK] Shelters migration: {shelter_stats['imported']} imported, "
            f"{shelter_stats['skipped']} skipped (already present), {shelter_stats['failed']} failed."
        )

        print("[..] Migrating alerts...")
        alert_stats = migrate_alerts(sqlite_conn, db)
        print(
            f"[OK] Alerts migration: {alert_stats['imported']} imported, "
            f"{alert_stats['skipped']} skipped (already present), {alert_stats['failed']} failed."
        )

    sqlite_conn.close()
    print("=" * 65)
    print("[SUCCESS] Data migration completed successfully! (Original SQLite file preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
