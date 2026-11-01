"""
Module 03.01: Missing Data Detection - Exchange Calendar & Trading Session Helper.
Provides exchange calendar logic for:
- NSE & BSE (Asia/Kolkata): 09:15:00 to 15:30:00 (Monday-Friday)
- NYSE & NASDAQ (America/New_York): 09:30:00 to 16:00:00 (Monday-Friday)
Handles holidays, weekend filtering, and candle interval timestamp generation.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Tuple
from zoneinfo import ZoneInfo


class ExchangeSessionResolver:
    """Calculates valid trading sessions, expected dates, and candle timestamps."""

    EXCHANGE_TIMEZONES = {
        "NSE": "Asia/Kolkata",
        "BSE": "Asia/Kolkata",
        "NYSE": "America/New_York",
        "NASDAQ": "America/New_York",
    }

    SESSION_HOURS = {
        "NSE": (time(9, 15), time(15, 30)),
        "BSE": (time(9, 15), time(15, 30)),
        "NYSE": (time(9, 30), time(16, 0)),
        "NASDAQ": (time(9, 30), time(16, 0)),
    }

    # Standard public holiday dates for demonstration/testing
    HOLIDAYS = {
        "NSE": {date(2026, 1, 26), date(2026, 8, 15), date(2026, 10, 2)},
        "BSE": {date(2026, 1, 26), date(2026, 8, 15), date(2026, 10, 2)},
        "NYSE": {date(2026, 1, 1), date(2026, 7, 4), date(2026, 12, 25)},
        "NASDAQ": {date(2026, 1, 1), date(2026, 7, 4), date(2026, 12, 25)},
    }

    @classmethod
    def get_timezone(cls, exchange: str) -> ZoneInfo:
        tz_name = cls.EXCHANGE_TIMEZONES.get(exchange.upper(), "UTC")
        return ZoneInfo(tz_name)

    @classmethod
    def is_trading_day(cls, exchange: str, check_date: date) -> bool:
        """Returns True if the date is a weekday and not a designated exchange holiday."""
        if check_date.weekday() >= 5:  # Saturday or Sunday
            return False
        holidays = cls.HOLIDAYS.get(exchange.upper(), set())
        return check_date not in holidays

    @classmethod
    def is_market_open_at(cls, exchange: str, dt_utc: datetime) -> bool:
        """Determines if the exchange was open at a specific UTC timestamp."""
        tz = cls.get_timezone(exchange)
        local_dt = dt_utc.astimezone(tz)
        if not cls.is_trading_day(exchange, local_dt.date()):
            return False

        open_time, close_time = cls.SESSION_HOURS.get(exchange.upper(), (time(9, 15), time(15, 30)))
        return open_time <= local_dt.time() <= close_time

    @classmethod
    def generate_expected_trading_days(cls, exchange: str, start_date: date, end_date: date) -> List[date]:
        """Generates list of valid business trading days between start_date and end_date inclusive."""
        cur = start_date
        days = []
        while cur <= end_date:
            if cls.is_trading_day(exchange, cur):
                days.append(cur)
            cur += timedelta(days=1)
        return days

    @classmethod
    def generate_expected_candle_timestamps(
        cls,
        exchange: str,
        trading_date: date,
        interval_minutes: int,
    ) -> List[datetime]:
        """Generates expected start timestamps for intraday candles on a given trading day."""
        if not cls.is_trading_day(exchange, trading_date):
            return []

        tz = cls.get_timezone(exchange)
        open_time, close_time = cls.SESSION_HOURS.get(exchange.upper(), (time(9, 15), time(15, 30)))

        start_dt = datetime.combine(trading_date, open_time, tzinfo=tz)
        end_dt = datetime.combine(trading_date, close_time, tzinfo=tz)

        timestamps = []
        curr = start_dt
        delta = timedelta(minutes=interval_minutes)
        while curr < end_dt:
            timestamps.append(curr.astimezone(timezone.utc))
            curr += delta

        return timestamps

