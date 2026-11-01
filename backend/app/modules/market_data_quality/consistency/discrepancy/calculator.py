"""
M03.06.02 - Price Discrepancy Calculator.
Calculates Decimal-precise absolute differences and reference/symmetric percentage divergences.
Enforces tolerance boundaries and severity classifications.
"""

from decimal import Decimal, InvalidOperation
from typing import Tuple, Optional, Dict, Any


class DiscrepancyCalculator:
    """
    Mathematical engine for cross-source price divergence calculations.
    """

    @staticmethod
    def to_decimal(val: Any) -> Optional[Decimal]:
        if val is None:
            return None
        try:
            d = Decimal(str(val))
            return d if d.is_finite() else None
        except (InvalidOperation, ValueError, TypeError):
            return None

    @classmethod
    def calculate_discrepancy(
        cls,
        val_a: Any,
        val_b: Any,
        percentage_tolerance: Decimal = Decimal("0.5000"),  # 0.5% default
        absolute_tolerance: Optional[Decimal] = None,
        method: str = "REFERENCE_PRICE"  # REFERENCE_PRICE or SYMMETRIC_AVERAGE
    ) -> Tuple[Decimal, Optional[Decimal], bool, str]:
        """
        Calculates (abs_diff, pct_diff, exceeds_tolerance, severity).
        """
        dec_a = cls.to_decimal(val_a)
        dec_b = cls.to_decimal(val_b)

        if dec_a is None or dec_b is None:
            return Decimal("0.0"), None, True, "CRITICAL"

        abs_diff = abs(dec_a - dec_b)

        # Calculate percentage difference
        pct_diff: Optional[Decimal] = None
        if method == "SYMMETRIC_AVERAGE":
            denom = (dec_a + dec_b) / Decimal("2.0")
            if denom > Decimal("0"):
                pct_diff = (abs_diff / denom) * Decimal("100.0")
        else:  # REFERENCE_PRICE (uses Source A as reference)
            if dec_a > Decimal("0"):
                pct_diff = (abs_diff / dec_a) * Decimal("100.0")

        # Evaluate tolerances
        exceeds = False
        if pct_diff is not None and pct_diff > percentage_tolerance:
            exceeds = True

        if absolute_tolerance is not None and abs_diff > absolute_tolerance:
            exceeds = True

        # Assign severity
        if not exceeds:
            severity = "PASS"
        elif pct_diff is not None and pct_diff > (percentage_tolerance * Decimal("2.0")):
            severity = "CRITICAL"
        else:
            severity = "WARNING"

        return abs_diff, pct_diff, exceeds, severity
