"""
M03.04.03 - Invalid Quantity Validator.
Validates displayed sizes across order book levels and deltas.
Rejects null, non-numeric, negative, infinite quantities, and rejects 0-quantity in active snapshots,
while permitting 0-quantity in delta deletion operations.
"""

from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any, Tuple
from backend.app.modules.market_data_quality.order_book.schemas import OrderBookLevelInput, OrderBookDeltaInput


class QuantityValidator:
    """
    Validates order book displayed quantities.
    """

    @staticmethod
    def parse_quantity(val: Any) -> Tuple[Optional[Decimal], Optional[str]]:
        """
        Parses and validates a numeric quantity.
        Returns (parsed_decimal, error_message).
        """
        if val is None:
            return None, "Quantity cannot be null."
        try:
            d = Decimal(str(val))
            if not d.is_finite():
                return None, f"Quantity must be a finite number: got {val}."
            return d, None
        except (InvalidOperation, ValueError, TypeError):
            return None, f"Quantity cannot be parsed as a valid numeric decimal: got {val}."

    @classmethod
    def validate_snapshot_levels(
        cls,
        levels: Optional[List[OrderBookLevelInput]],
        side: str,
        allow_fractional: bool = False,
        min_lot_size: Decimal = Decimal("1.0"),
        max_order_quantity: Optional[Decimal] = None
    ) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """
        Validates quantities within snapshot levels.
        Snapshots must NEVER contain 0 or negative quantities.
        """
        if not levels:
            return True, [], []

        errors = []
        parsed = []
        is_valid = True

        for idx, lvl in enumerate(levels, start=1):
            q_dec, err = cls.parse_quantity(lvl.quantity)
            if err:
                is_valid = False
                errors.append(f"{side} level {idx}: {err}")
                continue

            if q_dec <= Decimal("0"):
                is_valid = False
                errors.append(f"{side} level {idx} has invalid zero or negative quantity ({q_dec}) in snapshot.")
                continue

            if not allow_fractional:
                if q_dec % Decimal("1") != Decimal("0"):
                    is_valid = False
                    errors.append(f"{side} level {idx} quantity ({q_dec}) contains fractional shares not permitted for venue.")

            if min_lot_size and min_lot_size > Decimal("0"):
                if q_dec < min_lot_size:
                    is_valid = False
                    errors.append(f"{side} level {idx} quantity ({q_dec}) is below minimum lot size ({min_lot_size}).")

            if max_order_quantity and q_dec > max_order_quantity:
                is_valid = False
                errors.append(f"{side} level {idx} quantity ({q_dec}) exceeds maximum permitted quantity ({max_order_quantity}).")

            parsed.append({
                "side": side,
                "price": lvl.price,
                "quantity": q_dec,
                "level_position": lvl.level_position or idx
            })

        return is_valid, errors, parsed

    @classmethod
    def validate_delta(
        cls,
        delta: Optional[OrderBookDeltaInput],
        allow_fractional: bool = False,
        min_lot_size: Decimal = Decimal("1.0"),
        max_order_quantity: Optional[Decimal] = None
    ) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
        """
        Validates an incremental order book delta update.
        Allows quantity == 0 ONLY if operation is 'DELETE' or equivalent quantity removal.
        """
        if not delta:
            return True, [], None

        q_dec, err = cls.parse_quantity(delta.quantity)
        if err:
            return False, [f"Delta quantity error: {err}"], None

        op = (delta.operation or "UPDATE").upper()

        if q_dec < Decimal("0"):
            return False, [f"Delta quantity cannot be negative ({q_dec})."], None

        if q_dec == Decimal("0"):
            if op not in ["DELETE", "REMOVE", "DROP"]:
                return False, [f"Zero quantity in delta is only allowed for DELETE operation, got operation '{op}'."], None

        if q_dec > Decimal("0"):
            if not allow_fractional and (q_dec % Decimal("1") != Decimal("0")):
                return False, [f"Delta quantity ({q_dec}) contains fractional shares not permitted for venue."], None

            if min_lot_size and q_dec < min_lot_size and op != "DELETE":
                return False, [f"Delta quantity ({q_dec}) is below minimum lot size ({min_lot_size})."], None

            if max_order_quantity and q_dec > max_order_quantity:
                return False, [f"Delta quantity ({q_dec}) exceeds maximum permitted quantity ({max_order_quantity})."], None

        parsed = {
            "side": delta.side.upper(),
            "price": delta.price,
            "quantity": q_dec,
            "operation": op,
            "sequence_number": delta.sequence_number
        }
        return True, [], parsed
