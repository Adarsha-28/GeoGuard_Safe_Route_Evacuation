"""Initial PostGIS schema and indexes for GeoGuard V2.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-02 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostGIS Extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Create Grids Table
    op.create_table(
        "grids",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("elevation_m", sa.Float(), nullable=False),
        sa.Column("distance_to_water", sa.Float(), nullable=False),
        sa.Column("rainfall_mm", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("flood_risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("flood_risk", sa.String(length=20), server_default="Low", nullable=False),
        sa.Column("geom", Geometry(geometry_type="POLYGON", srid=4326), nullable=True),
        sa.Column("point_geom", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_grids_risk", "grids", ["flood_risk"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_grids_geom ON grids USING gist (geom);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_grids_point_geom ON grids USING gist (point_geom);")

    # 3. Create Shelters Table
    op.create_table(
        "shelters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("available_capacity", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), server_default="Moderate", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("facilities", sa.Text(), server_default="", nullable=False),
        sa.Column("contact", sa.String(length=50), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("capacity >= 0", name="chk_shelter_capacity_non_negative"),
        sa.CheckConstraint("available_capacity >= 0", name="chk_shelter_available_capacity_non_negative"),
        sa.CheckConstraint("available_capacity <= capacity", name="chk_shelter_available_lte_capacity"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_shelters_active_avail", "shelters", ["is_active", "available_capacity"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_shelters_location ON shelters USING gist (location);")

    # 4. Create Weather Observations Table
    op.create_table(
        "weather_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("rainfall_mm", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), server_default="Open-Meteo", nullable=False),
        sa.Column("observed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_weather_observed_at", "weather_observations", ["observed_at"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_weather_location ON weather_observations USING gist (location);")

    # 5. Create Risk Predictions Table
    op.create_table(
        "risk_predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grid_id", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("rainfall_score", sa.Float(), nullable=False),
        sa.Column("elevation_score", sa.Float(), nullable=False),
        sa.Column("water_proximity_score", sa.Float(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["grid_id"], ["grids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_risk_pred_grid", "risk_predictions", ["grid_id"])
    op.create_index("idx_risk_pred_time", "risk_predictions", ["calculated_at"])

    # 6. Create Alerts Table
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("zone", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "severity IN ('Low', 'Moderate', 'High', 'Critical', 'Warning')",
            name="chk_alert_severity_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alerts_timestamp", "alerts", ["timestamp"])

    # 7. Create Route Evaluations Table
    op.create_table(
        "route_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_lat", sa.Float(), nullable=False),
        sa.Column("source_lng", sa.Float(), nullable=False),
        sa.Column("shelter_id", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("safety_score", sa.Float(), nullable=False),
        sa.Column("max_risk", sa.String(length=20), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["shelter_id"], ["shelters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_route_eval_time", "route_evaluations", ["evaluated_at"])


def downgrade() -> None:
    op.drop_table("route_evaluations")
    op.drop_table("alerts")
    op.drop_table("risk_predictions")
    op.drop_table("weather_observations")
    op.drop_table("shelters")
    op.drop_table("grids")
