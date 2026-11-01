"""
M03.06 - Data Consistency Orchestration Service.
Orchestrates:
1. Source eligibility & pairing evaluation.
2. Cross-feed discrepancy calculations.
3. Automated source precedence resolution.
4. Intra-observation field consistency checks.
5. Conflict lifecycle management and evidence audit.
"""

import uuid
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.consistency.schemas import (
    CrossFeedCompareRequest,
    ComparisonResultResponse,
    OHLCFieldValidationInput,
    QuoteFieldValidationInput,
    FieldConsistencyResponse,
)
from backend.app.modules.market_data_quality.consistency.comparison.eligibility import (
    SourceEligibilityResolver,
)
from backend.app.modules.market_data_quality.consistency.discrepancy.calculator import (
    DiscrepancyCalculator,
)
from backend.app.modules.market_data_quality.consistency.fields.validator import (
    FieldConsistencyValidator,
)
from backend.app.modules.market_data_quality.consistency.precedence.resolver import (
    PrecedenceResolver,
)
from backend.app.modules.market_data_quality.consistency.conflicts.repository import (
    ConsistencyRepository,
    utc_now,
)

logger = logging.getLogger(__name__)


class DataConsistencyService:
    """
    Main orchestration service for M03.06 Data Consistency.
    """

    @classmethod
    async def compare_cross_feed(
        cls, session: AsyncSession, request: CrossFeedCompareRequest
    ) -> ComparisonResultResponse:
        """
        Compares two market observations from independent feeds or providers.
        """
        result_id = f"CMP_{uuid.uuid4().hex[:12].upper()}"

        # 1. Eligibility Check
        is_eligible, elig_status, elig_meta = SourceEligibilityResolver.evaluate_eligibility(request)

        val_a = DiscrepancyCalculator.to_decimal(request.source_a.value) or Decimal("0.0")
        val_b = DiscrepancyCalculator.to_decimal(request.source_b.value) or Decimal("0.0")

        if not is_eligible:
            # Record uncomparable result without calculating misleading divergence
            evidence = {
                "ineligibility_reason": elig_meta.get("reason") if elig_meta else elig_status,
                "eligibility_metadata": elig_meta,
            }
            res_record = {
                "result_id": result_id,
                "instrument_id": request.instrument_id,
                "exchange": request.exchange,
                "observation_type": request.observation_type,
                "source_a_provider": request.source_a.provider_id,
                "source_a_feed": request.source_a.feed_id,
                "observation_a_id": request.source_a.observation_id,
                "value_a": val_a,
                "timestamp_a": request.source_a.timestamp,
                "source_b_provider": request.source_b.provider_id,
                "source_b_feed": request.source_b.feed_id,
                "observation_b_id": request.source_b.observation_id,
                "value_b": val_b,
                "timestamp_b": request.source_b.timestamp,
                "currency": request.currency,
                "absolute_difference": Decimal("0.0"),
                "percentage_difference": None,
                "tolerance_applied": Decimal("0.0"),
                "comparison_status": elig_status,
                "severity": "INFO",
                "evidence": evidence,
            }
            await ConsistencyRepository.save_comparison_result(session, res_record)

            return ComparisonResultResponse(
                result_id=result_id,
                instrument_id=request.instrument_id,
                exchange=request.exchange,
                observation_type=request.observation_type,
                source_a_provider=request.source_a.provider_id,
                observation_a_id=request.source_a.observation_id,
                value_a=val_a,
                timestamp_a=request.source_a.timestamp,
                source_b_provider=request.source_b.provider_id,
                observation_b_id=request.source_b.observation_id,
                value_b=val_b,
                timestamp_b=request.source_b.timestamp,
                currency=request.currency,
                absolute_difference=Decimal("0.0"),
                percentage_difference=None,
                tolerance_applied=Decimal("0.0"),
                comparison_status=elig_status,
                severity="INFO",
                evidence=evidence,
                conflict_created=False,
            )

        # 2. Eligible: Calculate Price Discrepancy
        pct_tol = request.percentage_tolerance if request.percentage_tolerance is not None else Decimal("0.5000")
        abs_diff, pct_diff, exceeds, severity = DiscrepancyCalculator.calculate_discrepancy(
            val_a=val_a,
            val_b=val_b,
            percentage_tolerance=pct_tol,
            absolute_tolerance=request.absolute_tolerance,
        )

        comp_status = "INCONSISTENT" if exceeds else "CONSISTENT"
        evidence = {
            "source_a": {
                "observation_id": request.source_a.observation_id,
                "provider_id": request.source_a.provider_id,
                "feed_id": request.source_a.feed_id,
                "instrument_id": request.source_a.instrument_id,
                "exchange": request.source_a.exchange,
                "currency": request.source_a.currency,
                "timestamp": request.source_a.timestamp.isoformat(),
                "value": str(request.source_a.value),
                "data_origin": request.source_a.data_origin,
            },
            "source_b": {
                "observation_id": request.source_b.observation_id,
                "provider_id": request.source_b.provider_id,
                "feed_id": request.source_b.feed_id,
                "instrument_id": request.source_b.instrument_id,
                "exchange": request.source_b.exchange,
                "currency": request.source_b.currency,
                "timestamp": request.source_b.timestamp.isoformat(),
                "value": str(request.source_b.value),
                "data_origin": request.source_b.data_origin,
            },
            "exceeds_tolerance": exceeds,
            "pct_diff": str(pct_diff) if pct_diff is not None else None,
            "abs_diff": str(abs_diff),
        }

        # 3. Conflict Handling and Auto-Resolution via Precedence
        conflict_created = False
        conflict_key: Optional[str] = None

        if exceeds:
            conflict_created = True
            conflict_key = f"CONF_{request.instrument_id}_{request.source_a.provider_id}_{request.source_b.provider_id}_{request.source_a.observation_id}"

            # Attempt automatic resolution via Source Precedence
            winner_src, winner_obs_id, rule_code = await PrecedenceResolver.attempt_auto_resolution(
                session=session,
                exchange=request.exchange,
                source_a=request.source_a,
                source_b=request.source_b,
            )

            if winner_src:
                conflict_status = "AUTO_RESOLVED"
                resolution_method = "SOURCE_PRECEDENCE"
                resolution_reason = f"Resolved via precedence rule '{rule_code}': preferred source '{winner_src}'."
            else:
                conflict_status = "PENDING_MANUAL_REVIEW"
                resolution_method = None
                resolution_reason = "Sources have equal or unspecified precedence; sent for review."

            await ConsistencyRepository.create_or_update_conflict(
                session=session,
                conflict_key=conflict_key,
                instrument_id=request.instrument_id,
                exchange=request.exchange,
                conflict_type="CROSS_FEED_DISCREPANCY",
                observation_type=request.observation_type,
                comparison_result_id=result_id,
                severity=severity,
                evidence=evidence,
                selected_source=winner_src,
                selected_observation_id=winner_obs_id,
                resolution_method=resolution_method,
                resolution_rule_code=rule_code,
                resolution_reason=resolution_reason,
                conflict_status=conflict_status,
            )

        # 4. Save Comparison Result
        res_record = {
            "result_id": result_id,
            "instrument_id": request.instrument_id,
            "exchange": request.exchange,
            "observation_type": request.observation_type,
            "source_a_provider": request.source_a.provider_id,
            "source_a_feed": request.source_a.feed_id,
            "observation_a_id": request.source_a.observation_id,
            "value_a": val_a,
            "timestamp_a": request.source_a.timestamp,
            "source_b_provider": request.source_b.provider_id,
            "source_b_feed": request.source_b.feed_id,
            "observation_b_id": request.source_b.observation_id,
            "value_b": val_b,
            "timestamp_b": request.source_b.timestamp,
            "currency": request.currency,
            "absolute_difference": abs_diff,
            "percentage_difference": pct_diff,
            "tolerance_applied": pct_tol,
            "comparison_status": comp_status,
            "severity": severity,
            "evidence": evidence,
        }
        await ConsistencyRepository.save_comparison_result(session, res_record)

        return ComparisonResultResponse(
            result_id=result_id,
            instrument_id=request.instrument_id,
            exchange=request.exchange,
            observation_type=request.observation_type,
            source_a_provider=request.source_a.provider_id,
            observation_a_id=request.source_a.observation_id,
            value_a=val_a,
            timestamp_a=request.source_a.timestamp,
            source_b_provider=request.source_b.provider_id,
            observation_b_id=request.source_b.observation_id,
            value_b=val_b,
            timestamp_b=request.source_b.timestamp,
            currency=request.currency,
            absolute_difference=abs_diff,
            percentage_difference=pct_diff,
            tolerance_applied=pct_tol,
            comparison_status=comp_status,
            severity=severity,
            evidence=evidence,
            conflict_created=conflict_created,
            conflict_key=conflict_key,
        )

    @classmethod
    async def validate_ohlc_fields(
        cls, session: AsyncSession, ohlc_in: OHLCFieldValidationInput
    ) -> FieldConsistencyResponse:
        """
        Validates OHLC relational integrity.
        """
        result_id = f"FLD_OHLC_{uuid.uuid4().hex[:12].upper()}"
        is_valid, violations, evidence = FieldConsistencyValidator.validate_ohlc(ohlc_in)

        status = "FIELD_CONSISTENT" if is_valid else "FIELD_INCONSISTENT"
        rec = {
            "result_id": result_id,
            "instrument_id": ohlc_in.instrument_id,
            "observation_id": ohlc_in.observation_id,
            "observation_type": "OHLCV",
            "field_a": "high_price",
            "field_b": "low_price",
            "value_a": DiscrepancyCalculator.to_decimal(ohlc_in.high_price),
            "value_b": DiscrepancyCalculator.to_decimal(ohlc_in.low_price),
            "relationship_operator": "GTE",
            "expected_relationship": "High >= Low and High >= Open/Close and Low <= Open/Close",
            "actual_result": "; ".join(violations) if violations else "Valid boundaries",
            "validation_status": status,
            "evidence": evidence,
        }
        await ConsistencyRepository.save_field_consistency_result(session, rec)

        return FieldConsistencyResponse(
            result_id=result_id,
            instrument_id=ohlc_in.instrument_id,
            observation_id=ohlc_in.observation_id,
            observation_type="OHLCV",
            validation_status=status,
            violations=violations,
            evidence=evidence,
        )

    @classmethod
    async def validate_quote_fields(
        cls, session: AsyncSession, quote_in: QuoteFieldValidationInput
    ) -> FieldConsistencyResponse:
        """
        Validates Quote resting quantities and sanity.
        """
        result_id = f"FLD_QTE_{uuid.uuid4().hex[:12].upper()}"
        is_valid, violations, evidence = FieldConsistencyValidator.validate_quote(quote_in)

        status = "FIELD_CONSISTENT" if is_valid else "FIELD_INCONSISTENT"
        rec = {
            "result_id": result_id,
            "instrument_id": quote_in.instrument_id,
            "observation_id": quote_in.observation_id,
            "observation_type": "QUOTE",
            "field_a": "bid_quantity",
            "field_b": "ask_quantity",
            "value_a": DiscrepancyCalculator.to_decimal(quote_in.bid_quantity),
            "value_b": DiscrepancyCalculator.to_decimal(quote_in.ask_quantity),
            "relationship_operator": "NON_NEGATIVE",
            "expected_relationship": "Displayed bid/ask quantities >= 0 and prices > 0",
            "actual_result": "; ".join(violations) if violations else "Valid quote values",
            "validation_status": status,
            "evidence": evidence,
        }
        await ConsistencyRepository.save_field_consistency_result(session, rec)

        return FieldConsistencyResponse(
            result_id=result_id,
            instrument_id=quote_in.instrument_id,
            observation_id=quote_in.observation_id,
            observation_type="QUOTE",
            validation_status=status,
            violations=violations,
            evidence=evidence,
        )
