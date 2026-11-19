"""Bounded, cached daily close history for portfolio sparklines. No synthetic fallback."""
import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _fetch(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(symbol)
    frame = ticker.history(period="1mo", interval="1d", auto_adjust=True, timeout=10)
    points = []
    for timestamp, row in frame.iterrows():
        close = float(row["Close"])
        if math.isfinite(close) and close > 0:
            points.append({"timestamp": timestamp.isoformat(), "close": round(close, 6)})
    return {
        "symbol": symbol, "period": "1mo", "interval": "1d",
        "source": "Yahoo Finance via yfinance", "adjusted": True,
        "status": "available" if len(points) >= 2 else "unavailable",
        "currency": getattr(ticker, "history_metadata", {}).get("currency"),
        "points": points, "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_stock_history(symbol: str) -> dict[str, Any]:
    cached = _cache.get(symbol)
    if cached and time.monotonic() - cached[0] < 30:
        return cached[1]
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_fetch, symbol), timeout=15)
    except Exception:
        return {"symbol": symbol, "period": "1mo", "interval": "1d", "source": "Yahoo Finance via yfinance",
                "status": "unavailable", "points": [], "error": "Price history could not be retrieved."}
    if len(_cache) >= 128:
        _cache.pop(next(iter(_cache)))
    if result["status"] == "available":
        _cache[symbol] = (time.monotonic(), result)
    return result
