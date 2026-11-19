"""Latest provider quote, with its own timestamp and currency; independent of chart history."""
import asyncio
import math
import time
from datetime import datetime, timezone
import yfinance as yf

_cache = {}

def _fetch(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.get_info()
    candidates = []
    for price_key, time_key, session in [('regularMarketPrice', 'regularMarketTime', 'REGULAR'), ('postMarketPrice', 'postMarketTime', 'POST'), ('preMarketPrice', 'preMarketTime', 'PRE')]:
        price, market_time = info.get(price_key), info.get(time_key)
        if price is not None and not isinstance(price, bool) and math.isfinite(float(price)) and float(price) > 0:
            candidates.append((float(market_time) if market_time else 0, float(price), session))
    if not candidates:
        price = info.get('currentPrice')
        if price is None or isinstance(price, bool) or not math.isfinite(float(price)) or float(price) <= 0:
            raise ValueError('No valid latest quote')
        candidates.append((0, float(price), 'UNKNOWN'))
    market_time, price, session = max(candidates, key=lambda item: item[0])
    source_time = datetime.fromtimestamp(float(market_time), timezone.utc).isoformat() if market_time else None
    return {'symbol': symbol, 'price': float(price), 'currency': info.get('currency'),
            'source_time': source_time, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'status': 'available', 'session': session, 'source': 'Yahoo Finance via yfinance', 'quote_type': info.get('quoteType'),
            'market_state': info.get('marketState'), 'may_be_delayed': True}

async def latest_market_quote(symbol):
    cached = _cache.get(symbol)
    if cached and time.monotonic() - cached[0] < 30:
        return cached[1]
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_fetch, symbol), 15)
    except Exception:
        return {'symbol': symbol, 'status': 'unavailable', 'price': None, 'error': 'Latest market quote is unavailable.'}
    if len(_cache) >= 128:
        _cache.pop(next(iter(_cache)))
    _cache[symbol] = (time.monotonic(), result)
    return result
