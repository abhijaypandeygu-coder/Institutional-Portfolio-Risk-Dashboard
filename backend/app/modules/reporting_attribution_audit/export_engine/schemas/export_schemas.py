from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.modules.reporting_attribution_audit.export_engine.models.export_models import (
    ExportStatus,
    ExportFormat,
    ExportValidationStatus,
    SensitivityLevel,
)


class ExportSourceInput(BaseModel):
    module: str = Field(..., description="Source module code, e.g. M14, M05, M07, M13")
    feature: Optional[str] = Field(None, description="Source feature code, e.g. M14.01, M14.05")
    report_id: Optional[str] = Field(None, description="Authoritative upstream report ID if applicable")
    dataset_id: str = Field(..., description="Registered dataset code, e.g. daily_risk_summary, liquidity_positions")


class ExportScopeInput(BaseModel):
    portfolio_id: Optional[str] = Field(None, description="Target portfolio identifier")
    as_of_timestamp: Optional[datetime] = Field(None, description="As-of evaluation timestamp")
    scenario_run_id: Optional[str] = Field(None, description="Scenario execution run identifier")
    start_date: Optional[str] = Field(None, description="Start date ISO string")
    end_date: Optional[str] = Field(None, description="End date ISO string")


class ExportOptionsInput(BaseModel):
    reporting_currency: str = Field("INR", description="Reporting currency symbol")
    timezone: str = Field("UTC", description="Display timezone")
    template_id: Optional[str] = Field(None, description="Export template identifier")
    include_methodology: bool = Field(True, description="Whether to include methodology section/sheet")
    include_metadata: bool = Field(True, description="Whether to include provenance metadata")
    include_data_quality: bool = Field(True, description="Whether to include data quality disclosures")
    output_filename: Optional[str] = Field(None, description="Custom filename prefix")
    precision_overrides: Optional[Dict[str, int]] = Field(None, description="Column precision overrides")


class ExportCreateRequest(BaseModel):
    source: ExportSourceInput
    formats: List[ExportFormat] = Field(..., min_length=1, description="Requested formats (CSV, XLSX, PDF)")
    scope: ExportScopeInput = Field(default_factory=ExportScopeInput)
    fields: Optional[List[str]] = Field(None, description="Specific column selection in ordering preference")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Active filters")
    sorting: Optional[List[Dict[str, str]]] = Field(None, description="List of sorting rules {field: dir}")
    options: ExportOptionsInput = Field(default_factory=ExportOptionsInput)
    idempotency_key: Optional[str] = Field(None, description="Optional key to prevent duplicate submissions")
    created_by: str = Field("SYSTEM", description="Actor initiating export")


class ExportArtifactResponse(BaseModel):
    artifact_id: int
    artifact_type: ExportFormat
    file_name: str
    mime_type: str
    file_size_bytes: int
    file_hash: str
    storage_reference: str
    artifact_status: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class ExportValidationSummaryResponse(BaseModel):
    validation_status: ExportValidationStatus
    validation_version: str
    checks_performed: List[str]
    failed_checks: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    source_row_count: int
    exported_row_count: int
    excluded_row_count: int
    validated_at: datetime


class ExportJobSummaryResponse(BaseModel):
    id: int
    export_code: str
    requested_by: str
    source_module: str
    source_feature: Optional[str] = None
    source_report_id: Optional[str] = None
    dataset_id: str
    portfolio_id: Optional[str] = None
    export_status: ExportStatus
    progress_percentage: float
    current_stage: str
    total_records: int
    processed_records: int
    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    requested_formats: List[ExportFormat]
    artifacts: List[ExportArtifactResponse] = []
    validation_summary: Optional[ExportValidationSummaryResponse] = None


class DatasetFieldDefinitionSchema(BaseModel):
    field_name: str
    display_name: str
    data_type: str
    description: Optional[str] = None
    unit: Optional[str] = None
    currency_semantics: Optional[str] = None
    precision: Optional[int] = None
    sensitivity_level: SensitivityLevel
    is_required: bool
    is_selectable: bool
    is_exportable: bool
    field_order: int


class DatasetRegistrySchema(BaseModel):
    dataset_code: str
    dataset_name: str
    source_module: str
    source_feature: str
    description: Optional[str] = None
    schema_version: str
    supported_formats: List[ExportFormat]
    access_policy_reference: str
    maximum_rows: int
    fields: List[DatasetFieldDefinitionSchema] = []


class ExportTemplateSchema(BaseModel):
    template_code: str
    template_name: str
    export_format: ExportFormat
    dataset_code: str
    schema_version: str
    configuration: Dict[str, Any]
    template_version: str
    owner_id: str
    access_scope: str
    is_active: bool
    created_at: datetime


class ExportTemplateCreateRequest(BaseModel):
    template_code: str
    template_name: str
    export_format: ExportFormat
    dataset_code: str
    configuration: Dict[str, Any]
    owner_id: str = "SYSTEM"
    access_scope: str = "GLOBAL"


class ExportAuditEventResponse(BaseModel):
    id: int
    actor_id: str
    event_type: str
    event_timestamp: datetime
    event_details: Optional[Dict[str, Any]] = None
