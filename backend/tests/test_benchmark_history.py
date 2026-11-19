import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.modules.market_data_ingestion.adapters.yfinance import benchmark_history as history
from backend.app.modules.dashboard_visualization.liquidity_dashboard.router import router
class BenchmarkHistoryTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self): history._cache.clear()
 async def test_preserves_dates_and_actual_prices(self):
  ticker=MagicMock(); ticker.history.return_value=pd.DataFrame({'Close':[100,float('nan'),110]},index=pd.date_range('2025-12-30',periods=3,tz='America/New_York'));ticker.history_metadata={'currency':'USD'}
  with patch.object(history.yf,'Ticker',return_value=ticker) as provider:
   result=await history.benchmark_history('SPY','1Y')
  provider.assert_called_once_with('SPY');self.assertEqual([p['value'] for p in result['points']],[100,110]);self.assertTrue(result['points'][1]['timestamp'].startswith('2026-01-01'));self.assertEqual(result['return_treatment'],'adjusted_close_proxy')
 async def test_failure_never_returns_a_generated_curve(self):
  with patch.object(history,'_fetch',side_effect=RuntimeError('offline')):
   result=await history.benchmark_history('SPY','1Y')
  self.assertEqual(result['points'],[]);self.assertEqual(result['status'],'unavailable')
 async def test_price_index_disclosure(self):
  ticker=MagicMock();ticker.history.return_value=pd.DataFrame({'Close':[100,101]},index=pd.date_range('2026-01-01',periods=2));ticker.history_metadata={'currency':'INR'}
  with patch.object(history.yf,'Ticker',return_value=ticker):result=await history.benchmark_history('^NSEI','1Y')
  self.assertEqual(result['return_treatment'],'price_index');self.assertEqual(result['currency'],'INR')
class BenchmarkRouteTests(unittest.TestCase):
 def test_invalid_queries_rejected(self):
  app=FastAPI();app.include_router(router)
  with TestClient(app) as client:
   for args in [{'symbol':'AAPL,MSFT'},{'range':'BOGUS'},{'symbol':'../SPY'}]:self.assertEqual(client.get('/api/v1/dashboard/liquidity/benchmark-history',params=args).status_code,422)
if __name__=='__main__': unittest.main()
