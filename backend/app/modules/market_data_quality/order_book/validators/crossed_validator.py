"""
M03.04.01 - Crossed Order Book Validator.
Identifies Best Bid > Best Ask conditions, calculates cross amount, distinguishes
transient vs confirmed crosses, and handles auction sessions.
"""

from decimal import Decimal
from typing import Optional, Dict, Any
from backend.app.modules.market_data_quality.order_book.semantics.venue_resolver import VenuePolicyResolver


class CrossedBookValidator:
    """
    Validates whether an order book is crossed (Best Bid > Best Ask).
    """

    @staticmethod
    def evaluate(
        best_bid: Optional[Decimal],
        best_ask: Optional[Decimal],
        session_phase: str,
        venue: Optional[str] = None,
        duration_ms: Optional[int] = None,
        max_transient_ms: int = 50,
        allow_auction_cross: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates crossed state and returns validation flags and classifications.
        """
        if best_bid is None or best_ask is None:
            return {
                "is_crossed": False,
                "cross_amount": None,
                "classification": "UNCROSSED",
                "is_valid": True,
                "spread_eligible": True,
                "imbalance_eligible": True,
                "depth_eligible": True,
                "liquidity_eligible": True,
                "details": "One or both sides empty; cannot be crossed."
            }

        is_auction = VenuePolicyResolver.is_auction_phase(session_phase)
        policy = VenuePolicyResolver.get_policy(venue)

        # Check crossed condition
        if best_bid > best_ask:
            cross_amount = best_bid - best_ask

            if is_auction:
                # Crossed books during auction reflect call market order accumulation prior to clearing
                if allow_auction_cross and policy.get("allow_auction_cross", True):
                    return {
                        "is_crossed": True,
                        "cross_amount": cross_amount,
                        "classification": "AUCTION_CROSS_VALID",
                        "is_valid": True,
                        "spread_eligible": False,  # Bid-ask spread during auction is not standard continuous spread
                        "imbalance_eligible": True,  # Auction indicative imbalance is valid
                        "depth_eligible": True,
                        "liquidity_eligible": False,
                        "details": f"Crossed book permitted during auction phase ({session_phase}). Cross amount: {cross_amount}"
                    }

            # Continuous session cross
            curr_duration = duration_ms or 0
            configured_max_ms = max_transient_ms if max_transient_ms is not None else policy.get("max_transient_cross_ms", 50)

            if curr_duration <= configured_max_ms and configured_max_ms > 0:
                classification = "CROSSED_TRANSIENT"
                severity = "WARNING"
            else:
                classification = "CROSSED_CONFIRMED"
                severity = "ERROR"

            return {
                "is_crossed": True,
                "cross_amount": cross_amount,
                "classification": classification,
                "is_valid": False,
                "spread_eligible": False,
                "imbalance_eligible": False,
                "depth_eligible": False,
                "liquidity_eligible": False,
                "severity": severity,
                "details": f"Crossed book detected in {session_phase}: Best Bid ({best_bid}) > Best Ask ({best_ask}). Cross amount: {cross_amount}."
            }

        return {
            "is_crossed": False,
            "cross_amount": None,
            "classification": "UNCROSSED",
            "is_valid": True,
            "spread_eligible": True,
            "imbalance_eligible": True,
            "depth_eligible": True,
            "liquidity_eligible": True,
            "details": f"Book uncrossed: Best Bid ({best_bid}) <= Best Ask ({best_ask})."
        }
