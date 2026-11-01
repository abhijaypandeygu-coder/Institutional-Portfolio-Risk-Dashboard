"""
Module 03.02: Price Validation - Subfeature M03.02.03: Price Movement & Exchange Band Validator.
Validates:
- Configurable percentage change thresholds (e.g. 5%, 10%)
- Configurable absolute change thresholds (e.g. 100 INR, 20 USD)
- Optional volatility/Z-score thresholds using historical returns
- Official exchange price bands (upper/lower circuit bands for NSE/BSE and LULD for US)
- Corporate action continuity checks (splits, bonus, dividends)
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from backend.app.modules.market_data_quality.price_validation.framework.math_utils import (
    calculate_absolute_difference,
    calculate_percentage_change,
)
from backend.app.modules.market_data_quality.price_validation.integrations.m04_bridge import (
    InstrumentMetadata,
    InstrumentReferenceService,
)
from backend.app.modules.market_data_quality.price_validation.models import (
    ValidationStatus,
)
from backend.app.modules.market_data_quality.price_validation.schemas import (
    EvidenceItem,
    PriceObservationInput,
)


class PriceMovementValidator:
    """Evaluates percentage movement, absolute jumps, and exchange price-band boundaries."""

    def __init__(self, reference_service: InstrumentReferenceService):
        self.reference_service = reference_service

    def validate(
        self,
        obs: PriceObservationInput,
        parsed_price: Decimal,
        reference_price: Optional[Decimal],
        metadata: Optional[InstrumentMetadata] = None,
        pct_threshold: Decimal = Decimal("10.0"),  # Default 10%
        abs_threshold: Optional[Decimal] = None,
        historical_returns: Optional[List[Decimal]] = None,
    ) -> List[EvidenceItem]:
        evidence_list: List[EvidenceItem] = []

        if parsed_price <= Decimal("0"):
            return evidence_list

        obs_date = obs.observation_timestamp.date()

        # 1. Exchange Price Band Evaluation (Official upper & lower bands from M04)
        band = self.reference_service.get_exchange_price_band(
            obs.instrument_id, obs.exchange, obs_date
        )
        if band is not None:
            if parsed_price > band.upper_band:
                evidence_list.append(
                    EvidenceItem(
                        rule_code="BAND_BREACH_UPPER",
                        evidence_type="EXCHANGE_BAND_CHECK",
                        observed_value=parsed_price,
                        threshold_value=band.upper_band,
                        calculated_difference=parsed_price - band.upper_band,
                        source_reference=f"EXCHANGE_BAND_{band.exchange}",
                        status=ValidationStatus.QUARANTINED,
                        evidence_payload={
                            "classification": "ABOVE_EXCHANGE_UPPER_BAND",
                            "upper_band": str(band.upper_band),
                            "lower_band": str(band.lower_band),
                            "reason": f"Price {parsed_price} exceeds official exchange upper band {band.upper_band}",
                        },
                    )
                )
            elif parsed_price < band.lower_band:
                evidence_list.append(
                    EvidenceItem(
                        rule_code="BAND_BREACH_LOWER",
                        evidence_type="EXCHANGE_BAND_CHECK",
                        observed_value=parsed_price,
                        threshold_value=band.lower_band,
                        calculated_difference=band.lower_band - parsed_price,
                        source_reference=f"EXCHANGE_BAND_{band.exchange}",
                        status=ValidationStatus.QUARANTINED,
                        evidence_payload={
                            "classification": "BELOW_EXCHANGE_LOWER_BAND",
                            "upper_band": str(band.upper_band),
                            "lower_band": str(band.lower_band),
                            "reason": f"Price {parsed_price} is below official exchange lower band {band.lower_band}",
                        },
                    )
                )
            else:
                evidence_list.append(
                    EvidenceItem(
                        rule_code="BAND_VERIFIED_IN_BOUNDS",
                        evidence_type="EXCHANGE_BAND_CHECK",
                        observed_value=parsed_price,
                        source_reference=f"EXCHANGE_BAND_{band.exchange}",
                        status=ValidationStatus.ACCEPTED,
                        evidence_payload={"classification": "VERIFIED_IN_BAND"},
                    )
                )
        else:
            evidence_list.append(
                EvidenceItem(
                    rule_code="BAND_UNAVAILABLE",
                    evidence_type="EXCHANGE_BAND_CHECK",
                    observed_value=parsed_price,
                    status=ValidationStatus.UNKNOWN,
                    evidence_payload={
                        "classification": "BAND_UNKNOWN",
                        "reason": f"Official exchange price bands not configured for {obs.instrument_id} on {obs.exchange}",
                    },
                )
            )

        # 2. Reference Price Comparison & Movement Evaluation
        if reference_price is None or reference_price <= Decimal("0"):
            evidence_list.append(
                EvidenceItem(
                    rule_code="MOVEMENT_REFERENCE_UNAVAILABLE",
                    evidence_type="MOVEMENT_CHECK",
                    observed_value=parsed_price,
                    status=ValidationStatus.UNKNOWN,
                    evidence_payload={
                        "classification": "REFERENCE_UNAVAILABLE",
                        "reason": "Prior valid reference price is unavailable or non-positive.",
                    },
                )
            )
            return evidence_list

        # Check for active Corporate Actions (Splits, Reverse Splits) on observation date
        corp_actions = self.reference_service.get_corporate_actions(
            obs.instrument_id, obs_date, obs_date
        )
        is_corp_action_day = len(corp_actions) > 0
        corp_notes = [f"{a.action_type} (ratio {a.ratio})" for a in corp_actions]

        pct_change = calculate_percentage_change(parsed_price, reference_price)
        abs_diff = calculate_absolute_difference(parsed_price, reference_price)

        if pct_change is not None:
            # 2a. Percentage threshold check
            if abs(pct_change) > pct_threshold:
                direction = "EXTREME_UPWARD_MOVEMENT" if pct_change > 0 else "EXTREME_DOWNWARD_MOVEMENT"
                
                # If a corporate action occurred, classify as warning/review rather than outright quarantine
                if is_corp_action_day:
                    evidence_list.append(
                        EvidenceItem(
                            rule_code="CORP_ACTION_PRICE_MOVEMENT",
                            evidence_type="CORPORATE_ACTION_REVIEW",
                            observed_value=parsed_price,
                            reference_value=reference_price,
                            threshold_value=pct_threshold,
                            calculated_percentage=pct_change,
                            calculated_difference=abs_diff,
                            status=ValidationStatus.ACCEPTED_WITH_WARNING,
                            evidence_payload={
                                "classification": "CORPORATE_ACTION_REVIEW_REQUIRED",
                                "corporate_actions": corp_notes,
                                "reason": f"Large price movement ({pct_change:.2f}%) coincides with effective corporate action.",
                            },
                        )
                    )
                else:
                    evidence_list.append(
                        EvidenceItem(
                            rule_code="EXTREME_PRICE_MOVEMENT",
                            evidence_type="MOVEMENT_CHECK",
                            observed_value=parsed_price,
                            reference_value=reference_price,
                            threshold_value=pct_threshold,
                            calculated_percentage=pct_change,
                            calculated_difference=abs_diff,
                            status=ValidationStatus.ACCEPTED_WITH_WARNING,
                            evidence_payload={
                                "classification": direction,
                                "percentage_change": str(pct_change),
                                "threshold": str(pct_threshold),
                                "reason": f"Price movement of {pct_change:.2f}% exceeds configured threshold {pct_threshold}%.",
                            },
                        )
                    )
            else:
                evidence_list.append(
                    EvidenceItem(
                        rule_code="MOVEMENT_NORMAL",
                        evidence_type="MOVEMENT_CHECK",
                        observed_value=parsed_price,
                        reference_value=reference_price,
                        threshold_value=pct_threshold,
                        calculated_percentage=pct_change,
                        calculated_difference=abs_diff,
                        status=ValidationStatus.ACCEPTED,
                        evidence_payload={"classification": "NORMAL"},
                    )
                )

        # 2b. Optional Absolute threshold check
        if abs_threshold is not None and abs_diff > abs_threshold:
            evidence_list.append(
                EvidenceItem(
                    rule_code="ABSOLUTE_PRICE_JUMP",
                    evidence_type="ABSOLUTE_MOVEMENT_CHECK",
                    observed_value=parsed_price,
                    reference_value=reference_price,
                    threshold_value=abs_threshold,
                    calculated_difference=abs_diff,
                    status=ValidationStatus.ACCEPTED_WITH_WARNING,
                    evidence_payload={
                        "reason": f"Absolute price difference {abs_diff} exceeds absolute threshold {abs_threshold}",
                    },
                )
            )

        # 2c. Optional Volatility / Z-Score check
        if historical_returns and len(historical_returns) >= 20:
            mean_ret = sum(historical_returns) / Decimal(len(historical_returns))
            variance = sum((r - mean_ret) ** 2 for r in historical_returns) / Decimal(len(historical_returns) - 1)
            std_dev = Decimal(str(float(variance) ** 0.5))
            if std_dev > Decimal("0") and pct_change is not None:
                z_score = (pct_change - mean_ret) / std_dev
                if abs(z_score) > Decimal("3.0"):
                    evidence_list.append(
                        EvidenceItem(
                            rule_code="VOLATILITY_Z_SCORE_BREACH",
                            evidence_type="STATISTICAL_CHECK",
                            observed_value=parsed_price,
                            reference_value=reference_price,
                            threshold_value=Decimal("3.0"),
                            calculated_difference=abs(z_score),
                            status=ValidationStatus.ACCEPTED_WITH_WARNING,
                            evidence_payload={
                                "z_score": str(z_score),
                                "historical_std_dev": str(std_dev),
                                "reason": f"Z-score {z_score:.2f} exceeds 3-sigma statistical threshold",
                            },
                        )
                    )

        return evidence_list
