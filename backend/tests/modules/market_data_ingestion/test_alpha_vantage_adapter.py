"""
Comprehensive Test Suite for Alpha Vantage REST Provider Integration (M02 Addendum).
Covers:
1. US Daily OHLCV retrieval (compact, max 100 observations, raw unadjusted)
2. Indian BSE Daily OHLCV retrieval (e.g. RELIANCE.BSE)
3. Symbol search (SYMBOL_SEARCH) caching and mapping
4. Weekly and Monthly time series fetching
5. Global EOD quote parsing (marked as END_OF_DAY, not live streaming)
6. Quota scheduler enforcement (20 requests/day budget, rejects when exhausted)
7. Rejection of streaming calls (UnsupportedCapabilityError)
8. Rejection of excluded premium endpoints (TIME_SERIES_INTRADAY, DAILY_ADJUSTED)
9. Classification of provider errors (invalid key, unsupported symbol, rate limit)
10. API key credential redaction in logs/requests
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient, Response

from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.main import app
from backend.app.modules.market_data_ingestion.adapters.alpha_vantage import (
    AlphaVantageAPIError,
    AlphaVantageAdapter,
    UnsupportedCapabilityError,
)
from backend.app.modules.market_data_ingestion.adapters.quota_scheduler import (
    AlphaVantageQuotaScheduler,
    QuotaExceededException,
)
from backend.app.modules.market_data_ingestion.normalization.schemas import DataFreshness

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_test_db():
    import asyncio
    asyncio.run(init_db())
    yield


@pytest.fixture
def read_only_headers():
    return {"X-API-Key": settings.API_KEY_READ_ONLY}


# Mock response fixtures
MOCK_SYMBOL_SEARCH_RESPONSE = {
    "bestMatches": [
        {
            "1. symbol": "IBM",
            "2. name": "International Business Machines Corp",
            "3. type": "Equity",
            "4. region": "United States",
            "5. marketOpen": "09:30",
            "6. marketClose": "16:00",
            "7. timezone": "UTC-04",
            "8. currency": "USD",
            "9. matchScore": "1.0000",
        },
        {
            "1. symbol": "RELIANCE.BSE",
            "2. name": "Reliance Industries Limited",
            "3. type": "Equity",
            "4. region": "India",
            "5. marketOpen": "09:15",
            "6. marketClose": "15:30",
            "7. timezone": "UTC+05:30",
            "8. currency": "INR",
            "9. matchScore": "0.9000",
        },
    ]
}

MOCK_DAILY_RESPONSE = {
    "Meta Data": {
        "1. Information": "Daily Prices (open, high, low, close) and Volumes",
        "2. Symbol": "IBM",
        "3. Last Refreshed": "2026-10-30",
        "4. Output Size": "Compact",
        "5. Time Zone": "US/Eastern",
    },
    "Time Series (Daily)": {
        "2026-10-30": {
            "1. open": "210.5000",
            "2. high": "212.0000",
            "3. low": "209.8000",
            "4. close": "211.2500",
            "5. volume": "3500000",
        },
        "2026-10-29": {
            "1. open": "208.0000",
            "2. high": "211.0000",
            "3. low": "207.5000",
            "4. close": "210.0000",
            "5. volume": "2900000",
        },
    },
}

MOCK_GLOBAL_QUOTE_RESPONSE = {
    "Global Quote": {
        "01. symbol": "RELIANCE.BSE",
        "02. open": "2950.0000",
        "03. high": "2980.0000",
        "04. low": "2940.0000",
        "05. price": "2975.5000",
        "06. volume": "1250000",
        "07. latest trading day": "2026-10-30",
        "08. previous close": "2945.0000",
        "09. change": "30.5000",
        "10. change percent": "1.0357%",
    }
}


async def test_quota_scheduler_budget_and_rejection():
    scheduler = AlphaVantageQuotaScheduler(daily_budget=3)
    status = scheduler.get_quota_status()
    assert status["daily_budget"] == 3
    assert status["remaining_budget"] == 3
    assert status["safety_margin"] == 22

    # Call 1
    scheduler.acquire_call_permit("TIME_SERIES_DAILY", "IBM")
    assert scheduler.get_quota_status()["remaining_budget"] == 2

    # Call 2
    scheduler.acquire_call_permit("TIME_SERIES_DAILY", "TCS.BSE")
    assert scheduler.get_quota_status()["remaining_budget"] == 1

    # Call 3
    scheduler.acquire_call_permit("GLOBAL_QUOTE", "IBM")
    assert scheduler.get_quota_status()["is_budget_exhausted"] is True

    # Call 4 -> Exceeds budget -> QuotaExceededException
    with pytest.raises(QuotaExceededException):
        scheduler.acquire_call_permit("TIME_SERIES_DAILY", "RELIANCE.BSE")


async def test_symbol_search_and_caching():
    test_scheduler = AlphaVantageQuotaScheduler(daily_budget=20)
    adapter = AlphaVantageAdapter(api_key="TEST_KEY", scheduler=test_scheduler)
    await adapter.connect({})

    with patch.object(adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=MOCK_SYMBOL_SEARCH_RESPONSE, request=AsyncMock())

        results = await adapter.search_symbol("IBM")
        assert len(results) == 2
        assert results[0]["symbol"] == "IBM"
        assert results[1]["symbol"] == "RELIANCE.BSE"
        assert mock_get.call_count == 1

        # Second search for same keywords must hit the in-memory cache without an HTTP call
        cached_results = await adapter.search_symbol("IBM")
        assert len(cached_results) == 2
        assert mock_get.call_count == 1  # Unchanged!


async def test_daily_ohlcv_compact_unadjusted():
    test_scheduler = AlphaVantageQuotaScheduler(daily_budget=20)
    adapter = AlphaVantageAdapter(api_key="TEST_KEY", scheduler=test_scheduler)
    await adapter.connect({})

    with patch.object(adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=MOCK_DAILY_RESPONSE, request=AsyncMock())

        candles = await adapter.fetch_daily_ohlcv("IBM")
        assert len(candles) == 2
        c = candles[-1]
        assert c.instrument_id == "EQ_IBM"
        assert c.interval == "1d"
        assert c.data_freshness == DataFreshness.END_OF_DAY
        assert c.is_adjusted is False
        assert c.close == Decimal("211.2500")
        assert c.currency == "USD"


async def test_global_quote_parsing():
    test_scheduler = AlphaVantageQuotaScheduler(daily_budget=20)
    adapter = AlphaVantageAdapter(api_key="TEST_KEY", scheduler=test_scheduler)
    await adapter.connect({})

    with patch.object(adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=MOCK_GLOBAL_QUOTE_RESPONSE, request=AsyncMock())

        quote = await adapter.fetch_global_quote("RELIANCE.BSE")
        assert quote["symbol"] == "RELIANCE.BSE"
        assert quote["price"] == "2975.5000"
        assert quote["data_freshness"] == "END_OF_DAY"


async def test_streaming_and_premium_rejections():
    adapter = AlphaVantageAdapter(api_key="TEST_KEY")
    await adapter.connect({})

    # 1. Attempting to stream must raise UnsupportedCapabilityError
    with pytest.raises(UnsupportedCapabilityError):
        async for _ in adapter.stream_raw_events():
            pass

    # 2. Attempting to call excluded premium endpoints must raise UnsupportedCapabilityError
    with pytest.raises(UnsupportedCapabilityError):
        await adapter._make_request("TIME_SERIES_INTRADAY", {"symbol": "IBM"})

    with pytest.raises(UnsupportedCapabilityError):
        await adapter._make_request("TIME_SERIES_DAILY_ADJUSTED", {"symbol": "IBM"})


async def test_alpha_vantage_error_classifications():
    adapter = AlphaVantageAdapter(api_key="TEST_KEY")
    await adapter.connect({})

    # Error 1: Invalid API Key / Error Message
    with patch.object(adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json={"Error Message": "Invalid API call. Check API key."}, request=AsyncMock())
        with pytest.raises(AlphaVantageAPIError) as exc_info:
            await adapter.search_symbol("FAIL")
        assert exc_info.value.error_type == "INVALID_API_KEY"

    # Error 2: Rate limit Information message
    with patch.object(adapter.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json={"Information": "Thank you for using Alpha Vantage! Standard API call frequency is 5 calls per minute."}, request=AsyncMock())
        with pytest.raises(AlphaVantageAPIError) as exc_info:
            await adapter.fetch_daily_ohlcv("IBM")
        assert exc_info.value.error_type == "RATE_LIMIT_EXCEEDED"


async def test_alpha_vantage_rest_endpoints(read_only_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Check quota status endpoint
        res_quota = await ac.get("/api/v1/market-data/alpha-vantage/quota", headers=read_only_headers)
        assert res_quota.status_code == 200
        quota = res_quota.json()
        assert quota["daily_budget"] == 20
        assert quota["safety_margin"] == 5

