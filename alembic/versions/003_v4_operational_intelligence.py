"""V4 Near-Real-Time Operational Flood Intelligence Schema.

Adds:
1. weather_observations: wind_speed_kmh, latitude, longitude, ingested_at, compound unique constraint.
2. risk_predictions: trigger_type (scheduled / manual).
3. grid_risk_states: dedicated table for monitored grid risk states and transition tracking.
4. alerts: grid_id, previous_risk, current_risk, probability, model_version, and updated severity constraint.

Revision ID: 003_v4_operational_intelligence
Revises: 002_add_ml_prediction_fields
Create Date: 2026-09-03 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_v4_operational_intelligence"
down_revision: Union[str, None] = "002_add_ml_prediction_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Weather observations enhancements
    op.add_column(
        "weather_observations",
        sa.Column("wind_speed_kmh", sa.Float(), server_default="0.0", nullable=False),
    )
    op.add_column(
        "weather_observations",
        sa.Column("latitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("longitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "weather_observations",
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # Populate coordinates for existing observations from PostGIS Point geometry
    op.execute("""
        UPDATE weather_observations
        SET latitude = ST_Y(location::geometry),
            longitude = ST_X(location::geometry)
        WHERE latitude IS NULL AND location IS NOT NULL;
    """)

    # Create composite unique index to prevent duplicate observations
    op.create_index(
        "uq_weather_obs_source_time_coords",
        "weather_observations",
        ["source", "observed_at", "latitude", "longitude"],
        unique=True,
    )

    # 2. Risk predictions audit enhancements
    op.add_column(
        "risk_predictions",
        sa.Column("trigger_type", sa.String(length=20), server_default="manual", nullable=False),
    )
    op.create_index("idx_risk_pred_trigger", "risk_predictions", ["trigger_type"])

    # 3. Create grid_risk_states table for state-change detection
    op.create_table(
        "grid_risk_states",
        sa.Column("grid_id", sa.Integer(), nullable=False),
        sa.Column("current_risk_level", sa.String(length=20), server_default="Low", nullable=False),
        sa.Column("current_probability", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("previous_risk_level", sa.String(length=20), nullable=True),
        sa.Column("model_version", sa.String(length=50), server_default="v3.0.0", nullable=False),
        sa.Column("risk_changed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["grid_id"], ["grids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("grid_id"),
    )
    op.create_index("idx_grid_risk_states_level", "grid_risk_states", ["current_risk_level"])
    op.create_index("idx_grid_risk_states_updated", "grid_risk_states", ["updated_at"])

    # Initialize grid_risk_states from existing grids
    op.execute("""
        INSERT INTO grid_risk_states (grid_id, current_risk_level, current_probability, model_version, updated_at)
        SELECT id, flood_risk, flood_risk_score, 'v3.0.0', now()
        FROM grids
        ON CONFLICT (grid_id) DO NOTHING;
    """)

    # 4. Alerts table enhancements
    op.add_column(
        "alerts",
        sa.Column("grid_id", sa.Integer(), sa.ForeignKey("grids.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("previous_risk", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("current_risk", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("probability", sa.Float(), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("model_version", sa.String(length=50), nullable=True),
    )
    op.create_index("idx_alerts_grid_id", "alerts", ["grid_id"])

    # Update severity check constraint to allow 'Informational'
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS chk_alert_severity_valid;")
    op.execute("""
        ALTER TABLE alerts ADD CONSTRAINT chk_alert_severity_valid
        CHECK (severity IN ('Low', 'Moderate', 'High', 'Critical', 'Warning', 'Informational'));
    """)


def downgrade() -> None:
    # 4. Revert alerts
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS chk_alert_severity_valid;")
    op.execute("""
        ALTER TABLE alerts ADD CONSTRAINT chk_alert_severity_valid
        CHECK (severity IN ('Low', 'Moderate', 'High', 'Critical', 'Warning'));
    """)
    op.drop_index("idx_alerts_grid_id", table_name="alerts")
    op.drop_column("alerts", "model_version")
    op.drop_column("alerts", "probability")
    op.drop_column("alerts", "current_risk")
    op.drop_column("alerts", "previous_risk")
    op.drop_column("alerts", "grid_id")

    # 3. Drop grid_risk_states
    op.drop_index("idx_grid_risk_states_updated", table_name="grid_risk_states")
    op.drop_index("idx_grid_risk_states_level", table_name="grid_risk_states")
    op.drop_table("grid_risk_states")

    # 2. Revert risk_predictions
    op.drop_index("idx_risk_pred_trigger", table_name="risk_predictions")
    op.drop_column("risk_predictions", "trigger_type")

    # 1. Revert weather_observations
    op.drop_index("uq_weather_obs_source_time_coords", table_name="weather_observations")
    op.drop_column("weather_observations", "ingested_at")
    op.drop_column("weather_observations", "longitude")
    op.drop_column("weather_observations", "latitude")
    op.drop_column("weather_observations", "wind_speed_kmh")
