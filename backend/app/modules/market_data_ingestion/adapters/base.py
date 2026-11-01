"""
Module 02: Market Data Ingestion Engine - Abstract Provider Adapter Base Interface.
All streaming and REST provider adapters implement this contract.
"""
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from backend.app.modules.market_data_ingestion.normalization.schemas import MarketDataChannel


class BaseProviderAdapter(ABC):
    """
    Standard provider adapter contract for financial market data ingestion.
    Supports connect, disconnect, subscribe, streaming events, historical fetching, and health checks.
    """

    def __init__(self, feed_id: str, provider_id: str):
        self.feed_id = feed_id
        self.provider_id = provider_id
        self.is_connected = False
        self.subscribed_instruments: Dict[str, List[MarketDataChannel]] = {}

    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> bool:
        """Establish connection with the provider."""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the provider."""
        raise NotImplementedError

    @abstractmethod
    async def subscribe(self, instruments: List[str], channels: List[MarketDataChannel]) -> bool:
        """Subscribe to market data channels for specified instruments."""
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe(self, instruments: List[str], channels: List[MarketDataChannel]) -> bool:
        """Unsubscribe from market data channels for specified instruments."""
        raise NotImplementedError

    @abstractmethod
    async def stream_raw_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Asynchronously yield raw incoming event payloads."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_historical(
        self,
        instrument_id: str,
        channel: MarketDataChannel,
        start_time: Any,
        end_time: Any,
        interval: str = "1m",
    ) -> List[Dict[str, Any]]:
        """Fetch historical records via REST/replay API."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on connection status, latency, and subscription counts."""
        raise NotImplementedError
