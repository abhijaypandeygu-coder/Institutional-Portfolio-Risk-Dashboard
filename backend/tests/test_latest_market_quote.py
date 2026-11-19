import unittest
from unittest.mock import patch,MagicMock
from backend.app.modules.market_data_ingestion.adapters.yfinance import latest_quote as quote
class LatestQuoteTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):quote._cache.clear()
 async def test_preserves_price_currency_and_market_timestamp(self):
  ticker=MagicMock();ticker.get_info.return_value={'regularMarketPrice':123.45,'currency':'INR','regularMarketTime':1700000000,'marketState':'CLOSED'}
  with patch.object(quote.yf,'Ticker',return_value=ticker) as factory:result=await quote.latest_market_quote('RELIANCE.NS')
  factory.assert_called_once_with('RELIANCE.NS');self.assertEqual(result['price'],123.45);self.assertEqual(result['currency'],'INR');self.assertEqual(result['source_time'],'2023-11-14T22:13:20+00:00');self.assertEqual(result['market_state'],'CLOSED')
 async def test_invalid_price_never_becomes_zero_or_a_generated_quote(self):
  for price in [None,0,-1,float('nan'),float('inf')]:
   ticker=MagicMock();ticker.get_info.return_value={'regularMarketPrice':price}
   with patch.object(quote.yf,'Ticker',return_value=ticker):result=await quote.latest_market_quote('BAD')
   self.assertEqual(result['status'],'unavailable');self.assertIsNone(result['price'])
 async def test_quote_timestamp_is_not_replaced_with_retrieval_time(self):
  ticker=MagicMock();ticker.get_info.return_value={'regularMarketPrice':100,'currency':'USD'}
  with patch.object(quote.yf,'Ticker',return_value=ticker):result=await quote.latest_market_quote('SPY')
  self.assertIsNone(result['source_time']);self.assertIsNotNone(result['retrieved_at'])
 async def test_uses_newer_extended_session_when_available(self):
  ticker=MagicMock();ticker.get_info.return_value={'regularMarketPrice':100,'regularMarketTime':1700000000,'postMarketPrice':102,'postMarketTime':1700000060,'currency':'USD'}
  with patch.object(quote.yf,'Ticker',return_value=ticker):result=await quote.latest_market_quote('AAPL')
  self.assertEqual(result['price'],102);self.assertEqual(result['session'],'POST')
if __name__=='__main__':unittest.main()
