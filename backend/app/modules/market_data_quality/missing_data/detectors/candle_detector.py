"""
Module 03.01: Missing Data Detection - Missing Candle Detector.
Identifies absent OHLCV bars by comparing expected session timestamps against observed database candles,
taking into account holidays, session hours, and provider limitations (e.g. compact Alpha Vantage history).
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Set
from uuid import uuid4

from backend.app.modules.market_data_quality.missing_data.integrations.calendar_interface import ExchangeSessionResolver
from backend.app.modules.market_data_quality.missing_data.models import (
    ExpectationStatus,
    IncidentSeverity,
    IncidentStatus,
    IssueType,
    MissingDataIncident,
)
from backend.app.modules.market_data_quality.missing_data.policies.resolver import ExpectationPolicyResolver


class MissingCandleDetector:
    """
    Subfeature M03.01.02:
    - Generates expected daily and intraday candle timestamps using exchange calendar rules.
    - Identifies missing bars while ignoring holidays and closed session periods.
    """

    def __init__(self, policy_resolver: Optional[ExpectationPolicyResolver] = None):
        self.resolver = policy_resolver or ExpectationPolicyResolver()

    def detect_missing_daily_candles(
        self,
        instrument_id: str,
        feed_id: str,
        provider_id: str,
        exchange: str,
        start_date: date,
        end_date: date,
        observed_dates: Set[date],
    ) -> List[MissingDataIncident]:
        """Compares expected trading days against observed daily OHLCV bars."""
        expected_days = ExchangeSessionResolver.generate_expected_trading_days(exchange, start_date, end_date)
        incidents = []

        for d in expected_days:
            if d not in observed_dates:
                # Missing daily bar
                incident_key = f"candle-{feed_id}-{instrument_id}-1d-{d.isoformat()}"
                incident = MissingDataIncident(
                    incident_key=incident_key,
                    instrument_id=instrument_id,
                    feed_id=feed_id,
                    provider_id=provider_id,
                    exchange=exchange,
                    data_type="OHLCV",
                    issue_type=IssueType.MISSING_CANDLE.value,
                    missing_start=d.isoformat(),
                    missing_end=d.isoformat(),
                    missing_count=1,
                    severity=IncidentSeverity.WARNING.value,
                    evidence={
                        "interval": "1d",
                        "trading_date": d.isoformat(),
                        "calendar_validation": f"Confirmed open trading day for exchange {exchange}",
                    },
                )
                incidents.append(incident)

        return incidents

    def detect_missing_intraday_candles(
        self,
        instrument_id: str,
        feed_id: str,
        provider_id: str,
        exchange: str,
        trading_date: date,
        interval_minutes: int,
        observed_timestamps: Set[datetime],
    ) -> List[MissingDataIncident]:
        """Compares expected intraday candle timestamps against observed timestamps."""
        # Check if provider supports intraday
        dummy_time = datetime.combine(trading_date, datetime.min.time(), tzinfo=timezone.utc)
        status, reason = self.resolver.evaluate_expectation(
            provider_id=provider_id,
            exchange=exchange,
            channel="OHLCV",
            frequency=f"{interval_minutes}m",
            event_time_utc=dummy_time,
            instrument_id=instrument_id,
            feed_id=feed_id,
        )

        if status == ExpectationStatus.NOT_SUPPORTED:
            # Alpha Vantage Free does not support intraday, skip!
            return []

        expected_stamps = ExchangeSessionResolver.generate_expected_candle_timestamps(
            exchange, trading_date, interval_minutes
        )
        incidents = []

        for exp in expected_stamps:
            # Check presence (allowing second precision tolerance)
            match = any(abs((obs - exp).total_seconds()) < 30 for obs in observed_timestamps)
            if not match:
                incident_key = f"candle-{feed_id}-{instrument_id}-{interval_minutes}m-{int(exp.timestamp())}"
                incident = MissingDataIncident(
                    incident_key=incident_key,
                    instrument_id=instrument_id,
                    feed_id=feed_id,
                    provider_id=provider_id,
                    exchange=exchange,
                    data_type="OHLCV",
                    issue_type=IssueType.MISSING_CANDLE.value,
                    missing_start=exp.isoformat(),
                    missing_end=(exp + timedelta(minutes=interval_minutes)).isoformat(),
                    missing_count=1,
                    severity=IncidentSeverity.WARNING.value,
                    evidence={
                        "interval": f"{interval_minutes}m",
                        "expected_timestamp": exp.isoformat(),
                    },
                )
                incidents.append(incident)

        return incidents
