"""
Module 03.03: Timestamp Validation - Subfeature M03.03.03: Stale Timestamp Detector.
Evaluates:
- Event age (Current Validation Time - Observation Event Time)
- Real-time streaming staleness vs. Historical/EOD context
- Order-book update and snapshot staleness integrated with M02 state
- Market-closed period awareness (quiet market is not stale market)
- Future-dated timestamp rejection
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.app.modules.market_data_quality.missing_data.integrations.calendar_interface import (
    ExchangeSessionResolver,
)
from backend.app.modules.market_data_quality.timestamp_validation.models import (
    FinalTimestampStatus,
    FreshnessStatus,
)


@dataclass
class FreshnessEvaluationResult:
    status: FreshnessStatus
    final_status: FinalTimestampStatus
    age_seconds: float
    warning_threshold_sec: float
    critical_threshold_sec: float
    reason: str


class StaleTimestampDetector:
    """Evaluates observation age, context-dependent staleness, and order-book freshness."""

    def evaluate(
        self,
        event_timestamp: datetime,
        validation_time: Optional[datetime] = None,
        exchange: str = "NSE",
        processing_context: str = "REALTIME",  # REALTIME, EOD, HISTORICAL
        data_channel: str = "TICK",           # TICK, ORDER_BOOK_L2, OHLCV
        warning_threshold_sec: float = 5.0,   # 5 seconds warning for live ticks
        critical_threshold_sec: float = 30.0, # 30 seconds critical
        is_orderbook_synchronized: bool = True,
    ) -> FreshnessEvaluationResult:
        """
        Calculates age in seconds.
        Ensures historical data and market-closed periods are not falsely classified as stale.
        """
        now = validation_time or datetime.now(timezone.utc)
        age_sec = (now - event_timestamp).total_seconds()

        # 1. Historical & Backfill Processing Context (bypasses live freshness and future-date checks)
        if processing_context.upper() in ("HISTORICAL", "BACKFILL"):
            return FreshnessEvaluationResult(
                status=FreshnessStatus.HISTORICAL,
                final_status=FinalTimestampStatus.VALID,
                age_seconds=age_sec,
                warning_threshold_sec=warning_threshold_sec,
                critical_threshold_sec=critical_threshold_sec,
                reason="Historical processing context; real-time freshness rules bypassed.",
            )

        # 2. Future-dated event check (> 2 seconds ahead beyond clock uncertainty)
        if age_sec < -2.0:
            return FreshnessEvaluationResult(
                status=FreshnessStatus.FUTURE_DATED,
                final_status=FinalTimestampStatus.REJECTED,
                age_seconds=age_sec,
                warning_threshold_sec=warning_threshold_sec,
                critical_threshold_sec=critical_threshold_sec,
                reason=f"Event timestamp is {abs(age_sec):.2f}s in the future.",
            )

        # 3. End-of-Day (EOD) Processing Context (e.g. Alpha Vantage Daily OHLCV)
        if processing_context.upper() == "EOD" or data_channel.upper() in ("DAILY", "EOD"):
            return FreshnessEvaluationResult(
                status=FreshnessStatus.FRESH,
                final_status=FinalTimestampStatus.VALID,
                age_seconds=age_sec,
                warning_threshold_sec=warning_threshold_sec,
                critical_threshold_sec=critical_threshold_sec,
                reason="End-of-day daily bar evaluated under EOD publication guidelines.",
            )

        # 4. Market-Closed Awareness
        # If market is closed on the exchange at validation time, inactivity does not mean stale data
        is_open = ExchangeSessionResolver.is_market_open_at(exchange, now)
        if not is_open:
            return FreshnessEvaluationResult(
                status=FreshnessStatus.MARKET_CLOSED,
                final_status=FinalTimestampStatus.VALID,
                age_seconds=age_sec,
                warning_threshold_sec=warning_threshold_sec,
                critical_threshold_sec=critical_threshold_sec,
                reason=f"Market is currently closed on {exchange}; stream inactivity is expected.",
            )

        # 5. Order-Book Synchronization Dependency (from M02)
        if data_channel.upper() in ("ORDER_BOOK", "ORDER_BOOK_L2") and not is_orderbook_synchronized:
            return FreshnessEvaluationResult(
                status=FreshnessStatus.CRITICALLY_STALE,
                final_status=FinalTimestampStatus.QUARANTINED,
                age_seconds=age_sec,
                warning_threshold_sec=warning_threshold_sec,
                critical_threshold_sec=critical_threshold_sec,
                reason="Order book is desynchronized / unverified in M02 ingestion engine.",
            )

        # 6. Real-Time Streaming Freshness Checks
        if age_sec > critical_threshold_sec:
            return FreshnessEvaluationResult(
                status=FreshnessStatus.CRITICALLY_STALE,
                final_status=FinalTimestampStatus.QUARANTINED,
                age_seconds=age_sec,
                warning_threshold_sec=warning_threshold_sec,
                critical_threshold_sec=critical_threshold_sec,
                reason=f"Observation age of {age_sec:.1f}s exceeds critical staleness limit {critical_threshold_sec}s.",
            )
        elif age_sec > warning_threshold_sec:
            return FreshnessEvaluationResult(
                status=FreshnessStatus.AGING,
                final_status=FinalTimestampStatus.VALID_WITH_WARNING,
                age_seconds=age_sec,
                warning_threshold_sec=warning_threshold_sec,
                critical_threshold_sec=critical_threshold_sec,
                reason=f"Observation age of {age_sec:.1f}s exceeds warning threshold {warning_threshold_sec}s.",
            )

        return FreshnessEvaluationResult(
            status=FreshnessStatus.FRESH,
            final_status=FinalTimestampStatus.VALID,
            age_seconds=age_sec,
            warning_threshold_sec=warning_threshold_sec,
            critical_threshold_sec=critical_threshold_sec,
            reason="Observation is fresh and within real-time latency limits.",
        )
