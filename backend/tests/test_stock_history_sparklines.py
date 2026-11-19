import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.modules.market_data_ingestion.adapters.yfinance import stock_history as history
from backend.app.modules.dashboard_visualization.liquidity_dashboard.router import router

class StockHistoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        history._cache.clear()

    async def test_filters_invalid_prices_without_substituting_other_symbols(self):
        ticker = MagicMock()
        ticker.history.return_value = pd.DataFrame({"Close": [100, float("nan"), float("inf"), -3, 110]}, index=pd.date_range("2026-11-01", periods=5, tz="UTC"))
        ticker.history_metadata = {"currency": "USD"}
        with patch.object(history.yf, "Ticker", return_value=ticker) as factory:
            data = await history.get_stock_history("RELIANCE.NS")
        factory.assert_called_once_with("RELIANCE.NS")
        self.assertEqual([p["close"] for p in data["points"]], [100, 110])
        self.assertEqual(data["status"], "available")
        self.assertTrue(data["adjusted"])

    async def test_failure_returns_unavailable_not_generated_values(self):
        with patch.object(history, "_fetch", side_effect=RuntimeError("offline")):
            data = await history.get_stock_history("AAPL")
        self.assertEqual(data["points"], [])
        self.assertEqual(data["status"], "unavailable")
        self.assertNotIn("AAPL", history._cache)

    async def test_success_is_cached(self):
        result = {"status": "available", "symbol": "AAPL", "points": [{"close": 100}, {"close": 101}]}
        with patch.object(history, "_fetch", return_value=result) as fetch:
            await history.get_stock_history("AAPL")
            await history.get_stock_history("AAPL")
        self.assertEqual(fetch.call_count, 1)

    async def test_single_observation_is_not_a_history_chart(self):
        ticker = MagicMock()
        ticker.history.return_value = pd.DataFrame({"Close": [100]}, index=pd.date_range("2026-11-01", periods=1, tz="UTC"))
        ticker.history_metadata = {}
        with patch.object(history.yf, "Ticker", return_value=ticker):
            result = await history.get_stock_history("AAPL")
        self.assertEqual(result["status"], "unavailable")

class HistoryRouteTests(unittest.TestCase):
    def test_rejects_invalid_symbol_before_provider_call(self):
        app = FastAPI(); app.include_router(router)
        with TestClient(app) as client:
            for symbol in ["AAPL/../MSFT", "AAPL,MSFT", "", "A" * 25]:
                self.assertEqual(client.get("/api/v1/dashboard/liquidity/stock-history", params={"symbol": symbol}).status_code, 422)

if __name__ == "__main__":
    unittest.main()
