"""
Module 03.03: Timestamp Validation - Subfeature M03.03.04: Session Alignment Validator.
Evaluates:
- Regular trading sessions for Indian (NSE/BSE) and US (NYSE/NASDAQ) markets
- Pre-market, opening auction, closing auction, and post-market sessions
- Weekend and exchange holiday filtering
- Daylight Saving Time (DST) transitions using IANA timezones (Asia/Kolkata, America/New_York)
- Date-only daily OHLCV bar association
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from backend.app.modules.market_data_quality.missing_data.integrations.calendar_interface import (
    ExchangeSessionResolver,
)
from backend.app.modules.market_data_quality.timestamp_validation.models import (
    FinalTimestampStatus,
    SessionStatus,
)


@dataclass
class SessionEvaluationResult:
    status: SessionStatus
    final_status: FinalTimestampStatus
    exchange: str
    trading_date: date
    local_time: time
    session_name: str
    is_auction: bool
    reason: str


class SessionAlignmentValidator:
    """Validates whether timestamps correspond to valid trading sessions on the designated exchange."""

    # Extended exchange session windows (Local Time)
    EXCHANGE_SESSION_WINDOWS = {
        "NSE": {
            "PRE_OPEN": (time(9, 0), time(9, 15)),
            "REGULAR": (time(9, 15), time(15, 30)),
            "CLOSING_AUCTION": (time(15, 30), time(15, 40)),
            "POST_MARKET": (time(15, 40), time(16, 0)),
        },
        "BSE": {
            "PRE_OPEN": (time(9, 0), time(9, 15)),
            "REGULAR": (time(9, 15), time(15, 30)),
            "CLOSING_AUCTION": (time(15, 30), time(15, 40)),
            "POST_MARKET": (time(15, 40), time(16, 0)),
        },
        "NYSE": {
            "PRE_MARKET": (time(4, 0), time(9, 30)),
            "OPENING_AUCTION": (time(9, 29, 30), time(9, 30, 0)),
            "REGULAR": (time(9, 30), time(16, 0)),
            "CLOSING_AUCTION": (time(15, 59, 30), time(16, 0, 0)),
            "POST_MARKET": (time(16, 0), time(20, 0)),
        },
        "NASDAQ": {
            "PRE_MARKET": (time(4, 0), time(9, 30)),
            "OPENING_AUCTION": (time(9, 29, 30), time(9, 30, 0)),
            "REGULAR": (time(9, 30), time(16, 0)),
            "CLOSING_AUCTION": (time(15, 59, 30), time(16, 0, 0)),
            "POST_MARKET": (time(16, 0), time(20, 0)),
        },
    }

    def evaluate(
        self,
        event_timestamp: datetime,
        exchange: str = "NSE",
        is_date_only: bool = False,
        allow_extended_hours: bool = True,
    ) -> SessionEvaluationResult:
        """
        Converts event_timestamp (UTC) to exchange local time using IANA timezone.
        Evaluates session status: REGULAR, AUCTION, PRE/POST MARKET, or OUT_OF_SESSION.
        """
        exch = exchange.upper()
        tz = ExchangeSessionResolver.get_timezone(exch)
        local_dt = event_timestamp.astimezone(tz)
        local_date = local_dt.date()
        local_t = local_dt.time()

        # 1. Date-only daily candle evaluation (e.g. EOD Alpha Vantage daily bar)
        if is_date_only:
            is_valid_day = ExchangeSessionResolver.is_trading_day(exch, local_date)
            if not is_valid_day:
                return SessionEvaluationResult(
                    status=SessionStatus.OUT_OF_SESSION,
                    final_status=FinalTimestampStatus.REJECTED,
                    exchange=exch,
                    trading_date=local_date,
                    local_time=local_t,
                    session_name="HOLIDAY_OR_WEEKEND",
                    is_auction=False,
                    reason=f"Trading date {local_date} falls on a weekend or official holiday on {exch}.",
                )
            return SessionEvaluationResult(
                status=SessionStatus.REGULAR_SESSION,
                final_status=FinalTimestampStatus.VALID,
                exchange=exch,
                trading_date=local_date,
                local_time=local_t,
                session_name="DAILY_EOD",
                is_auction=False,
                reason=f"Valid business trading date {local_date} for {exch}.",
            )

        # 2. Check if the calendar date is an exchange trading day
        if not ExchangeSessionResolver.is_trading_day(exch, local_date):
            return SessionEvaluationResult(
                status=SessionStatus.MARKET_CLOSED,
                final_status=FinalTimestampStatus.REJECTED,
                exchange=exch,
                trading_date=local_date,
                local_time=local_t,
                session_name="MARKET_CLOSED",
                is_auction=False,
                reason=f"Timestamp falls on a closed trading day ({local_date}) for {exch}.",
            )

        # 3. Match within Exchange Session Windows
        windows = self.EXCHANGE_SESSION_WINDOWS.get(exch, {})

        # Regular Trading Session
        reg_start, reg_end = windows.get("REGULAR", (time(9, 15), time(15, 30)))
        if reg_start <= local_t <= reg_end:
            return SessionEvaluationResult(
                status=SessionStatus.REGULAR_SESSION,
                final_status=FinalTimestampStatus.VALID,
                exchange=exch,
                trading_date=local_date,
                local_time=local_t,
                session_name="REGULAR_HOURS",
                is_auction=False,
                reason=f"Timestamp within regular session ({reg_start} - {reg_end}) on {exch}.",
            )

        # Pre-Market / Opening Auction
        if "PRE_OPEN" in windows:
            po_start, po_end = windows["PRE_OPEN"]
            if po_start <= local_t < po_end:
                return SessionEvaluationResult(
                    status=SessionStatus.OPENING_AUCTION,
                    final_status=FinalTimestampStatus.VALID if allow_extended_hours else FinalTimestampStatus.VALID_WITH_WARNING,
                    exchange=exch,
                    trading_date=local_date,
                    local_time=local_t,
                    session_name="PRE_OPEN_AUCTION",
                    is_auction=True,
                    reason=f"Timestamp within pre-open auction window on {exch}.",
                )

        if "PRE_MARKET" in windows:
            pm_start, pm_end = windows["PRE_MARKET"]
            if pm_start <= local_t < pm_end:
                return SessionEvaluationResult(
                    status=SessionStatus.PRE_MARKET,
                    final_status=FinalTimestampStatus.VALID if allow_extended_hours else FinalTimestampStatus.VALID_WITH_WARNING,
                    exchange=exch,
                    trading_date=local_date,
                    local_time=local_t,
                    session_name="US_PRE_MARKET",
                    is_auction=False,
                    reason=f"Timestamp within US pre-market trading hours on {exch}.",
                )

        # Closing Auction / Post-Market
        if "CLOSING_AUCTION" in windows:
            ca_start, ca_end = windows["CLOSING_AUCTION"]
            if ca_start <= local_t <= ca_end:
                return SessionEvaluationResult(
                    status=SessionStatus.CLOSING_AUCTION,
                    final_status=FinalTimestampStatus.VALID,
                    exchange=exch,
                    trading_date=local_date,
                    local_time=local_t,
                    session_name="CLOSING_AUCTION",
                    is_auction=True,
                    reason=f"Timestamp within closing auction window on {exch}.",
                )

        if "POST_MARKET" in windows:
            post_start, post_end = windows["POST_MARKET"]
            if post_start <= local_t <= post_end:
                return SessionEvaluationResult(
                    status=SessionStatus.POST_MARKET,
                    final_status=FinalTimestampStatus.VALID if allow_extended_hours else FinalTimestampStatus.VALID_WITH_WARNING,
                    exchange=exch,
                    trading_date=local_date,
                    local_time=local_t,
                    session_name="POST_MARKET",
                    is_auction=False,
                    reason=f"Timestamp within post-market trading hours on {exch}.",
                )

        # Outside all defined sessions
        return SessionEvaluationResult(
            status=SessionStatus.OUT_OF_SESSION,
            final_status=FinalTimestampStatus.QUARANTINED if not allow_extended_hours else FinalTimestampStatus.VALID_WITH_WARNING,
            exchange=exch,
            trading_date=local_date,
            local_time=local_t,
            session_name="OUT_OF_HOURS",
            is_auction=False,
            reason=f"Timestamp {local_t} falls outside all active exchange session windows on {exch}.",
        )
