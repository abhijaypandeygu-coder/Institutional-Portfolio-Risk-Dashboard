"""
M01 -> M02 Integration Interface Contract.
Provides typed schemas and client contract for M02 (Market Data Ingestion Engine)
to discover feeds, consume desired state/configs, and report runtime health.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from backend.app.modules.feed_registry.models import (
    AssetClass,
    FeedDesiredState,
    FeedRuntimeState,
    TransportProtocol,
)


class FeedRuntimeConfig(BaseModel):
    """Configuration bundle consumed by M02 to initialize connection and session."""
    feed_id: UUID
    feed_code: str
    asset_class: AssetClass
    transport_protocol: TransportProtocol
    desired_state: FeedDesiredState
    version_number: int
    endpoint_url: str
    backup_endpoint_url: Optional[str] = None
    heartbeat_interval_seconds: int = 15
    reconnect_backoff_initial_ms: int = 500
    reconnect_backoff_max_ms: int = 10000
    max_reconnect_attempts: int = 10
    subscription_symbols: List[str] = []
    auth_credentials_ref: Optional[str] = None
    custom_parameters: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class M02HealthReportPayload(BaseModel):
    """Runtime telemetry reported by M02 to M01 health sink."""
    runtime_state: FeedRuntimeState
    latency_ms: Optional[float] = None
    messages_received_delta: int = 0
    bytes_received_delta: int = 0
    error_count_delta: int = 0
    last_heartbeat_timestamp: Optional[datetime] = None
    last_data_timestamp: Optional[datetime] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class IM01FeedRegistryClient:
    """Interface that M02 calls to interact with M01."""

    async def get_active_feeds(self) -> List[FeedRuntimeConfig]:
        """Fetch all feeds currently flagged as ACTIVE with their latest configuration."""
        raise NotImplementedError

    async def report_health(self, feed_id: UUID, report: M02HealthReportPayload) -> None:
        """Report runtime connection health, state, and metrics to M01."""
        raise NotImplementedError

