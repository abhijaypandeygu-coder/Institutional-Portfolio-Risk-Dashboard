"""Exact dated benchmark observations; no generated fallback or final-NAV rescaling."""
import asyncio
import math
import time
from datetime import datetime, timezone
import yfinance as yf

_cache = {}
PERIODS = {"1D": ("1d", "15m"), "1W": ("5d", "1d"), "1M": ("1mo", "1d"), "3M": ("3mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1d"), "ALL": ("5y", "1d")}


def _fetch(symbol, horizon):
    period, interval = PERIODS[horizon]
    ticker = yf.Ticker(symbol)
    frame = ticker.history(period=period, interval=interval, auto_adjust=True, timeout=10)
    points = []
    for stamp, row in frame.iterrows():
        close = float(row["Close"])
        if math.isfinite(close) and close > 0:
            points.append({"timestamp": stamp.isoformat(), "value": close})
    currency = (ticker.history_metadata or {}).get("currency")
    return {"symbol": symbol, "currency": currency, "interval": interval, "points": points,
            "status": "available" if len(points) > 1 else "unavailable",
            "source": "Yahoo Finance via yfinance", "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "return_treatment": "price_index" if symbol.startswith("^") else "adjusted_close_proxy"}


async def benchmark_history(symbol, horizon):
    key = (symbol, horizon)
    if key in _cache and time.monotonic() - _cache[key][0] < 30:
        return _cache[key][1]
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_fetch, symbol, horizon), 20)
    except Exception:
        return {"symbol": symbol, "status": "unavailable", "points": [], "error": "Benchmark history could not be retrieved."}
    if result["status"] == "available":
        if len(_cache) >= 64:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic(), result)
    return result
