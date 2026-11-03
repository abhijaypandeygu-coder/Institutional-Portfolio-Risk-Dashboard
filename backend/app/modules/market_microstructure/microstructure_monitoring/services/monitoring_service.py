"""
Microstructure Monitoring Service (M09.09).
Orchestrates spread volatility monitoring, depth fluctuation & depletion,
message/book update intensity, feed freshness, and anomaly lifecycle management.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.monitoring_models import (
    MicrostructureMonitoringConfig,
    MicrostructureSpreadMonitoring,
    MicrostructureDepthMonitoring,
    MicrostructureDepthEvent,
    MicrostructureUpdateIntensity,
    MicrostructureFeedFreshness,
    MicrostructureAnomalyEvent,
    MicrostructureAnomalyEvidence,
    MicrostructureAnomalyTransition
)
from ..schemas.monitoring_schemas import (
    MonitoringConfigCreate,
    MonitoringConfigResponse,
    SpreadMonitoringRequest,
    SpreadMonitoringResponse,
    DepthMonitoringRequest,
    DepthMonitoringResponse,
    DepthEventInput,
    UpdateIntensityRequest,
    UpdateIntensityResponse,
    FeedFreshnessRequest,
    FeedFreshnessResponse,
    AnomalyEventResponse,
    AnomalyAcknowledgeRequest,
    AnomalyResolveRequest,
    CurrentMonitoringOverviewResponse
)
from ..repositories.monitoring_repository import MicrostructureMonitoringRepository
from ..calculations.monitoring_math import (
    to_decimal,
    compute_spread_changes,
    compute_spread_series_metrics,
    compute_robust_z_score,
    classify_spread_deterioration,
    compute_depth_fluctuations,
    compute_replenishment_metrics,
    compute_update_intensity,
    compute_staleness_metrics
)


class MicrostructureMonitoringService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MicrostructureMonitoringRepository(db)

    async def create_monitoring_config(self, req: MonitoringConfigCreate) -> MonitoringConfigResponse:
        cfg_dict = req.model_dump()
        cfg_dict["id"] = f"cfg_{uuid.uuid4().hex[:12]}"
        cfg_model = await self.repo.get_or_create_config(cfg_dict)
        return MonitoringConfigResponse.model_validate(cfg_model)

    async def monitor_spread(self, req: SpreadMonitoringRequest) -> SpreadMonitoringResponse:
        """
        Processes spread observations, computes short-horizon rolling metrics and widening flags.
        """
        sorted_obs = sorted(req.observations, key=lambda x: x.timestamp)
        spread_vals = [obs.absolute_spread for obs in sorted_obs]
        ts_vals = [obs.timestamp for obs in sorted_obs]

        # Rolling series metrics
        series_metrics = compute_spread_series_metrics(spread_vals, ts_vals)
        latest_obs = sorted_obs[-1]
        prev_spread = sorted_obs[-2].absolute_spread if len(sorted_obs) >= 2 else None

        # Change metrics
        changes = compute_spread_changes(
            current_spread=latest_obs.absolute_spread,
            previous_spread=prev_spread,
            current_midpoint=latest_obs.midpoint
        )

        # Baseline & robust z-score comparison
        baseline_spread = req.historical_baseline_spread or series_metrics["mean"] or latest_obs.absolute_spread
        _, _, z_rob = compute_robust_z_score(latest_obs.absolute_spread, spread_vals)

        category, severity = classify_spread_deterioration(
            current_spread=latest_obs.absolute_spread,
            baseline_spread=baseline_spread,
            z_robust=z_rob,
            bps_change=changes.get("change_bps")
        )

        is_widening = category in ["MILD_WIDENING", "SIGNIFICANT_WIDENING", "EXTREME_WIDENING"]

        rec_id = f"sprm_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)

        record = MicrostructureSpreadMonitoring(
            id=rec_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            source_feed_id=req.source_feed_id,
            observation_timestamp=latest_obs.timestamp,
            calculation_timestamp=now_utc,
            absolute_spread=latest_obs.absolute_spread,
            relative_spread=changes["relative_change_pct"],
            spread_bps=changes["spread_bps"],
            spread_change=changes["absolute_change"],
            spread_change_percentage=changes["relative_change_pct"],
            rolling_mean_spread=series_metrics["mean"],
            rolling_stddev_spread=series_metrics["stddev"],
            spread_cv=series_metrics["cv"],
            spread_range=series_metrics["spread_range"],
            time_weighted_spread=series_metrics["time_weighted_mean"],
            historical_percentile=None,
            valid_observation_count=len(sorted_obs),
            coverage_ratio=Decimal("1.0"),
            quality_status=latest_obs.quality_status,
            config_id=None,
            config_version=req.config_version,
            calculation_version="1.0.0"
        )
        await self.repo.save_spread_monitoring(record)

        # If widening detected, register anomaly event
        if is_widening:
            anomaly_id = f"anom_{uuid.uuid4().hex[:12]}"
            anomaly = MicrostructureAnomalyEvent(
                id=anomaly_id,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
                venue_id=req.venue_id,
                source_feed_id=req.source_feed_id,
                anomaly_category=category,
                anomaly_description=f"Spread widening detected: current {latest_obs.absolute_spread} vs baseline {baseline_spread}",
                severity=severity,
                detected_metric="ABSOLUTE_SPREAD",
                observed_value=latest_obs.absolute_spread,
                baseline_value=baseline_spread,
                threshold_value=baseline_spread * Decimal("1.4"),
                deviation_magnitude=latest_obs.absolute_spread - baseline_spread,
                event_start_timestamp=latest_obs.timestamp,
                detection_timestamp=now_utc,
                last_observed_timestamp=latest_obs.timestamp,
                affected_side="BOTH",
                affected_level_count=1,
                detection_method="DETERMINISTIC_RULE",
                lifecycle_status="ACTIVE",
                quality_status="VALID"
            )
            await self.repo.save_anomaly_event(anomaly)

        return SpreadMonitoringResponse(
            id=rec_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            source_feed_id=req.source_feed_id,
            observation_timestamp=latest_obs.timestamp,
            calculation_timestamp=now_utc,
            absolute_spread=latest_obs.absolute_spread,
            relative_spread=changes["relative_change_pct"],
            spread_bps=changes["spread_bps"],
            spread_change=changes["absolute_change"],
            spread_change_percentage=changes["relative_change_pct"],
            rolling_mean_spread=series_metrics["mean"],
            rolling_stddev_spread=series_metrics["stddev"],
            spread_cv=series_metrics["cv"],
            spread_range=series_metrics["spread_range"],
            time_weighted_spread=series_metrics["time_weighted_mean"],
            historical_percentile=None,
            valid_observation_count=len(sorted_obs),
            coverage_ratio=Decimal("1.0"),
            quality_status=latest_obs.quality_status,
            spread_widening_flag=is_widening,
            deterioration_severity=severity
        )

    async def monitor_depth(self, req: DepthMonitoringRequest) -> DepthMonitoringResponse:
        """
        Monitors displayed depth fluctuations, depletion velocity, and replenishment recovery.
        """
        sorted_obs = sorted(req.observations, key=lambda x: x.timestamp)
        latest_obs = sorted_obs[-1]
        prev_obs = sorted_obs[-2] if len(sorted_obs) >= 2 else None

        elapsed_secs = None
        if prev_obs:
            elapsed_secs = Decimal(str(max(0.001, (latest_obs.timestamp - prev_obs.timestamp).total_seconds())))

        prev_depth = prev_obs.displayed_depth if prev_obs else None
        flucts = compute_depth_fluctuations(
            current_depth=latest_obs.displayed_depth,
            previous_depth=prev_depth,
            elapsed_seconds=elapsed_secs
        )

        # Baseline & replenishment
        baseline = latest_obs.baseline_depth or (prev_obs.displayed_depth if prev_obs else latest_obs.displayed_depth)
        replenishment_metrics = compute_replenishment_metrics(
            baseline_depth=baseline,
            post_depletion_depth=latest_obs.displayed_depth if flucts["classification"] == "DEPTH_REDUCTION" else (prev_obs.displayed_depth if prev_obs else latest_obs.displayed_depth),
            current_depth=latest_obs.displayed_depth
        )

        rec_id = f"dptm_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)

        record = MicrostructureDepthMonitoring(
            id=rec_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            event_timestamp=latest_obs.timestamp,
            calculation_timestamp=now_utc,
            side=latest_obs.side,
            depth_measure="TOP_5_CUMULATIVE",
            depth_level_count=latest_obs.level_count,
            baseline_depth=baseline,
            current_depth=latest_obs.displayed_depth,
            absolute_depth_change=flucts["absolute_change"],
            relative_depth_change=flucts["relative_change_pct"],
            depletion_amount=flucts["depletion_amount"],
            depletion_rate=flucts["depletion_rate"],
            replenishment_amount=replenishment_metrics["replenishment_amount"],
            recovery_ratio=replenishment_metrics["recovery_ratio"],
            quality_status=latest_obs.quality_status,
            config_id=None,
            config_version=req.config_version
        )
        await self.repo.save_depth_monitoring(record)

        # Severe depth withdrawal check (> 40% reduction)
        if flucts["relative_change_pct"] and flucts["relative_change_pct"] <= Decimal("-40.0"):
            anomaly_id = f"anom_{uuid.uuid4().hex[:12]}"
            anomaly = MicrostructureAnomalyEvent(
                id=anomaly_id,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
                venue_id=req.venue_id,
                source_feed_id=req.source_feed_id,
                anomaly_category=f"{latest_obs.side}_DEPTH_WITHDRAWAL",
                anomaly_description=f"Rapid {latest_obs.side} depth depletion: {flucts['relative_change_pct']}% reduction",
                severity="HIGH" if flucts["relative_change_pct"] <= Decimal("-60.0") else "MEDIUM",
                detected_metric="CUMULATIVE_DEPTH",
                observed_value=latest_obs.displayed_depth,
                baseline_value=baseline,
                threshold_value=baseline * Decimal("0.60"),
                deviation_magnitude=flucts["depletion_amount"],
                event_start_timestamp=latest_obs.timestamp,
                detection_timestamp=now_utc,
                last_observed_timestamp=latest_obs.timestamp,
                affected_side=latest_obs.side,
                affected_level_count=latest_obs.level_count,
                detection_method="DETERMINISTIC_RULE",
                lifecycle_status="ACTIVE",
                quality_status="VALID"
            )
            await self.repo.save_anomaly_event(anomaly)

        return DepthMonitoringResponse(
            id=rec_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            side=latest_obs.side,
            event_timestamp=latest_obs.timestamp,
            calculation_timestamp=now_utc,
            current_depth=latest_obs.displayed_depth,
            baseline_depth=baseline,
            absolute_depth_change=flucts["absolute_change"],
            relative_depth_change=flucts["relative_change_pct"],
            depletion_amount=flucts["depletion_amount"],
            depletion_rate=flucts["depletion_rate"],
            replenishment_amount=replenishment_metrics["replenishment_amount"],
            recovery_ratio=replenishment_metrics["recovery_ratio"],
            classification=flucts["classification"],
            quality_status=latest_obs.quality_status
        )

    async def record_depth_event(
        self,
        instrument_id: str,
        listing_id: str,
        venue_id: str,
        source_feed_id: str,
        event: DepthEventInput
    ) -> MicrostructureDepthEvent:
        """
        Records explicit source depth event (ADD, MODIFY, CANCEL, EXECUTION).
        """
        rec_id = f"dpte_{uuid.uuid4().hex[:12]}"
        model = MicrostructureDepthEvent(
            id=rec_id,
            instrument_id=instrument_id,
            listing_id=listing_id,
            venue_id=venue_id,
            source_feed_id=source_feed_id,
            event_timestamp=event.event_timestamp,
            receive_timestamp=event.receive_timestamp,
            sequence_number=event.sequence_number,
            event_type=event.event_type,
            side=event.side,
            price=event.price,
            quantity_change=event.quantity_change,
            notional_change=event.notional_change,
            order_reference=event.order_reference,
            classification_source=event.classification_source,
            classification_status=event.classification_status,
            quality_status="VALID"
        )
        return await self.repo.save_depth_event(model)

    async def monitor_update_intensity(self, req: UpdateIntensityRequest) -> UpdateIntensityResponse:
        """
        Measures message rate and book-change rate over an interval.
        Detects message bursts.
        """
        elapsed_secs = Decimal(str(max(0.1, (req.interval_end - req.interval_start).total_seconds())))
        rates = compute_update_intensity(
            total_messages=req.total_message_count,
            valid_messages=req.valid_message_count,
            book_updates=req.book_update_count,
            elapsed_seconds=elapsed_secs,
            baseline_rate=req.baseline_message_rate
        )

        burst_detected = False
        burst_sev = "INFO"
        if rates["intensity_ratio"]:
            if rates["intensity_ratio"] >= Decimal("3.0"):
                burst_detected = True
                burst_sev = "HIGH"
            elif rates["intensity_ratio"] >= Decimal("2.0"):
                burst_detected = True
                burst_sev = "MEDIUM"

        rec_id = f"updi_{uuid.uuid4().hex[:12]}"
        record = MicrostructureUpdateIntensity(
            id=rec_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            source_feed_id=req.source_feed_id,
            interval_start=req.interval_start,
            interval_end=req.interval_end,
            source_mode=req.source_mode,
            total_message_count=req.total_message_count,
            valid_message_count=req.valid_message_count,
            unique_event_count=req.unique_event_count,
            book_update_count=req.book_update_count,
            trade_message_count=req.trade_message_count,
            add_event_count=req.add_event_count,
            modify_event_count=req.modify_event_count,
            cancel_event_count=req.cancel_event_count,
            snapshot_count=req.snapshot_count,
            heartbeat_count=req.heartbeat_count,
            duplicate_message_count=req.duplicate_message_count,
            invalid_message_count=req.invalid_message_count,
            message_rate=rates["message_rate"],
            book_change_rate=rates["book_change_rate"],
            baseline_message_rate=req.baseline_message_rate,
            intensity_ratio=rates["intensity_ratio"],
            quality_status="VALID",
            calculation_version="1.0.0"
        )
        await self.repo.save_update_intensity(record)

        if burst_detected:
            anomaly_id = f"anom_{uuid.uuid4().hex[:12]}"
            anomaly = MicrostructureAnomalyEvent(
                id=anomaly_id,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
                venue_id=req.venue_id,
                source_feed_id=req.source_feed_id,
                anomaly_category="UPDATE_BURST",
                anomaly_description=f"Message burst detected: {rates['message_rate']} msgs/sec ({rates['intensity_ratio']}x baseline)",
                severity=burst_sev,
                detected_metric="MESSAGE_RATE",
                observed_value=rates["message_rate"],
                baseline_value=req.baseline_message_rate,
                threshold_value=(req.baseline_message_rate * Decimal("2.0")) if req.baseline_message_rate else None,
                deviation_magnitude=(rates["message_rate"] - req.baseline_message_rate) if req.baseline_message_rate else None,
                event_start_timestamp=req.interval_start,
                detection_timestamp=datetime.now(timezone.utc),
                last_observed_timestamp=req.interval_end,
                affected_side="BOTH",
                affected_level_count=None,
                detection_method="DETERMINISTIC_RULE",
                lifecycle_status="ACTIVE",
                quality_status="VALID"
            )
            await self.repo.save_anomaly_event(anomaly)

        return UpdateIntensityResponse(
            id=rec_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            source_feed_id=req.source_feed_id,
            interval_start=req.interval_start,
            interval_end=req.interval_end,
            source_mode=req.source_mode,
            total_message_count=req.total_message_count,
            valid_message_count=req.valid_message_count,
            book_update_count=req.book_update_count,
            message_rate=rates["message_rate"],
            book_change_rate=rates["book_change_rate"],
            intensity_ratio=rates["intensity_ratio"],
            burst_detected=burst_detected,
            burst_severity=burst_sev,
            quality_status="VALID"
        )

    async def monitor_feed_freshness(self, req: FeedFreshnessRequest) -> FeedFreshnessResponse:
        """
        Monitors observation age, receive latency, and feed staleness.
        """
        st_metrics = compute_staleness_metrics(
            current_time=req.monitoring_timestamp,
            source_timestamp=req.last_source_event_timestamp,
            receive_timestamp=req.last_receive_timestamp,
            expected_cadence_ms=req.expected_update_cadence_ms
        )

        rec_id = f"frsh_{uuid.uuid4().hex[:12]}"
        record = MicrostructureFeedFreshness(
            id=rec_id,
            source_feed_id=req.source_feed_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            monitoring_timestamp=req.monitoring_timestamp,
            last_source_event_timestamp=req.last_source_event_timestamp,
            last_receive_timestamp=req.last_receive_timestamp,
            last_valid_book_timestamp=req.last_valid_book_timestamp,
            observation_age_ms=st_metrics["observation_age_ms"],
            receive_latency_ms=st_metrics["receive_latency_ms"],
            expected_update_cadence_ms=st_metrics["expected_update_cadence_ms"],
            feed_status=st_metrics["staleness_state"],
            book_status="ACTIVE" if st_metrics["staleness_state"] == "FRESH" else "STALE",
            sequence_status="IN_SEQUENCE",
            recovery_status="NORMAL",
            quality_status="VALID",
            calculation_version="1.0.0"
        )
        await self.repo.save_feed_freshness(record)

        if st_metrics["staleness_state"] in ["STALE", "FEED_UNAVAILABLE"]:
            anomaly_id = f"anom_{uuid.uuid4().hex[:12]}"
            anomaly = MicrostructureAnomalyEvent(
                id=anomaly_id,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
                venue_id=req.venue_id,
                source_feed_id=req.source_feed_id,
                anomaly_category="FEED_STALENESS",
                anomaly_description=f"Feed staleness detected: age {st_metrics['observation_age_ms']}ms > cadence {req.expected_update_cadence_ms}ms",
                severity="HIGH" if st_metrics["staleness_state"] == "FEED_UNAVAILABLE" else "MEDIUM",
                detected_metric="OBSERVATION_AGE_MS",
                observed_value=Decimal(str(st_metrics["observation_age_ms"])),
                baseline_value=Decimal(str(req.expected_update_cadence_ms)),
                threshold_value=Decimal(str(req.expected_update_cadence_ms * 3)),
                deviation_magnitude=Decimal(str(st_metrics["observation_age_ms"] - req.expected_update_cadence_ms)),
                event_start_timestamp=req.last_source_event_timestamp,
                detection_timestamp=datetime.now(timezone.utc),
                last_observed_timestamp=req.monitoring_timestamp,
                affected_side="BOTH",
                affected_level_count=None,
                detection_method="DETERMINISTIC_RULE",
                lifecycle_status="ACTIVE",
                quality_status="VALID"
            )
            await self.repo.save_anomaly_event(anomaly)

        return FeedFreshnessResponse(
            id=rec_id,
            source_feed_id=req.source_feed_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            monitoring_timestamp=req.monitoring_timestamp,
            observation_age_ms=st_metrics["observation_age_ms"],
            receive_latency_ms=st_metrics["receive_latency_ms"],
            expected_update_cadence_ms=st_metrics["expected_update_cadence_ms"],
            feed_status=st_metrics["staleness_state"],
            book_status=record.book_status,
            sequence_status=record.sequence_status,
            recovery_status=record.recovery_status,
            quality_status=record.quality_status
        )

    async def acknowledge_anomaly(self, anomaly_id: str, req: AnomalyAcknowledgeRequest) -> AnomalyEventResponse:
        anomaly = await self.repo.get_anomaly_by_id(anomaly_id)
        if not anomaly:
            raise ValueError(f"Anomaly {anomaly_id} not found")

        prev_status = anomaly.lifecycle_status
        anomaly.lifecycle_status = "ACKNOWLEDGED"

        trans_id = f"trns_{uuid.uuid4().hex[:12]}"
        transition = MicrostructureAnomalyTransition(
            id=trans_id,
            anomaly_event_id=anomaly.id,
            previous_status=prev_status,
            new_status="ACKNOWLEDGED",
            transition_reason="User acknowledged",
            actor_id=req.actor_id,
            notes=req.notes
        )
        await self.repo.save_anomaly_transition(transition)
        return AnomalyEventResponse.model_validate(anomaly)

    async def resolve_anomaly(self, anomaly_id: str, req: AnomalyResolveRequest) -> AnomalyEventResponse:
        anomaly = await self.repo.get_anomaly_by_id(anomaly_id)
        if not anomaly:
            raise ValueError(f"Anomaly {anomaly_id} not found")

        prev_status = anomaly.lifecycle_status
        anomaly.lifecycle_status = "RESOLVED"
        anomaly.event_end_timestamp = datetime.now(timezone.utc)

        trans_id = f"trns_{uuid.uuid4().hex[:12]}"
        transition = MicrostructureAnomalyTransition(
            id=trans_id,
            anomaly_event_id=anomaly.id,
            previous_status=prev_status,
            new_status="RESOLVED",
            transition_reason=req.resolution_reason,
            actor_id=req.actor_id,
            notes=req.notes
        )
        await self.repo.save_anomaly_transition(transition)
        return AnomalyEventResponse.model_validate(anomaly)

    async def get_current_overview(self, instrument_id: str) -> CurrentMonitoringOverviewResponse:
        """
        Retrieves top-level monitoring overview across spread, depth, update rate, and active anomalies.
        """
        spreads = await self.repo.get_spread_history(instrument_id, limit=1)
        depths = await self.repo.get_depth_history(instrument_id, limit=2)
        intensity = await self.repo.get_latest_intensity(instrument_id)
        freshness = await self.repo.get_latest_feed_freshness(instrument_id)
        active_anomalies = await self.repo.get_anomalies(instrument_id=instrument_id, lifecycle_status="ACTIVE")

        latest_spread = spreads[0].absolute_spread if spreads else None
        spread_bps = spreads[0].spread_bps if spreads else None
        spread_cv = spreads[0].spread_cv if spreads else None

        bid_depth = None
        ask_depth = None
        for d in depths:
            if d.side == "BID":
                bid_depth = d.current_depth
            elif d.side == "ASK":
                ask_depth = d.current_depth

        severities = [a.severity for a in active_anomalies]
        highest_sev = "INFO"
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            if sev in severities:
                highest_sev = sev
                break

        return CurrentMonitoringOverviewResponse(
            instrument_id=instrument_id,
            listing_id=spreads[0].listing_id if spreads else "EQ_DEF",
            venue_id=spreads[0].venue_id if spreads else "NSE",
            source_feed_id=spreads[0].source_feed_id if spreads else "FEED_DEFAULT",
            latest_spread=latest_spread,
            spread_bps=spread_bps,
            spread_volatility_cv=spread_cv,
            latest_bid_depth=bid_depth,
            latest_ask_depth=ask_depth,
            depth_depletion_indicator=any(d.depletion_amount > Decimal("0") for d in depths),
            latest_message_rate=intensity.message_rate if intensity else None,
            book_change_rate=intensity.book_change_rate if intensity else None,
            feed_freshness_status=freshness.feed_status if freshness else "FRESH",
            active_anomaly_count=len(active_anomalies),
            highest_active_severity=highest_sev,
            quality_status="VALID"
        )
