"""
M03.04.02 - Locked Order Book Validator.
Identifies Best Bid == Best Ask conditions, tracks duration, enforces venue-specific
rules (e.g. Reg NMS Rule 610, SEBI auction vs continuous), and manages conditional metric eligibility.
"""

from decimal import Decimal
from typing import Optional, Dict, Any
from backend.app.modules.market_data_quality.order_book.semantics.venue_resolver import VenuePolicyResolver


class LockedBookValidator:
    """
    Validates whether an order book is locked (Best Bid == Best Ask).
    """

    @staticmethod
    def evaluate(
        best_bid: Optional[Decimal],
        best_ask: Optional[Decimal],
        session_phase: str,
        venue: Optional[str] = None,
        duration_ms: Optional[int] = None,
        max_transient_ms: int = 100,
        allow_auction_lock: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates locked state and returns validation flags and classifications.
        """
        if best_bid is None or best_ask is None:
            return {
                "is_locked": False,
                "classification": "UNLOCKED",
                "is_valid": True,
                "spread_eligible": True,
                "imbalance_eligible": True,
                "depth_eligible": True,
                "liquidity_eligible": True,
                "details": "One or both sides empty; cannot be locked."
            }

        is_auction = VenuePolicyResolver.is_auction_phase(session_phase)
        policy = VenuePolicyResolver.get_policy(venue)

        # Check locked condition
        if best_bid == best_ask:
            if is_auction:
                if allow_auction_lock and policy.get("allow_auction_lock", True):
                    return {
                        "is_locked": True,
                        "classification": "LOCKED_AUCTION_VALID",
                        "is_valid": True,
                        "spread_eligible": False,  # Zero spread is indicative auction equilibrium
                        "imbalance_eligible": True,
                        "depth_eligible": True,
                        "liquidity_eligible": False,
                        "severity": "INFO",
                        "details": f"Locked book indicative of auction equilibrium at price {best_bid}."
                    }

            # Continuous session lock
            curr_duration = duration_ms or 0
            configured_max_ms = max_transient_ms if max_transient_ms is not None else policy.get("max_transient_lock_ms", 100)

            if curr_duration <= configured_max_ms and configured_max_ms > 0:
                classification = "LOCKED_TRANSIENT"
                severity = "WARNING"
                is_valid = True
            else:
                classification = "LOCKED_SUSPICIOUS"
                severity = "ERROR"
                is_valid = False

            return {
                "is_locked": True,
                "classification": classification,
                "is_valid": is_valid,
                "spread_eligible": False,     # Spread is 0.00, dangerous for percent spread / divisor calculations
                "imbalance_eligible": True,   # Queue sizes at locked price remain analytically informative
                "depth_eligible": True,
                "liquidity_eligible": False,
                "severity": severity,
                "details": f"Locked book detected in {session_phase}: Best Bid ({best_bid}) == Best Ask ({best_ask}). Duration: {curr_duration}ms."
            }

        return {
            "is_locked": False,
            "classification": "UNLOCKED",
            "is_valid": True,
            "spread_eligible": True,
            "imbalance_eligible": True,
            "depth_eligible": True,
            "liquidity_eligible": True,
            "details": f"Book unlocked: Best Bid ({best_bid}) < Best Ask ({best_ask})."
        }
