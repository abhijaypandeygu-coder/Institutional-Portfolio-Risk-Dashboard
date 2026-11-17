from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.reporting_attribution_audit.report_archive.models.archive_models import (
    ReportArchiveType,
    ArchiveStatus,
    GenerationReason,
    ArtifactFormat,
    IntegrityStatus,
    LegalHoldStatus,
)


# Input Schemas
class ModelVersionInput(BaseModel):
    model_id: str = Field(..., description="Unique model identifier")
    model_name: str = Field(..., description="Canonical model name, e.g. GARCH_VOLATILITY, HISTORICAL_VAR")
    model_version: str = Field(..., description="Version of model or statistical specification")
    implementation_version: Optional[str] = Field(None, description="Software implementation version")
    configuration_version: Optional[str] = Field(None, description="Model configuration version")
    model_artifact_hash: Optional[str] = Field(None, description="SHA-256 of model weights/parameters")
    parameter_set_id: Optional[str] = Field(None, description="ID of calibrated parameter set")
    effective_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None


class DataVersionInput(BaseModel):
    source_type: str = Field(..., description="Type of source data e.g. MARKET_DATA, VALUATION, REFERENCE_DATA")
    source_id: str = Field(..., description="Authoritative identifier")
    dataset_id: Optional[str] = None
    snapshot_id: Optional[str] = Field(None, description="Authoritative snapshot ID from upstream")
    provider_id: Optional[str] = None
    source_version: Optional[str] = None
    data_as_of: datetime = Field(..., description="Data cutoff timestamp")
    ingested_at: Optional[datetime] = None
    data_cutoff_at: Optional[datetime] = None
    quality_status: str = Field("VERIFIED", description="Data quality grade or state")


class ConfigVersionInput(BaseModel):
    configuration_id: str
    configuration_version: str
    configuration_type: str
    configuration_snapshot: Dict[str, Any]


class ProvenanceInput(BaseModel):
    application_version: str = Field("1.0.0", description="Dashboard release version")
    code_commit: Optional[str] = Field(None, description="Git commit hash")
    environment_id: str = Field("production-local", description="Environment identifier")
    execution_started_at: datetime
    execution_completed_at: datetime
    trigger_source: str = Field("SCHEDULED_RUN", description="Trigger mechanism")
    requesting_actor_id: str = Field("SYSTEM", description="Actor requesting run")
    report_parameters: Dict[str, Any] = Field(default_factory=dict)
    data_quality_summary: Optional[Dict[str, Any]] = None
    known_limitations: Optional[Dict[str, Any]] = None


class ArchiveSubmissionRequest(BaseModel):
    report_id: str = Field(..., description="Upstream report ID")
    report_run_id: str = Field(..., description="Exact execution run ID")
    portfolio_id: str = Field(..., description="Target portfolio identifier")
    portfolio_name_snapshot: Optional[str] = None
    report_type: ReportArchiveType
    report_title_snapshot: str
    report_definition_id: Optional[str] = None
    report_definition_version: Optional[str] = None

    period_start: datetime
    period_end: datetime
    valuation_timestamp: Optional[datetime] = None
    generated_at: datetime

    generation_reason: GenerationReason = GenerationReason.INITIAL
    previous_version_id: Optional[str] = None
    supersedes_version_id: Optional[str] = None
    restates_version_id: Optional[str] = None
    restatement_reason: Optional[str] = None

    # Summary metrics for comparison
    summary_nav: Optional[Decimal] = None
    summary_var_value: Optional[Decimal] = None
    summary_es_value: Optional[Decimal] = None
    currency: str = "USD"

    # Artifact payload
    artifact_filename: str
    artifact_format: ArtifactFormat
    mime_type: str
    content_base64: str = Field(..., description="Base64 encoded report artifact bytes")

    # Provenance
    provenance: ProvenanceInput
    models: List[ModelVersionInput] = Field(default_factory=list)
    data_sources: List[DataVersionInput] = Field(default_factory=list)
    configurations: List[ConfigVersionInput] = Field(default_factory=list)


class ReportSupersedeRequest(BaseModel):
    new_archive_id: str = Field(..., description="Archive ID of superseding report")
    reason: str = Field(..., description="Reason for supersession")


class ReportRestateRequest(BaseModel):
    new_archive_id: str = Field(..., description="Archive ID of restated report")
    restatement_reason: str = Field(..., description="Detailed justification for restatement")


class ReportWithdrawRequest(BaseModel):
    reason: str = Field(..., description="Justification for withdrawal")
    actor_id: str = Field("SYSTEM", description="Authorizing actor")


class LegalHoldCreateRequest(BaseModel):
    archive_id: str
    reason: str
    initiated_by: str
    approved_by: Optional[str] = None


class LegalHoldReleaseRequest(BaseModel):
    release_reason: str
    released_by: str


# Output / Response Schemas
class ArtifactSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: str
    format: str
    mime_type: str
    file_size_bytes: int
    hash_algorithm: str
    artifact_hash: str
    integrity_status: IntegrityStatus
    last_verified_at: Optional[datetime] = None


class ModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    model_name: str
    model_version: str
    implementation_version: Optional[str] = None
    configuration_version: Optional[str] = None
    model_artifact_hash: Optional[str] = None
    parameter_set_id: Optional[str] = None
    effective_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None


class DataVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: str
    source_id: str
    dataset_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    provider_id: Optional[str] = None
    source_version: Optional[str] = None
    data_as_of: datetime
    ingested_at: Optional[datetime] = None
    quality_status: str


class ConfigVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    configuration_id: str
    configuration_version: str
    configuration_type: str
    configuration_snapshot: Dict[str, Any]
    configuration_hash: str


class ProvenanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    archive_id: str
    report_run_id: str
    application_version: str
    code_commit: Optional[str] = None
    environment_id: str
    execution_started_at: datetime
    execution_completed_at: datetime
    trigger_source: str
    requesting_actor_id: str
    report_parameters: Dict[str, Any]
    data_quality_summary: Optional[Dict[str, Any]] = None
    known_limitations: Optional[Dict[str, Any]] = None
    manifest_hash: str
    models: List[ModelVersionResponse] = Field(default_factory=list)
    data_sources: List[DataVersionResponse] = Field(default_factory=list)
    configurations: List[ConfigVersionResponse] = Field(default_factory=list)


class ReportArchiveSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    archive_id: str
    report_id: str
    report_run_id: str
    portfolio_id: str
    portfolio_name_snapshot: Optional[str] = None
    report_type: ReportArchiveType
    report_title_snapshot: str
    period_start: datetime
    period_end: datetime
    valuation_timestamp: Optional[datetime] = None
    generated_at: datetime
    archived_at: datetime
    version_number: int
    generation_reason: GenerationReason
    status: ArchiveStatus
    summary_nav: Optional[Decimal] = None
    summary_var_value: Optional[Decimal] = None
    summary_es_value: Optional[Decimal] = None
    currency: str
    artifact: Optional[ArtifactSummaryResponse] = None
    has_active_legal_hold: bool = False


class ReportArchiveDetailResponse(ReportArchiveSummaryResponse):
    report_definition_id: Optional[str] = None
    report_definition_version: Optional[str] = None
    previous_version_id: Optional[str] = None
    supersedes_version_id: Optional[str] = None
    restates_version_id: Optional[str] = None
    withdraws_version_id: Optional[str] = None
    restatement_reason: Optional[str] = None
    withdrawal_reason: Optional[str] = None
    provenance: Optional[ProvenanceResponse] = None


class ArchiveSearchResponse(BaseModel):
    items: List[ReportArchiveSummaryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class VersionComparisonResponse(BaseModel):
    base_archive: ReportArchiveDetailResponse
    compared_archive: ReportArchiveDetailResponse
    nav_diff: Optional[Decimal] = None
    var_diff: Optional[Decimal] = None
    es_diff: Optional[Decimal] = None
    model_changes: List[str] = Field(default_factory=list)
    data_source_changes: List[str] = Field(default_factory=list)
    configuration_changes: List[str] = Field(default_factory=list)


class RetentionEvaluationItem(BaseModel):
    archive_id: str
    report_type: ReportArchiveType
    archived_at: datetime
    age_days: int
    applicable_policy_id: Optional[str] = None
    retention_days: Optional[int] = None
    is_expired: bool
    has_legal_hold: bool
    eligible_for_disposal: bool
    recommended_action: str


class RetentionEvaluationResponse(BaseModel):
    evaluated_at: datetime
    total_evaluated: int
    eligible_for_disposal_count: int
    held_count: int
    retained_count: int
    items: List[RetentionEvaluationItem]
