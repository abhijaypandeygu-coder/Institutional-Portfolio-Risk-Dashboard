"""
M03.07.01 - Feed Reliability Scoring Calculator.
Measures operational reliability from availability, timeliness, and operational error rates.
Availability = (Eligible Duration - Outage Duration) / Eligible Duration * 100
Timeliness = (Timely Observations / Eligible Observations) * 100
Error Score = (1 - (Failed Ops / Eligible Ops)) * 100
Reliability = (wA * Availability) + (wT * Timeliness) + (wE * Error Score)
"""

from decimal import Decimal
from typing import Tuple, Dict, Any
from backend.app.modules.market_data_quality.quality_scoring.schemas import FeedReliabilityInput


class ReliabilityCalculator:
    """
    Computes feed operational availability, timeliness, and error rate scores.
    """

    @classmethod
    def calculate_reliability(
        cls,
        inp: FeedReliabilityInput,
        weight_avail: Decimal = Decimal("0.4000"),
        weight_time: Decimal = Decimal("0.3500"),
        weight_error: Decimal = Decimal("0.2500"),
    ) -> Tuple[Decimal, Decimal, Decimal, Decimal, str, Dict[str, Any]]:
        """
        Calculates (availability, timeliness, error_score, reliability_score, classification, metadata).
        """
        # 1. Availability Score
        if inp.expected_duration_seconds > 0:
            active_sec = max(0, inp.expected_duration_seconds - inp.unavailable_duration_seconds)
            avail_score = (Decimal(str(active_sec)) / Decimal(str(inp.expected_duration_seconds))) * Decimal("100.0")
        else:
            avail_score = Decimal("100.0")  # Outside scheduled operating window / no expected downtime
        avail_score = min(Decimal("100.0"), max(Decimal("0.0"), avail_score))

        # 2. Timeliness Score
        if inp.eligible_expected_observations > 0:
            time_score = (Decimal(str(inp.timely_observations)) / Decimal(str(inp.eligible_expected_observations))) * Decimal("100.0")
        else:
            time_score = Decimal("100.0")
        time_score = min(Decimal("100.0"), max(Decimal("0.0"), time_score))

        # 3. Error Score
        if inp.eligible_operations > 0:
            err_rate = Decimal(str(inp.failed_operations)) / Decimal(str(inp.eligible_operations))
            err_score = (Decimal("1.0") - min(Decimal("1.0"), err_rate)) * Decimal("100.0")
        else:
            err_score = Decimal("100.0")
        err_score = min(Decimal("100.0"), max(Decimal("0.0"), err_score))

        # 4. Weighted Reliability Score
        rel_score = (weight_avail * avail_score) + (weight_time * time_score) + (weight_error * err_score)
        rel_score = round(min(Decimal("100.0"), max(Decimal("0.0"), rel_score)), 2)

        # 5. Classification
        if rel_score >= Decimal("95.00"):
            classification = "EXCELLENT"
        elif rel_score >= Decimal("85.00"):
            classification = "GOOD"
        elif rel_score >= Decimal("70.00"):
            classification = "ACCEPTABLE"
        elif rel_score >= Decimal("50.00"):
            classification = "POOR"
        else:
            classification = "UNRELIABLE"

        metadata = {
            "weight_availability": str(weight_avail),
            "weight_timeliness": str(weight_time),
            "weight_error": str(weight_error),
            "availability_score": str(avail_score.quantize(Decimal("0.01"))),
            "timeliness_score": str(time_score.quantize(Decimal("0.01"))),
            "error_score": str(err_score.quantize(Decimal("0.01"))),
        }
        return (
            avail_score.quantize(Decimal("0.01")),
            time_score.quantize(Decimal("0.01")),
            err_score.quantize(Decimal("0.01")),
            rel_score,
            classification,
            metadata,
        )

