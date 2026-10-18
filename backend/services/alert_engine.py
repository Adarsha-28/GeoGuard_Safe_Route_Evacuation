"""Alert Engine for GeoGuard V4.

Automatically evaluates risk state transitions, formats calibrated decision-support advisories,
prevents duplicate alerts for the same transition, deactivates superseded alerts upon de-escalation,
and persists alerts in PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.alert import Alert
from backend.services.risk_state_service import RiskTransition


class AlertEngine:
    """Evaluates risk transitions and produces calibrated operational alerts."""

    @staticmethod
    def map_transition_to_alert_spec(trans: RiskTransition) -> dict[str, str] | None:
        """Map a risk state transition to title, severity, and calibrated decision-support message."""
        prev = trans.previous_risk
        curr = trans.current_risk
        zone = trans.grid_name
        prob_pct = f"{trans.probability * 100:.1f}%"

        # Escalation rules
        if prev == "Low" and curr == "Moderate":
            return {
                "title": f"Flood Risk Advisory: {zone}",
                "severity": "Informational",
                "message": (
                    f"Elevated flood hazard observed in {zone} (estimated risk probability: {prob_pct}). "
                    f"Residents are advised to monitor local conditions and review shelter availability."
                ),
            }
        elif curr == "High":
            return {
                "title": f"High Flood Risk Warning: {zone}",
                "severity": "Warning",
                "message": (
                    f"High flood risk detected in {zone} (estimated risk probability: {prob_pct}). "
                    f"Consider moving toward the nearest available safe shelter and review recommended evacuation paths."
                ),
            }
        elif curr == "Severe":
            return {
                "title": f"CRITICAL Flood Hazard Alert: {zone}",
                "severity": "Critical",
                "message": (
                    f"Critical flood inundation risk detected for {zone} (estimated risk probability: {prob_pct}). "
                    f"Immediate decision support: Consider moving toward the nearest available safe shelter immediately."
                ),
            }

        # De-escalation rules
        elif prev == "Severe" and curr in ("High", "Moderate", "Low"):
            return {
                "title": f"Flood Risk Status Update: {zone}",
                "severity": "Moderate" if curr == "Moderate" else "Warning" if curr == "High" else "Informational",
                "message": (
                    f"Flood hazard in {zone} has subsided from Severe to {curr}. "
                    f"Maintain situational awareness as stormwater drainage continues."
                ),
            }
        elif prev == "High" and curr in ("Moderate", "Low"):
            return {
                "title": f"Flood Risk De-escalation: {zone}",
                "severity": "Informational",
                "message": (
                    f"Flood hazard in {zone} has subsided from High to {curr}. "
                    f"Local road accessibility is expected to improve. Continue following local guidance."
                ),
            }
        elif prev == "Moderate" and curr == "Low":
            return {
                "title": f"All Clear / Low Risk: {zone}",
                "severity": "Low",
                "message": (
                    f"Flood conditions in {zone} have returned to Low hazard baseline. Normal operations resumed."
                ),
            }

        return None

    def evaluate_transitions_and_generate_alerts(
        self,
        db: Session,
        transitions: list[RiskTransition],
    ) -> list[dict[str, Any]]:
        """Process transitions, filter duplicates, manage alert lifecycle, and persist new alerts."""
        now_dt = datetime.utcnow()
        created_alerts: list[dict[str, Any]] = []

        for trans in transitions:
            # Skip unchanged state
            if trans.transition_type == "unchanged":
                continue

            # For initial state, only alert if current risk is Moderate, High, or Severe
            if trans.transition_type == "initial" and trans.current_risk == "Low":
                continue

            alert_spec = self.map_transition_to_alert_spec(trans)
            if not alert_spec:
                continue

            # Check for duplicate active alert for the same grid and state transition
            existing_alert = (
                db.query(Alert)
                .filter(
                    Alert.grid_id == trans.grid_id,
                    Alert.is_active == True,
                    Alert.current_risk == trans.current_risk,
                    Alert.previous_risk == trans.previous_risk,
                )
                .first()
            )

            if existing_alert:
                logger.debug(
                    f"Duplicate alert suppressed for Grid {trans.grid_id}: "
                    f"active alert {existing_alert.id} already exists for {trans.previous_risk} -> {trans.current_risk}."
                )
                continue

            # When risk de-escalates, deactivate older active alerts for this grid
            if trans.transition_type == "de-escalation" or trans.current_risk == "Low":
                prior_active = (
                    db.query(Alert)
                    .filter(
                        Alert.grid_id == trans.grid_id,
                        Alert.is_active == True,
                    )
                    .all()
                )
                for pa in prior_active:
                    pa.is_active = False
                    from backend.services.timeline_service import TimelineService
                    TimelineService.record_event(
                        db=db,
                        event_type="alert_deactivated",
                        category="ALERT",
                        severity="INFO",
                        message=f"Alert #{pa.id} ({pa.title}) deactivated due to risk de-escalation.",
                        grid_id=trans.grid_id,
                        metadata={"alert_id": pa.id, "previous_risk": pa.previous_risk, "current_risk": trans.current_risk},
                    )

            # Create new persistent alert
            new_alert = Alert(
                grid_id=trans.grid_id,
                title=alert_spec["title"],
                severity=alert_spec["severity"],
                zone=trans.grid_name,
                message=alert_spec["message"],
                previous_risk=trans.previous_risk,
                current_risk=trans.current_risk,
                probability=trans.probability,
                model_version=trans.model_version,
                is_active=True,
                timestamp=now_dt,
            )
            db.add(new_alert)
            db.commit()
            db.refresh(new_alert)

            # Record timeline event
            from backend.services.timeline_service import TimelineService
            TimelineService.record_event(
                db=db,
                event_type="alert_generated",
                category="ALERT",
                severity=new_alert.severity.upper() if new_alert.severity in ("Critical", "Warning") else "INFO",
                message=f"[{new_alert.severity}] {new_alert.title}: {new_alert.message[:120]}...",
                grid_id=trans.grid_id,
                metadata={"alert_id": new_alert.id, "probability": new_alert.probability, "trend": trans.transition_type},
            )

            logger.info(
                f"alert_created: ID {new_alert.id} - [{new_alert.severity}] {new_alert.title} "
                f"(Grid {trans.grid_id}, {trans.previous_risk} -> {trans.current_risk})"
            )
            created_alerts.append(new_alert.to_dict())

        return created_alerts


_singleton_alert_engine: AlertEngine | None = None


def get_alert_engine() -> AlertEngine:
    """Retrieve singleton instance of AlertEngine."""
    global _singleton_alert_engine
    if _singleton_alert_engine is None:
        _singleton_alert_engine = AlertEngine()
    return _singleton_alert_engine
