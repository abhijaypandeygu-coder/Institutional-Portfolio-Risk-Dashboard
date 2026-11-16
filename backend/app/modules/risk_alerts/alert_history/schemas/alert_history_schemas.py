"""
Pydantic schemas for M12.08 — Alert History.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# Search and Item Schemas
class HistoricalAlertItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_alert_id: str
    alert_title: str
    alert_category: str
    alert_type: str
    source_module: str
    source_rule_id: str
    source_rule_version: int
    portfolio_id: Optional[str] = None
    portfolio_name: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    severity_at_trigger: str
    priority_at_trigger: str
    priority_score_at_trigger: Decimal
    current_or_final_status_snapshot: str
    triggered_at: datetime
    first_acknowledged_at: Optional[datetime] = None
    first_assigned_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    last_event_at: datetime
    metric_value_snapshot: Optional[Decimal] = None
    threshold_value_snapshot: Optional[Decimal] = None
    metric_unit_snapshot: Optional[str] = None
    indexed_at: datetime


class HistoricalAlertSearchResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    items: List[HistoricalAlertItemResponse]


class HistoricalAlertCountsResponse(BaseModel):
    total_alerts: int
    by_severity: Dict[str, int]
    by_category: Dict[str, int]
    by_status: Dict[str, int]
    recurring_count: int
    reopened_count: int


# Timeline Schemas
class HistoricalEventItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_alert_id: str
    source_event_id: str
    event_type: str
    actor_type: str
    actor_id: str
    source_module: str
    occurred_at: datetime
    recorded_at: datetime
    effective_at: Optional[datetime] = None
    event_sequence: int
    event_summary: str
    event_details: Dict[str, Any]
    source_reference: Optional[str] = None


class AlertTimelineResponse(BaseModel):
    source_alert_id: str
    total_events: int
    first_triggered_at: datetime
    current_or_final_status: str
    duration_metrics: Dict[str, Optional[float]]  # trigger_to_ack_s, trigger_to_closure_s, etc.
    events: List[HistoricalEventItemResponse]


# Recurrence Schemas
class RecurrenceGroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_alert_id: str
    occurrence_timestamp: datetime
    membership_reason: str


class AlertRecurrenceGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    grouping_key: str
    source_rule_id: str
    alert_category: str
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    first_occurrence_at: datetime
    last_occurrence_at: datetime
    occurrence_count: int
    average_interarrival_seconds: Optional[Decimal] = None
    recurrence_window_days: int
    members: Optional[List[RecurrenceGroupMemberResponse]] = None


# Rule Analytics Schemas
class RuleAnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_rule_id: str
    rule_name: Optional[str] = None
    rule_version: int
    observation_start: datetime
    observation_end: datetime
    observation_days: Decimal
    trigger_count: int
    recurrence_count: int
    affected_portfolio_count: int
    affected_instrument_count: int
    warning_count: int
    critical_count: int
    emergency_count: int
    trigger_frequency_per_day: Decimal
    average_interarrival_seconds: Optional[Decimal] = None
    noise_score: Decimal
    is_noisy: bool
    score_components_json: Dict[str, Any]
    score_configuration_version: str
    calculated_at: datetime


# Export Schemas
class AlertExportCreateRequest(BaseModel):
    requested_by: str = Field(default="admin")
    export_type: str = "HISTORICAL_ALERTS"  # HISTORICAL_ALERTS, TIMELINE, RECURRENCE, RULE_ANALYTICS
    export_format: str = "CSV"  # CSV, XLSX, PDF
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    severity: Optional[str] = None
    alert_category: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source_rule_id: Optional[str] = None


class AlertExportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    requested_by: str
    export_type: str
    export_format: str
    requested_filters_json: Dict[str, Any]
    export_status: str
    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    record_count: int
    file_reference: Optional[str] = None
    file_checksum_sha256: Optional[str] = None
    file_size_bytes: Optional[int] = None
    expires_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


# Integrity Schemas
class IntegrityIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_alert_id: str
    source_event_id: Optional[str] = None
    issue_type: str
    issue_description: str
    severity: str
    detected_at: datetime
    investigation_status: str
    resolved_at: Optional[datetime] = None


class IntegrityOverviewResponse(BaseModel):
    total_indexed_alerts: int
    total_indexed_events: int
    total_integrity_issues: int
    open_integrity_issues: int
    issues_by_type: Dict[str, int]

