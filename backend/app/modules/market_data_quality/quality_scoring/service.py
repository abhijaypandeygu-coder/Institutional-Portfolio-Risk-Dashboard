"""
M03.07 - Quality Scoring Orchestration Service.
Orchestrates:
1. Operational feed reliability scoring.
2. Dataset and field-level completeness scoring.
3. Cadence-aware piecewise freshness scoring.
4. Composite quality snapshot synthesis.
5. Calculation-specific use eligibility evaluation with mandatory hard gates.
"""

import uuid
import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.quality_scoring.schemas import (
    FeedReliabilityInput,
    FeedReliabilityResponse,
    CompletenessEvaluationInput,
    CompletenessScoreResponse,
    FreshnessEvaluationInput,
    FreshnessScoreResponse,
    CompositeQualityRequest,
    CompositeQualitySnapshotResponse,
    EligibilityEvaluationRequest,
    UseEligibilityDecisionResponse,
)
from backend.app.modules.market_data_quality.quality_scoring.reliability.calculator import (
    ReliabilityCalculator,
)
from backend.app.modules.market_data_quality.quality_scoring.completeness.calculator import (
    CompletenessCalculator,
)
from backend.app.modules.market_data_quality.quality_scoring.freshness.calculator import (
    FreshnessCalculator,
)
from backend.app.modules.market_data_quality.quality_scoring.eligibility.evaluator import (
    EligibilityEvaluator,
)
from backend.app.modules.market_data_quality.quality_scoring.repository.repository import (
    QualityScoringRepository,
    utc_now,
)

logger = logging.getLogger(__name__)


class QualityScoringService:
    """
    Main orchestration service for M03.07 Quality Scoring.
    """

    @classmethod
    async def evaluate_reliability(
        cls, session: AsyncSession, inp: FeedReliabilityInput
    ) -> FeedReliabilityResponse:
        score_id = f"SCR_REL_{uuid.uuid4().hex[:12].upper()}"
        avail_s, time_s, err_s, rel_s, classif, meta = ReliabilityCalculator.calculate_reliability(inp)

        record = {
            "score_id": score_id,
            "provider_id": inp.provider_id,
            "feed_id": inp.feed_id,
            "instrument_id": inp.instrument_id,
            "data_type": inp.data_type,
            "availability_score": avail_s,
            "timeliness_score": time_s,
            "error_score": err_s,
            "reliability_score": rel_s,
            "reliability_classification": classif,
            "expected_duration_seconds": inp.expected_duration_seconds,
            "unavailable_duration_seconds": inp.unavailable_duration_seconds,
            "eligible_operations": inp.eligible_operations,
            "failed_operations": inp.failed_operations,
            "timely_observations": inp.timely_observations,
            "late_observations": inp.late_observations,
            "calculation_metadata": meta,
        }
        await QualityScoringRepository.save_reliability_score(session, record)

        return FeedReliabilityResponse(
            score_id=score_id,
            provider_id=inp.provider_id,
            feed_id=inp.feed_id,
            instrument_id=inp.instrument_id,
            data_type=inp.data_type,
            availability_score=avail_s,
            timeliness_score=time_s,
            error_score=err_s,
            reliability_score=rel_s,
            reliability_classification=classif,
            calculated_at=utc_now(),
        )

    @classmethod
    async def evaluate_completeness(
        cls, session: AsyncSession, inp: CompletenessEvaluationInput
    ) -> CompletenessScoreResponse:
        score_id = f"SCR_CMP_{uuid.uuid4().hex[:12].upper()}"
        comp_s, field_r, classif, meta = CompletenessCalculator.calculate_completeness(inp)

        record = {
            "score_id": score_id,
            "provider_id": inp.provider_id,
            "feed_id": inp.feed_id,
            "instrument_id": inp.instrument_id,
            "data_type": inp.data_type,
            "expected_records": inp.expected_records,
            "observed_unique_records": inp.observed_unique_records,
            "valid_records": inp.valid_records,
            "missing_records": inp.missing_records,
            "invalid_records": inp.invalid_records,
            "duplicate_receipts": inp.duplicate_receipts,
            "field_completeness_ratio": field_r,
            "completeness_score": comp_s,
            "completeness_classification": classif,
            "calculation_metadata": meta,
        }
        await QualityScoringRepository.save_completeness_score(session, record)

        return CompletenessScoreResponse(
            score_id=score_id,
            provider_id=inp.provider_id,
            feed_id=inp.feed_id,
            instrument_id=inp.instrument_id,
            data_type=inp.data_type,
            expected_records=inp.expected_records,
            observed_unique_records=inp.observed_unique_records,
            completeness_score=comp_s,
            completeness_classification=classif,
            field_completeness_ratio=field_r,
            calculated_at=utc_now(),
        )

    @classmethod
    async def evaluate_freshness(
        cls, session: AsyncSession, inp: FreshnessEvaluationInput
    ) -> FreshnessScoreResponse:
        score_id = f"SCR_FRH_{uuid.uuid4().hex[:12].upper()}"
        fresh_s, classif, meta = FreshnessCalculator.calculate_freshness(inp)

        record = {
            "score_id": score_id,
            "provider_id": inp.provider_id,
            "feed_id": inp.feed_id,
            "instrument_id": inp.instrument_id,
            "data_type": inp.data_type,
            "calculation_context": inp.calculation_context,
            "target_age_ms": inp.target_age_ms,
            "maximum_age_ms": inp.maximum_age_ms,
            "observed_age_ms": inp.observed_age_ms,
            "freshness_score": fresh_s,
            "freshness_classification": classif,
            "calculation_metadata": meta,
        }
        await QualityScoringRepository.save_freshness_score(session, record)

        return FreshnessScoreResponse(
            score_id=score_id,
            provider_id=inp.provider_id,
            feed_id=inp.feed_id,
            instrument_id=inp.instrument_id,
            data_type=inp.data_type,
            calculation_context=inp.calculation_context,
            observed_age_ms=inp.observed_age_ms,
            freshness_score=fresh_s,
            freshness_classification=classif,
            calculated_at=utc_now(),
        )

    @classmethod
    async def calculate_composite_snapshot(
        cls, session: AsyncSession, req: CompositeQualityRequest
    ) -> CompositeQualitySnapshotResponse:
        snapshot_id = f"SNP_QAL_{uuid.uuid4().hex[:12].upper()}"

        rel_resp = await cls.evaluate_reliability(session, req.reliability)
        compl_resp = await cls.evaluate_completeness(session, req.completeness)
        fresh_resp = await cls.evaluate_freshness(session, req.freshness)

        # Composite = 0.35 * R + 0.35 * C + 0.30 * F
        composite_score = (
            (Decimal("0.3500") * rel_resp.reliability_score)
            + (Decimal("0.3500") * compl_resp.completeness_score)
            + (Decimal("0.3000") * fresh_resp.freshness_score)
        )
        composite_score = round(composite_score, 2)

        record = {
            "snapshot_id": snapshot_id,
            "provider_id": req.provider_id,
            "feed_id": req.feed_id,
            "instrument_id": req.instrument_id,
            "data_type": req.data_type,
            "reliability_score": rel_resp.reliability_score,
            "completeness_score": compl_resp.completeness_score,
            "freshness_score": fresh_resp.freshness_score,
            "composite_quality_score": composite_score,
            "score_status": "SCORE_AVAILABLE",
            "data_origin": req.data_origin,
        }
        await QualityScoringRepository.save_quality_snapshot(session, record)

        return CompositeQualitySnapshotResponse(
            snapshot_id=snapshot_id,
            provider_id=req.provider_id,
            feed_id=req.feed_id,
            instrument_id=req.instrument_id,
            reliability_score=rel_resp.reliability_score,
            completeness_score=compl_resp.completeness_score,
            freshness_score=fresh_resp.freshness_score,
            composite_quality_score=composite_score,
            score_status="SCORE_AVAILABLE",
            data_origin=req.data_origin,
            calculated_at=utc_now(),
        )

    @classmethod
    async def evaluate_eligibility(
        cls, session: AsyncSession, req: EligibilityEvaluationRequest
    ) -> UseEligibilityDecisionResponse:
        decision_id = f"DEC_ELG_{uuid.uuid4().hex[:12].upper()}"

        status, hard_gates, reasons, explanation = EligibilityEvaluator.evaluate(req)

        record = {
            "decision_id": decision_id,
            "profile_code": req.profile_code,
            "provider_id": req.provider_id,
            "feed_id": req.feed_id,
            "instrument_id": req.instrument_id,
            "calculation_context": req.calculation_context,
            "eligibility_status": status,
            "reliability_score": req.reliability_score,
            "completeness_score": req.completeness_score,
            "freshness_score": req.freshness_score,
            "hard_gate_results": hard_gates,
            "restriction_reasons": {"reasons": reasons} if reasons else None,
            "warning_reasons": {"reasons": reasons} if status == "ACCEPTED_WITH_WARNING" else None,
            "decision_explanation": explanation,
        }
        await QualityScoringRepository.save_eligibility_decision(session, record)

        return UseEligibilityDecisionResponse(
            decision_id=decision_id,
            profile_code=req.profile_code,
            provider_id=req.provider_id,
            feed_id=req.feed_id,
            instrument_id=req.instrument_id,
            calculation_context=req.calculation_context,
            eligibility_status=status,
            reliability_score=req.reliability_score,
            completeness_score=req.completeness_score,
            freshness_score=req.freshness_score,
            hard_gate_results=hard_gates,
            decision_explanation=explanation,
            evaluated_at=utc_now(),
        )

