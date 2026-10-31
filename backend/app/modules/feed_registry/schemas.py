"""
Module 01: Feed Registry & Configuration - Pydantic V2 Schemas.
"""
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.feed_registry.models import (
    AssetClass,
    CommandStatus,
    FeedCategory,
    FeedCommandType,
    FeedDesiredState,
    FeedRecordStatus,
    FeedRuntimeState,
    TransportProtocol,
)


# ============================================================================
# Generic / Base Schemas
# ============================================================================

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Feed Registry Schemas (Milestone 1 & 2)
# ============================================================================

class FeedCapabilities(BaseModel):
    depth: int = Field(default=1, ge=1, le=50, description="Order book depth supported")
    tick_by_tick: bool = Field(default=False, description="Tick by tick trade support")
    snapshots: bool = Field(default=True, description="Periodic snapshot support")
    historical: bool = Field(default=False, description="Historical replay support")
    conflated: bool = Field(default=False, description="Conflated feed stream support")
    custom: Dict[str, Any] = Field(default_factory=dict, description="Custom vendor specific capabilities")


class FeedCreate(BaseModel):
    feed_code: str = Field(..., min_length=2, max_length=64, description="Unique human-readable feed identifier")
    feed_name: str = Field(..., min_length=2, max_length=128, description="Display name for the feed")
    description: Optional[str] = Field(default=None, max_length=512)
    category: FeedCategory
    asset_class: AssetClass = AssetClass.EQUITIES
    transport_protocol: TransportProtocol
    capabilities: FeedCapabilities = Field(default_factory=FeedCapabilities)
    is_primary_eligible: bool = True
    is_backup_eligible: bool = True
    metadata_json: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("feed_code")
    @classmethod
    def validate_feed_code(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean.replace("_", "").replace("-", "").isalnum():
            raise ValueError("feed_code must contain only alphanumeric characters, underscores, and hyphens")
        return clean


class FeedUpdate(BaseModel):
    feed_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    capabilities: Optional[FeedCapabilities] = None
    is_primary_eligible: Optional[bool] = None
    is_backup_eligible: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None


class FeedResponse(ORMModel):
    id: UUID
    feed_code: str
    feed_name: str
    description: Optional[str] = None
    category: FeedCategory
    asset_class: AssetClass
    transport_protocol: TransportProtocol
    capabilities: Dict[str, Any]
    desired_state: FeedDesiredState
    record_status: FeedRecordStatus
    current_version: int
    is_primary_eligible: bool
    is_backup_eligible: bool
    metadata_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Feed Configuration Versioning Schemas (Milestone 3)
# ============================================================================

class ConfigurationPayload(BaseModel):
    endpoint_url: str = Field(..., description="Connection URL (ws://, wss://, tcp://, http://, udp://)")
    backup_endpoint_url: Optional[str] = Field(default=None)
    heartbeat_interval_seconds: int = Field(default=15, ge=1, le=300)
    reconnect_backoff_initial_ms: int = Field(default=500, ge=50, le=60000)
    reconnect_backoff_max_ms: int = Field(default=10000, ge=100, le=300000)
    max_reconnect_attempts: int = Field(default=10, ge=0, le=1000)
    subscription_symbols: List[str] = Field(default_factory=list)
    auth_credentials_ref: Optional[str] = Field(
        default=None,
        description="SecretReference in format secret://<scope>/<key>"
    )
    custom_parameters: Dict[str, Any] = Field(default_factory=dict)


class ConfigCreate(BaseModel):
    schema_version: str = Field(default="1.0.0", description="Semantic schema version")
    config_payload: ConfigurationPayload
    change_reason: str = Field(..., min_length=3, max_length=256, description="Mandatory audit justification")


class ConfigVersionResponse(ORMModel):
    id: UUID
    feed_id: UUID
    version_number: int
    schema_version: str
    config_payload: Dict[str, Any]
    config_hash: str
    change_reason: str
    author: str
    created_at: datetime


class ConfigDiffResponse(BaseModel):
    feed_id: UUID
    from_version: int
    to_version: int
    added: Dict[str, Any]
    removed: Dict[str, Any]
    modified: Dict[str, Dict[str, Any]]


class ConfigRollbackRequest(BaseModel):
    target_version: int = Field(..., ge=1, description="Target version number to rollback to")
    change_reason: str = Field(..., min_length=5, max_length=256, description="Rollback justification")


# ============================================================================
# Feed Lifecycle & Outbox Schemas (Milestone 4)
# ============================================================================

class StateTransitionRequest(BaseModel):
    target_state: FeedDesiredState
    reason: str = Field(..., min_length=3, max_length=256)
    command_parameters: Dict[str, Any] = Field(default_factory=dict)


class LifecycleCommandResponse(ORMModel):
    id: UUID
    feed_id: UUID
    command_type: FeedCommandType
    parameters: Dict[str, Any]
    idempotency_key: str
    status: CommandStatus
    attempts: int
    executed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime


# ============================================================================
# Feed Scheduling Schemas (Milestone 5)
# ============================================================================

class TradingSessionInterval(BaseModel):
    name: str = Field(..., description="e.g. Regular, Pre-market, Post-market")
    start_time: str = Field(..., description="HH:MM:SS format (24-hour)")
    end_time: str = Field(..., description="HH:MM:SS format (24-hour)")


class ScheduleCreate(BaseModel):
    timezone: str = Field(default="Asia/Kolkata", description="IANA Timezone e.g. Asia/Kolkata, UTC, America/New_York")
    auto_start_stop_enabled: bool = True
    sessions: List[TradingSessionInterval] = Field(default_factory=list)
    polling_interval_ms: int = Field(default=1000, ge=10, le=60000)
    active_days: List[int] = Field(
        default=[0, 1, 2, 3, 4],
        description="Days of week active (0=Monday, 6=Sunday)"
    )


class ScheduleResponse(ORMModel):
    id: UUID
    feed_id: UUID
    timezone: str
    auto_start_stop_enabled: bool
    sessions: List[Dict[str, Any]]
    polling_interval_ms: int
    active_days: List[int]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Priority & Failover Schemas (Milestone 6)
# ============================================================================

class PriorityMemberCreate(BaseModel):
    feed_id: UUID
    priority_rank: int = Field(..., ge=1, le=100)
    is_active_in_group: bool = True
    custom_weight: float = Field(default=1.0, gt=0.0)


class FailoverGroupCreate(BaseModel):
    group_name: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = Field(default=None, max_length=256)
    required_capabilities: Dict[str, Any] = Field(default_factory=dict)
    failover_latency_threshold_ms: float = Field(default=500.0, gt=0.0)
    consecutive_error_threshold: int = Field(default=3, ge=1, le=50)
    members: List[PriorityMemberCreate] = Field(default_factory=list)


class PriorityMemberResponse(ORMModel):
    id: UUID
    group_id: UUID
    feed_id: UUID
    priority_rank: int
    is_active_in_group: bool
    custom_weight: float
    created_at: datetime


class FailoverGroupResponse(ORMModel):
    id: UUID
    group_name: str
    description: Optional[str] = None
    required_capabilities: Dict[str, Any]
    failover_latency_threshold_ms: float
    consecutive_error_threshold: int
    created_at: datetime
    updated_at: datetime
    priority_members: List[PriorityMemberResponse] = []


# ============================================================================
# Health & Monitoring Schemas (Milestone 7)
# ============================================================================

class HealthEventReport(BaseModel):
    runtime_state: FeedRuntimeState
    latency_ms: Optional[float] = Field(default=None, ge=0.0)
    messages_received_delta: int = Field(default=0, ge=0)
    bytes_received_delta: int = Field(default=0, ge=0)
    error_count_delta: int = Field(default=0, ge=0)
    last_heartbeat_timestamp: Optional[datetime] = None
    last_data_timestamp: Optional[datetime] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class HealthEventResponse(ORMModel):
    id: int
    feed_id: UUID
    timestamp: datetime
    runtime_state: FeedRuntimeState
    latency_ms: Optional[float] = None
    messages_received_delta: int
    bytes_received_delta: int
    error_count_delta: int
    last_heartbeat_timestamp: Optional[datetime] = None
    last_data_timestamp: Optional[datetime] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class FeedHealthSummary(BaseModel):
    feed_id: UUID
    feed_code: str
    desired_state: FeedDesiredState
    latest_runtime_state: Optional[FeedRuntimeState] = None
    last_heartbeat_timestamp: Optional[datetime] = None
    last_data_timestamp: Optional[datetime] = None
    current_latency_ms: Optional[float] = None
    total_errors_recorded: int = 0
    is_healthy: bool = False


# ============================================================================
# Audit Log Schemas (Milestone 8)
# ============================================================================

class AuditLogResponse(ORMModel):
    id: int
    actor: str
    operation: str
    resource_type: str
    resource_id: Optional[str] = None
    success: bool
    details: Dict[str, Any]
    client_ip: Optional[str] = None
    created_at: datetime
