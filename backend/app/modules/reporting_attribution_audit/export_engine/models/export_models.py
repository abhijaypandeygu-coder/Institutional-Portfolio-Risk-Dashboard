import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class ExportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ExportFormat(str, enum.Enum):
    CSV = "CSV"
    XLSX = "XLSX"
    PDF = "PDF"


class ExportValidationStatus(str, enum.Enum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    PARTIALLY_VALID = "PARTIALLY_VALID"
    INVALID = "INVALID"
    FAILED = "FAILED"


class SensitivityLevel(str, enum.Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class ExportJob(Base):
    __tablename__ = "m14_export_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_code = Column(String(100), unique=True, nullable=False, index=True)
    requested_by = Column(String(100), nullable=False, default="SYSTEM", index=True)
    source_module = Column(String(50), nullable=False, index=True)
    source_feature = Column(String(50), nullable=True)
    source_report_id = Column(String(100), nullable=True, index=True)
    dataset_id = Column(String(100), nullable=False, index=True)
    portfolio_id = Column(String(100), nullable=True, index=True)
    export_status = Column(SQLEnum(ExportStatus), nullable=False, default=ExportStatus.QUEUED, index=True)
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    
    # Progress & metrics
    progress_percentage = Column(Float, nullable=False, default=0.0)
    current_stage = Column(String(100), nullable=False, default="INITIATED")
    total_records = Column(Integer, nullable=False, default=0)
    processed_records = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    requested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error classification
    failure_code = Column(String(100), nullable=True)
    failure_message = Column(Text, nullable=True)
    correlation_id = Column(String(100), nullable=True)

    # Relationships
    configuration = relationship("ExportConfiguration", back_populates="job", uselist=False, cascade="all, delete-orphan")
    artifacts = relationship("ExportArtifact", back_populates="job", cascade="all, delete-orphan")
    validation_results = relationship("ExportValidationResult", back_populates="job", cascade="all, delete-orphan")
    audit_events = relationship("ExportAuditEvent", back_populates="job", cascade="all, delete-orphan")
    executions = relationship("ExportJobExecution", back_populates="job", cascade="all, delete-orphan")


class ExportConfiguration(Base):
    __tablename__ = "m14_export_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_job_id = Column(Integer, ForeignKey("m14_export_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    export_formats = Column(JSON, nullable=False)  # List of string formats e.g. ["CSV", "XLSX", "PDF"]
    selected_fields = Column(JSON, nullable=True)  # List of string field names
    filters = Column(JSON, nullable=True)          # Dict of filter key-values
    sorting = Column(JSON, nullable=True)          # List of {field, direction}
    reporting_currency = Column(String(10), nullable=False, default="INR")
    timezone = Column(String(50), nullable=False, default="UTC")
    precision_settings = Column(JSON, nullable=True) # Dict of field-precision overrides
    template_id = Column(String(100), nullable=True)
    template_version = Column(String(50), nullable=True)
    include_methodology = Column(Boolean, nullable=False, default=True)
    include_metadata = Column(Boolean, nullable=False, default=True)
    include_data_quality = Column(Boolean, nullable=False, default=True)
    configuration_snapshot = Column(JSON, nullable=True)

    job = relationship("ExportJob", back_populates="configuration")


class ExportDatasetRegistry(Base):
    __tablename__ = "m14_export_dataset_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_code = Column(String(100), unique=True, nullable=False, index=True)
    dataset_name = Column(String(200), nullable=False)
    source_module = Column(String(50), nullable=False, index=True)
    source_feature = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    schema_version = Column(String(50), nullable=False, default="v1.0")
    supported_formats = Column(JSON, nullable=False)  # List[str] e.g. ["CSV", "XLSX", "PDF"]
    access_policy_reference = Column(String(100), nullable=False, default="STANDARD_PORTFOLIO_READ")
    maximum_rows = Column(Integer, nullable=False, default=100000)
    is_active = Column(Boolean, nullable=False, default=True)
    registered_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    fields = relationship("ExportDatasetField", back_populates="dataset", cascade="all, delete-orphan")


class ExportDatasetField(Base):
    __tablename__ = "m14_export_dataset_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("m14_export_dataset_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    data_type = Column(String(50), nullable=False) # STRING, NUMERIC, INTEGER, BOOLEAN, DATE, DATETIME
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    currency_semantics = Column(String(50), nullable=True)
    precision = Column(Integer, nullable=True)
    sensitivity_level = Column(SQLEnum(SensitivityLevel), nullable=False, default=SensitivityLevel.INTERNAL)
    is_required = Column(Boolean, nullable=False, default=False)
    is_selectable = Column(Boolean, nullable=False, default=True)
    is_exportable = Column(Boolean, nullable=False, default=True)
    field_order = Column(Integer, nullable=False, default=0)

    dataset = relationship("ExportDatasetRegistry", back_populates="fields")


class ExportTemplate(Base):
    __tablename__ = "m14_export_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_code = Column(String(100), unique=True, nullable=False, index=True)
    template_name = Column(String(200), nullable=False)
    export_format = Column(SQLEnum(ExportFormat), nullable=False)
    dataset_code = Column(String(100), nullable=False, index=True)
    schema_version = Column(String(50), nullable=False, default="v1.0")
    configuration = Column(JSON, nullable=False)
    template_version = Column(String(50), nullable=False, default="v1.0")
    owner_id = Column(String(100), nullable=False, default="SYSTEM")
    access_scope = Column(String(50), nullable=False, default="GLOBAL") # GLOBAL, TEAM, PERSONAL
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ExportArtifact(Base):
    __tablename__ = "m14_export_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_job_id = Column(Integer, ForeignKey("m14_export_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(SQLEnum(ExportFormat), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    storage_reference = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False) # SHA-256
    artifact_status = Column(String(50), nullable=False, default="AVAILABLE")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("ExportJob", back_populates="artifacts")


class ExportValidationResult(Base):
    __tablename__ = "m14_export_validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_job_id = Column(Integer, ForeignKey("m14_export_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_id = Column(Integer, ForeignKey("m14_export_artifacts.id", ondelete="SET NULL"), nullable=True)
    validation_status = Column(SQLEnum(ExportValidationStatus), nullable=False, default=ExportValidationStatus.VALID)
    validation_version = Column(String(50), nullable=False, default="v1.0")
    checks_performed = Column(JSON, nullable=False)
    failed_checks = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    source_row_count = Column(Integer, nullable=False, default=0)
    exported_row_count = Column(Integer, nullable=False, default=0)
    excluded_row_count = Column(Integer, nullable=False, default=0)
    validated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    job = relationship("ExportJob", back_populates="validation_results")


class ExportAuditEvent(Base):
    __tablename__ = "m14_export_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_job_id = Column(Integer, ForeignKey("m14_export_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(100), nullable=False, default="SYSTEM")
    event_type = Column(String(100), nullable=False) # CONFIGURED, QUEUED, STARTED, COMPLETED, VALIDATED, DOWNLOADED, CANCELLED, FAILED
    event_timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    event_details = Column(JSON, nullable=True)
    correlation_id = Column(String(100), nullable=True)

    job = relationship("ExportJob", back_populates="audit_events")


class ExportJobExecution(Base):
    __tablename__ = "m14_export_job_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_job_id = Column(Integer, ForeignKey("m14_export_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    execution_status = Column(String(50), nullable=False, default="RUNNING")
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_details = Column(Text, nullable=True)

    job = relationship("ExportJob", back_populates="executions")
