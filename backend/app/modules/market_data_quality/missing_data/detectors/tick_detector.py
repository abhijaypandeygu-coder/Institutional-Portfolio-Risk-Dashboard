"""
Module 03.01: Missing Data Detection - Missing Tick Detector.
Identifies sequence discontinuities in tick streams and detects prolonged quote/trade inactivity
while respecting provider capabilities and exchange session status.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.app.modules.market_data_quality.missing_data.models import (
    ExpectationStatus,
    IncidentSeverity,
    IncidentStatus,
    IssueType,
    MissingDataIncident,
)
from backend.app.modules.market_data_quality.missing_data.policies.resolver import ExpectationPolicyResolver


class MissingTickDetector:
    """
    Subfeature M03.01.01:
    - Sequence Gap Detection (e.g. expected 1004, observed 1006).
    - Quote/Trade Inactivity Detection (beyond configured grace period).
    """

    def __init__(self, policy_resolver: Optional[ExpectationPolicyResolver] = None):
        self.resolver = policy_resolver or ExpectationPolicyResolver()

    def detect_sequence_gap(
        self,
        feed_id: str,
        provider_id: str,
        instrument_id: str,
        exchange: str,
        expected_seq: int,
        observed_seq: int,
        channel: str = "TICK",
        event_time: Optional[datetime] = None,
    ) -> Optional[MissingDataIncident]:
        """Detects missing sequence range if observed_seq > expected_seq."""
        if observed_seq <= expected_seq:
            return None

        event_time = event_time or datetime.now(timezone.utc)
        status, reason = self.resolver.evaluate_expectation(
            provider_id=provider_id,
            exchange=exchange,
            channel=channel,
            frequency="REALTIME",
            event_time_utc=event_time,
            instrument_id=instrument_id,
            feed_id=feed_id,
        )

        if status != ExpectationStatus.EXPECTED:
            return None  # Do not raise incident if data was not expected or market closed!

        missing_count = observed_seq - expected_seq
        incident_key = f"gap-{feed_id}-{instrument_id}-{channel}-{expected_seq}-{observed_seq}"

        return MissingDataIncident(
            incident_key=incident_key,
            instrument_id=instrument_id,
            feed_id=feed_id,
            provider_id=provider_id,
            exchange=exchange,
            data_type=channel,
            issue_type=IssueType.SEQUENCE_GAP.value,
            missing_start=str(expected_seq),
            missing_end=str(observed_seq - 1),
            missing_count=missing_count,
            severity=IncidentSeverity.CRITICAL.value if missing_count > 5 else IncidentSeverity.WARNING.value,
            evidence={
                "expected_sequence": expected_seq,
                "observed_sequence": observed_seq,
                "missing_range": f"{expected_seq}..{observed_seq - 1}",
                "event_time": event_time.isoformat(),
            },
        )

    def detect_inactivity(
        self,
        feed_id: str,
        provider_id: str,
        instrument_id: str,
        exchange: str,
        last_event_time: datetime,
        current_time: datetime,
        inactivity_threshold_seconds: int = 300,
        channel: str = "TICK",
    ) -> Optional[MissingDataIncident]:
        """Detects absent updates when elapsed time exceeds the inactivity threshold during active sessions."""
        status, reason = self.resolver.evaluate_expectation(
            provider_id=provider_id,
            exchange=exchange,
            channel=channel,
            frequency="REALTIME",
            event_time_utc=current_time,
            instrument_id=instrument_id,
            feed_id=feed_id,
        )

        if status != ExpectationStatus.EXPECTED:
            return None

        elapsed = (current_time - last_event_time).total_seconds()
        if elapsed <= inactivity_threshold_seconds:
            return None

        incident_key = f"inactivity-{feed_id}-{instrument_id}-{channel}-{int(last_event_time.timestamp())}"
        return MissingDataIncident(
            incident_key=incident_key,
            instrument_id=instrument_id,
            feed_id=feed_id,
            provider_id=provider_id,
            exchange=exchange,
            data_type=channel,
            issue_type=IssueType.MISSING_TICK.value if channel == "TICK" else IssueType.MISSING_TRADE.value,
            missing_start=last_event_time.isoformat(),
            missing_end=current_time.isoformat(),
            missing_count=1,
            severity=IncidentSeverity.WARNING.value,
            evidence={
                "last_event_timestamp": last_event_time.isoformat(),
                "current_timestamp": current_time.isoformat(),
                "elapsed_seconds": elapsed,
                "threshold_seconds": inactivity_threshold_seconds,
            },
        )
