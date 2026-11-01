"""
Order Book Structure & Monotonicity Validator.
Validates that:
- Bids are strictly descending by price: Bid_1 > Bid_2 > ... > Bid_n
- Asks are strictly ascending by price: Ask_1 < Ask_2 < ... < Ask_n
- No duplicate price levels exist on either side.
"""

from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple, Dict, Any
from backend.app.modules.market_data_quality.order_book.schemas import OrderBookLevelInput


class StructureValidator:
    """
    Validates internal monotonicity, sorting, and duplicate price levels.
    """

    @staticmethod
    def parse_price(val: Any) -> Tuple[Optional[Decimal], Optional[str]]:
        if val is None:
            return None, "Price cannot be null."
        try:
            d = Decimal(str(val))
            if not d.is_finite():
                return None, f"Price must be finite: got {val}."
            if d <= Decimal("0"):
                return None, f"Price must be positive: got {val}."
            return d, None
        except (InvalidOperation, ValueError, TypeError):
            return None, f"Invalid price format: got {val}."

    @classmethod
    def validate_levels_structure(
        cls,
        levels: Optional[List[OrderBookLevelInput]],
        side: str
    ) -> Tuple[bool, List[str], List[Decimal]]:
        """
        Validates sorting and uniqueness for order book levels.
        Bids must be strictly descending. Asks must be strictly ascending.
        """
        if not levels:
            return True, [], []

        is_valid = True
        errors = []
        prices = []
        seen_prices = set()

        side_upper = side.upper()

        for idx, lvl in enumerate(levels, start=1):
            p_dec, err = cls.parse_price(lvl.price)
            if err:
                is_valid = False
                errors.append(f"{side_upper} level {idx}: {err}")
                continue

            # Check duplicate price
            if p_dec in seen_prices:
                is_valid = False
                errors.append(f"{side_upper} contains duplicate price level at {p_dec}.")
            seen_prices.add(p_dec)

            # Check monotonicity against previous price
            if prices:
                prev_p = prices[-1]
                if side_upper == "BID":
                    if p_dec >= prev_p:
                        is_valid = False
                        errors.append(f"Bid levels not strictly descending: level {idx} ({p_dec}) >= previous level ({prev_p}).")
                elif side_upper == "ASK":
                    if p_dec <= prev_p:
                        is_valid = False
                        errors.append(f"Ask levels not strictly ascending: level {idx} ({p_dec}) <= previous level ({prev_p}).")

            prices.append(p_dec)

        return is_valid, errors, prices
