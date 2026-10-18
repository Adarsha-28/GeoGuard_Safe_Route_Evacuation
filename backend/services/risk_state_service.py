"""Risk State Management Service for GeoGuard V4.

Maintains persistent spatial risk states per monitored grid sector in PostgreSQL/PostGIS.
Tracks state changes, detects risk escalations and de-escalations, records change timestamps,
and suppresses redundant alert generation when risk state remains unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.risk_state import GridRiskState
from backend.services.prediction_pipeline_service import SectorPredictionResult

RISK_ORDER = {"Low": 0, "Moderate": 1, "High": 2, "Severe": 3}


class RiskTransition:
    """Represents a detected flood risk transition for a monitored grid sector."""

    def __init__(
        self,
        grid_id: int,
        grid_name: str,
        previous_risk: str,
        current_risk: str,
        probability: float,
        model_version: str,
        transition_type: str,  # "escalation", "de-escalation", "unchanged", "initial"
        risk_changed_at: datetime,
    ) -> None:
        self.grid_id = grid_id
        self.grid_name = grid_name
        self.previous_risk = previous_risk
        self.current_risk = current_risk
        self.probability = probability
        self.model_version = model_version
        self.transition_type = transition_type
        self.risk_changed_at = risk_changed_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_id": self.grid_id,
            "grid_name": self.grid_name,
            "previous_risk": self.previous_risk,
            "current_risk": self.current_risk,
            "probability": round(self.probability, 4),
            "model_version": self.model_version,
            "transition_type": self.transition_type,
            "risk_changed_at": self.risk_changed_at.isoformat(),
        }


class RiskStateService:
    """Manages persistent grid risk states and transition event detection."""

    @staticmethod
    def classify_transition_type(prev_risk: str | None, curr_risk: str) -> str:
        """Categorize risk transition as escalation, de-escalation, unchanged, or initial."""
        if prev_risk is None or prev_risk == "":
            return "initial"
        prev_rank = RISK_ORDER.get(prev_risk, 0)
        curr_rank = RISK_ORDER.get(curr_risk, 0)

        if curr_rank > prev_rank:
            return "escalation"
        elif curr_rank < prev_rank:
            return "de-escalation"
        return "unchanged"

    def update_grid_risk_states(
        self,
        db: Session,
        predictions: list[SectorPredictionResult],
    ) -> list[RiskTransition]:
        """Update persistent grid risk states and detect all valid state transitions."""
        now_dt = datetime.utcnow()
        transitions: list[RiskTransition] = []

        # Build map of predictions by grid_id
        pred_map = {p.grid_id: p for p in predictions}

        # Query all existing states
        existing_states = {s.grid_id: s for s in db.query(GridRiskState).all()}
        grids = {g.id: g for g in db.query(Grid).all()}

        for grid_id, pred in pred_map.items():
            grid = grids.get(grid_id)
            grid_name = grid.name if grid else f"Grid {grid_id}"
            state = existing_states.get(grid_id)

            if state is None:
                # First time seeing this grid state
                trans_type = "initial"
                state = GridRiskState(
                    grid_id=grid_id,
                    current_risk_level=pred.risk_level,
                    current_probability=pred.probability,
                    previous_risk_level=None,
                    model_version=pred.model_version,
                    risk_changed_at=now_dt,
                    updated_at=now_dt,
                )
                db.add(state)
                # Sync with Grid entity
                if grid:
                    grid.flood_risk = pred.risk_level
                    grid.flood_risk_score = pred.probability

                transitions.append(
                    RiskTransition(
                        grid_id=grid_id,
                        grid_name=grid_name,
                        previous_risk="Low",
                        current_risk=pred.risk_level,
                        probability=pred.probability,
                        model_version=pred.model_version,
                        transition_type=trans_type,
                        risk_changed_at=now_dt,
                    )
                )
            else:
                prev_risk = state.current_risk_level
                curr_risk = pred.risk_level
                trans_type = self.classify_transition_type(prev_risk, curr_risk)

                if trans_type != "unchanged":
                    # Risk has shifted!
                    logger.info(
                        f"risk_transition: Grid {grid_id} ({grid_name}) transitioned "
                        f"{prev_risk} -> {curr_risk} (p={pred.probability:.4f}, type={trans_type})"
                    )
                    state.previous_risk_level = prev_risk
                    state.current_risk_level = curr_risk
                    state.current_probability = pred.probability
                    state.model_version = pred.model_version
                    state.risk_changed_at = now_dt
                    state.updated_at = now_dt

                    # Sync with Grid entity
                    if grid:
                        grid.flood_risk = curr_risk
                        grid.flood_risk_score = pred.probability

                    transitions.append(
                        RiskTransition(
                            grid_id=grid_id,
                            grid_name=grid_name,
                            previous_risk=prev_risk,
                            current_risk=curr_risk,
                            probability=pred.probability,
                            model_version=pred.model_version,
                            transition_type=trans_type,
                            risk_changed_at=now_dt,
                        )
                    )
                else:
                    # Risk level is unchanged; simply update probability and timestamp
                    state.current_probability = pred.probability
                    state.model_version = pred.model_version
                    state.updated_at = now_dt
                    if grid:
                        grid.flood_risk_score = pred.probability

        db.commit()
        return transitions

    def get_all_grid_states(self, db: Session) -> list[dict[str, Any]]:
        """Retrieve current operational risk state for all monitored sectors."""
        states = (
            db.query(GridRiskState)
            .join(Grid, GridRiskState.grid_id == Grid.id)
            .order_by(GridRiskState.grid_id.asc())
            .all()
        )
        results = []
        for s in states:
            d = s.to_dict()
            d["place_name"] = s.grid.name if s.grid else f"Sector {s.grid_id}"
            results.append(d)
        return results

    def get_high_risk_grid_count(self, db: Session) -> int:
        """Count sectors currently in High or Severe risk states."""
        return (
            db.query(GridRiskState)
            .filter(GridRiskState.current_risk_level.in_(["High", "Severe"]))
            .count()
        )


_singleton_risk_state_service: RiskStateService | None = None


def get_risk_state_service() -> RiskStateService:
    """Retrieve singleton instance of RiskStateService."""
    global _singleton_risk_state_service
    if _singleton_risk_state_service is None:
        _singleton_risk_state_service = RiskStateService()
    return _singleton_risk_state_service
