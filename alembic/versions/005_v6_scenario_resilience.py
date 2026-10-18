"""V6 Flood Scenario Simulation, Adaptive Evacuation & Resilience Schema.

Adds:
1. scenarios: master record for simulated flood scenarios
2. scenario_sector_results: sector-level comparative outputs under simulation
3. scenario_shelter_results: shelter capacity stress test outputs
4. scenario_route_results: multi-path evacuation route resilience outputs
5. resilience_assessments: 5-component resilience scores
6. failure_simulations: controlled failure & fallback audit
7. decision_audit_log: operational decision audit trail

Revision ID: 005_v6_scenario_resilience
Revises: 004_v5_predictive_intelligence
Create Date: 2026-09-17 22:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_v6_scenario_resilience"
down_revision: Union[str, None] = "004_v5_predictive_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Scenarios master table
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rainfall_multiplier", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("horizon", sa.String(length=20), server_default="nowcast", nullable=False),
        sa.Column("simulation_demand_factor", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("baseline_rainfall_mm", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("simulated_rainfall_mm", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("total_sectors", sa.Integer(), server_default="34", nullable=False),
        sa.Column("sectors_deteriorated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sectors_improved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sectors_critical", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sectors_high", sa.Integer(), server_default="0", nullable=False),
        sa.Column("shelters_stressed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("shelters_overloaded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("routes_unsafe", sa.Integer(), server_default="0", nullable=False),
        sa.Column("routes_blocked", sa.Integer(), server_default="0", nullable=False),
        sa.Column("system_resilience_score", sa.Float(), server_default="100.0", nullable=False),
        sa.Column("shelter_resilience_score", sa.Float(), server_default="100.0", nullable=False),
        sa.Column("route_resilience_score", sa.Float(), server_default="100.0", nullable=False),
        sa.Column("data_resilience_score", sa.Float(), server_default="100.0", nullable=False),
        sa.Column("model_resilience_score", sa.Float(), server_default="100.0", nullable=False),
        sa.Column("operational_resilience_score", sa.Float(), server_default="100.0", nullable=False),
        sa.Column("model_version", sa.String(length=50), server_default="v5.0.0", nullable=False),
        sa.Column("is_fallback", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("execution_duration_ms", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("disclaimer", sa.String(length=200), server_default="SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_scenarios_time", "scenarios", ["created_at"])
    op.create_index("idx_scenarios_horizon", "scenarios", ["horizon"])

    # 2. Scenario Sector Results
    op.create_table(
        "scenario_sector_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_id", sa.String(length=36), sa.ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grid_id", sa.Integer(), sa.ForeignKey("grids.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grid_name", sa.String(length=100), nullable=False),
        sa.Column("baseline_probability", sa.Float(), nullable=False),
        sa.Column("simulated_probability", sa.Float(), nullable=False),
        sa.Column("probability_delta", sa.Float(), nullable=False),
        sa.Column("baseline_risk", sa.String(length=20), nullable=False),
        sa.Column("simulated_risk", sa.String(length=20), nullable=False),
        sa.Column("risk_transition", sa.String(length=50), nullable=False),
        sa.Column("is_transitioned", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("spatial_propagation_type", sa.String(length=20), server_default="UNAFFECTED", nullable=False),
        sa.Column("priority_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("priority_rank", sa.Integer(), server_default="0", nullable=False),
        sa.Column("priority_category", sa.String(length=20), server_default="Low", nullable=False),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_scen_sec_scen_grid", "scenario_sector_results", ["scenario_id", "grid_id"])
    op.create_index("idx_scen_sec_risk", "scenario_sector_results", ["simulated_risk"])

    # 3. Scenario Shelter Results
    op.create_table(
        "scenario_shelter_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_id", sa.String(length=36), sa.ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shelter_id", sa.Integer(), sa.ForeignKey("shelters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shelter_name", sa.String(length=150), nullable=False),
        sa.Column("total_capacity", sa.Integer(), nullable=False),
        sa.Column("current_available_capacity", sa.Integer(), nullable=False),
        sa.Column("simulation_demand_factor", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("simulated_demand", sa.Integer(), server_default="0", nullable=False),
        sa.Column("remaining_simulated_capacity", sa.Integer(), nullable=False),
        sa.Column("stress_status", sa.String(length=20), server_default="NORMAL", nullable=False),
        sa.Column("surrounding_flood_risk", sa.String(length=20), server_default="Low", nullable=False),
        sa.Column("suitability_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("alternative_shelter_id", sa.Integer(), sa.ForeignKey("shelters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_scen_shelt_scen", "scenario_shelter_results", ["scenario_id"])
    op.create_index("idx_scen_shelt_status", "scenario_shelter_results", ["stress_status"])

    # 4. Scenario Route Results
    op.create_table(
        "scenario_route_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_id", sa.String(length=36), sa.ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin_grid_id", sa.Integer(), sa.ForeignKey("grids.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_shelter_id", sa.Integer(), sa.ForeignKey("shelters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_role", sa.String(length=20), server_default="PRIMARY", nullable=False),
        sa.Column("distance_km", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("duration_min", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("baseline_hazard_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("simulated_hazard_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("simulated_peak_risk", sa.String(length=20), server_default="Low", nullable=False),
        sa.Column("high_risk_exposure_pct", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("severe_risk_exposure_pct", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("route_status", sa.String(length=30), server_default="AVAILABLE", nullable=False),
        sa.Column("advisory_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_scen_route_scen", "scenario_route_results", ["scenario_id"])
    op.create_index("idx_scen_route_status", "scenario_route_results", ["route_status"])

    # 5. Resilience Assessments
    op.create_table(
        "resilience_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_id", sa.String(length=36), sa.ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("overall_resilience_score", sa.Float(), nullable=False),
        sa.Column("shelter_resilience_score", sa.Float(), nullable=False),
        sa.Column("route_resilience_score", sa.Float(), nullable=False),
        sa.Column("data_resilience_score", sa.Float(), nullable=False),
        sa.Column("model_resilience_score", sa.Float(), nullable=False),
        sa.Column("operational_resilience_score", sa.Float(), nullable=False),
        sa.Column("formula_version", sa.String(length=50), server_default="v6.0.0", nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_resilience_time", "resilience_assessments", ["assessed_at"])

    # 6. Failure Simulations
    op.create_table(
        "failure_simulations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("simulation_type", sa.String(length=50), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("detected", sa.Boolean(), nullable=False),
        sa.Column("fallback_activated", sa.Boolean(), nullable=False),
        sa.Column("fallback_type", sa.String(length=100), nullable=False),
        sa.Column("degraded_status", sa.String(length=50), nullable=False),
        sa.Column("response_time_ms", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("audit_record_created", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_fail_sim_time", "failure_simulations", ["triggered_at"])
    op.create_index("idx_fail_sim_type", "failure_simulations", ["simulation_type"])

    # 7. Decision Audit Log
    op.create_table(
        "decision_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_id", sa.String(length=36), sa.ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("operator", sa.String(length=50), server_default="Command Center Operator", nullable=False),
        sa.Column("action_taken", sa.String(length=200), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=True),
        sa.Column("impact_summary_json", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_decision_time", "decision_audit_log", ["timestamp"])
    op.create_index("idx_decision_event", "decision_audit_log", ["event_type"])


def downgrade() -> None:
    op.drop_table("decision_audit_log")
    op.drop_table("failure_simulations")
    op.drop_table("resilience_assessments")
    op.drop_table("scenario_route_results")
    op.drop_table("scenario_shelter_results")
    op.drop_table("scenario_sector_results")
    op.drop_table("scenarios")
