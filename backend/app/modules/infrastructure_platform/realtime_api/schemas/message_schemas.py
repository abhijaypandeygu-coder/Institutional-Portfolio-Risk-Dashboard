import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, ConfigDict


class RealtimeChannelType(str, enum.Enum):
    MARKET = "market"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    ALERTS = "alerts"


class ClientMessageType(str, enum.Enum):
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    RESYNC_REQUEST = "resync.request"
    PING = "ping"


class ServerMessageType(str, enum.Enum):
    CONNECTION_ACK = "connection.ack"
    SUBSCRIPTION_ACK = "subscription.ack"
    SUBSCRIPTION_ERROR = "subscription.error"
    EVENT = "event"
    RESYNC_STARTED = "resync.started"
    RESYNC_COMPLETED = "resync.completed"
    RESYNC_REQUIRED = "resync.required"
    PONG = "pong"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


# Client Inbound Message Schemas
class SubscribeMessage(BaseModel):
    type: ClientMessageType = ClientMessageType.SUBSCRIBE
    request_id: str = Field(..., description="Unique client request ID")
    channel: RealtimeChannelType
    resource_ids: List[str] = Field(default_factory=list, description="Target IDs (e.g. ['PORT-001'] or ['AAPL', 'RELIANCE'])")
    event_types: List[str] = Field(default_factory=list, description="Target event sub-types (e.g. ['market.quote', 'risk.var.updated'])")
    options: Dict[str, Any] = Field(default_factory=dict, description="Channel options (e.g. {'depth': 10})")


class UnsubscribeMessage(BaseModel):
    type: ClientMessageType = ClientMessageType.UNSUBSCRIBE
    request_id: str
    subscription_id: str


class ResyncRequestMessage(BaseModel):
    type: ClientMessageType = ClientMessageType.RESYNC_REQUEST
    request_id: str
    stream_id: str
    from_sequence: int = Field(..., ge=1, description="Sequence number after the last received event")


# Server Outbound Message Schemas
class ConnectionAckMessage(BaseModel):
    type: ServerMessageType = ServerMessageType.CONNECTION_ACK
    connection_id: str
    status: str = "CONNECTED"
    server_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    heartbeat_interval_seconds: int = 30
    protocol_version: int = 1


class SubscriptionAckMessage(BaseModel):
    type: ServerMessageType = ServerMessageType.SUBSCRIPTION_ACK
    request_id: str
    subscription_id: str
    channel: RealtimeChannelType
    accepted_resources: List[str]
    rejected_resources: List[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionErrorMessage(BaseModel):
    type: ServerMessageType = ServerMessageType.SUBSCRIPTION_ERROR
    request_id: str
    code: str
    message: str


class RealtimeEventEnvelope(BaseModel):
    """Institutional standardized outer envelope for real-time messages."""
    event_id: str
    event_type: str
    channel: RealtimeChannelType
    schema_version: int = 1
    stream_id: str
    sequence: int
    occurred_at: datetime
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    producer_module: str
    resource_id: str
    quality_status: str = "VALID"
    payload: Dict[str, Any]


class RealtimeServerMessage(BaseModel):
    type: ServerMessageType = ServerMessageType.EVENT
    event: RealtimeEventEnvelope


class ResyncStatusMessage(BaseModel):
    type: ServerMessageType
    stream_id: str
    from_sequence: int
    to_sequence: Optional[int] = None
    replayed_count: Optional[int] = None
    message: Optional[str] = None
