"""
Module 03.03: Timestamp Validation - Service Layer.
Coordinates:
- Foundation timestamp parsing, provenance, and UTC normalization
- Subfeature 1: Out-of-Order & sequence regression evaluation
- Subfeature 2: Clock divergence, offset, and drift rate evaluation
- Subfeature 3: Real-time, EOD, and historical staleness evaluation
- Subfeature 4: Exchange session alignment and trading holiday checks
- Incident creation and downstream eligibility reporting
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.timestamp_validation.clock.drift_detector import (
    ClockDriftDetector,
)
from backend.app.modules.market_data_quality.timestamp_validation.foundation.parser import (
    TimestampFoundation,
    TimestampPrecision,
)
from backend.app.modules.market_data_quality.timestamp_validation.freshness.stale_detector import (
    StaleTimestampDetector,
)
from backend.app.modules.market_data_quality.timestamp_validation.incidents.repository import (
    TimestampValidationRepository,
)
from backend.app.modules.market_data_quality.timestamp_validation.models import (
    ClockOffsetSample,
    ClockStatus,
    FinalTimestampStatus,
    FreshnessStatus,
    OrderingStatus,
    SessionStatus,
    TimestampAnomalyIncident,
    TimestampAnomalyStatus,
    TimestampRuleCategory,
    TimestampValidationEvidence,
    TimestampValidationResult,
    TimestampValidationRule,
)
from backend.app.modules.market_data_quality.timestamp_validation.ordering.ordering_detector import (
    OutOfOrderDetector,
)
from backend.app.modules.market_data_quality.timestamp_validation.schemas import (
    ClockStatusResponse,
    SessionCheckRequest,
    SessionCheckResponse,
    TimestampAnomalyIncidentResponse,
    TimestampEvidenceItem,
    TimestampObservationInput,
    TimestampQualitySummary,
    TimestampRuleCreate,
    TimestampRuleResponse,
    TimestampRuleUpdate,
    TimestampValidationResultResponse,
)
from backend.app.modules.market_data_quality.timestamp_validation.session.session_validator import (
    SessionAlignmentValidator,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampValidationService:
    def __init__(
        self,
        session: AsyncSession,
        ordering_detector: Optional[OutOfOrderDetector] = None,
        clock_detector: Optional[ClockDriftDetector] = None,
        stale_detector: Optional[StaleTimestampDetector] = None,
        session_validator: Optional[SessionAlignmentValidator] = None,
    ):
        self.session = session
        self.repo = TimestampValidationRepository(session)
        self.ordering_detector = ordering_detector or OutOfOrderDetector()
        self.clock_detector = clock_detector or ClockDriftDetector()
        self.stale_detector = stale_detector or StaleTimestampDetector()
        self.session_validator = session_validator or SessionAlignmentValidator()

    # =========================================================================
    # Observation Validation Pipeline
    # =========================================================================

    async def validate_observation(
        self, obs: TimestampObservationInput
    ) -> TimestampValidationResultResponse:
        """
        Executes the shared 4-stage timestamp validation pipeline:
        Stage 0: Provenance extraction & UTC normalization
        Stage 1: Out-of-Order & Sequence Evaluation
        Stage 2: Clock Drift & Offset Evaluation
        Stage 3: Stale Timestamp & Freshness Evaluation
        Stage 4: Session Alignment & Exchange Calendar Evaluation
        """
        now_utc = utc_now()
        local_rx = obs.local_receive_timestamp or now_utc
        evidence_items: List[TimestampEvidenceItem] = []

        # Stage 0: Timestamp Foundation (Parsing & Normalization)
        parsed_utc, precision, is_date_only = TimestampFoundation.parse_and_normalize(
            raw_val=obs.source_timestamp,
            exchange=obs.exchange,
        )

        if parsed_utc is None:
            # Fatal unparseable or absent timestamp
            evidence_items.append(
                TimestampEvidenceItem(
                    rule_code="TS_PARSE_FAILURE",
                    evidence_type="PARSER",
                    current_value=str(obs.source_timestamp),
                    status=FinalTimestampStatus.REJECTED,
                    evidence_payload={"reason": "Timestamp could not be parsed or normalized to UTC."},
                )
            )
            # Create rejection result
            db_res = TimestampValidationResult(
                observation_id=obs.observation_id,
                instrument_id=obs.instrument_id,
                feed_id=obs.feed_id,
                provider_id=obs.provider_id,
                exchange=obs.exchange,
                event_type=obs.event_type,
                source_timestamp=str(obs.source_timestamp),
                normalized_event_timestamp=now_utc,
                local_receive_timestamp=local_rx,
                processing_timestamp=now_utc,
                validation_timestamp=now_utc,
                ordering_status=OrderingStatus.UNKNOWN_ORDERING,
                clock_status=ClockStatus.INSUFFICIENT_CLOCK_EVIDENCE,
                freshness_status=FreshnessStatus.UNKNOWN,
                session_status=SessionStatus.UNKNOWN_SESSION,
                final_status=FinalTimestampStatus.REJECTED,
                is_downstream_eligible=False,
                rule_version_summary={"engine_version": "M03.03-v1.0"},
                evidence_summary={"error": "Malformed source timestamp"},
            )
            saved = await self.repo.save_validation_result(db_res, [])
            await self.session.commit()
            return self._build_response(saved, evidence_items)

        # Stage 1: Out-of-Order & Sequence Evaluation
        is_backfill = obs.processing_context.upper() in ("HISTORICAL", "BACKFILL")
        ord_res = self.ordering_detector.evaluate(
            provider_id=obs.provider_id,
            feed_id=obs.feed_id,
            instrument_id=obs.instrument_id,
            channel=obs.event_type,
            current_event_timestamp=parsed_utc,
            current_sequence=obs.sequence_number,
            receive_timestamp=local_rx,
            connection_epoch=obs.connection_epoch,
            is_historical_backfill=is_backfill,
        )
        evidence_items.append(
            TimestampEvidenceItem(
                rule_code="ORDERING_EVALUATION",
                evidence_type="ORDERING",
                current_value=parsed_utc.isoformat(),
                calculated_value=ord_res.delta_ms,
                status=ord_res.final_status,
                evidence_payload={
                    "ordering_status": ord_res.status.value,
                    "sequence_delta": ord_res.sequence_delta,
                    "reason": ord_res.reason,
                },
            )
        )

        # Stage 2: Clock Drift & Offset Evaluation (Evaluated on intraday/streaming events, NOT date-only EOD)
        if is_date_only or obs.processing_context.upper() in ("EOD", "HISTORICAL", "BACKFILL"):
            clk_status = ClockStatus.INSUFFICIENT_CLOCK_EVIDENCE
            clk_final = FinalTimestampStatus.VALID
            clk_reason = "Clock drift evaluation bypassed for date-only EOD / historical processing context."
            apparent_offset = 0.0
            est_offset = None
            drift_rate = None
            uncertainty = 0.0
        else:
            clk_res = self.clock_detector.evaluate(
                provider_id=obs.provider_id,
                feed_id=obs.feed_id,
                source_timestamp=parsed_utc,
                local_receive_timestamp=local_rx,
            )
            clk_status = clk_res.status
            clk_final = clk_res.final_status
            clk_reason = clk_res.reason
            apparent_offset = clk_res.apparent_offset_ms
            est_offset = clk_res.estimated_offset_ms
            drift_rate = clk_res.drift_rate_ms_per_min
            uncertainty = clk_res.uncertainty_ms

        evidence_items.append(
            TimestampEvidenceItem(
                rule_code="CLOCK_EVALUATION",
                evidence_type="CLOCK_DRIFT",
                current_value=parsed_utc.isoformat(),
                calculated_value=apparent_offset,
                status=clk_final,
                evidence_payload={
                    "clock_status": clk_status.value,
                    "estimated_offset_ms": est_offset,
                    "drift_rate_ms_per_min": drift_rate,
                    "uncertainty_ms": uncertainty,
                    "reason": clk_reason,
                },
            )
        )

        # Record clock sample telemetry asynchronously
        await self.repo.save_clock_sample(
            ClockOffsetSample(
                provider_id=obs.provider_id,
                feed_id=obs.feed_id,
                source_timestamp=parsed_utc,
                local_reference_timestamp=local_rx,
                apparent_offset_ms=apparent_offset,
                estimated_offset_ms=est_offset,
                uncertainty_ms=uncertainty,
            )
        )

        # Stage 3: Freshness & Staleness Evaluation
        fresh_res = self.stale_detector.evaluate(
            event_timestamp=parsed_utc,
            validation_time=now_utc,
            exchange=obs.exchange,
            processing_context=obs.processing_context,
            data_channel=obs.event_type,
            is_orderbook_synchronized=obs.is_orderbook_synchronized,
        )
        evidence_items.append(
            TimestampEvidenceItem(
                rule_code="FRESHNESS_EVALUATION",
                evidence_type="FRESHNESS",
                current_value=parsed_utc.isoformat(),
                calculated_value=fresh_res.age_seconds,
                threshold_value=fresh_res.critical_threshold_sec,
                status=fresh_res.final_status,
                evidence_payload={
                    "freshness_status": fresh_res.status.value,
                    "age_seconds": fresh_res.age_seconds,
                    "reason": fresh_res.reason,
                },
            )
        )

        # Stage 4: Session Alignment & Exchange Calendar Evaluation
        sess_res = self.session_validator.evaluate(
            event_timestamp=parsed_utc,
            exchange=obs.exchange,
            is_date_only=is_date_only,
            allow_extended_hours=obs.allow_extended_hours,
        )
        evidence_items.append(
            TimestampEvidenceItem(
                rule_code="SESSION_EVALUATION",
                evidence_type="SESSION_ALIGNMENT",
                current_value=parsed_utc.isoformat(),
                status=sess_res.final_status,
                evidence_payload={
                    "session_status": sess_res.status.value,
                    "session_name": sess_res.session_name,
                    "is_auction": sess_res.is_auction,
                    "trading_date": str(sess_res.trading_date),
                    "local_time": str(sess_res.local_time),
                    "reason": sess_res.reason,
                },
            )
        )

        # Final Aggregation & Downstream Eligibility
        statuses = [ord_res.final_status, clk_final, fresh_res.final_status, sess_res.final_status]
        final_status = FinalTimestampStatus.VALID
        if FinalTimestampStatus.REJECTED in statuses:
            final_status = FinalTimestampStatus.REJECTED
        elif FinalTimestampStatus.QUARANTINED in statuses:
            final_status = FinalTimestampStatus.QUARANTINED
        elif FinalTimestampStatus.VALID_WITH_WARNING in statuses:
            final_status = FinalTimestampStatus.VALID_WITH_WARNING

        is_eligible = final_status in (
            FinalTimestampStatus.VALID,
            FinalTimestampStatus.VALID_WITH_WARNING,
        )

        # Construct and persist database records
        db_res = TimestampValidationResult(
            observation_id=obs.observation_id,
            instrument_id=obs.instrument_id,
            feed_id=obs.feed_id,
            provider_id=obs.provider_id,
            exchange=obs.exchange,
            event_type=obs.event_type,
            source_timestamp=str(obs.source_timestamp),
            normalized_event_timestamp=parsed_utc,
            provider_receive_timestamp=None,
            local_receive_timestamp=local_rx,
            processing_timestamp=now_utc,
            validation_timestamp=now_utc,
            ordering_status=ord_res.status,
            clock_status=clk_status,
            freshness_status=fresh_res.status,
            session_status=sess_res.status,
            final_status=final_status,
            is_downstream_eligible=is_eligible,
            rule_version_summary={"engine_version": "M03.03-v1.0"},
            evidence_summary={
                "ordering": ord_res.status.value,
                "clock": clk_status.value,
                "freshness": fresh_res.status.value,
                "session": sess_res.status.value,
            },
        )

        db_evs = [
            TimestampValidationEvidence(
                rule_code=e.rule_code,
                evidence_type=e.evidence_type,
                previous_value=e.previous_value,
                current_value=e.current_value,
                calculated_value=e.calculated_value,
                threshold_value=e.threshold_value,
                source_reference=e.source_reference,
                status=e.status,
                evidence_payload=e.evidence_payload,
            )
            for e in evidence_items
        ]

        saved = await self.repo.save_validation_result(db_res, db_evs)

        # If rejected or quarantined, record anomaly incident
        if final_status in (FinalTimestampStatus.REJECTED, FinalTimestampStatus.QUARANTINED):
            anomaly_key = f"ts-anomaly-{obs.feed_id}-{obs.instrument_id}-{obs.event_type}-{obs.observation_id[:8]}"
            incident = TimestampAnomalyIncident(
                incident_key=anomaly_key,
                instrument_id=obs.instrument_id,
                feed_id=obs.feed_id,
                provider_id=obs.provider_id,
                exchange=obs.exchange,
                anomaly_type=ord_res.status.value if ord_res.final_status in (FinalTimestampStatus.REJECTED, FinalTimestampStatus.QUARANTINED) else fresh_res.status.value,
                event_timestamp=parsed_utc,
                local_receive_timestamp=local_rx,
                calculated_difference_ms=ord_res.delta_ms,
                severity="HIGH" if final_status == FinalTimestampStatus.QUARANTINED else "CRITICAL",
                incident_status=TimestampAnomalyStatus.OPEN,
                evidence={"evidence_items": [e.model_dump() for e in evidence_items]},
            )
            await self.repo.upsert_anomaly_incident(incident)

        await self.session.commit()
        return self._build_response(saved, evidence_items)

    async def validate_batch(
        self, observations: List[TimestampObservationInput]
    ) -> List[TimestampValidationResultResponse]:
        results = []
        for obs in observations:
            res = await self.validate_observation(obs)
            results.append(res)
        return results

    # =========================================================================
    # Rule Management Service
    # =========================================================================

    async def create_rule(
        self, payload: Union[TimestampRuleCreate, dict]
    ) -> TimestampValidationRule:
        if isinstance(payload, dict):
            payload = TimestampRuleCreate(**payload)
        rule = TimestampValidationRule(
            rule_code=payload.rule_code,
            rule_name=payload.rule_name,
            rule_category=payload.rule_category,
            provider_id=payload.provider_id,
            feed_id=payload.feed_id,
            instrument_id=payload.instrument_id,
            exchange=payload.exchange,
            event_type=payload.event_type,
            processing_context=payload.processing_context,
            rule_parameters=payload.rule_parameters,
            priority=payload.priority,
            description=payload.description,
        )
        saved = await self.repo.create_rule(rule)
        await self.session.commit()
        return saved

    async def list_rules(self, enabled_only: bool = False) -> List[TimestampValidationRule]:
        return await self.repo.list_rules(enabled_only=enabled_only)

    async def update_rule(
        self, rule_id: UUID, updates: Dict[str, Any]
    ) -> TimestampValidationRule:
        rule = await self.repo.update_rule(rule_id, updates)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        await self.session.commit()
        return rule

    async def disable_rule(self, rule_id: UUID) -> TimestampValidationRule:
        return await self.update_rule(rule_id, {"enabled": False})

    # =========================================================================
    # Anomaly Incident Lifecycle
    # =========================================================================

    async def list_incidents(
        self,
        status: Optional[TimestampAnomalyStatus] = None,
        instrument_id: Optional[str] = None,
    ) -> List[TimestampAnomalyIncident]:
        return await self.repo.list_incidents(status=status, instrument_id=instrument_id)

    async def resolve_incident(
        self,
        incident_id: UUID,
        req_status: TimestampAnomalyStatus,
        reason: str,
        user: str = "operator",
    ) -> TimestampAnomalyIncident:
        incident = await self.repo.get_incident_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
        incident.incident_status = req_status
        incident.resolved_at = utc_now()
        incident.resolved_by = user
        incident.resolution_reason = reason
        await self.session.commit()
        return incident

    # =========================================================================
    # Session Check & Telemetry Inquiries
    # =========================================================================

    def check_session(self, req: SessionCheckRequest) -> SessionCheckResponse:
        res = self.session_validator.evaluate(
            event_timestamp=req.timestamp,
            exchange=req.exchange,
            allow_extended_hours=req.allow_extended_hours,
        )
        is_valid = res.final_status in (
            FinalTimestampStatus.VALID,
            FinalTimestampStatus.VALID_WITH_WARNING,
        )
        return SessionCheckResponse(
            exchange=req.exchange,
            normalized_utc_timestamp=req.timestamp,
            exchange_local_time=str(res.local_time),
            trading_date=res.trading_date,
            session_status=res.status,
            is_auction=res.is_auction,
            session_name=res.session_name,
            is_valid=is_valid,
            reason=res.reason,
        )

    async def get_quality_summary(self) -> TimestampQualitySummary:
        results = await self.repo.list_results(limit=1000)
        total = len(results)
        valid_cnt = sum(1 for r in results if r.final_status == FinalTimestampStatus.VALID)
        warn_cnt = sum(1 for r in results if r.final_status == FinalTimestampStatus.VALID_WITH_WARNING)
        rej_cnt = sum(1 for r in results if r.final_status == FinalTimestampStatus.REJECTED)
        quar_cnt = sum(1 for r in results if r.final_status == FinalTimestampStatus.QUARANTINED)

        ord_anom = sum(1 for r in results if r.ordering_status not in (OrderingStatus.IN_ORDER, OrderingStatus.UNKNOWN_ORDERING))
        clk_anom = sum(1 for r in results if r.clock_status not in (ClockStatus.CLOCK_NORMAL, ClockStatus.INSUFFICIENT_CLOCK_EVIDENCE))
        stale_cnt = sum(1 for r in results if r.freshness_status in (FreshnessStatus.STALE, FreshnessStatus.CRITICALLY_STALE))
        sess_mis = sum(1 for r in results if r.session_status in (SessionStatus.OUT_OF_SESSION, SessionStatus.MARKET_CLOSED))

        open_inc = len(await self.repo.list_incidents(status=TimestampAnomalyStatus.OPEN))
        rate = ((valid_cnt + warn_cnt) / total * 100.0) if total > 0 else 100.0

        return TimestampQualitySummary(
            total_observations_validated=total,
            valid_count=valid_cnt,
            warning_count=warn_cnt,
            rejected_count=rej_cnt,
            quarantined_count=quar_cnt,
            ordering_anomalies_count=ord_anom,
            clock_anomalies_count=clk_anom,
            stale_observations_count=stale_cnt,
            session_misalignments_count=sess_mis,
            open_incidents_count=open_inc,
            downstream_eligibility_rate_percentage=round(rate, 2),
        )

    def _build_response(
        self, db_res: TimestampValidationResult, evidence_items: List[TimestampEvidenceItem]
    ) -> TimestampValidationResultResponse:
        return TimestampValidationResultResponse(
            id=db_res.id,
            observation_id=db_res.observation_id,
            instrument_id=db_res.instrument_id,
            feed_id=db_res.feed_id,
            provider_id=db_res.provider_id,
            exchange=db_res.exchange,
            event_type=db_res.event_type,
            source_timestamp=db_res.source_timestamp,
            normalized_event_timestamp=db_res.normalized_event_timestamp,
            provider_receive_timestamp=db_res.provider_receive_timestamp,
            local_receive_timestamp=db_res.local_receive_timestamp,
            processing_timestamp=db_res.processing_timestamp,
            validation_timestamp=db_res.validation_timestamp,
            ordering_status=db_res.ordering_status,
            clock_status=db_res.clock_status,
            freshness_status=db_res.freshness_status,
            session_status=db_res.session_status,
            final_status=db_res.final_status,
            is_downstream_eligible=db_res.is_downstream_eligible,
            rule_version_summary=db_res.rule_version_summary,
            evidence_summary=db_res.evidence_summary,
            evidence_items=evidence_items,
        )
