export type ActorType =
  | 'USER'
  | 'SYSTEM'
  | 'SERVICE'
  | 'SCHEDULED_JOB'
  | 'EXTERNAL_INTEGRATION';

export type EventCategory =
  | 'USER_ACTION'
  | 'SYSTEM_EVENT'
  | 'CONFIGURATION_CHANGE'
  | 'APPROVAL'
  | 'AUTHORIZATION_DECISION'
  | 'OPERATIONAL_COMMAND'
  | 'CONTROL_DECISION'
  | 'DATA_ACCESS'
  | 'REPORTING_EVENT'
  | 'SECURITY_EVENT'
  | 'INTEGRITY_EVENT'
  | 'RETENTION_EVENT';

export type EventSeverity = 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export type EventOutcome =
  | 'SUCCESS'
  | 'FAILURE'
  | 'REJECTED'
  | 'DENIED'
  | 'PARTIAL'
  | 'CANCELLED'
  | 'UNKNOWN';

export type IntegrityVerificationStatus =
  | 'VERIFIED'
  | 'VERIFICATION_PENDING'
  | 'VERIFICATION_FAILED'
  | 'INTEGRITY_UNKNOWN';

export interface AuditConfigurationChange {
  configuration_id: string;
  configuration_type: string;
  owning_module: string;
  previous_version: number;
  new_version: number;
  effective_at: string;
  recorded_at: string;
  changed_fields: string[];
  old_values_redacted?: Record<string, any>;
  new_values_redacted?: Record<string, any>;
  reason?: string;
  approval_reference?: string;
}

export interface AuditApprovalDetails {
  approval_id: string;
  target_type: string;
  target_id: string;
  requesting_actor_id: string;
  approving_actor_id?: string;
  decision: string;
  reason?: string;
  policy_version: string;
  approval_timestamp: string;
}

export interface AuditEventItem {
  id: number;
  event_id: string;
  event_type: string;
  event_category: EventCategory;
  severity: EventSeverity;
  actor_type: ActorType;
  actor_id: string;
  actor_role?: string;
  source_module: string;
  source_feature?: string;
  target_type?: string;
  target_id?: string;
  action: string;
  outcome: EventOutcome;
  reason?: string;
  occurred_at: string;
  recorded_at: string;
  correlation_id?: string;
  causation_id?: string;
  parent_event_id?: string;
  payload?: Record<string, any>;
  schema_version: string;
  chain_id: string;
  chain_sequence: number;
  integrity_hash: string;
  previous_hash: string;
  verification_status: IntegrityVerificationStatus;
  configuration_change?: AuditConfigurationChange;
  approval_details?: AuditApprovalDetails;
}

export interface AuditSearchResponse {
  items: AuditEventItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditIntegrityRunResult {
  run_id: number;
  chain_id: string;
  verification_status: IntegrityVerificationStatus;
  events_checked: number;
  mismatch_count: number;
  missing_sequence_count: number;
  started_at: string;
  completed_at?: string;
  result_summary?: string;
}

export interface AuditCheckpointItem {
  id: number;
  chain_id: string;
  highest_sequence: number;
  checkpoint_hash: string;
  hash_algorithm: string;
  event_count: number;
  created_at: string;
  verification_status: IntegrityVerificationStatus;
}

export interface AuditRetentionPolicyItem {
  id: number;
  policy_code: string;
  policy_name: string;
  event_category: EventCategory;
  retention_days: number;
  archive_before_expiry: boolean;
  policy_version: string;
  status: string;
}
