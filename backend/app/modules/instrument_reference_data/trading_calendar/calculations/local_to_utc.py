from datetime import datetime, date, time
from zoneinfo import ZoneInfo
from typing import Tuple

def local_to_utc(local_dt: datetime, timezone_name: str) -> datetime:
    """
    Converts a naive or aware local datetime in `timezone_name` to a timezone-aware UTC datetime.
    Handles DST transitions dynamically using standard Python zoneinfo.
    """
    tz = ZoneInfo(timezone_name)
    if local_dt.tzinfo is None:
        local_aware = local_dt.replace(tzinfo=tz)
    else:
        local_aware = local_dt.astimezone(tz)
    return local_aware.astimezone(ZoneInfo("UTC"))


def utc_to_local(utc_dt: datetime, timezone_name: str) -> datetime:
    """
    Converts a UTC datetime to exchange-local datetime.
    """
    tz = ZoneInfo(timezone_name)
    if utc_dt.tzinfo is None:
        utc_aware = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    else:
        utc_aware = utc_dt.astimezone(ZoneInfo("UTC"))
    return utc_aware.astimezone(tz)


def get_utc_offset_str(dt: datetime, timezone_name: str) -> str:
    """
    Returns the ISO-8601 UTC offset string (e.g. '+05:30', '-04:00', '-05:00') for a specific date and time.
    """
    tz = ZoneInfo(timezone_name)
    if dt.tzinfo is None:
        aware = dt.replace(tzinfo=tz)
    else:
        aware = dt.astimezone(tz)
    offset = aware.utcoffset()
    if offset is None:
        return "+00:00"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{sign}{hours:02d}:{minutes:02d}"

