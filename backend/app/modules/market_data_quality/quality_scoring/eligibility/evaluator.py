"""
M03.07.04 - Use Eligibility Evaluator with Mandatory Hard Gates.
Combines reliability, completeness, and freshness scores with upstream hard-gate signals
(price validity, timestamp validity, book continuity, unresolved conflicts, data capability).
Outputs: ACCEPTED, ACCEPTED_WITH_WARNING, RESTRICTED, REJECTED, NOT_SUPPORTED.
"""

from decimal import Decimal
from typing import Tuple, Dict, Any, List
from backend.app.modules.market_data_quality.quality_scoring.schemas import EligibilityEvaluationRequest


class EligibilityEvaluator:
    """
    Evaluates calculation-specific data fitness with mandatory upstream hard-gate overrides.
    """

    @classmethod
    def evaluate(
        cls,
        req: EligibilityEvaluationRequest,
        min_reliability: Decimal = Decimal("70.00"),
        min_completeness: Decimal = Decimal("90.00"),
        min_freshness: Decimal = Decimal("50.00"),
    ) -> Tuple[str, Dict[str, Any], List[str], str]:
        """
        Calculates (eligibility_status, hard_gate_results, reasons, explanation).
        """
        hard_gates = {
            "price_valid": req.is_price_valid,
            "timestamp_valid": req.is_timestamp_valid,
            "order_book_continuous": req.is_order_book_continuous,
            "cross_feed_consistent": not req.has_unresolved_cross_feed_conflict,
            "capability_supported": req.is_capability_supported,
        }
        reasons = []

        # 1. Check capability support first (e.g. Alpha Vantage Free does not support L2 book)
        if not req.is_capability_supported:
            return (
                "NOT_SUPPORTED",
                hard_gates,
                [f"Data capability required by {req.profile_code} is not supported by provider {req.provider_id}."],
                f"Provider {req.provider_id} does not provide data entitlement for {req.profile_code}.",
            )

        # 2. Hard Rejections
        if not req.is_price_valid:
            reasons.append("Mandatory price validation failed (invalid, negative, or extreme price).")
        if not req.is_timestamp_valid:
            reasons.append("Timestamp validation failed (out of order, excessive drift, or future dated).")
        if req.profile_code in ["ORDER_BOOK_IMBALANCE", "SPREAD_CALCULATION", "LIQUIDITY_ANALYTICS"] and not req.is_order_book_continuous:
            reasons.append("Critical order book continuity broken; sequence gap detected.")
        if req.has_unresolved_cross_feed_conflict:
            reasons.append("Unresolved cross-feed price discrepancy exists between providers.")

        if reasons:
            return "REJECTED", hard_gates, reasons, f"Dataset rejected due to {len(reasons)} hard-gate failure(s)."

        # 3. Score Threshold Gating
        below_scores = []
        if req.reliability_score < min_reliability:
            below_scores.append(f"Reliability ({req.reliability_score}) < required ({min_reliability})")
        if req.completeness_score < min_completeness:
            below_scores.append(f"Completeness ({req.completeness_score}) < required ({min_completeness})")
        if req.freshness_score < min_freshness:
            below_scores.append(f"Freshness ({req.freshness_score}) < required ({min_freshness})")

        # 4. Classification
        if below_scores:
            # If completeness is partial (e.g. 80-89%) or data is slightly stale, restrict rather than fully reject
            if req.completeness_score >= Decimal("75.00") and req.reliability_score >= Decimal("60.00"):
                return (
                    "RESTRICTED",
                    hard_gates,
                    below_scores,
                    f"Dataset restricted: suitable for exploratory or historical analysis but restricted from live execution: {'; '.join(below_scores)}",
                )
            else:
                return (
                    "REJECTED",
                    hard_gates,
                    below_scores,
                    f"Dataset rejected: quality score thresholds breached: {'; '.join(below_scores)}",
                )

        # 5. Warning check
        if req.reliability_score < Decimal("85.00") or req.completeness_score < Decimal("95.00"):
            return (
                "ACCEPTED_WITH_WARNING",
                hard_gates,
                ["Quality scores acceptable but below optimal thresholds."],
                "Accepted for financial calculations with minor quality warning.",
            )

        return "ACCEPTED", hard_gates, [], f"Dataset fully eligible and verified for {req.profile_code}."

