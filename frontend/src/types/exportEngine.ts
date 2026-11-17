export type ExportStatus =
  | 'DRAFT'
  | 'QUEUED'
  | 'RUNNING'
  | 'VALIDATING'
  | 'COMPLETED'
  | 'COMPLETED_WITH_WARNINGS'
  | 'FAILED'
  | 'CANCEL_REQUESTED'
  | 'CANCELLED'
  | 'EXPIRED';

export type ExportFormat = 'CSV' | 'XLSX' | 'PDF';

export type ExportValidationStatus =
  | 'VALID'
  | 'VALID_WITH_WARNINGS'
  | 'PARTIALLY_VALID'
  | 'INVALID'
  | 'FAILED';

export interface DatasetFieldDefinition {
  field_name: string;
  display_name: string;
  data_type: string;
  description?: string;
  unit?: string;
  currency_semantics?: string;
  precision?: number;
  sensitivity_level: 'PUBLIC' | 'INTERNAL' | 'CONFIDENTIAL' | 'RESTRICTED';
  is_required: boolean;
  is_selectable: boolean;
  is_exportable: boolean;
  field_order: number;
}

export interface DatasetRegistryItem {
  dataset_code: string;
  dataset_name: string;
  source_module: string;
  source_feature: string;
  description?: string;
  schema_version: string;
  supported_formats: ExportFormat[];
  access_policy_reference: string;
  maximum_rows: number;
  fields: DatasetFieldDefinition[];
}

export interface ExportArtifactItem {
  artifact_id: number;
  artifact_type: ExportFormat;
  file_name: string;
  mime_type: string;
  file_size_bytes: number;
  file_hash: string;
  storage_reference: string;
  artifact_status: string;
  created_at: string;
  expires_at?: string;
}

export interface ExportValidationSummary {
  validation_status: ExportValidationStatus;
  validation_version: string;
  checks_performed: string[];
  failed_checks?: string[];
  warnings?: string[];
  source_row_count: number;
  exported_row_count: number;
  excluded_row_count: number;
  validated_at: string;
}

export interface ExportJobSummary {
  id: number;
  export_code: string;
  requested_by: string;
  source_module: string;
  source_feature?: string;
  source_report_id?: string;
  dataset_id: string;
  portfolio_id?: string;
  export_status: ExportStatus;
  progress_percentage: number;
  current_stage: string;
  total_records: number;
  processed_records: number;
  requested_at: string;
  started_at?: string;
  completed_at?: string;
  failure_code?: string;
  failure_message?: string;
  requested_formats: ExportFormat[];
  artifacts: ExportArtifactItem[];
  validation_summary?: ExportValidationSummary;
}

export interface ExportCreateRequestPayload {
  source: {
    module: string;
    feature?: string;
    report_id?: string;
    dataset_id: string;
  };
  formats: ExportFormat[];
  scope: {
    portfolio_id?: string;
    as_of_timestamp?: string;
    scenario_run_id?: string;
    start_date?: string;
    end_date?: string;
  };
  fields?: string[];
  filters?: Record<string, any>;
  sorting?: Array<Record<string, string>>;
  options: {
    reporting_currency: string;
    timezone: string;
    template_id?: string;
    include_methodology: boolean;
    include_metadata: boolean;
    include_data_quality: boolean;
    output_filename?: string;
    precision_overrides?: Record<string, number>;
  };
  idempotency_key?: string;
  created_by?: string;
}

export interface ExportAuditEvent {
  id: number;
  actor_id: string;
  event_type: string;
  event_timestamp: string;
  event_details?: Record<string, any>;
}
