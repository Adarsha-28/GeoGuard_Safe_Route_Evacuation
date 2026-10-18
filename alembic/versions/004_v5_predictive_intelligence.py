"""V5 Predictive Flood Intelligence & Decision Support Schema.

Adds:
1. prediction_history: audit and temporal tracking across prediction horizons (nowcast, 6h, 12h, 24h).
2. risk_transitions: historical log of risk transitions and deterioration / improvement trends.
3. operational_events: timeline event log for weather syncs, prediction cycles, alerts, evacuations, etc.
4. zone_priorities: operational priority scoring and ranking for Chennai sectors.

Revision ID: 004_v5_predictive_intelligence
Revises: 003_v4_operational_intelligence
Create Date: 2026-09-15 22:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_v5_predictive_intelligence"
down_revision: Union[str, None] = "003_v4_operational_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Prediction History table
    op.create_table(
        "prediction_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grid_id", sa.Integer(), sa.ForeignKey("grids.id", ondelete="CASCADE"), nullable=False),
        sa.Column("horizon", sa.String(length=20), server_default="nowcast", nullable=False),
        sa.Column("predicted_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.85", nullable=False),
        sa.Column("confidence_category", sa.String(length=20), server_default="High", nullable=False),
        sa.Column("rainfall_mm", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("rainfall_3d_mm", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("rainfall_7d_mm", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("model_version", sa.String(length=50), server_default="v5.0.0", nullable=False),
        sa.Column("trigger_type", sa.String(length=20), server_default="scheduled", nullable=False),
        sa.Column("is_fallback", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("contributing_features_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pred_hist_grid_horizon_time", "prediction_history", ["grid_id", "horizon", "predicted_at"])
    op.create_index("idx_pred_hist_time", "prediction_history", ["predicted_at"])
    op.create_index("idx_pred_hist_horizon", "prediction_history", ["horizon"])
    op.create_index("idx_pred_hist_risk", "prediction_history", ["risk_level"])

    # 2. Risk Transitions table
    op.create_table(
        "risk_transitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grid_id", sa.Integer(), sa.ForeignKey("grids.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_risk", sa.String(length=20), nullable=True),
        sa.Column("current_risk", sa.String(length=20), nullable=False),
        sa.Column("previous_probability", sa.Float(), nullable=True),
        sa.Column("current_probability", sa.Float(), nullable=False),
        sa.Column("probability_delta", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("trend", sa.String(length=30), server_default="STABLE", nullable=False),
        sa.Column("horizon", sa.String(length=20), server_default="nowcast", nullable=False),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_risk_trans_grid_time", "risk_transitions", ["grid_id", "detected_at"])
    op.create_index("idx_risk_trans_trend", "risk_transitions", ["trend"])

    # 3. Operational Events table
    op.create_table(
        "operational_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), server_default="SYSTEM", nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="INFO", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("grid_id", sa.Integer(), sa.ForeignKey("grids.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_op_events_time", "operational_events", ["created_at"])
    op.create_index("idx_op_events_type", "operational_events", ["event_type"])
    op.create_index("idx_op_events_grid", "operational_events", ["grid_id"])

    # 4. Zone Priorities table
    op.create_table(
        "zone_priorities",
        sa.Column("grid_id", sa.Integer(), sa.ForeignKey("grids.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("priority_rank", sa.Integer(), server_default="1", nullable=False),
        sa.Column("priority_category", sa.String(length=20), server_default="Low", nullable=False),
        sa.Column("risk_level", sa.String(length=20), server_default="Low", nullable=False),
        sa.Column("predicted_probability", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("probability_delta", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("rainfall_accumulation_mm", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("shelter_accessibility_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.85", nullable=False),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("grid_id"),
    )
    op.create_index("idx_zone_prio_category", "zone_priorities", ["priority_category"])
    op.create_index("idx_zone_prio_score", "zone_priorities", ["priority_score"])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index("idx_zone_prio_score", table_name="zone_priorities")
    op.drop_index("idx_zone_prio_category", table_name="zone_priorities")
    op.drop_table("zone_priorities")

    op.drop_index("idx_op_events_grid", table_name="operational_events")
    op.drop_index("idx_op_events_type", table_name="operational_events")
    op.drop_index("idx_op_events_time", table_name="operational_events")
    op.drop_table("operational_events")

    op.drop_index("idx_risk_trans_trend", table_name="risk_transitions")
    op.drop_index("idx_risk_trans_grid_time", table_name="risk_transitions")
    op.drop_table("risk_transitions")

    op.drop_index("idx_pred_hist_risk", table_name="prediction_history")
    op.drop_index("idx_pred_hist_horizon", table_name="prediction_history")
    op.drop_index("idx_pred_hist_time", table_name="prediction_history")
    op.drop_index("idx_pred_hist_grid_horizon_time", table_name="prediction_history")
    op.drop_table("prediction_history")
