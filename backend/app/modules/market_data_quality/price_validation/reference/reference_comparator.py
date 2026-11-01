"""
Module 03.02: Price Validation - Subfeature M03.02.04: Reference Price Comparison Engine.
Validates:
- Comparison against previous official close
- Official exchange reference prices
- Prior accepted observation baseline
- Cross-source comparison between independent providers (e.g. Alpha Vantage vs. Primary Exchange Feed)
- Currency compatibility & freshness constraints
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from backend.app.modules.market_data_quality.price_validation.framework.math_utils import (
    calculate_cross_source_discrepancy,
)
from backend.app.modules.market_data_quality.price_validation.integrations.m04_bridge import (
    InstrumentMetadata,
    InstrumentReferenceService,
    ReferencePriceSnapshot,
)
from backend.app.modules.market_data_quality.price_validation.models import (
    ValidationStatus,
)
from backend.app.modules.market_data_quality.price_validation.schemas import (
    CrossSourceCompareRequest,
    CrossSourceCompareResponse,
    EvidenceItem,
    PriceObservationInput,
)


class ReferencePriceComparator:
    """Performs previous-close, official reference, and multi-provider cross comparisons."""

    def __init__(self, reference_service: InstrumentReferenceService):
        self.reference_service = reference_service

    def compare_with_reference(
        self,
        obs: PriceObservationInput,
        parsed_price: Decimal,
        reference_snapshot: Optional[ReferencePriceSnapshot],
        max_deviation_pct: Decimal = Decimal("5.0"),
    ) -> List[EvidenceItem]:
        evidence_list: List[EvidenceItem] = []

        if parsed_price <= Decimal("0"):
            return evidence_list

        if reference_snapshot is None:
            evidence_list.append(
                EvidenceItem(
                    rule_code="REF_SNAPSHOT_UNAVAILABLE",
                    evidence_type="REFERENCE_COMPARISON",
                    observed_value=parsed_price,
                    status=ValidationStatus.UNKNOWN,
                    evidence_payload={
                        "reason": f"No active reference snapshot found for {obs.instrument_id}."
                    },
                )
            )
            return evidence_list

        # Check currency compatibility
        obs_curr = (obs.currency or "INR").upper()
        ref_curr = reference_snapshot.currency.upper()
        if obs_curr != ref_curr:
            evidence_list.append(
                EvidenceItem(
                    rule_code="REF_CURRENCY_MISMATCH",
                    evidence_type="CURRENCY_CHECK",
                    observed_value=parsed_price,
                    reference_value=reference_snapshot.reference_value,
                    status=ValidationStatus.QUARANTINED,
                    evidence_payload={
                        "observed_currency": obs_curr,
                        "reference_currency": ref_curr,
                        "reason": f"Cannot compare price {parsed_price} {obs_curr} against reference in {ref_curr} without FX conversion.",
                    },
                )
            )
            return evidence_list

        ref_val = reference_snapshot.reference_value
        if ref_val <= Decimal("0"):
            evidence_list.append(
                EvidenceItem(
                    rule_code="REF_VALUE_NON_POSITIVE",
                    evidence_type="REFERENCE_VALIDITY",
                    observed_value=parsed_price,
                    reference_value=ref_val,
                    status=ValidationStatus.UNKNOWN,
                    evidence_payload={
                        "reason": "Reference snapshot contains zero or negative value, cannot use as benchmark."
                    },
                )
            )
            return evidence_list

        abs_diff, pct_disc = calculate_cross_source_discrepancy(
            parsed_price, ref_val, reference_denominator=ref_val
        )

        if pct_disc is not None and pct_disc > max_deviation_pct:
            evidence_list.append(
                EvidenceItem(
                    rule_code="REF_PRICE_DISCREPANCY_BREACH",
                    evidence_type="REFERENCE_DEVIATION",
                    observed_value=parsed_price,
                    reference_value=ref_val,
                    threshold_value=max_deviation_pct,
                    calculated_difference=abs_diff,
                    calculated_percentage=pct_disc,
                    source_reference=f"{reference_snapshot.reference_type}_{reference_snapshot.source_provider}",
                    status=ValidationStatus.QUARANTINED,
                    evidence_payload={
                        "reference_type": reference_snapshot.reference_type,
                        "deviation_pct": str(pct_disc),
                        "threshold_pct": str(max_deviation_pct),
                        "reason": f"Price deviates by {pct_disc:.2f}% from {reference_snapshot.reference_type} ({ref_val}), exceeds tolerance {max_deviation_pct}%.",
                    },
                )
            )
        else:
            evidence_list.append(
                EvidenceItem(
                    rule_code="REF_PRICE_ALIGNED",
                    evidence_type="REFERENCE_DEVIATION",
                    observed_value=parsed_price,
                    reference_value=ref_val,
                    threshold_value=max_deviation_pct,
                    calculated_difference=abs_diff,
                    calculated_percentage=pct_disc,
                    source_reference=f"{reference_snapshot.reference_type}_{reference_snapshot.source_provider}",
                    status=ValidationStatus.ACCEPTED,
                    evidence_payload={"reason": "Observation conforms with reference price."},
                )
            )

        return evidence_list

    def compare_cross_sources(
        self, req: CrossSourceCompareRequest
    ) -> CrossSourceCompareResponse:
        """Compares price observations from two independent market data providers."""
        abs_diff, pct_disc = calculate_cross_source_discrepancy(
            req.price_a, req.price_b, reference_denominator=max(req.price_a, req.price_b)
        )

        is_discrepant = False
        notes = "Providers aligned within acceptable tolerance."
        status = ValidationStatus.ACCEPTED

        if pct_disc is not None and pct_disc > req.max_tolerance_percentage:
            is_discrepant = True
            status = ValidationStatus.QUARANTINED
            notes = (
                f"Discrepancy of {pct_disc:.2f}% between {req.provider_a} ({req.price_a}) "
                f"and {req.provider_b} ({req.price_b}) exceeds tolerance of {req.max_tolerance_percentage}%."
            )

        return CrossSourceCompareResponse(
            instrument_id=req.instrument_id,
            exchange=req.exchange,
            price_a=req.price_a,
            provider_a=req.provider_a,
            price_b=req.price_b,
            provider_b=req.provider_b,
            absolute_difference=abs_diff,
            percentage_discrepancy=pct_disc,
            tolerance_percentage=req.max_tolerance_percentage,
            is_discrepant=is_discrepant,
            status=status,
            notes=notes,
        )
