"""
Exchange and venue regulatory policies for order book validation.
Understands continuous vs auction trading mechanics across NSE, BSE, NYSE, NASDAQ.
"""

from typing import Dict, Any


class VenuePolicyResolver:
    """
    Provides venue-specific rules for crossed/locked books and tick/lot sizes.
    """

    DEFAULT_POLICY = {
        "allow_auction_cross": True,
        "allow_auction_lock": True,
        "max_transient_cross_ms": 50,
        "max_transient_lock_ms": 100,
        "allow_fractional_shares": False,
        "default_lot_size": 1.0,
    }

    VENUE_POLICIES: Dict[str, Dict[str, Any]] = {
        "NSE": {
            "allow_auction_cross": True,
            "allow_auction_lock": True,
            "max_transient_cross_ms": 0,       # Strict continuous uncrossed on single exchange
            "max_transient_lock_ms": 0,        # Continuous locks strictly prohibited (immediate execution or rejection)
            "allow_fractional_shares": False,  # Indian equities do not permit fractional shares
            "default_lot_size": 1.0,
        },
        "BSE": {
            "allow_auction_cross": True,
            "allow_auction_lock": True,
            "max_transient_cross_ms": 0,
            "max_transient_lock_ms": 0,
            "allow_fractional_shares": False,
            "default_lot_size": 1.0,
        },
        "NYSE": {
            "allow_auction_cross": True,
            "allow_auction_lock": True,
            "max_transient_cross_ms": 50,      # Reg NMS transient inter-market crossing during propagation
            "max_transient_lock_ms": 100,      # Reg NMS Rule 610 lock avoidance with slight transient allowance
            "allow_fractional_shares": True,   # Supported for retail brokers
            "default_lot_size": 1.0,
        },
        "NASDAQ": {
            "allow_auction_cross": True,
            "allow_auction_lock": True,
            "max_transient_cross_ms": 50,
            "max_transient_lock_ms": 100,
            "allow_fractional_shares": True,
            "default_lot_size": 1.0,
        },
        "SIMULATOR": {
            "allow_auction_cross": True,
            "allow_auction_lock": True,
            "max_transient_cross_ms": 100,
            "max_transient_lock_ms": 200,
            "allow_fractional_shares": True,
            "default_lot_size": 1.0,
        }
    }

    @classmethod
    def get_policy(cls, venue: str = None) -> Dict[str, Any]:
        if not venue:
            return cls.DEFAULT_POLICY
        return cls.VENUE_POLICIES.get(venue.upper(), cls.DEFAULT_POLICY)

    @classmethod
    def is_auction_phase(cls, session_phase: str) -> bool:
        if not session_phase:
            return False
        normalized = session_phase.upper()
        return any(term in normalized for term in ["AUCTION", "CALL", "PRE_OPEN", "POST_CLOSE", "OPENING"])
