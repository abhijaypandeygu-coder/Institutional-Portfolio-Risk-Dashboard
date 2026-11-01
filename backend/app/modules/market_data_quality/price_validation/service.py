"""
Module 03.02: Price Validation - Service Layer.
Coordinates:
- Structural, zero-price, movement/band, and reference-price validators
- Rule-engine evaluation with explicit priority and severity aggregation
- Downstream eligibility determination (REJECTED / QUARANTINED -> Not eligible)
- Idempotent anomaly creation and lifecycle management
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.price_validation.framework.math_utils import (
    to_decimal,
)
from backend.app.modules.market_data_quality.price_validation.incidents.repository import (
    PriceValidationRepository,
)
from backend.app.modules.market_data_quality.price_validation.integrations.m04_bridge import (
    InstrumentMetadata,
    InstrumentReferenceService,
    ReferencePriceSnapshot,
)
from backend.app.modules.market_data_quality.price_validation.models import (
    AnomalyIncidentStatus,
    EnforcementAction,
    PriceAnomalyIncident,
    PriceReferenceSnapshot as DBReferenceSnapshot,
    PriceValidationEvidence,
    PriceValidationResult,
    PriceValidationRule,
    RuleCategory,
    ValidationSeverity,
    ValidationStatus,
)
from backend.app.modules.market_data_quality.price_validation.movement.movement_validator import (
    PriceMovementValidator,
)
from backend.app.modules.market_data_quality.price_validation.reference.reference_comparator import (
    ReferencePriceComparator,
)
from backend.app.modules.market_data_quality.price_validation.schemas import (
    CrossSourceCompareRequest,
    CrossSourceCompareResponse,
    EvidenceItem,
    PriceObservationInput,
    PriceQualitySummary,
    ReferenceSnapshotCreate,
    RuleCreate,
    RuleUpdate,
    ValidationResultResponse,
)
from backend.app.modules.market_data_quality.price_validation.validators.structural_validator import (
    StructuralPriceValidator,
)
from backend.app.modules.market_data_quality.price_validation.validators.zero_validator import (
    ZeroPriceValidator,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PriceValidationService:
    def __init__(
        self,
        session: AsyncSession,
        reference_service: Optional[InstrumentReferenceService] = None,
    ):
        self.session = session
        self.repo = PriceValidationRepository(session)
        self.reference_service = reference_service or InstrumentReferenceService()
        self.structural_validator = StructuralPriceValidator(self.reference_service)
        self.zero_validator = ZeroPriceValidator()
        self.movement_validator = PriceMovementValidator(self.reference_service)
        self.reference_comparator = ReferencePriceComparator(self.reference_service)

    # =========================================================================
    # Observation Validation Pipeline
    # =========================================================================

    async def validate_observation(
        self, obs: PriceObservationInput, reference_price: Optional[Decimal] = None
    ) -> ValidationResultResponse:
        """
        Executes the shared 4-stage validation pipeline on a single market observation:
        1. Structural Validation (Null, Non-numeric, NaN/Inf, Negatives, Range, Tick Size, Precision, OHLC)
        2. Zero Price Validation (Field-specific, quote absence vs invalid trade)
        3. Extreme Movement & Price Band Validation (Percentage, absolute, exchange bands, corporate actions)
        4. Reference Price Comparison (Previous close, official reference, independent sources)
        """
        metadata = self.reference_service.get_instrument_metadata(obs.instrument_id)
        all_evidence: List[EvidenceItem] = []

        # Stage 1: Structural Validation
        parsed_price, struct_evidence = self.structural_validator.validate(obs, metadata)
        all_evidence.extend(struct_evidence)

        # Stage 2: Zero Price Validation (Only if price was parsed)
        if parsed_price is not None:
            zero_evidence = self.zero_validator.validate(obs, parsed_price)
            all_evidence.extend(zero_evidence)

        # Check if any structural or zero rejection occurred before evaluating movements
        has_fatal_structural_error = any(e.status == ValidationStatus.REJECTED for e in all_evidence)

        # If reference price was not explicitly passed, check reference service snapshot
        ref_snapshot = None
        if reference_price is None and parsed_price is not None:
            ref_snapshot = self.reference_service.get_reference_price(
                obs.instrument_id, "PREVIOUS_CLOSE"
            )
            if ref_snapshot:
                reference_price = ref_snapshot.reference_value

        # Stage 3: Extreme Price Movement & Exchange Bands
        if parsed_price is not None and not has_fatal_structural_error:
            movement_evidence = self.movement_validator.validate(
                obs=obs,
                parsed_price=parsed_price,
                reference_price=reference_price,
                metadata=metadata,
            )
            all_evidence.extend(movement_evidence)

        # Stage 4: Reference Price Comparison
        if parsed_price is not None and not has_fatal_structural_error:
            ref_evidence = self.reference_comparator.compare_with_reference(
                obs=obs,
                parsed_price=parsed_price,
                reference_snapshot=ref_snapshot,
            )
            all_evidence.extend(ref_evidence)

        # Aggregate Final Decision & Overall Severity
        overall_status = ValidationStatus.ACCEPTED
        overall_sev = ValidationSeverity.INFO
        failed_count = sum(1 for e in all_evidence if e.status == ValidationStatus.REJECTED)
        warning_count = sum(1 for e in all_evidence if e.status == ValidationStatus.ACCEPTED_WITH_WARNING)
        quarantine_count = sum(1 for e in all_evidence if e.status == ValidationStatus.QUARANTINED)

        if failed_count > 0:
            overall_status = ValidationStatus.REJECTED
            overall_sev = ValidationSeverity.CRITICAL
        elif quarantine_count > 0:
            overall_status = ValidationStatus.QUARANTINED
            overall_sev = ValidationSeverity.HIGH
        elif warning_count > 0:
            overall_status = ValidationStatus.ACCEPTED_WITH_WARNING
            overall_sev = ValidationSeverity.MEDIUM

        is_eligible = overall_status in (
            ValidationStatus.ACCEPTED,
            ValidationStatus.ACCEPTED_WITH_WARNING,
        )

        # Construct and persist PriceValidationResult
        db_result = PriceValidationResult(
            observation_id=obs.observation_id,
            instrument_id=obs.instrument_id,
            feed_id=obs.feed_id,
            provider_id=obs.provider_id,
            exchange=obs.exchange,
            observation_type=obs.observation_type,
            price_field=obs.price_field,
            original_price_value=str(obs.raw_price) if obs.raw_price is not None else None,
            parsed_price_value=parsed_price,
            validation_status=overall_status,
            overall_severity=overall_sev,
            failed_rule_count=failed_count,
            warning_count=warning_count,
            rule_version_summary={"engine_version": "M03.02-v1.0"},
            evidence_summary={
                "statuses": [e.status.value for e in all_evidence],
                "rule_codes": [e.rule_code for e in all_evidence],
            },
        )

        db_evidence_items = [
            PriceValidationEvidence(
                rule_code=e.rule_code,
                evidence_type=e.evidence_type,
                observed_value=e.observed_value,
                reference_value=e.reference_value,
                threshold_value=e.threshold_value,
                calculated_difference=e.calculated_difference,
                calculated_percentage=e.calculated_percentage,
                source_reference=e.source_reference,
                status=e.status,
                evidence_payload=e.evidence_payload,
            )
            for e in all_evidence
        ]

        saved_result = await self.repo.save_validation_result(db_result, db_evidence_items)

        # If quarantined or rejected with critical severity, log or upsert Anomaly Incident
        if overall_status in (ValidationStatus.REJECTED, ValidationStatus.QUARANTINED):
            anomaly_key = f"anomaly-{obs.feed_id}-{obs.instrument_id}-{obs.price_field}-{obs.observation_id[:8]}"
            incident = PriceAnomalyIncident(
                incident_key=anomaly_key,
                instrument_id=obs.instrument_id,
                feed_id=obs.feed_id,
                provider_id=obs.provider_id,
                exchange=obs.exchange,
                anomaly_type=all_evidence[0].rule_code if all_evidence else "UNKNOWN_ANOMALY",
                observed_price=parsed_price,
                reference_price=reference_price,
                severity=overall_sev,
                incident_status=AnomalyIncidentStatus.OPEN,
                evidence={
                    "evidence_items": [
                        {"rule": e.rule_code, "status": e.status.value, "payload": e.evidence_payload}
                        for e in all_evidence
                    ]
                },
            )
            await self.repo.upsert_anomaly_incident(incident)

        await self.session.commit()

        return ValidationResultResponse(
            id=saved_result.id,
            observation_id=saved_result.observation_id,
            instrument_id=saved_result.instrument_id,
            feed_id=saved_result.feed_id,
            provider_id=saved_result.provider_id,
            exchange=saved_result.exchange,
            observation_type=saved_result.observation_type,
            price_field=saved_result.price_field,
            original_price_value=saved_result.original_price_value,
            parsed_price_value=saved_result.parsed_price_value,
            validation_status=saved_result.validation_status,
            overall_severity=saved_result.overall_severity,
            failed_rule_count=saved_result.failed_rule_count,
            warning_count=saved_result.warning_count,
            is_downstream_eligible=is_eligible,
            rule_version_summary=saved_result.rule_version_summary,
            evidence_summary=saved_result.evidence_summary,
            validation_timestamp=saved_result.validation_timestamp,
            evidence_items=all_evidence,
        )

    async def validate_batch(
        self, observations: List[PriceObservationInput]
    ) -> List[ValidationResultResponse]:
        results = []
        for obs in observations:
            res = await self.validate_observation(obs)
            results.append(res)
        return results

    # =========================================================================
    # Rule Management Service
    # =========================================================================

    async def create_rule(self, payload: Union[RuleCreate, dict]) -> PriceValidationRule:
        if isinstance(payload, dict):
            payload = RuleCreate(**payload)
        rule = PriceValidationRule(
            rule_code=payload.rule_code,
            rule_name=payload.rule_name,
            rule_category=payload.rule_category,
            observation_type=payload.observation_type,
            price_field=payload.price_field,
            instrument_id=payload.instrument_id,
            exchange=payload.exchange,
            provider_id=payload.provider_id,
            currency=payload.currency,
            threshold_type=payload.threshold_type,
            threshold_value=payload.threshold_value,
            severity=payload.severity,
            enforcement_action=payload.enforcement_action,
            rule_parameters=payload.rule_parameters,
            priority=payload.priority,
            description=payload.description,
        )
        saved = await self.repo.create_rule(rule)
        await self.session.commit()
        return saved

    async def list_rules(self, enabled_only: bool = False) -> List[PriceValidationRule]:
        return await self.repo.list_rules(enabled_only=enabled_only)

    async def update_rule(self, rule_id: UUID, updates: Dict[str, Any]) -> PriceValidationRule:
        rule = await self.repo.update_rule(rule_id, updates)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        await self.session.commit()
        return rule

    async def disable_rule(self, rule_id: UUID) -> PriceValidationRule:
        return await self.update_rule(rule_id, {"enabled": False})

    # =========================================================================
    # Anomaly Incident Lifecycle
    # =========================================================================

    async def list_incidents(
        self,
        status: Optional[AnomalyIncidentStatus] = None,
        instrument_id: Optional[str] = None,
    ) -> List[PriceAnomalyIncident]:
        return await self.repo.list_incidents(status=status, instrument_id=instrument_id)

    async def resolve_incident(
        self, incident_id: UUID, req_status: AnomalyIncidentStatus, reason: str, user: str = "operator"
    ) -> PriceAnomalyIncident:
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
    # Cross-Source & Reference Snapshots
    # =========================================================================

    def compare_cross_sources(
        self, req: CrossSourceCompareRequest
    ) -> CrossSourceCompareResponse:
        return self.reference_comparator.compare_cross_sources(req)

    async def save_reference_snapshot(
        self, payload: ReferenceSnapshotCreate
    ) -> DBReferenceSnapshot:
        db_snap = DBReferenceSnapshot(
            instrument_id=payload.instrument_id,
            exchange=payload.exchange,
            reference_type=payload.reference_type,
            reference_value=payload.reference_value,
            currency=payload.currency,
            source_provider=payload.source_provider,
            effective_date=payload.effective_date or date.today(),
            adjustment_basis=payload.adjustment_basis,
            metadata_payload=payload.metadata_payload,
        )
        saved = await self.repo.save_reference_snapshot(db_snap)
        
        # Also register in in-memory reference bridge
        self.reference_service.set_reference_price(
            ReferencePriceSnapshot(
                instrument_id=payload.instrument_id,
                exchange=payload.exchange,
                reference_type=payload.reference_type,
                reference_value=payload.reference_value,
                currency=payload.currency,
                source_provider=payload.source_provider,
                effective_date=payload.effective_date or date.today(),
            )
        )
        await self.session.commit()
        return saved

    async def get_quality_summary(self) -> PriceQualitySummary:
        results = await self.repo.list_results(limit=1000)
        total = len(results)
        accepted = sum(1 for r in results if r.validation_status == ValidationStatus.ACCEPTED)
        warnings = sum(1 for r in results if r.validation_status == ValidationStatus.ACCEPTED_WITH_WARNING)
        rejected = sum(1 for r in results if r.validation_status == ValidationStatus.REJECTED)
        quarantined = sum(1 for r in results if r.validation_status == ValidationStatus.QUARANTINED)
        
        incidents = await self.repo.list_incidents(status=AnomalyIncidentStatus.OPEN)
        open_anomalies = len(incidents)
        
        eligible_rate = ((accepted + warnings) / total * 100.0) if total > 0 else 100.0

        return PriceQualitySummary(
            total_observations_validated=total,
            accepted_count=accepted,
            warning_count=warnings,
            rejected_count=rejected,
            quarantined_count=quarantined,
            open_anomalies_count=open_anomalies,
            eligibility_rate_percentage=round(eligible_rate, 2),
        )

