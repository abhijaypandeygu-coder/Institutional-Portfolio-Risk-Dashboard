"""
M03.07.03 - Freshness Scoring Calculator.
Quantifies observation ages against required update cadence SLAs.
Piecewise formula:
- Age <= Target -> 100.0
- Target < Age < Maximum -> 100 * (Maximum - Age) / (Maximum - Target)
- Age >= Maximum -> 0.0
Handles EOD historical bars and market closure without false stale penalties.
"""

from decimal import Decimal
from typing import Tuple, Dict, Any
from backend.app.modules.market_data_quality.quality_scoring.schemas import FreshnessEvaluationInput


class FreshnessCalculator:
    """
    Computes piecewise data freshness scores.
    """

    @classmethod
    def calculate_freshness(
        cls, inp: FreshnessEvaluationInput
    ) -> Tuple[Decimal, str, Dict[str, Any]]:
        """
        Calculates (freshness_score, classification, metadata).
        """
        # 1. Market Closed Exception
        if inp.is_market_closed:
            return Decimal("100.00"), "MARKET_CLOSED", {"reason": "Expected inactivity outside trading session"}

        # 2. Historical / EOD Observation
        if inp.is_historical_eod:
            return Decimal("100.00"), "HISTORICAL", {"reason": "Valid daily/weekly historical bar evaluated in EOD context"}

        # 3. Piecewise Real-Time Scoring
        age = Decimal(str(inp.observed_age_ms))
        target = Decimal(str(inp.target_age_ms))
        maximum = Decimal(str(max(inp.maximum_age_ms, inp.target_age_ms + 1)))

        if age <= target:
            fresh_score = Decimal("100.00")
            classification = "FRESH"
        elif age >= maximum:
            fresh_score = Decimal("0.00")
            classification = "CRITICALLY_STALE"
        else:
            # Linear decay
            decay_ratio = (maximum - age) / (maximum - target)
            fresh_score = round(Decimal("100.00") * decay_ratio, 2)
            classification = "AGING" if fresh_score >= Decimal("50.00") else "STALE"

        metadata = {
            "observed_age_ms": inp.observed_age_ms,
            "target_age_ms": inp.target_age_ms,
            "maximum_age_ms": inp.maximum_age_ms,
            "freshness_classification": classification,
        }
        return fresh_score, classification, metadata
