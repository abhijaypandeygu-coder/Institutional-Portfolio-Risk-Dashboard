"""
Module 03.01: Missing Data Detection - Quantitative Coverage Window Calculator.
Computes expected vs observed data availability units, calculates coverage percentages,
and classifies completeness without division-by-zero errors or false 100% metrics.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from backend.app.modules.market_data_quality.missing_data.models import (
    CoverageStatus,
    CoverageWindow,
)


class CoverageCalculator:
    """
    Subfeature M03.01.04:
    Coverage Percentage = (Valid Observed Units / Eligible Expected Units) * 100.
    """

    @staticmethod
    def calculate_coverage(
        instrument_id: str,
        feed_id: str,
        provider_id: str,
        exchange: str,
        data_type: str,
        interval_type: str,
        window_start: datetime,
        window_end: datetime,
        expected_units: int,
        observed_units: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CoverageWindow:
        # Validate units
        observed_clean = max(0, min(observed_units, expected_units))
        missing_units = max(0, expected_units - observed_clean)

        if expected_units <= 0:
            percentage = 0.0
            status = CoverageStatus.NOT_APPLICABLE.value
        else:
            percentage = round((observed_clean / expected_units) * 100.0, 2)
            if percentage >= 99.9:
                status = CoverageStatus.COMPLETE.value
            elif percentage > 0.0:
                status = CoverageStatus.PARTIAL.value
            else:
                status = CoverageStatus.MISSING.value

        return CoverageWindow(
            instrument_id=instrument_id,
            feed_id=feed_id,
            provider_id=provider_id,
            exchange=exchange,
            data_type=data_type,
            interval_type=interval_type,
            window_start=window_start,
            window_end=window_end,
            expected_units=expected_units,
            observed_units=observed_clean,
            missing_units=missing_units,
            coverage_percentage=percentage,
            coverage_status=status,
            calculation_metadata=metadata or {},
        )
