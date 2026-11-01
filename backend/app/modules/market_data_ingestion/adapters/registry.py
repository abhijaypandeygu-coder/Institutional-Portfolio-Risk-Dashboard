"""
Module 02: Market Data Ingestion Engine - Provider Adapter Registry.
Manages provider adapter lifecycle and registration across multiple providers.
"""
from typing import Dict, Type
from backend.app.modules.market_data_ingestion.adapters.base import BaseProviderAdapter
from backend.app.modules.market_data_ingestion.adapters.simulator import SimulatedMarketDataAdapter


class ProviderAdapterRegistry:
    """Registry maintaining available adapter classes and active instances."""

    _adapter_classes: Dict[str, Type[BaseProviderAdapter]] = {
        "SIMULATOR": SimulatedMarketDataAdapter,
        "SIM_EXCHANGE_01": SimulatedMarketDataAdapter,
    }
    _instances: Dict[str, BaseProviderAdapter] = {}

    @classmethod
    def register_adapter_class(cls, provider_type: str, adapter_cls: Type[BaseProviderAdapter]) -> None:
        cls._adapter_classes[provider_type.upper()] = adapter_cls

    @classmethod
    def get_or_create_adapter(cls, feed_id: str, provider_type: str = "SIMULATOR") -> BaseProviderAdapter:
        key = f"{feed_id}_{provider_type.upper()}"
        if key not in cls._instances:
            adapter_cls = cls._adapter_classes.get(provider_type.upper(), SimulatedMarketDataAdapter)
            cls._instances[key] = adapter_cls(feed_id=feed_id, provider_id=provider_type)
        return cls._instances[key]

    @classmethod
    def get_instance(cls, feed_id: str, provider_type: str = "SIMULATOR") -> BaseProviderAdapter:
        key = f"{feed_id}_{provider_type.upper()}"
        return cls._instances.get(key) or cls.get_or_create_adapter(feed_id, provider_type)

    @classmethod
    def clear_all(cls) -> None:
        cls._instances.clear()
