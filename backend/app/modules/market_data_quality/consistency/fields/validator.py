"""
M03.06.03 - Field Consistency Validator.
Validates mathematical and relational integrity between related fields:
- OHLC: High >= Low, High >= Open, High >= Close, Low <= Open, Low <= Close.
- Quote: Non-negative displayed bid/ask sizes, price sanity.
"""

from decimal import Decimal
from typing import Tuple, List, Dict, Any
from backend.app.modules.market_data_quality.consistency.discrepancy.calculator import DiscrepancyCalculator
from backend.app.modules.market_data_quality.consistency.schemas import (
    OHLCFieldValidationInput,
    QuoteFieldValidationInput,
)


class FieldConsistencyValidator:
    """
    Intra-observation field relationship validator.
    """

    @classmethod
    def validate_ohlc(
        cls, ohlc: OHLCFieldValidationInput
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validates OHLC candle boundaries and relationships.
        """
        violations = []
        op = DiscrepancyCalculator.to_decimal(ohlc.open_price)
        hi = DiscrepancyCalculator.to_decimal(ohlc.high_price)
        lo = DiscrepancyCalculator.to_decimal(ohlc.low_price)
        cl = DiscrepancyCalculator.to_decimal(ohlc.close_price)

        if None in (op, hi, lo, cl):
            return False, ["One or more OHLC prices are non-numeric or invalid."], {}

        # 1. High >= Low
        if hi < lo:
            violations.append(f"High price ({hi}) is less than Low price ({lo}).")

        # 2. High >= Open and High >= Close
        if hi < op:
            violations.append(f"High price ({hi}) is less than Open price ({op}).")
        if hi < cl:
            violations.append(f"High price ({hi}) is less than Close price ({cl}).")

        # 3. Low <= Open and Low <= Close
        if lo > op:
            violations.append(f"Low price ({lo}) is greater than Open price ({op}).")
        if lo > cl:
            violations.append(f"Low price ({lo}) is greater than Close price ({cl}).")

        is_valid = len(violations) == 0
        evidence = {
            "open": str(op),
            "high": str(hi),
            "low": str(lo),
            "close": str(cl),
            "violations_count": len(violations),
        }
        return is_valid, violations, evidence

    @classmethod
    def validate_quote(
        cls, quote: QuoteFieldValidationInput
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validates Quote displayed quantities and relationships.
        """
        violations = []
        bp = DiscrepancyCalculator.to_decimal(quote.bid_price)
        ap = DiscrepancyCalculator.to_decimal(quote.ask_price)
        bq = DiscrepancyCalculator.to_decimal(quote.bid_quantity)
        aq = DiscrepancyCalculator.to_decimal(quote.ask_quantity)

        if None in (bp, ap, bq, aq):
            return False, ["One or more Quote fields are non-numeric or invalid."], {}

        # Displayed resting quantities must be non-negative
        if bq < Decimal("0"):
            violations.append(f"Displayed Bid quantity cannot be negative ({bq}).")
        if aq < Decimal("0"):
            violations.append(f"Displayed Ask quantity cannot be negative ({aq}).")

        # Prices must be strictly positive
        if bp <= Decimal("0"):
            violations.append(f"Bid price must be positive ({bp}).")
        if ap <= Decimal("0"):
            violations.append(f"Ask price must be positive ({ap}).")

        is_valid = len(violations) == 0
        evidence = {
            "bid_price": str(bp),
            "ask_price": str(ap),
            "bid_quantity": str(bq),
            "ask_quantity": str(aq),
            "violations_count": len(violations),
        }
        return is_valid, violations, evidence
