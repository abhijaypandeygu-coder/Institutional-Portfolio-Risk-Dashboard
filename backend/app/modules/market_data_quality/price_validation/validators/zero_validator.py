"""
Module 03.02: Price Validation - Subfeature M03.02.02: Zero Price Validator.
Applies instrument-aware and field-specific rules to zero-valued prices.
Distinguishes between:
- Invalid trade execution at zero (INVALID_ZERO_PRICE)
- Unavailable quote sides (QUOTE_SIDE_UNAVAILABLE)
- Provider-specific sentinel values (PROVIDER_UNAVAILABLE_SENTINEL)
- Volume = 0 (Never rejected as a zero-price violation)
"""
from decimal import Decimal
from typing import List, Optional

from backend.app.modules.market_data_quality.price_validation.models import (
    ValidationStatus,
)
from backend.app.modules.market_data_quality.price_validation.schemas import (
    EvidenceItem,
    PriceObservationInput,
)


class ZeroPriceValidator:
    """Evaluates zero-valued prices using observation type and provider conventions."""

    def validate(
        self, obs: PriceObservationInput, parsed_price: Decimal
    ) -> List[EvidenceItem]:
        evidence_list: List[EvidenceItem] = []

        if parsed_price != Decimal("0"):
            return evidence_list

        price_field = obs.price_field.lower()
        obs_type = obs.observation_type.upper()
        provider = obs.provider_id.upper()

        # 1. Volume = 0 is legitimate market activity (no trades in period), must NOT trigger zero-price rejection
        if price_field == "volume":
            evidence_list.append(
                EvidenceItem(
                    rule_code="ZERO_VOLUME_ACCEPTED",
                    evidence_type="ZERO_CHECK",
                    observed_value=Decimal("0"),
                    status=ValidationStatus.ACCEPTED,
                    evidence_payload={
                        "reason": "Zero volume is economically valid and not a price violation."
                    },
                )
            )
            return evidence_list

        # 2. Quote side (Bid / Ask): Often used as market maker absence / unavailable side
        if price_field in ("best_bid_price", "bid", "best_ask_price", "ask"):
            # If provider explicitly documents 0 as empty side
            evidence_list.append(
                EvidenceItem(
                    rule_code="ZERO_QUOTE_SIDE_UNAVAILABLE",
                    evidence_type="ZERO_CHECK",
                    observed_value=Decimal("0"),
                    status=ValidationStatus.ACCEPTED_WITH_WARNING,
                    evidence_payload={
                        "field": price_field,
                        "classification": "QUOTE_SIDE_UNAVAILABLE",
                        "reason": f"Zero on quote field {price_field} indicates unavailable side/empty order-book queue.",
                    },
                )
            )
            return evidence_list

        # 3. Provider-specific unavailable sentinel (e.g., Alpha Vantage returning 0.0000 for unquoted / halted)
        if provider == "ALPHA_VANTAGE" and obs.source_metadata.get("is_sentinel", False):
            evidence_list.append(
                EvidenceItem(
                    rule_code="ZERO_PROVIDER_SENTINEL",
                    evidence_type="ZERO_CHECK",
                    observed_value=Decimal("0"),
                    status=ValidationStatus.QUARANTINED,
                    evidence_payload={
                        "classification": "PROVIDER_UNAVAILABLE_SENTINEL",
                        "reason": "Alpha Vantage sentinel zero indicates unavailable price or market halt.",
                    },
                )
            )
            return evidence_list

        # 4. Standard Equity Trade / Last Traded Price / OHLC: Zero is economically impossible
        if obs_type in ("TICK", "TRADE", "OHLCV") or price_field in (
            "last_traded_price",
            "price",
            "close",
            "open",
            "high",
            "low",
        ):
            evidence_list.append(
                EvidenceItem(
                    rule_code="ZERO_PRICE_REJECTED",
                    evidence_type="ZERO_CHECK",
                    observed_value=Decimal("0"),
                    status=ValidationStatus.REJECTED,
                    evidence_payload={
                        "field": price_field,
                        "observation_type": obs_type,
                        "classification": "INVALID_ZERO_PRICE",
                        "reason": f"Zero is economically invalid for ordinary listed equity {price_field}.",
                    },
                )
            )

        return evidence_list
