"""Operational Scheduler with Concurrency Guard for GeoGuard V4.

Coordinates periodic near-real-time flood intelligence workflows:
1. Live Weather Ingestion (Open-Meteo)
2. Feature Generation (exact 8 features matching V3)
3. Prediction Pipeline (V3 ML inference with V2 fallback)
4. Risk State Management (transition tracking)
5. Alert Engine (calibrated advisories & deduplication)

Implements strict concurrency protection via threading.Lock:
- Skips overlapping cycles with structured logging (prediction_cycle_skipped)
- Recovers gracefully from transient failures without killing the scheduler
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.config import (
    PREDICTION_INTERVAL_SECONDS,
    WEATHER_SYNC_INTERVAL_SECONDS,
    logger,
    settings,
)
from backend.database.connection import SessionLocal
from backend.models.alert import Alert
from backend.services.alert_engine import AlertEngine, get_alert_engine
from backend.services.feature_service import FeatureService, get_feature_service
from backend.services.ml_prediction_service import MLPredictionService, get_ml_prediction_service
from backend.services.prediction_pipeline_service import (
    PredictionPipelineResult,
    PredictionPipelineService,
    get_prediction_pipeline_service,
)
from backend.services.risk_state_service import RiskStateService, get_risk_state_service
from backend.services.weather_ingestion_service import (
    WeatherIngestionResult,
    WeatherIngestionService,
    get_weather_ingestion_service,
)


class OperationalScheduler:
    """Production scheduler orchestrating automated flood intelligence cycles."""

    def __init__(
        self,
        weather_service: WeatherIngestionService | None = None,
        feature_service: FeatureService | None = None,
        pipeline_service: PredictionPipelineService | None = None,
        risk_state_service: RiskStateService | None = None,
        alert_engine: AlertEngine | None = None,
        weather_interval_seconds: int = WEATHER_SYNC_INTERVAL_SECONDS,
        prediction_interval_seconds: int = PREDICTION_INTERVAL_SECONDS,
    ) -> None:
        self.weather_service = weather_service or get_weather_ingestion_service()
        self.feature_service = feature_service or get_feature_service()
        self.pipeline_service = pipeline_service or get_prediction_pipeline_service()
        self.risk_state_service = risk_state_service or get_risk_state_service()
        self.alert_engine = alert_engine or get_alert_engine()

        self.weather_interval_seconds = max(10, weather_interval_seconds)
        self.prediction_interval_seconds = max(10, prediction_interval_seconds)

        # Concurrency guard
        self._cycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_running = False

        # Operational telemetry state
        self.last_cycle_start: datetime | None = None
        self.last_cycle_completed: datetime | None = None
        self.next_cycle_scheduled: datetime | None = None
        self.last_cycle_latency_ms: float = 0.0
        self.last_cycle_status: str = "initialized"  # "success", "failed", "skipped"
        self.cycles_completed_count: int = 0
        self.cycles_skipped_count: int = 0
        self.cycles_failed_count: int = 0

    @property
    def is_running(self) -> bool:
        """Check if background scheduling thread is currently active."""
        return self._is_running and (self._thread is not None and self._thread.is_alive())

    def run_single_cycle(
        self,
        db: Session,
        trigger_type: str = "scheduled",
    ) -> dict[str, Any]:
        """Execute one complete end-to-end operational intelligence cycle under concurrency lock."""
        # Non-blocking lock check to prevent concurrent overlapping executions
        acquired = self._cycle_lock.acquire(blocking=False)
        if not acquired:
            logger.warning(
                "prediction_cycle_skipped: a previous operational cycle is still running. "
                "Skipping current cycle invocation."
            )
            self.cycles_skipped_count += 1
            self.last_cycle_status = "skipped"
            return {
                "status": "skipped",
                "reason": "Previous prediction cycle is still active in another worker thread.",
            }

        start_time = time.perf_counter()
        cycle_start_dt = datetime.utcnow()
        self.last_cycle_start = cycle_start_dt
        logger.info(f"prediction_cycle_started: beginning cycle (trigger={trigger_type})")

        try:
            # 1. Live Weather Ingestion
            weather_result = self.weather_service.ingest_current_weather(db)

            # 2. Prediction Pipeline (Monitored grids -> Feature generation -> ML Inference -> Audit persistence)
            pipeline_result = self.pipeline_service.run_prediction_pipeline(
                db=db,
                weather_result=weather_result,
                trigger_type=trigger_type,
            )

            # 3. Risk State Update & Transition Detection
            transitions = self.risk_state_service.update_grid_risk_states(
                db=db,
                predictions=pipeline_result.predictions,
            )

            # 4. Alert Engine (Rule-based advisory dispatch & duplicate suppression)
            new_alerts = self.alert_engine.evaluate_transitions_and_generate_alerts(
                db=db,
                transitions=transitions,
            )

            # 5. V5 Prediction History & Temporal Delta Tracking
            try:
                from backend.services.risk_trend_service import get_risk_trend_service
                trend_service = get_risk_trend_service()
                for p in pipeline_result.predictions:
                    trend_service.record_prediction_and_detect_delta(
                        db=db,
                        prediction_item=p.to_dict(),
                        trigger_type=trigger_type,
                    )
            except Exception as trend_err:
                logger.warning(f"V5 risk trend tracking warning: {trend_err}")

            # 6. V5 Zone Prioritization Calculation
            try:
                from backend.services.priority_service import get_priority_service
                prio_service = get_priority_service()
                prio_service.calculate_priorities(db=db, horizon="nowcast", persist=True)
            except Exception as prio_err:
                logger.warning(f"V5 priority calculation warning: {prio_err}")

            # 7. V5 Operational Timeline Event Logging
            try:
                from backend.services.timeline_service import TimelineService
                TimelineService.record_event(
                    db=db,
                    event_type="prediction_cycle",
                    category="PREDICTION",
                    severity="INFO",
                    message=(
                        f"Operational cycle completed: {pipeline_result.total_grids} sectors analyzed, "
                        f"{len(transitions)} transitions, {len(new_alerts)} alerts dispatched. "
                        f"Engine: {pipeline_result.active_model} (fallback={pipeline_result.fallback_active})."
                    ),
                    metadata={
                        "total_grids": pipeline_result.total_grids,
                        "transitions": len(transitions),
                        "alerts": len(new_alerts),
                        "fallback": pipeline_result.fallback_active,
                        "trigger": trigger_type,
                    },
                )
                if pipeline_result.fallback_active:
                    TimelineService.record_event(
                        db=db,
                        event_type="model_fallback_activation",
                        category="SYSTEM",
                        severity="WARNING",
                        message="V2 deterministic multi-criteria fallback activated for operational prediction cycle.",
                        metadata={"active_model": pipeline_result.active_model},
                    )
                db.commit()
            except Exception as tl_err:
                logger.warning(f"V5 timeline logging warning: {tl_err}")

            # Update telemetry
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            self.last_cycle_completed = datetime.utcnow()
            self.last_cycle_latency_ms = latency_ms
            self.last_cycle_status = "success"
            self.cycles_completed_count += 1
            self.next_cycle_scheduled = self.last_cycle_completed + timedelta(
                seconds=self.prediction_interval_seconds
            )

            logger.info(
                f"prediction_cycle_completed: processed {pipeline_result.total_grids} sectors, "
                f"detected {len(transitions)} state changes, issued {len(new_alerts)} alerts "
                f"in {latency_ms:.2f} ms (fallback_active={pipeline_result.fallback_active})."
            )

            return {
                "status": "success",
                "trigger_type": trigger_type,
                "latency_ms": round(latency_ms, 2),
                "total_grids": pipeline_result.total_grids,
                "transitions_detected": len(transitions),
                "new_alerts_issued": len(new_alerts),
                "fallback_active": pipeline_result.fallback_active,
                "model_version": pipeline_result.model_version,
                "active_model": pipeline_result.active_model,
                "completed_at": self.last_cycle_completed.isoformat(),
            }

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            self.last_cycle_latency_ms = latency_ms
            self.last_cycle_status = "failed"
            self.cycles_failed_count += 1
            logger.error(
                f"prediction_cycle_failed: operational cycle encountered an error: {type(e).__name__}: {e}",
                exc_info=True,
            )
            return {
                "status": "failed",
                "error": f"{type(e).__name__}: {e}",
                "latency_ms": round(latency_ms, 2),
            }

        finally:
            self._cycle_lock.release()

    def start(self) -> bool:
        """Launch background scheduler worker thread."""
        if self._is_running:
            logger.info("Operational scheduler is already running.")
            return False

        self._stop_event.clear()
        self._is_running = True

        def worker():
            logger.info(
                f"GeoGuard Operational Scheduler initialized. Periodic cycle interval: "
                f"{self.prediction_interval_seconds}s."
            )
            time.sleep(2)  # Initial grace delay for server startup

            # Execute initial operational cycle
            try:
                with SessionLocal() as db:
                    self.run_single_cycle(db, trigger_type="scheduled")
            except Exception as ex:
                logger.warning(f"Initial operational cycle warning: {ex}")

            # Recurring loop
            while not self._stop_event.is_set():
                # Sleep in short increments to allow rapid shutdown response
                sleep_target = self.prediction_interval_seconds
                steps = max(1, int(sleep_target / 0.5))
                for _ in range(steps):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)

                if self._stop_event.is_set():
                    break

                try:
                    with SessionLocal() as db:
                        self.run_single_cycle(db, trigger_type="scheduled")
                except Exception as e:
                    logger.error(f"Scheduled operational cycle error: {e}", exc_info=True)

            logger.info("Operational scheduler worker thread stopped.")

        self._thread = threading.Thread(
            target=worker,
            daemon=True,
            name="GeoGuard-OperationalScheduler",
        )
        self._thread.start()
        return True

    def stop(self, timeout: float = 3.0) -> None:
        """Signal background worker thread to terminate cleanly."""
        if not self._is_running:
            return
        logger.info("Stopping operational scheduler worker...")
        self._stop_event.set()
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def get_operational_status(self, db: Session) -> dict[str, Any]:
        """Compute real, verified system status and operational telemetry from database."""
        # 1. Weather status from ingestion service
        weather_status = self.weather_service.last_sync_status
        last_weather_sync = (
            self.weather_service.last_sync_timestamp.isoformat()
            if self.weather_service.last_sync_timestamp
            else None
        )

        # 2. Prediction run times
        last_pred_run = (
            self.last_cycle_completed.isoformat() if self.last_cycle_completed else None
        )
        next_pred_run = (
            self.next_cycle_scheduled.isoformat() if self.next_cycle_scheduled else None
        )

        # 3. Model metadata
        ml_service = get_ml_prediction_service()
        model_ver = ml_service.model_version
        active_model = (
            "Deterministic Multi-Criteria (Baseline)"
            if not ml_service.is_available or self.pipeline_service.last_fallback_state
            else ml_service._metadata.get("algorithm", "Gradient Boosting")
        )
        fallback_active = not ml_service.is_available or self.pipeline_service.last_fallback_state

        # 4. Count active alerts from PostgreSQL
        active_alerts_count = db.query(Alert).filter(Alert.is_active == True).count()

        # 5. Count high risk grids from PostgreSQL
        high_risk_grids_count = self.risk_state_service.get_high_risk_grid_count(db)

        return {
            "weather_status": weather_status,
            "last_weather_sync": last_weather_sync,
            "last_prediction_run": last_pred_run,
            "next_prediction_run": next_pred_run,
            "model_version": model_ver,
            "active_model": active_model,
            "fallback_active": fallback_active,
            "active_alerts": active_alerts_count,
            "high_risk_grids": high_risk_grids_count,
            "prediction_latency_ms": round(self.last_cycle_latency_ms, 2),
            "scheduler_status": "running" if self.is_running else "stopped",
            "cycles_completed": self.cycles_completed_count,
            "cycles_skipped": self.cycles_skipped_count,
            "cycles_failed": self.cycles_failed_count,
        }


_singleton_scheduler: OperationalScheduler | None = None


def get_operational_scheduler() -> OperationalScheduler:
    """Retrieve singleton instance of OperationalScheduler."""
    global _singleton_scheduler
    if _singleton_scheduler is None:
        _singleton_scheduler = OperationalScheduler()
    return _singleton_scheduler
