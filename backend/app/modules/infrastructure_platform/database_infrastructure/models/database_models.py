import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Numeric,
    DateTime,
    Boolean,
    Text,
    JSON,
    Enum as SQLEnum,
    Index,
)
from backend.app.core.database import Base


class BackupStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CORRUPTED = "CORRUPTED"


class BackupType(str, enum.Enum):
    FULL = "FULL"
    DIFFERENTIAL = "DIFFERENTIAL"
    WAL_ARCHIVE = "WAL_ARCHIVE"


class PartitionInterval(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class DatabasePartitionMetadata(Base):
    """Catalog tracking declarative and dynamic table partition boundaries and health."""
    __tablename__ = "db_partition_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_table: str = Column(String(128), nullable=False, index=True)
    partition_name: str = Column(String(128), unique=True, nullable=False, index=True)
    partition_interval = Column(SQLEnum(PartitionInterval), nullable=False, default=PartitionInterval.MONTHLY)
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    row_count = Column(BigInteger, nullable=False, default=0)
    size_bytes = Column(BigInteger, nullable=False, default=0)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_db_partition_lookup", "parent_table", "period_start", "period_end"),
    )


class DatabaseBackupRecord(Base):
    """Institutional disaster recovery backup manifest and verification record."""
    __tablename__ = "db_backup_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    backup_id = Column(String(64), unique=True, nullable=False, index=True)
    backup_type = Column(SQLEnum(BackupType), nullable=False, default=BackupType.FULL)
    storage_path = Column(String(512), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    checksum_sha256 = Column(String(128), nullable=False)
    rpo_timestamp = Column(DateTime, nullable=False, comment="Point-in-time recovery watermark")
    duration_seconds = Column(Numeric(precision=10, scale=2), nullable=False)
    status = Column(SQLEnum(BackupStatus), nullable=False, default=BackupStatus.COMPLETED, index=True)
    verification_status = Column(String(32), nullable=False, default="UNVERIFIED")
    last_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class DatabaseQueryPerformanceBaseline(Base):
    """Tracks query latency regressions and execution profiles for critical analytical queries."""
    __tablename__ = "db_query_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_signature = Column(String(128), unique=True, nullable=False, index=True)
    workload_type = Column(String(32), nullable=False, default="TRANSACTIONAL") # TRANSACTIONAL vs ANALYTICAL
    avg_latency_ms = Column(Numeric(precision=10, scale=3), nullable=False)
    p95_latency_ms = Column(Numeric(precision=10, scale=3), nullable=False)
    p99_latency_ms = Column(Numeric(precision=10, scale=3), nullable=False)
    call_count = Column(BigInteger, nullable=False, default=1)
    last_executed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
