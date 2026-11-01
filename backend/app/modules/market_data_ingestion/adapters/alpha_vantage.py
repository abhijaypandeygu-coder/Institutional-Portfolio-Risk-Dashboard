"""
Module 02: Market Data Ingestion Engine - Real Alpha Vantage REST Provider Adapter.
Implements official Alpha Vantage REST endpoints for US and Indian equities:
- SYMBOL_SEARCH
- TIME_SERIES_DAILY (outputsize=compact, 100 observations max, raw unadjusted)
- TIME_SERIES_WEEKLY
- TIME_SERIES_MONTHLY
- GLOBAL_QUOTE (EOD quote)

Excludes premium endpoints (INTRADAY, DAILY_ADJUSTED, outputsize=full, REALTIME_BULK).
Enforces zero streaming capability (raises UnsupportedCapabilityError).
Redacts API keys from all logs.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from backend.app.core.config import settings
from backend.app.modules.market_data_ingestion.adapters.base import BaseProviderAdapter
from backend.app.modules.market_data_ingestion.adapters.quota_scheduler import (
    AlphaVantageQuotaScheduler,
    QuotaExceededException,
    quota_scheduler,
)
from backend.app.modules.market_data_ingestion.normalization.schemas import (
    DataFreshness,
    MarketDataChannel,
    OHLCVCandle,
)

logger = logging.getLogger("ingestion.alpha_vantage")


class UnsupportedCapabilityError(Exception):
    """Raised when an unsupported operation (e.g. streaming, intraday) is invoked on free plan."""
    pass


class AlphaVantageAPIError(Exception):
    """Raised when Alpha Vantage returns an error message or rate limit notice."""
    def __init__(self, error_type: str, message: str):
        super().__init__(f"[{error_type}] {message}")
        self.error_type = error_type
        self.message = message


class AlphaVantageAdapter(BaseProviderAdapter):
    """
    Production-conscious Alpha Vantage adapter adhering strictly to Free Tier entitlements.
    Supports US tickers (e.g. IBM, AAPL) and Indian BSE/NSE tickers (e.g. RELIANCE.BSE).
    """

    EXCLUDED_PREMIUM_FUNCTIONS = {
        "TIME_SERIES_INTRADAY",
        "TIME_SERIES_DAILY_ADJUSTED",
        "REALTIME_BULK_QUOTES",
        "REALTIME_BULK_BID_ASK_PRICES",
    }

    def __init__(
        self,
        feed_id: str = "FEED_ALPHA_VANTAGE",
        provider_id: str = "ALPHA_VANTAGE",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        scheduler: Optional[AlphaVantageQuotaScheduler] = None,
    ):
        super().__init__(feed_id, provider_id)
        self.api_key = api_key or settings.ALPHA_VANTAGE_API_KEY
        self.base_url = base_url or settings.ALPHA_VANTAGE_BASE_URL
        self.scheduler = scheduler or quota_scheduler
        self.client: Optional[httpx.AsyncClient] = None

    def _ensure_api_key(self) -> str:
        if not self.api_key or self.api_key.strip() in ("", "your_api_key", "your_api_key_here"):
            raise AlphaVantageAPIError(
                "INVALID_API_KEY",
                "Alpha Vantage API key is missing or not configured in environment.",
            )
        return self.api_key

    async def connect(self, config: Dict[str, Any]) -> bool:
        if not self.client or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=15.0)
        self.is_connected = True
        return True

    async def disconnect(self) -> None:
        if self.client and not self.client.is_closed:
            await self.client.aclose()
        self.is_connected = False

    async def subscribe(self, instruments: List[str], channels: List[MarketDataChannel]) -> bool:
        for inst in instruments:
            clean = inst.upper()
            if clean not in self.subscribed_instruments:
                self.subscribed_instruments[clean] = []
            for ch in channels:
                if ch not in self.subscribed_instruments[clean]:
                    self.subscribed_instruments[clean].append(ch)
        return True

    async def unsubscribe(self, instruments: List[str], channels: List[MarketDataChannel]) -> bool:
        for inst in instruments:
            clean = inst.upper()
            if clean in self.subscribed_instruments:
                for ch in channels:
                    if ch in self.subscribed_instruments[clean]:
                        self.subscribed_instruments[clean].remove(ch)
        return True

    async def stream_raw_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Free-tier Alpha Vantage does not offer streaming WebSocket connections."""
        raise UnsupportedCapabilityError(
            "Streaming is not supported by Alpha Vantage on the Free Plan. "
            "Alpha Vantage adapter operates exclusively in scheduled REST polling mode."
        )
        yield {}  # Make it an async generator so async for raises UnsupportedCapabilityError

    # -------------------------------------------------------------------------
    # Core HTTP Request Handler with Redaction and Quota Checking
    # -------------------------------------------------------------------------
    async def _make_request(self, function: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes HTTP GET with key redaction in logging and quota verification."""
        if function in self.EXCLUDED_PREMIUM_FUNCTIONS:
            raise UnsupportedCapabilityError(
                f"Function '{function}' is an excluded premium endpoint not available on the Free Plan."
            )

        api_key = self._ensure_api_key()
        symbol = params.get("symbol")

        # Acquire permit from quota scheduler
        self.scheduler.acquire_call_permit(function_name=function, symbol=symbol)

        full_params = {
            "function": function,
            "apikey": api_key,
            **params,
        }

        # Redacted params for logging
        redacted_params = {k: ("***REDACTED***" if k == "apikey" else v) for k, v in full_params.items()}
        logger.info(f"Alpha Vantage HTTP GET {self.base_url} with params: {redacted_params}")

        if not self.client or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=15.0)

        try:
            resp = await self.client.get(self.base_url, params=full_params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            logger.error("Alpha Vantage request timed out.")
            raise AlphaVantageAPIError("NETWORK_TIMEOUT", "Alpha Vantage connection timed out after 15 seconds.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Alpha Vantage returned HTTP status {e.response.status_code}")
            raise AlphaVantageAPIError("SERVER_ERROR", f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as ex:
            logger.error(f"Alpha Vantage request failed: {str(ex)}")
            raise AlphaVantageAPIError("SERVER_ERROR", str(ex))

        # Classify provider error notices in response JSON
        if "Error Message" in data:
            err_msg = data["Error Message"]
            logger.error(f"Alpha Vantage API error: {err_msg}")
            if "the parameter apikey is invalid" in err_msg.lower() or "check api key" in err_msg.lower():
                raise AlphaVantageAPIError("INVALID_API_KEY", err_msg)
            elif "symbol" in err_msg.lower() or "invalid api call" in err_msg.lower():
                raise AlphaVantageAPIError("UNSUPPORTED_SYMBOL", err_msg)
            raise AlphaVantageAPIError("INVALID_API_KEY", err_msg)

        if "Information" in data:
            info_msg = data["Information"]
            logger.warning(f"Alpha Vantage API information notice: {info_msg}")
            if "rate limit" in info_msg.lower() or "call frequency" in info_msg.lower():
                raise AlphaVantageAPIError("RATE_LIMIT_EXCEEDED", info_msg)

        if "Note" in data:
            note_msg = data["Note"]
            logger.warning(f"Alpha Vantage API note: {note_msg}")
            if "higher API call volume" in note_msg or "frequency" in note_msg:
                raise AlphaVantageAPIError("DAILY_QUOTA_EXHAUSTED", note_msg)

        return data

    # -------------------------------------------------------------------------
    # 1. SYMBOL_SEARCH
    # -------------------------------------------------------------------------
    async def search_symbol(self, keywords: str) -> List[Dict[str, Any]]:
        cached = self.scheduler.get_cached_symbol_search(keywords)
        if cached is not None:
            return cached

        data = await self._make_request("SYMBOL_SEARCH", {"keywords": keywords})
        matches = data.get("bestMatches", [])
        results = []
        for m in matches:
            results.append({
                "symbol": m.get("1. symbol"),
                "name": m.get("2. name"),
                "type": m.get("3. type"),
                "region": m.get("4. region"),
                "marketOpen": m.get("5. marketOpen"),
                "marketClose": m.get("6. marketClose"),
                "timezone": m.get("7. timezone"),
                "currency": m.get("8. currency"),
                "matchScore": m.get("9. matchScore"),
            })
        self.scheduler.cache_symbol_search(keywords, results)
        return results

    # -------------------------------------------------------------------------
    # 2. TIME_SERIES_DAILY (outputsize=compact, raw unadjusted)
    # -------------------------------------------------------------------------
    async def fetch_daily_ohlcv(self, symbol: str) -> List[OHLCVCandle]:
        data = await self._make_request(
            "TIME_SERIES_DAILY",
            {"symbol": symbol, "outputsize": "compact"},
        )
        time_series = data.get("Time Series (Daily)", {})
        if not time_series:
            raise AlphaVantageAPIError("EMPTY_RESPONSE", f"No daily time series returned for symbol '{symbol}'.")

        candles = []
        for dt_str, bar in sorted(time_series.items()):
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
            candles.append(OHLCVCandle(
                feed_id=self.feed_id,
                instrument_id=f"EQ_{symbol.upper()}",
                exchange="BSE" if ".BSE" in symbol.upper() else ("NSE" if ".NSE" in symbol.upper() else "US"),
                interval="1d",
                open=Decimal(str(bar["1. open"])),
                high=Decimal(str(bar["2. high"])),
                low=Decimal(str(bar["3. low"])),
                close=Decimal(str(bar["4. close"])),
                volume=Decimal(str(bar["5. volume"])),
                candle_start=dt,
                candle_end=dt,
                source_provider="ALPHA_VANTAGE",
                data_freshness=DataFreshness.END_OF_DAY,
                is_adjusted=False,
                currency="INR" if (".BSE" in symbol.upper() or ".NSE" in symbol.upper()) else "USD",
            ))
        return candles

    # -------------------------------------------------------------------------
    # 3. TIME_SERIES_WEEKLY
    # -------------------------------------------------------------------------
    async def fetch_weekly_ohlcv(self, symbol: str) -> List[OHLCVCandle]:
        data = await self._make_request("TIME_SERIES_WEEKLY", {"symbol": symbol})
        time_series = data.get("Weekly Time Series", {})
        candles = []
        for dt_str, bar in sorted(time_series.items()):
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
            candles.append(OHLCVCandle(
                feed_id=self.feed_id,
                instrument_id=f"EQ_{symbol.upper()}",
                exchange="BSE" if ".BSE" in symbol.upper() else ("NSE" if ".NSE" in symbol.upper() else "US"),
                interval="1w",
                open=Decimal(str(bar["1. open"])),
                high=Decimal(str(bar["2. high"])),
                low=Decimal(str(bar["3. low"])),
                close=Decimal(str(bar["4. close"])),
                volume=Decimal(str(bar["5. volume"])),
                candle_start=dt,
                candle_end=dt,
                source_provider="ALPHA_VANTAGE",
                data_freshness=DataFreshness.HISTORICAL,
                is_adjusted=False,
                currency="INR" if (".BSE" in symbol.upper() or ".NSE" in symbol.upper()) else "USD",
            ))
        return candles

    # -------------------------------------------------------------------------
    # 4. TIME_SERIES_MONTHLY
    # -------------------------------------------------------------------------
    async def fetch_monthly_ohlcv(self, symbol: str) -> List[OHLCVCandle]:
        data = await self._make_request("TIME_SERIES_MONTHLY", {"symbol": symbol})
        time_series = data.get("Monthly Time Series", {})
        candles = []
        for dt_str, bar in sorted(time_series.items()):
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
            candles.append(OHLCVCandle(
                feed_id=self.feed_id,
                instrument_id=f"EQ_{symbol.upper()}",
                exchange="BSE" if ".BSE" in symbol.upper() else ("NSE" if ".NSE" in symbol.upper() else "US"),
                interval="1M",
                open=Decimal(str(bar["1. open"])),
                high=Decimal(str(bar["2. high"])),
                low=Decimal(str(bar["3. low"])),
                close=Decimal(str(bar["4. close"])),
                volume=Decimal(str(bar["5. volume"])),
                candle_start=dt,
                candle_end=dt,
                source_provider="ALPHA_VANTAGE",
                data_freshness=DataFreshness.HISTORICAL,
                is_adjusted=False,
                currency="INR" if (".BSE" in symbol.upper() or ".NSE" in symbol.upper()) else "USD",
            ))
        return candles

    # -------------------------------------------------------------------------
    # 5. GLOBAL_QUOTE (EOD quote, not real-time)
    # -------------------------------------------------------------------------
    async def fetch_global_quote(self, symbol: str) -> Dict[str, Any]:
        cached = self.scheduler.get_cached_quote(symbol)
        if cached:
            return cached

        data = await self._make_request("GLOBAL_QUOTE", {"symbol": symbol})
        quote_data = data.get("Global Quote", {})
        if not quote_data:
            raise AlphaVantageAPIError("EMPTY_RESPONSE", f"No global quote returned for symbol '{symbol}'.")

        normalized = {
            "symbol": quote_data.get("01. symbol", symbol),
            "open": quote_data.get("02. open"),
            "high": quote_data.get("03. high"),
            "low": quote_data.get("04. low"),
            "price": quote_data.get("05. price"),
            "volume": quote_data.get("06. volume"),
            "latest_trading_day": quote_data.get("07. latest trading day"),
            "previous_close": quote_data.get("08. previous close"),
            "change": quote_data.get("09. change"),
            "change_percent": quote_data.get("10. change percent"),
            "data_freshness": DataFreshness.END_OF_DAY.value,
        }
        self.scheduler.cache_quote(symbol, normalized)
        return normalized

    # -------------------------------------------------------------------------
    # BaseProviderAdapter historical requirement
    # -------------------------------------------------------------------------
    async def fetch_historical(
        self,
        instrument_id: str,
        channel: MarketDataChannel,
        start_time: Any,
        end_time: Any,
        interval: str = "1d",
    ) -> List[Dict[str, Any]]:
        symbol = instrument_id.replace("EQ_", "")
        if interval == "1w":
            candles = await self.fetch_weekly_ohlcv(symbol)
        elif interval == "1M":
            candles = await self.fetch_monthly_ohlcv(symbol)
        else:
            candles = await self.fetch_daily_ohlcv(symbol)
        return [c.model_dump() for c in candles]

    async def health_check(self) -> Dict[str, Any]:
        quota = self.scheduler.get_quota_status()
        return {
            "provider_id": self.provider_id,
            "feed_id": self.feed_id,
            "plan": settings.ALPHA_VANTAGE_PLAN,
            "is_connected": self.is_connected,
            "quota_status": quota,
            "supported_functions": [
                "SYMBOL_SEARCH",
                "TIME_SERIES_DAILY (compact)",
                "TIME_SERIES_WEEKLY",
                "TIME_SERIES_MONTHLY",
                "GLOBAL_QUOTE",
            ],
            "excluded_premium_functions": list(self.EXCLUDED_PREMIUM_FUNCTIONS),
        }
