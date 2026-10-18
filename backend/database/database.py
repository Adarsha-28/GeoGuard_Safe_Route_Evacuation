"""SQLite database layer for GeoGuard V1.

Provides parameterized query execution, schema migrations, and CRUD operations
for relief shelters and emergency alerts.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from backend.config import DB_PATH, logger

DEFAULT_SHELTERS_DATA = [
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

DEFAULT_ALERTS_DATA = [
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


@contextmanager
def get_db_connection(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional SQLite database connection with row factory."""
    path = str(db_path or DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize database tables, create indexes, and seed initial data idempotently."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Create shelters table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS shelters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                address TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                availableCapacity INTEGER NOT NULL CHECK(availableCapacity >= 0),
                riskLevel TEXT NOT NULL,
                isActive INTEGER NOT NULL DEFAULT 1,
                facilities TEXT NOT NULL,
                contact TEXT NOT NULL
            )
            """
        )

        # Create alerts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                zone TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create performance indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_shelters_active ON shelters(isActive);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);"
        )

        # Seed shelters idempotently
        for s in DEFAULT_SHELTERS_DATA:
            cursor.execute(
                """
                INSERT OR IGNORE INTO shelters 
                (name, latitude, longitude, address, capacity, availableCapacity, riskLevel, isActive, facilities, contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    s["name"],
                    s["lat"],
                    s["lng"],
                    s["address"],
                    s["capacity"],
                    s["availableCapacity"],
                    s["riskLevel"],
                    s["facilities"],
                    s["contact"],
                ),
            )

        # Seed initial alerts idempotently
        cursor.execute("SELECT COUNT(*) FROM alerts")
        if cursor.fetchone()[0] == 0:
            for a in DEFAULT_ALERTS_DATA:
                cursor.execute(
                    """
                    INSERT INTO alerts (title, severity, zone, message)
                    VALUES (?, ?, ?, ?)
                    """,
                    (a["title"], a["severity"], a["zone"], a["message"]),
                )

        conn.commit()


def get_all_shelters(active_only: bool = True, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Retrieve all shelters from database."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM shelters WHERE isActive = 1 ORDER BY name ASC")
        else:
            cursor.execute("SELECT * FROM shelters ORDER BY name ASC")
        return [dict(row) for row in cursor.fetchall()]


def get_shelter_by_id(shelter_id: int, db_path: Path | str | None = None) -> dict[str, Any] | None:
    """Retrieve a single shelter by ID."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_shelter_capacity(shelter_id: int, new_capacity: int, db_path: Path | str | None = None) -> bool:
    """Update available capacity for a specific shelter (rejects negative numbers)."""
    if new_capacity < 0:
        return False

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE shelters SET availableCapacity = ? WHERE id = ?",
                (new_capacity, shelter_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False


def get_all_alerts(limit: int = 50, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Retrieve recent alerts ordered by ID descending."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


def create_alert(
    title: str, severity: str, zone: str, message: str, db_path: Path | str | None = None
) -> dict[str, Any]:
    """Insert a new alert into the database and return the created record."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO alerts (title, severity, zone, message)
            VALUES (?, ?, ?, ?)
            """,
            (title, severity, zone, message),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM alerts WHERE id = ?", (new_id,))
        return dict(cursor.fetchone())
