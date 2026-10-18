"""Database package for GeoGuard."""

from backend.database.database import (
    init_db,
    get_db_connection,
    get_all_shelters,
    get_shelter_by_id,
    update_shelter_capacity,
    get_all_alerts,
    create_alert,
)

__all__ = [
    "init_db",
    "get_db_connection",
    "get_all_shelters",
    "get_shelter_by_id",
    "update_shelter_capacity",
    "get_all_alerts",
    "create_alert",
]
