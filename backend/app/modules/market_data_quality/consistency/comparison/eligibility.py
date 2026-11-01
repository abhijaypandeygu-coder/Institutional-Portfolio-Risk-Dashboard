"""
M03.06.01 - Source Eligibility and Comparison Pairing Resolver.
Verifies instrument matching, currency compatibility, timestamp alignment,
and enforces provider independence (real vs simulated boundary).
"""

from decimal import Decimal
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from backend.app.modules.market_data_quality.consistency.schemas import (
    ObservationComparisonInput,
    CrossFeedCompareRequest,
)


class SourceEligibilityResolver:
    """
    Validates whether two observations are compatible and eligible for cross-feed comparison.
    """

    @classmethod
    def evaluate_eligibility(
        cls, request: CrossFeedCompareRequest
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validates source eligibility and comparability.
        Returns (is_eligible, status_reason, metadata).
        """
        src_a = request.source_a
        src_b = request.source_b

        # 1. Real vs Simulated Data Isolation
        if not request.allow_real_vs_sim:
            if (src_a.data_origin == "REAL" and src_b.data_origin == "SIMULATOR") or (
                src_a.data_origin == "SIMULATOR" and src_b.data_origin == "REAL"
            ):
                return False, "UNCOMPARABLE", {
                    "reason": "Synthetic simulated data cannot be compared against real market observations as an independent source."
                }

        # 2. Source Upstream Validity Checks
        if not src_a.is_valid:
            return False, "SOURCE_INVALID", {"reason": f"Source A ({src_a.provider_id}) failed upstream validation."}
        if not src_b.is_valid:
            return False, "SOURCE_INVALID", {"reason": f"Source B ({src_b.provider_id}) failed upstream validation."}

        # 3. Staleness Check
        if src_a.is_stale:
            return False, "SOURCE_STALE", {"reason": f"Source A ({src_a.provider_id}) is stale."}
        if src_b.is_stale:
            return False, "SOURCE_STALE", {"reason": f"Source B ({src_b.provider_id}) is stale."}

        # 4. Instrument & Exchange Matching
        if src_a.instrument_id.upper() != src_b.instrument_id.upper():
            return False, "INSTRUMENT_MISMATCH", {
                "reason": f"Instrument mismatch: '{src_a.instrument_id}' vs '{src_b.instrument_id}'."
            }
        if src_a.exchange.upper() != src_b.exchange.upper():
            return False, "EXCHANGE_MISMATCH", {
                "reason": f"Cross-exchange comparison requires explicit policy: '{src_a.exchange}' vs '{src_b.exchange}'."
            }

        # 5. Currency Matching
        if src_a.currency.upper() != src_b.currency.upper():
            return False, "CURRENCY_MISMATCH", {
                "reason": f"Currency mismatch without FX conversion: '{src_a.currency}' vs '{src_b.currency}'."
            }

        # 6. Observation Type Compatibility
        if src_a.observation_type.upper() != src_b.observation_type.upper():
            return False, "OBSERVATION_TYPE_MISMATCH", {
                "reason": f"Incompatible observation types: '{src_a.observation_type}' vs '{src_b.observation_type}'."
            }

        # 7. Timestamp Alignment Window
        time_diff_ms = abs((src_a.timestamp - src_b.timestamp).total_seconds() * 1000)
        if time_diff_ms > request.max_time_alignment_ms:
            return False, "TIMESTAMP_MISMATCH", {
                "reason": f"Timestamps diverge by {time_diff_ms:.1f}ms, exceeding max window ({request.max_time_alignment_ms}ms)."
            }

        return True, "ELIGIBLE", {"time_alignment_ms": time_diff_ms}
