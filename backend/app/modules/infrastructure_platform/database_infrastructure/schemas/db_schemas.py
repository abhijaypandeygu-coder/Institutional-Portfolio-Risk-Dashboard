from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.database_infrastructure.models.database_models import (
    BackupStatus,
    BackupType,
    PartitionInterval,
)


class DatabaseHealthSummary(BaseModel):
    is_connected: bool
    database_engine: str
    active_connections: int
    idle_connections: int
    pool_size: int
    transaction_isolation: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PartitionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parent_table: str
    partition_name: str
    partition_interval: PartitionInterval
    period_start: datetime
    period_end: datetime
    row_count: int
    size_bytes: int
    is_archived: bool
    created_at: datetime


class BackupCreateRequest(BaseModel):
    backup_type: BackupType = BackupType.FULL
    target_directory: Optional[str] = None


class BackupRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    backup_id: str
    backup_type: BackupType
    storage_path: str
    size_bytes: int
    checksum_sha256: str
    rpo_timestamp: datetime
    duration_seconds: Decimal
    status: BackupStatus
    verification_status: str
    last_verified_at: Optional[datetime] = None
    created_at: datetime


class QueryBaselineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query_signature: str
    workload_type: str
    avg_latency_ms: Decimal
    p95_latency_ms: Decimal
    p99_latency_ms: Decimal
    call_count: int
    last_executed_at: datetime
