export type ReportArchiveType =
  | 'DAILY_RISK'
  | 'PORTFOLIO_PERFORMANCE'
  | 'RISK_ATTRIBUTION'
  | 'STRESS_TESTING'
  | 'LIQUIDITY'
  | 'OTHER';

export type ArchiveStatus =
  | 'ARCHIVING'
  | 'AVAILABLE'
  | 'ARCHIVE_FAILED'
  | 'SUPERSEDED'
  | 'RESTATED'
  | 'WITHDRAWN'
  | 'EXPIRED'
  | 'QUARANTINED';

export type GenerationReason =
  | 'INITIAL'
  | 'SCHEDULED_REGENERATION'
  | 'DATA_CORRECTION'
  | 'MODEL_UPDATE'
  | 'CONFIGURATION_UPDATE'
  | 'USER_REQUESTED_REGENERATION'
  | 'RESTATEMENT'
  | 'OTHER';

export type ArtifactFormat = 'PDF' | 'CSV' | 'XLSX' | 'HTML' | 'JSON' | 'OTHER';

export type IntegrityStatus = 'UNVERIFIED' | 'VERIFIED' | 'CORRUPTED' | 'MISSING';

export type LegalHoldStatus = 'ACTIVE' | 'RELEASED';

export interface ArtifactSummary {
  artifact_id: string;
  format: string;
  mime_type: string;
  file_size_bytes: number;
  hash_algorithm: string;
  artifact_hash: string;
  integrity_status: IntegrityStatus;
  last_verified_at?: string;
}

export interface ModelVersion {
  model_id: string;
  model_name: string;
  model_version: string;
  implementation_version?: string;
  configuration_version?: string;
  model_artifact_hash?: string;
  parameter_set_id?: string;
  effective_at?: string;
  executed_at?: string;
}

export interface DataVersion {
  source_type: string;
  source_id: string;
  dataset_id?: string;
  snapshot_id?: string;
  provider_id?: string;
  source_version?: string;
  data_as_of: string;
  ingested_at?: string;
  quality_status: string;
}

export interface ConfigVersion {
  configuration_id: string;
  configuration_version: string;
  configuration_type: string;
  configuration_snapshot: Record<string, any>;
  configuration_hash: string;
}

export interface ProvenanceManifest {
  archive_id: string;
  report_run_id: string;
  application_version: string;
  code_commit?: string;
  environment_id: string;
  execution_started_at: string;
  execution_completed_at: string;
  trigger_source: string;
  requesting_actor_id: string;
  report_parameters: Record<string, any>;
  data_quality_summary?: Record<string, any>;
  known_limitations?: Record<string, any>;
  manifest_hash: string;
  models: ModelVersion[];
  data_sources: DataVersion[];
  configurations: ConfigVersion[];
}

export interface ReportArchiveSummary {
  archive_id: string;
  report_id: string;
  report_run_id: string;
  portfolio_id: string;
  portfolio_name_snapshot?: string;
  report_type: ReportArchiveType;
  report_title_snapshot: string;
  period_start: string;
  period_end: string;
  valuation_timestamp?: string;
  generated_at: string;
  archived_at: string;
  version_number: number;
  generation_reason: GenerationReason;
  status: ArchiveStatus;
  summary_nav?: number;
  summary_var_value?: number;
  summary_es_value?: number;
  currency: string;
  artifact?: ArtifactSummary;
  has_active_legal_hold: boolean;
}

export interface ReportArchiveDetail extends ReportArchiveSummary {
  report_definition_id?: string;
  report_definition_version?: string;
  previous_version_id?: string;
  supersedes_version_id?: string;
  restates_version_id?: string;
  withdraws_version_id?: string;
  restatement_reason?: string;
  withdrawal_reason?: string;
  provenance?: ProvenanceManifest;
}

export interface ArchiveSearchResponse {
  items: ReportArchiveSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface VersionComparison {
  base_archive: ReportArchiveDetail;
  compared_archive: ReportArchiveDetail;
  nav_diff?: number;
  var_diff?: number;
  es_diff?: number;
  model_changes: string[];
  data_source_changes: string[];
  configuration_changes: string[];
}

export interface RetentionEvaluationItem {
  archive_id: string;
  report_type: ReportArchiveType;
  archived_at: string;
  age_days: number;
  applicable_policy_id?: string;
  retention_days?: number;
  is_expired: boolean;
  has_legal_hold: boolean;
  eligible_for_disposal: boolean;
  recommended_action: string;
}

export interface RetentionEvaluationResponse {
  evaluated_at: string;
  total_evaluated: number;
  eligible_for_disposal_count: number;
  held_count: number;
  retained_count: number;
  items: RetentionEvaluationItem[];
}
