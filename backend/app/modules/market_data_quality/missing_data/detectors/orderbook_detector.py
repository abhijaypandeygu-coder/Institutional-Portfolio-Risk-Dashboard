"""
Module 03.01: Missing Data Detection - Missing Order Book Update & Stale Book Detector.
Monitors M02 order-book reconstruction state, sequence boundaries, and detects prolonged staleness.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from backend.app.modules.market_data_quality.missing_data.models import (
    ExpectationStatus,
    IncidentSeverity,
    IncidentStatus,
    IssueType,
    MissingDataIncident,
)
from backend.app.modules.market_data_quality.missing_data.policies.resolver import ExpectationPolicyResolver


class MissingOrderBookDetector:
    """
    Subfeature M03.01.03:
    - Order Book Sequence Discontinuity & Delta Gaps.
    - Stale Order Book Detection (unchanged/un-updated book during active market sessions).
    """

    def __init__(self, policy_resolver: Optional[ExpectationPolicyResolver] = None):
        self.resolver = policy_resolver or ExpectationPolicyResolver()

    def check_order_book_status(
        self,
        instrument_id: str,
        feed_id: str,
        provider_id: str,
        exchange: str,
        is_synchronized: bool,
        last_sequence: int,
        last_update_timestamp: datetime,
        current_time: datetime,
        stale_threshold_seconds: int = 60,
    ) -> Optional[MissingDataIncident]:
        """
        Evaluates book continuity:
        1. If is_synchronized is False -> Unsynchronized / Sequence Gap incident.
        2. If elapsed time > stale_threshold_seconds during active session -> Stale Book incident.
        """
        # Ensure data is expected
        status, reason = self.resolver.evaluate_expectation(
            provider_id=provider_id,
            exchange=exchange,
            channel="ORDER_BOOK_L2",
            frequency="REALTIME",
            event_time_utc=current_time,
            instrument_id=instrument_id,
            feed_id=feed_id,
        )

        if status != ExpectationStatus.EXPECTED:
            return None

        # 1. Unsynchronized book (broken snapshot/delta sequence)
        if not is_synchronized:
            incident_key = f"ob-unsync-{feed_id}-{instrument_id}-{last_sequence}"
            return MissingDataIncident(
                incident_key=incident_key,
                instrument_id=instrument_id,
                feed_id=feed_id,
                provider_id=provider_id,
                exchange=exchange,
                data_type="ORDER_BOOK_L2",
                issue_type=IssueType.MISSING_ORDER_BOOK_UPDATE.value,
                missing_start=str(last_sequence),
                missing_end=str(last_sequence + 1),
                missing_count=1,
                severity=IncidentSeverity.CRITICAL.value,
                evidence={
                    "is_synchronized": False,
                    "last_valid_sequence": last_sequence,
                    "error": "Sequence continuity broken; order book resynchronization required.",
                },
            )

        # 2. Stale order book during active market
        elapsed = (current_time - last_update_timestamp).total_seconds()
        if elapsed > stale_threshold_seconds:
            incident_key = f"ob-stale-{feed_id}-{instrument_id}-{int(last_update_timestamp.timestamp())}"
            return MissingDataIncident(
                incident_key=incident_key,
                instrument_id=instrument_id,
                feed_id=feed_id,
                provider_id=provider_id,
                exchange=exchange,
                data_type="ORDER_BOOK_L2",
                issue_type=IssueType.STALE_ORDER_BOOK.value,
                missing_start=last_update_timestamp.isoformat(),
                missing_end=current_time.isoformat(),
                missing_count=1,
                severity=IncidentSeverity.HIGH.value,
                evidence={
                    "last_update_timestamp": last_update_timestamp.isoformat(),
                    "elapsed_seconds": elapsed,
                    "threshold_seconds": stale_threshold_seconds,
                    "last_sequence": last_sequence,
                },
            )

        return None
