"""Liquidity presentation metadata. Missing calendars/FX/history stay explicit."""
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import asyncio
import time
from sqlalchemy import select, desc
from backend.app.modules.instrument_reference_data.instrument_master.models import InstrumentListing
from backend.app.modules.instrument_reference_data.trading_calendar.services.service import TradingCalendarService
from backend.app.modules.market_data_ingestion.persistence.models import MarketOHLCV
from backend.app.modules.market_microstructure.liquidity_estimation.models import LiquidityVolumeAggregate, LiquidityTurnoverAggregate

_volume_cache = {}


async def conversion_rate(native: str, base: str):
    if native == base:
        return Decimal(1), None, "Same currency"
    from backend.app.modules.market_data_ingestion.adapters.yfinance.latest_quote import latest_market_quote
    quote = await latest_market_quote(f"{native}{base}=X")
    stamp = quote.get('source_time')
    if quote.get('status') != 'available' or not stamp or quote.get('currency') != base:
        return None, None, "FX unavailable"
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds()
    value = Decimal(str(quote['price']))
    if not value.is_finite() or value <= 0 or age < -60 or age > 7 * 86400:
        return None, stamp, "FX unavailable or stale"
    return value, stamp, f"Yahoo Finance {native}{base}=X; provider quote, may be delayed"


def native_currency(symbol: str) -> str:
    return "INR" if symbol.upper().endswith((".NS", ".BO")) else "USD"


def regular_session(symbol: str, exchange: str = "") -> dict:
    indian = symbol.upper().endswith((".NS", ".BO")) or exchange in ("NSE", "BSE")
    return {
        "exchange": exchange or ("NSE" if symbol.upper().endswith(".NS") else "BSE" if symbol.upper().endswith(".BO") else "US equities"),
        "timezone": "Asia/Kolkata" if indian else "America/New_York",
        "session_minutes": 375 if indian else 390,
        "regular_hours": "09:15–15:30" if indian else "09:30–16:00",
        "session_status": "UNKNOWN",
        "calendar_basis": "Regular-session assumption; holiday calendar unavailable",
        "calendar_id": None,
    }


async def market_context(db, instrument_id: str, symbol: str) -> dict:
    listing = (await db.execute(select(InstrumentListing).where(
        InstrumentListing.instrument_id == instrument_id,
        InstrumentListing.effective_to.is_(None),
    ).order_by(desc(InstrumentListing.id)).limit(1))).scalar_one_or_none()
    exchange = listing.exchange_id if listing else ""
    result = regular_session(symbol, exchange)
    # Do not infer an authoritative US exchange from an unregistered ticker.
    code = exchange or ("NSE" if symbol.endswith(".NS") else "BSE" if symbol.endswith(".BO") else "")
    if code:
        try:
            now = datetime.now(timezone.utc)
            calendar = TradingCalendarService(db)
            resolved = await calendar.resolve_session(code, now)
            schedule = await calendar.get_day_schedule(code, resolved.resolved_trading_date)
            sessions = [s for s in schedule.sessions if s.trade_matching_permitted and s.session_type.value == "REGULAR_TRADING"]
            minutes = sum((s.utc_end - s.utc_start).total_seconds() / 60 for s in sessions)
            result.update({
                "exchange": code, "timezone": schedule.timezone_name,
                "session_status": "SCHEDULED_OPEN" if resolved.scheduled_trading_permitted else "SCHEDULED_CLOSED",
                "calendar_basis": "Configured exchange calendar; intraday halts not verified",
                "calendar_id": resolved.calendar_id,
            })
            if minutes > 0:
                result["session_minutes"] = minutes
                result["regular_hours"] = ", ".join(f"{s.local_start:%H:%M}–{s.local_end:%H:%M}" for s in sessions)
        except ValueError:
            pass
    return result


def summarize_daily_bars(bars, currency: str, source: str) -> dict:
    """Average DAILY volume/turnover, never total multi-day volume or a USD relabel."""
    unique = {}
    for day, close, volume in bars:
        if close is not None and volume is not None and float(close) > 0 and float(volume) >= 0:
            unique[day] = (Decimal(str(close)), Decimal(str(volume)))
    dates = sorted(unique)[-20:]
    if not dates:
        return {"adv_shares": None, "adtv_native": None, "currency": currency, "observation_count": 0, "source": "Unavailable", "as_of": None}
    n = Decimal(len(dates))
    return {
        "adv_shares": sum((unique[d][1] for d in dates), Decimal(0)) / n,
        "adtv_native": sum((unique[d][0] * unique[d][1] for d in dates), Decimal(0)) / n,
        "currency": currency, "observation_count": len(dates), "source": source, "as_of": str(dates[-1]),
    }


async def volume_context(db, instrument_id: str, symbol: str, currency: str) -> dict:
    rows = (await db.execute(select(MarketOHLCV).where(
        MarketOHLCV.instrument_id == instrument_id, MarketOHLCV.interval == "1d",
    ).order_by(desc(MarketOHLCV.candle_start)).limit(80))).scalars().all()
    today = datetime.now(ZoneInfo("Asia/Kolkata" if currency == "INR" else "America/New_York")).date()
    bars = [(r.candle_start.date(), r.close_price, r.volume) for r in rows if r.candle_start.date() < today]
    if bars:
        return summarize_daily_bars(bars, currency, "Recorded daily OHLCV")
    volumes = (await db.execute(select(LiquidityVolumeAggregate).where(
        LiquidityVolumeAggregate.instrument_id == instrument_id,
        LiquidityVolumeAggregate.aggregation_interval == "1d",
    ).order_by(desc(LiquidityVolumeAggregate.aggregation_end)).limit(60))).scalars().all()
    turnover = (await db.execute(select(LiquidityTurnoverAggregate).where(
        LiquidityTurnoverAggregate.instrument_id == instrument_id,
        LiquidityTurnoverAggregate.aggregation_interval == "1d",
        LiquidityTurnoverAggregate.currency == currency,
    ).order_by(desc(LiquidityTurnoverAggregate.aggregation_end)).limit(60))).scalars().all()
    if volumes:
        daily = {}
        for row in volumes:
            daily.setdefault(row.aggregation_start.date(), Decimal(str(row.traded_volume)))
        dates = sorted(daily)[-20:]
        turns = {}
        for row in turnover:
            turns.setdefault(row.aggregation_start.date(), Decimal(str(row.turnover_amount)))
        return {"adv_shares": sum((daily[d] for d in dates), Decimal(0)) / len(dates),
                "adtv_native": sum((turns[d] for d in dates), Decimal(0)) / len(dates) if all(d in turns for d in dates) else None,
                "currency": currency, "observation_count": len(dates), "source": "Recorded daily aggregates", "as_of": str(dates[-1])}
    cached = _volume_cache.get((symbol, currency))
    if cached and time.monotonic() - cached[0] < 60:
        return cached[1]
    def history():
        import yfinance as yf
        frame = yf.Ticker(symbol).history(period="3mo", interval="1d", auto_adjust=False, timeout=8)
        return [(i.date(), float(row['Close']), float(row['Volume'])) for i, row in frame.iterrows() if i.date() < today]
    try:
        bars = await asyncio.wait_for(asyncio.to_thread(history), timeout=10)
    except Exception:
        bars = []
    result = summarize_daily_bars(bars, currency, "Yahoo Finance completed daily bars")
    _volume_cache[(symbol, currency)] = (time.monotonic(), result)
    return result
