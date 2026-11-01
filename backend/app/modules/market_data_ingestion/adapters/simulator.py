"""
Module 02: Market Data Ingestion Engine - High-Fidelity Simulated Market Data Adapter.
Generates realistic Level 1 ticks, OHLCV candles, executed trades, L2 snapshots,
incremental order book deltas, heartbeats, simulated sequence gaps, duplicates, and disconnects.
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import random
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import uuid4

from backend.app.modules.market_data_ingestion.adapters.base import BaseProviderAdapter
from backend.app.modules.market_data_ingestion.normalization.schemas import MarketDataChannel


class SimulatedMarketDataAdapter(BaseProviderAdapter):
    """
    Institutional simulator adapter supporting deterministic or synthetic market feeds.
    Provides controllable chaos features: duplicate injection, gap creation, and disconnects.
    """

    def __init__(self, feed_id: str, provider_id: str = "SIM_EXCHANGE_01"):
        super().__init__(feed_id, provider_id)
        self._running = False
        self._sequence_counter = 1000
        self._base_prices = {
            "RELIANCE": Decimal("2950.00"),
            "TCS": Decimal("3820.50"),
            "INFY": Decimal("1540.25"),
            "HDFCBANK": Decimal("1670.00"),
        }
        self.inject_duplicate_once = False
        self.inject_gap_once = False

    async def connect(self, config: Dict[str, Any]) -> bool:
        self.is_connected = True
        self._running = True
        return True

    async def disconnect(self) -> None:
        self._running = False
        self.is_connected = False

    async def subscribe(self, instruments: List[str], channels: List[MarketDataChannel]) -> bool:
        for inst in instruments:
            clean = inst.upper()
            if clean not in self.subscribed_instruments:
                self.subscribed_instruments[clean] = []
            for ch in channels:
                if ch not in self.subscribed_instruments[clean]:
                    self.subscribed_instruments[clean].append(ch)
            if clean not in self._base_prices:
                self._base_prices[clean] = Decimal("1000.00")
        return True

    async def unsubscribe(self, instruments: List[str], channels: List[MarketDataChannel]) -> bool:
        for inst in instruments:
            clean = inst.upper()
            if clean in self.subscribed_instruments:
                for ch in channels:
                    if ch in self.subscribed_instruments[clean]:
                        self.subscribed_instruments[clean].remove(ch)
        return True

    def _next_sequence(self) -> int:
        if self.inject_gap_once:
            self.inject_gap_once = False
            self._sequence_counter += 5  # Skip 5 sequence numbers to trigger gap detection!
        self._sequence_counter += 1
        return self._sequence_counter

    def generate_tick_payload(self, symbol: str) -> Dict[str, Any]:
        curr = self._base_prices.get(symbol, Decimal("1000.00"))
        delta = Decimal(str(round(random.uniform(-1.5, 1.5), 2)))
        new_price = max(Decimal("1.00"), curr + delta)
        self._base_prices[symbol] = new_price

        spread = Decimal("0.25")
        bid_price = new_price - spread
        ask_price = new_price + spread
        qty = Decimal(str(random.randint(10, 500)))

        return {
            "msg_type": "TICK",
            "provider_event_id": f"evt-{uuid4().hex[:8]}",
            "feed_id": self.feed_id,
            "provider_id": self.provider_id,
            "symbol": symbol,
            "instrument_id": f"EQ_{symbol}",
            "exchange": "NSE",
            "last_price": str(new_price),
            "last_qty": str(qty),
            "best_bid": str(bid_price),
            "best_bid_qty": str(random.randint(50, 1000)),
            "best_ask": str(ask_price),
            "best_ask_qty": str(random.randint(50, 1000)),
            "sequence": self._next_sequence(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def generate_snapshot_payload(self, symbol: str) -> Dict[str, Any]:
        mid = self._base_prices.get(symbol, Decimal("1000.00"))
        seq = self._next_sequence()

        bids = []
        asks = []
        for i in range(1, 6):
            step = Decimal(str(i * 0.25))
            bids.append({
                "price": str(mid - step),
                "quantity": str(random.randint(100, 2000)),
                "order_count": random.randint(1, 15),
                "level_position": i,
            })
            asks.append({
                "price": str(mid + step),
                "quantity": str(random.randint(100, 2000)),
                "order_count": random.randint(1, 15),
                "level_position": i,
            })

        return {
            "msg_type": "SNAPSHOT",
            "event_id": f"snap-{uuid4().hex[:8]}",
            "feed_id": self.feed_id,
            "provider_id": self.provider_id,
            "symbol": symbol,
            "instrument_id": f"EQ_{symbol}",
            "exchange": "NSE",
            "sequence": seq,
            "bids": bids,
            "asks": asks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def generate_delta_payload(self, symbol: str, side: str, operation: str, price: Decimal, qty: Decimal) -> Dict[str, Any]:
        seq = self._next_sequence()
        return {
            "msg_type": "DELTA",
            "event_id": f"delta-{uuid4().hex[:8]}",
            "feed_id": self.feed_id,
            "provider_id": self.provider_id,
            "symbol": symbol,
            "instrument_id": f"EQ_{symbol}",
            "exchange": "NSE",
            "sequence": seq,
            "side": side,
            "operation": operation,
            "price": str(price),
            "quantity": str(qty),
            "order_count": random.randint(1, 10),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def generate_trade_payload(self, symbol: str) -> Dict[str, Any]:
        curr = self._base_prices.get(symbol, Decimal("1000.00"))
        seq = self._next_sequence()
        return {
            "msg_type": "TRADE",
            "event_id": f"trade-{uuid4().hex[:8]}",
            "provider_trade_id": f"TRD-{uuid4().hex[:10].upper()}",
            "feed_id": self.feed_id,
            "provider_id": self.provider_id,
            "symbol": symbol,
            "instrument_id": f"EQ_{symbol}",
            "exchange": "NSE",
            "price": str(curr),
            "quantity": str(random.randint(25, 250)),
            "aggressor_side": random.choice(["BID", "ASK"]),
            "sequence": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def stream_raw_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Continuously streams ticks, snapshots, deltas, and trades."""
        symbols = list(self.subscribed_instruments.keys())
        if not symbols:
            symbols = ["RELIANCE", "TCS"]

        while self._running and self.is_connected:
            for sym in symbols:
                channels = self.subscribed_instruments.get(sym, [MarketDataChannel.TICK])

                # Tick stream
                if MarketDataChannel.TICK in channels or MarketDataChannel.ORDER_BOOK_L1 in channels:
                    tick = self.generate_tick_payload(sym)
                    yield tick
                    if self.inject_duplicate_once:
                        self.inject_duplicate_once = False
                        yield tick  # Re-emit duplicate message!

                # Trade stream
                if MarketDataChannel.TRADE in channels:
                    yield self.generate_trade_payload(sym)

            # Heartbeat every cycle
            yield {
                "msg_type": "HEARTBEAT",
                "feed_id": self.feed_id,
                "provider_id": self.provider_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await asyncio.sleep(0.01)

    async def fetch_historical(
        self,
        instrument_id: str,
        channel: MarketDataChannel,
        start_time: Any,
        end_time: Any,
        interval: str = "1m",
    ) -> List[Dict[str, Any]]:
        """Simulate historical OHLCV or trade retrieval."""
        results = []
        base = Decimal("2500.00")
        for i in range(10):
            o = base + Decimal(str(i * 2))
            h = o + Decimal("5.00")
            l = o - Decimal("3.00")
            c = o + Decimal("1.50")
            v = Decimal(str(10000 + i * 500))
            results.append({
                "interval": interval,
                "open": str(o),
                "high": str(h),
                "low": str(l),
                "close": str(c),
                "volume": str(v),
                "candle_start": datetime.now(timezone.utc).isoformat(),
                "candle_end": datetime.now(timezone.utc).isoformat(),
            })
        return results

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY" if self.is_connected else "DISCONNECTED",
            "provider_id": self.provider_id,
            "feed_id": self.feed_id,
            "is_connected": self.is_connected,
            "subscribed_symbols_count": len(self.subscribed_instruments),
            "current_sequence": self._sequence_counter,
        }
