"""Add ML prediction audit fields to risk_predictions table.

Revision ID: 002_add_ml_prediction_fields
Revises: 001_initial_schema
Create Date: 2026-09-02 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_add_ml_prediction_fields"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "risk_predictions",
        sa.Column("model_version", sa.String(length=50), server_default="v2.0.0-deterministic", nullable=False),
    )
    op.add_column(
        "risk_predictions",
        sa.Column("probability", sa.Float(), nullable=True),
    )
    op.add_column(
        "risk_predictions",
        sa.Column("prediction_horizon", sa.String(length=50), server_default="24-Hour Hazard", nullable=True),
    )
    op.add_column(
        "risk_predictions",
        sa.Column("is_fallback", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("risk_predictions", "is_fallback")
    op.drop_column("risk_predictions", "prediction_horizon")
    op.drop_column("risk_predictions", "probability")
    op.drop_column("risk_predictions", "model_version")
