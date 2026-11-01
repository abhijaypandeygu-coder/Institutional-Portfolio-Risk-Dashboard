"""
Module 03.02: Price Validation - Subfeature M03.02.01: Structural Price Validator.
Validates:
- Null, missing, and non-numeric representations
- Non-finite values (NaN, +Inf, -Inf)
- Negative equity prices
- Out-of-range bounds (min_price, max_price from M04 instrument master)
- Tick-size divisibility and decimal precision limits
- OHLC structural price relationships (Open > 0, High >= Low, High >= Open/Close, Low <= Open/Close)
"""
from decimal import Decimal
from typing import List, Optional, Tuple

from backend.app.modules.market_data_quality.price_validation.framework.math_utils import (
    count_decimal_places,
    is_ohlc_structurally_valid,
    is_tick_size_valid,
    to_decimal,
)
from backend.app.modules.market_data_quality.price_validation.integrations.m04_bridge import (
    InstrumentMetadata,
    InstrumentReferenceService,
)
from backend.app.modules.market_data_quality.price_validation.models import (
    ValidationSeverity,
    ValidationStatus,
)
from backend.app.modules.market_data_quality.price_validation.schemas import (
    EvidenceItem,
    PriceObservationInput,
)


class StructuralPriceValidator:
    """Evaluates numerical, representation, instrument conventions, and OHLC structural validity."""

    def __init__(self, reference_service: InstrumentReferenceService):
        self.reference_service = reference_service

    def validate(
        self, obs: PriceObservationInput, metadata: Optional[InstrumentMetadata] = None
    ) -> Tuple[Optional[Decimal], List[EvidenceItem]]:
        """
        Runs structural checks on a single price observation.
        Returns (parsed_decimal_or_none, list_of_evidence_items).
        """
        evidence_list: List[EvidenceItem] = []
        raw = obs.raw_price

        # 1. Null / Missing field check
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            evidence_list.append(
                EvidenceItem(
                    rule_code="STRUCT_NULL_PRICE",
                    evidence_type="NULL_DETECTION",
                    status=ValidationStatus.REJECTED,
                    evidence_payload={
                        "raw_value": str(raw),
                        "reason": "Price field is null, missing, or empty whitespace",
                    },
                )
            )
            return None, evidence_list

        # 2. Non-numeric / Non-finite check
        parsed = to_decimal(raw)
        if parsed is None:
            evidence_list.append(
                EvidenceItem(
                    rule_code="STRUCT_NON_NUMERIC_OR_NON_FINITE",
                    evidence_type="NUMERICAL_PARSING",
                    status=ValidationStatus.REJECTED,
                    evidence_payload={
                        "raw_value": str(raw),
                        "reason": "Value is malformed, non-numeric, NaN, or infinite",
                    },
                )
            )
            return None, evidence_list

        # 3. Negative price check (Strict rejection for listed equities)
        if parsed < Decimal("0"):
            evidence_list.append(
                EvidenceItem(
                    rule_code="STRUCT_NEGATIVE_EQUITY_PRICE",
                    evidence_type="SIGN_CHECK",
                    observed_value=parsed,
                    threshold_value=Decimal("0"),
                    status=ValidationStatus.REJECTED,
                    evidence_payload={
                        "raw_value": str(raw),
                        "reason": "Negative prices are strictly forbidden for listed equities",
                    },
                )
            )
            return parsed, evidence_list

        # 4. Instrument conventions (Min/Max range, Tick size, Decimal precision)
        if metadata is not None:
            # 4a. Range checks
            if metadata.min_price is not None and parsed < metadata.min_price:
                evidence_list.append(
                    EvidenceItem(
                        rule_code="STRUCT_PRICE_BELOW_MINIMUM",
                        evidence_type="RANGE_CHECK",
                        observed_value=parsed,
                        threshold_value=metadata.min_price,
                        status=ValidationStatus.REJECTED,
                        evidence_payload={
                            "reason": f"Price {parsed} is below instrument minimum {metadata.min_price}"
                        },
                    )
                )
            elif metadata.max_price is not None and parsed > metadata.max_price:
                evidence_list.append(
                    EvidenceItem(
                        rule_code="STRUCT_PRICE_ABOVE_MAXIMUM",
                        evidence_type="RANGE_CHECK",
                        observed_value=parsed,
                        threshold_value=metadata.max_price,
                        status=ValidationStatus.REJECTED,
                        evidence_payload={
                            "reason": f"Price {parsed} exceeds instrument maximum {metadata.max_price}"
                        },
                    )
                )

            # 4b. Tick-size alignment
            if metadata.tick_size is not None and metadata.tick_size > Decimal("0"):
                if not is_tick_size_valid(parsed, metadata.tick_size):
                    evidence_list.append(
                        EvidenceItem(
                            rule_code="STRUCT_TICK_SIZE_VIOLATION",
                            evidence_type="TICK_SIZE_ALIGNMENT",
                            observed_value=parsed,
                            threshold_value=metadata.tick_size,
                            status=ValidationStatus.REJECTED,
                            evidence_payload={
                                "tick_size": str(metadata.tick_size),
                                "reason": f"Price {parsed} does not conform to tick size {metadata.tick_size}",
                            },
                        )
                    )

            # 4c. Decimal precision limit
            if metadata.price_precision is not None:
                dec_places = count_decimal_places(parsed)
                if dec_places > metadata.price_precision:
                    evidence_list.append(
                        EvidenceItem(
                            rule_code="STRUCT_DECIMAL_PRECISION_EXCEEDED",
                            evidence_type="PRECISION_CHECK",
                            observed_value=parsed,
                            status=ValidationStatus.REJECTED,
                            evidence_payload={
                                "observed_places": dec_places,
                                "allowed_places": metadata.price_precision,
                                "reason": f"Price {parsed} has {dec_places} decimals, exceeds max {metadata.price_precision}",
                            },
                        )
                    )

        # 5. OHLC relationship checks if applicable
        if obs.observation_type.upper() == "OHLCV":
            o = to_decimal(obs.open_price if obs.open_price is not None else parsed)
            h = to_decimal(obs.high_price if obs.high_price is not None else parsed)
            l = to_decimal(obs.low_price if obs.low_price is not None else parsed)
            c = to_decimal(obs.close_price if obs.close_price is not None else parsed)
            if o is not None and h is not None and l is not None and c is not None:
                valid_ohlc, ohlc_err = is_ohlc_structurally_valid(o, h, l, c)
                if not valid_ohlc:
                    evidence_list.append(
                        EvidenceItem(
                            rule_code="STRUCT_INVALID_OHLC_RELATIONSHIP",
                            evidence_type="OHLC_INVARIANT",
                            observed_value=parsed,
                            status=ValidationStatus.REJECTED,
                            evidence_payload={
                                "open": str(o),
                                "high": str(h),
                                "low": str(l),
                                "close": str(c),
                                "error": ohlc_err,
                            },
                        )
                    )

        return parsed, evidence_list
