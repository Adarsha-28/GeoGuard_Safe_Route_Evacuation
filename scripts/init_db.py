#!/usr/bin/env python3
"""Database initialization script for GeoGuard V2 using Alembic and PostGIS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.config import ROOT_DIR as PROJ_ROOT, logger, settings
from backend.database.connection import SessionLocal, check_db_connection, engine
from backend.models.alert import Alert
from backend.models.grid import Grid
from backend.models.shelter import Shelter
from scripts.load_grids import load_grids
from scripts.load_shelters import load_shelters

DEFAULT_ALERTS = [
    {
        "title": "Heavy Rainfall Advisory",
        "severity": "High",
        "zone": "All Zones",
        "message": "Continuous precipitation expected across coastal corridors. Low-lying areas advised to monitor shelter status.",
    },
    {
        "title": "River Basin Water Warning",
        "severity": "Critical",
        "zone": "Adyar River Basin",
        "message": "Water discharge elevated near South Chennai basins. Residents in flood plains should identify nearest safe routes.",
    },
]


def seed_default_alerts(db) -> int:
    """Seed baseline administrative alerts if table is empty."""
    count = db.query(Alert).count()
    if count == 0:
        for a in DEFAULT_ALERTS:
            db.add(
                Alert(
                    title=a["title"],
                    severity=a["severity"],
                    zone=a["zone"],
                    message=a["message"],
                    is_active=True,
                )
            )
        db.commit()
        print(f"[OK] Seeded {len(DEFAULT_ALERTS)} default emergency alerts.")
        return len(DEFAULT_ALERTS)
    return count


def run_migrations() -> None:
    """Apply Alembic database migrations up to head."""
    print("[..] Applying Alembic database migrations...")
    alembic_cfg = Config(str(PROJ_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PROJ_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")
    print("[OK] Migrations applied successfully.")


def main() -> int:
    print("=" * 65)
    print("   GeoGuard V2 — PostgreSQL & PostGIS Database Initialization")
    print("=" * 65)

    try:
        # 1. Verify DB connection
        print("[..] Testing database connection...")
        connected, msg = check_db_connection()
        if not connected:
            print(f"[ERROR] Database unreachable: {msg}", file=sys.stderr)
            print("\nIf PostgreSQL/PostGIS is not running, either:")
            print("  1. Run: python scripts/setup_local_postgres.py")
            print("  2. Or run: docker compose up -d\n")
            return 1

        print(f"[OK] Database connection verified: {msg}")

        # 2. Run migrations
        run_migrations()

        # 3. Load Grids and Shelters
        with SessionLocal() as db:
            print("\n[..] Seeding initial datasets...")
            grids_count = load_grids(db)
            shelters_count = load_shelters(db)
            alerts_count = seed_default_alerts(db)

            print("\n" + "=" * 65)
            print("   Database Status Summary:")
            print(f"   - Monitored Sectors (PostGIS): {grids_count}")
            print(f"   - Relief Shelters (PostGIS):   {shelters_count}")
            print(f"   - Emergency Alerts:            {alerts_count}")
            print("=" * 65)
            print("[SUCCESS] GeoGuard V2 database setup completed successfully!\n")
            return 0

    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
