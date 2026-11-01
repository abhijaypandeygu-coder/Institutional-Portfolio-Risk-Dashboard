"""
Module 02: Market Data Ingestion Engine - In-Process Event Distribution Bus.
Delivers normalized market events to internal subscribers (M03 Quality, M05 Portfolio, M13 Dashboard)
with consumer isolation and asynchronous decoupling.
"""
import asyncio
from typing import Callable, Coroutine, Dict, List, Set
from backend.app.modules.market_data_ingestion.normalization.schemas import MarketDataChannel


class EventBus:
    """Asynchronous pub/sub event bus with consumer isolation."""

    def __init__(self):
        # channel -> set of async handler callbacks
        self._subscribers: Dict[MarketDataChannel, List[Callable[[dict], Coroutine]]] = {}
        for ch in MarketDataChannel:
            self._subscribers[ch] = []

    def subscribe(self, channel: MarketDataChannel, handler: Callable[[dict], Coroutine]) -> None:
        if handler not in self._subscribers[channel]:
            self._subscribers[channel].append(handler)

    def unsubscribe(self, channel: MarketDataChannel, handler: Callable[[dict], Coroutine]) -> None:
        if handler in self._subscribers[channel]:
            self._subscribers[channel].remove(handler)

    async def publish(self, channel: MarketDataChannel, event_data: dict) -> None:
        """Asynchronously dispatches event to all subscribers without blocking sender."""
        handlers = list(self._subscribers.get(channel, []))
        for h in handlers:
            try:
                # Fire and protect execution
                asyncio.create_task(h(event_data))
            except Exception:
                pass

    def clear(self) -> None:
        for ch in self._subscribers:
            self._subscribers[ch].clear()


# Global Singleton Event Bus for M02
global_event_bus = EventBus()
