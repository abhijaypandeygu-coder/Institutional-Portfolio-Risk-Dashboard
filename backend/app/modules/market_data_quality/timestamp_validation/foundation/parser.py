"""
Module 03.03: Timestamp Validation - Foundation Parser and Normalizer.
Provides:
- Timezone-aware timestamp parsing (ISO 8601, epoch ms, date-only)
- Provenance preservation (Exchange vs Provider vs Local receive)
- Precision tracking (seconds, milliseconds, microseconds)
- Standardized UTC normalization
- Safe timezone handling (Asia/Kolkata, America/New_York)
"""
from datetime import date, datetime, time, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimestampPrecision(str, Enum):
    DATE_ONLY = "DATE_ONLY"
    SECONDS = "SECONDS"
    MILLISECONDS = "MILLISECONDS"
    MICROSECONDS = "MICROSECONDS"


class TimestampSourceType(str, Enum):
    EXCHANGE = "EXCHANGE"
    PROVIDER_EVENT = "PROVIDER_EVENT"
    PROVIDER_RECEIVE = "PROVIDER_RECEIVE"
    LOCAL_RECEIVE = "LOCAL_RECEIVE"
    PROCESSING = "PROCESSING"


class TimestampFoundation:
    """Core utilities for timezone normalization, provenance preservation, and precision tracking."""

    KNOWN_TIMEZONES = {
        "NSE": "Asia/Kolkata",
        "BSE": "Asia/Kolkata",
        "NYSE": "America/New_York",
        "NASDAQ": "America/New_York",
    }

    @classmethod
    def resolve_exchange_timezone(cls, exchange: str) -> ZoneInfo:
        tz_name = cls.KNOWN_TIMEZONES.get(exchange.upper(), "UTC")
        return ZoneInfo(tz_name)

    @classmethod
    def parse_and_normalize(
        cls,
        raw_val: Any,
        default_tz: Optional[ZoneInfo] = None,
        exchange: Optional[str] = None,
    ) -> Tuple[Optional[datetime], TimestampPrecision, bool]:
        """
        Parses raw input (string, datetime, date, epoch ms) and normalizes to UTC datetime.
        Returns: (utc_datetime, precision, is_date_only)
        """
        if raw_val is None:
            return None, TimestampPrecision.SECONDS, False

        # If already datetime
        if isinstance(raw_val, datetime):
            if raw_val.tzinfo is None:
                # Timezone-naive: apply exchange timezone if supplied, else default_tz or UTC
                tz = default_tz or (cls.resolve_exchange_timezone(exchange) if exchange else timezone.utc)
                dt_aware = raw_val.replace(tzinfo=tz)
            else:
                dt_aware = raw_val
            utc_dt = dt_aware.astimezone(timezone.utc)
            prec = TimestampPrecision.MICROSECONDS if raw_val.microsecond > 0 else TimestampPrecision.SECONDS
            return utc_dt, prec, False

        # If date object (e.g. daily OHLCV)
        if isinstance(raw_val, date) and not isinstance(raw_val, datetime):
            # Combine with start of day in exchange timezone
            tz = default_tz or (cls.resolve_exchange_timezone(exchange) if exchange else timezone.utc)
            dt_aware = datetime.combine(raw_val, time(0, 0, 0), tzinfo=tz)
            return dt_aware.astimezone(timezone.utc), TimestampPrecision.DATE_ONLY, True

        # If string
        if isinstance(raw_val, str):
            s = raw_val.strip()
            if not s:
                return None, TimestampPrecision.SECONDS, False
            
            # Check for date-only format (YYYY-MM-DD)
            if len(s) == 10 and s[4] == "-" and s[7] == "-":
                try:
                    d = date.fromisoformat(s)
                    tz = default_tz or (cls.resolve_exchange_timezone(exchange) if exchange else timezone.utc)
                    dt_aware = datetime.combine(d, time(0, 0, 0), tzinfo=tz)
                    return dt_aware.astimezone(timezone.utc), TimestampPrecision.DATE_ONLY, True
                except ValueError:
                    return None, TimestampPrecision.DATE_ONLY, True

            # Try ISO format
            try:
                # Replace trailing 'Z' if present for standard fromisoformat compatibility
                iso_str = s.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(iso_str)
                if parsed.tzinfo is None:
                    tz = default_tz or (cls.resolve_exchange_timezone(exchange) if exchange else timezone.utc)
                    parsed = parsed.replace(tzinfo=tz)
                utc_dt = parsed.astimezone(timezone.utc)
                prec = TimestampPrecision.MICROSECONDS if parsed.microsecond > 0 else TimestampPrecision.SECONDS
                return utc_dt, prec, False
            except ValueError:
                # Try epoch numeric string
                try:
                    num = float(s)
                    return cls._from_epoch(num)
                except ValueError:
                    return None, TimestampPrecision.SECONDS, False

        # If epoch int/float
        if isinstance(raw_val, (int, float)):
            return cls._from_epoch(raw_val)

        return None, TimestampPrecision.SECONDS, False

    @classmethod
    def _from_epoch(cls, epoch_val: Union[int, float]) -> Tuple[datetime, TimestampPrecision, bool]:
        # Assume ms if > 1e11 (year ~2286 in seconds, but ~1973 in ms)
        if epoch_val > 1e11:
            sec = epoch_val / 1000.0
            prec = TimestampPrecision.MILLISECONDS
        else:
            sec = float(epoch_val)
            prec = TimestampPrecision.SECONDS
        dt = datetime.fromtimestamp(sec, tz=timezone.utc)
        return dt, prec, False
