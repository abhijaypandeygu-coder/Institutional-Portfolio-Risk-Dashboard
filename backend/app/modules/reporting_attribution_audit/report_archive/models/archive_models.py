import enum
from datetime import datetime, timezone
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
    ForeignKey,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class ReportArchiveType(str, enum.Enum):
    DAILY_RISK = "DAILY_RISK"
    PORTFOLIO_PERFORMANCE = "PORTFOLIO_PERFORMANCE"
    RISK_ATTRIBUTION = "RISK_ATTRIBUTION"
    STRESS_TESTING = "STRESS_TESTING"
    LIQUIDITY = "LIQUIDITY"
    OTHER = "OTHER"


class ArchiveStatus(str, enum.Enum):
    ARCHIVING = "ARCHIVING"
    AVAILABLE = "AVAILABLE"
    ARCHIVE_FAILED = "ARCHIVE_FAILED"
    SUPERSEDED = "SUPERSEDED"
    RESTATED = "RESTATED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    QUARANTINED = "QUARANTINED"


class GenerationReason(str, enum.Enum):
    INITIAL = "INITIAL"
    SCHEDULED_REGENERATION = "SCHEDULED_REGENERATION"
    DATA_CORRECTION = "DATA_CORRECTION"
    MODEL_UPDATE = "MODEL_UPDATE"
    CONFIGURATION_UPDATE = "CONFIGURATION_UPDATE"
    USER_REQUESTED_REGENERATION = "USER_REQUESTED_REGENERATION"
    RESTATEMENT = "RESTATEMENT"
    OTHER = "OTHER"


class ArtifactFormat(str, enum.Enum):
    PDF = "PDF"
    CSV = "CSV"
    XLSX = "XLSX"
    HTML = "HTML"
    JSON = "JSON"
    OTHER = "OTHER"


class IntegrityStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CORRUPTED = "CORRUPTED"
    MISSING = "MISSING"


class LegalHoldStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"


class ReportArchive(Base):
    """Core registry representing an immutable, versioned historical report archive record."""
    __tablename__ = "report_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String(64), unique=True, nullable=False, index=True)
    report_id = Column(String(64), nullable=False, index=True)
    report_run_id = Column(String(64), nullable=False, index=True)
    portfolio_id = Column(String(64), nullable=False, index=True)
    portfolio_name_snapshot = Column(String(255), nullable=True)
    report_type = Column(SQLEnum(ReportArchiveType), nullable=False, index=True)
    report_title_snapshot = Column(String(255), nullable=False)
    report_definition_id = Column(String(64), nullable=True)
    report_definition_version = Column(String(32), nullable=True)

    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    valuation_timestamp = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    version_number = Column(Integer, nullable=False, default=1)
    generation_reason = Column(SQLEnum(GenerationReason), nullable=False, default=GenerationReason.INITIAL)
    status = Column(SQLEnum(ArchiveStatus), nullable=False, default=ArchiveStatus.ARCHIVING, index=True)

    # Lineage & Relationships
    previous_version_id = Column(String(64), nullable=True)
    supersedes_version_id = Column(String(64), nullable=True)
    restates_version_id = Column(String(64), nullable=True)
    withdraws_version_id = Column(String(64), nullable=True)
    restatement_reason = Column(Text, nullable=True)
    withdrawal_reason = Column(Text, nullable=True)

    # Key structured financial summary metrics (for cross-version comparison)
    summary_nav = Column(Numeric(precision=20, scale=4), nullable=True)
    summary_var_value = Column(Numeric(precision=20, scale=4), nullable=True)
    summary_es_value = Column(Numeric(precision=20, scale=4), nullable=True)
    currency = Column(String(10), nullable=False, default="USD")

    created_by = Column(String(64), nullable=False, default="SYSTEM")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    artifact = relationship("ReportArchiveArtifact", back_populates="archive", uselist=False, cascade="all, delete-orphan")
    provenance = relationship("ReportArchiveProvenance", back_populates="archive", uselist=False, cascade="all, delete-orphan")
    model_versions = relationship("ReportArchiveModelVersion", back_populates="archive", cascade="all, delete-orphan")
    data_versions = relationship("ReportArchiveDataVersion", back_populates="archive", cascade="all, delete-orphan")
    config_versions = relationship("ReportArchiveConfigVersion", back_populates="archive", cascade="all, delete-orphan")
    legal_holds = relationship("ReportArchiveLegalHold", back_populates="archive", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_report_archive_lookup", "portfolio_id", "report_type", "period_start", "period_end"),
        Index("ix_report_archive_version_lookup", "portfolio_id", "report_type", "version_number"),
    )


class ReportArchiveArtifact(Base):
    """Metadata regarding physical or object-stored report artifacts and their cryptographic integrity."""
    __tablename__ = "report_archive_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(String(64), unique=True, nullable=False, index=True)
    archive_id = Column(String(64), ForeignKey("report_archive.archive_id", ondelete="CASCADE"), nullable=False, index=True)
    
    storage_backend = Column(String(32), nullable=False, default="LOCAL_FS")
    storage_key = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_extension = Column(String(16), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    
    hash_algorithm = Column(String(16), nullable=False, default="SHA256")
    artifact_hash = Column(String(128), nullable=False, index=True)
    integrity_status = Column(SQLEnum(IntegrityStatus), nullable=False, default=IntegrityStatus.UNVERIFIED)
    last_verified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    archive = relationship("ReportArchive", back_populates="artifact")


class ReportArchiveProvenance(Base):
    """Reproducibility manifest preserving execution environment, runtime parameters, and limitations."""
    __tablename__ = "report_archive_provenance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String(64), ForeignKey("report_archive.archive_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    report_run_id = Column(String(64), nullable=False, index=True)

    application_version = Column(String(64), nullable=False, default="1.0.0")
    code_commit = Column(String(64), nullable=True)
    environment_id = Column(String(32), nullable=False, default="production-local")
    
    execution_started_at = Column(DateTime, nullable=False)
    execution_completed_at = Column(DateTime, nullable=False)
    trigger_source = Column(String(64), nullable=False, default="SCHEDULED_RUN")
    requesting_actor_id = Column(String(64), nullable=False, default="SYSTEM")
    
    report_parameters = Column(JSON, nullable=False, default=dict)
    data_quality_summary = Column(JSON, nullable=True)
    known_limitations = Column(JSON, nullable=True)
    
    provenance_schema_version = Column(String(16), nullable=False, default="1.0")
    manifest_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    archive = relationship("ReportArchive", back_populates="provenance")


class ReportArchiveModelVersion(Base):
    """Analytical & quantitative models executed to construct the report."""
    __tablename__ = "report_archive_model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String(64), ForeignKey("report_archive.archive_id", ondelete="CASCADE"), nullable=False, index=True)

    model_id = Column(String(64), nullable=False)
    model_name = Column(String(128), nullable=False)
    model_version = Column(String(32), nullable=False)
    implementation_version = Column(String(32), nullable=True)
    configuration_version = Column(String(32), nullable=True)
    model_artifact_hash = Column(String(128), nullable=True)
    parameter_set_id = Column(String(64), nullable=True)
    effective_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)

    archive = relationship("ReportArchive", back_populates="model_versions")


class ReportArchiveDataVersion(Base):
    """Source datasets, market data, and portfolio state snapshots consumed during report calculation."""
    __tablename__ = "report_archive_data_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String(64), ForeignKey("report_archive.archive_id", ondelete="CASCADE"), nullable=False, index=True)

    source_type = Column(String(64), nullable=False) # e.g. MARKET_DATA, PORTFOLIO_VALUATION, REFERENCE_DATA
    source_id = Column(String(64), nullable=False)
    dataset_id = Column(String(64), nullable=True)
    snapshot_id = Column(String(64), nullable=True, index=True)
    provider_id = Column(String(64), nullable=True)
    source_version = Column(String(32), nullable=True)
    data_as_of = Column(DateTime, nullable=False)
    ingested_at = Column(DateTime, nullable=True)
    data_cutoff_at = Column(DateTime, nullable=True)
    quality_status = Column(String(32), nullable=False, default="VERIFIED")

    archive = relationship("ReportArchive", back_populates="data_versions")


class ReportArchiveConfigVersion(Base):
    """Immutable snapshot of report methodology, risk parameters, and limits used."""
    __tablename__ = "report_archive_config_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String(64), ForeignKey("report_archive.archive_id", ondelete="CASCADE"), nullable=False, index=True)

    configuration_id = Column(String(64), nullable=False)
    configuration_version = Column(String(32), nullable=False)
    configuration_type = Column(String(64), nullable=False) # e.g. RISK_METHODOLOGY, BENCHMARK_MAP, REPORT_TEMPLATE
    configuration_snapshot = Column(JSON, nullable=False)
    configuration_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    archive = relationship("ReportArchive", back_populates="config_versions")


class ReportArchiveRetentionPolicy(Base):
    """Retention rule configuration defining storage duration and expiration lifecycle."""
    __tablename__ = "report_archive_retention_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(String(64), unique=True, nullable=False, index=True)
    policy_name = Column(String(128), nullable=False)
    policy_version = Column(Integer, nullable=False, default=1)
    report_type = Column(SQLEnum(ReportArchiveType), nullable=False, index=True)
    retention_days = Column(Integer, nullable=False) # e.g. 2555 (7 years)
    effective_from = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    effective_to = Column(DateTime, nullable=True)
    expiration_action = Column(String(32), nullable=False, default="QUARANTINE_THEN_DISPOSE") # e.g. ARCHIVE_COLD, QUARANTINE, DISPOSE
    approval_required = Column(Boolean, nullable=False, default=True)
    policy_status = Column(String(32), nullable=False, default="ACTIVE")
    created_by = Column(String(64), nullable=False, default="SYSTEM")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class ReportArchiveLegalHold(Base):
    """Compliance legal hold preventing automated expiration or disposal of preserved reports."""
    __tablename__ = "report_archive_legal_holds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hold_id = Column(String(64), unique=True, nullable=False, index=True)
    archive_id = Column(String(64), ForeignKey("report_archive.archive_id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    status = Column(SQLEnum(LegalHoldStatus), nullable=False, default=LegalHoldStatus.ACTIVE, index=True)
    initiated_by = Column(String(64), nullable=False)
    approved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    released_at = Column(DateTime, nullable=True)
    release_reason = Column(Text, nullable=True)

    archive = relationship("ReportArchive", back_populates="legal_holds")
