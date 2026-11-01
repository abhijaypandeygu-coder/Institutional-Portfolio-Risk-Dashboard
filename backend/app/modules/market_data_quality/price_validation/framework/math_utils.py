"""
Module 03.02: Price Validation - Decimal Arithmetic Utilities.
Provides strictly Decimal-compatible, precision-aware calculations for:
- Percentage price change
- Absolute price difference
- Multi-provider percentage discrepancy
- Divisibility and tick-size alignment without floating-point modulo
- OHLC relationship validation
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Tuple


def to_decimal(val: any) -> Optional[Decimal]:
    """Safely parse input value to Decimal or return None if malformed/non-finite."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        if val.is_nan() or val.is_infinite():
            return None
        return val
    try:
        s = str(val).strip()
        if not s or s.lower() in ("nan", "inf", "-inf", "+inf", "null", "none"):
            return None
        d = Decimal(s)
        if d.is_nan() or d.is_infinite():
            return None
        return d
    except (InvalidOperation, ValueError, TypeError):
        return None


def calculate_percentage_change(current: Decimal, reference: Decimal) -> Optional[Decimal]:
    """
    Calculate ((Current Price - Reference Price) / Reference Price) * 100.
    Returns None if reference price is zero or non-positive.
    """
    if reference <= Decimal("0"):
        return None
    return ((current - reference) / reference) * Decimal("100")


def calculate_absolute_difference(current: Decimal, reference: Decimal) -> Decimal:
    """Return |Current - Reference|."""
    return abs(current - reference)


def calculate_cross_source_discrepancy(
    price_a: Decimal, price_b: Decimal, reference_denominator: Optional[Decimal] = None
) -> Tuple[Decimal, Optional[Decimal]]:
    """
    Calculate absolute difference and percentage discrepancy:
    (|Price A - Price B| / Denominator) * 100.
    If reference_denominator is omitted, max(price_a, price_b) is used if positive.
    """
    abs_diff = abs(price_a - price_b)
    denom = reference_denominator if reference_denominator is not None else max(price_a, price_b)
    if denom <= Decimal("0"):
        return abs_diff, None
    pct_disc = (abs_diff / denom) * Decimal("100")
    return abs_diff, pct_disc


def is_tick_size_valid(price: Decimal, tick_size: Decimal) -> bool:
    """
    Check whether price aligns exactly with tick_size.
    Uses integer quantization: (price / tick_size) must equal its integer round.
    Avoids binary floating-point modulo inaccuracies.
    """
    if tick_size <= Decimal("0"):
        return False
    quotient = price / tick_size
    return quotient == quotient.to_integral_value(rounding=ROUND_HALF_UP)


def count_decimal_places(price: Decimal) -> int:
    """Return the number of digits after the decimal point."""
    sign, digits, exponent = price.as_tuple()
    if exponent >= 0:
        return 0
    return abs(exponent)


def is_ohlc_structurally_valid(
    open_p: Decimal, high_p: Decimal, low_p: Decimal, close_p: Decimal
) -> Tuple[bool, Optional[str]]:
    """
    Validate OHLC invariants:
    - Open > 0, Close > 0
    - High >= Open, High >= Close, High >= Low
    - Low <= Open, Low <= Close
    """
    if open_p <= Decimal("0"):
        return False, "Open price must be positive"
    if close_p <= Decimal("0"):
        return False, "Close price must be positive"
    if high_p < low_p:
        return False, f"High ({high_p}) is lower than Low ({low_p})"
    if high_p < open_p:
        return False, f"High ({high_p}) is lower than Open ({open_p})"
    if high_p < close_p:
        return False, f"High ({high_p}) is lower than Close ({close_p})"
    if low_p > open_p:
        return False, f"Low ({low_p}) is higher than Open ({open_p})"
    if low_p > close_p:
        return False, f"Low ({low_p}) is higher than Close ({close_p})"
    return True, None
