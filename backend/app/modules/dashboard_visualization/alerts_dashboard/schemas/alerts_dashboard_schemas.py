"""
Pydantic schemas for M13.08 — Alerts Dashboard.

Enforces strict request and response validation for:
- M13.08.01: Active breaches summary, active breach listing, and breach detail.
- M13.08.02: Recent alerts summary, alert feed items, and alert detail.
- M13.08.03: Operational alert actions (Acknowledge, Assign, Close, Reopen, Audit History).
- M13.08.04: Filter query parameters, preferences, and saved views.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Freshness & Scope Metadata
# ============================================================================

class DashboardScopeMeta(BaseModel):
    portfolio_ids: List[str] = Field(default_factory=list)
    time_range_preset: Optional[str] = None
    as_of: datetime
    freshness_status: str = Field(default="FRESH")  # FRESH, STALE, DELAYED, UNAVAILABLE


# ============================================================================
# Feature M13.08.01 — Active Breaches
# ============================================================================

class BreachSummaryCounts(BaseModel):
    total_active: int = 0
    emergency: int = 0
    critical: int = 0
    warning: int = 0
    unacknowledged: int = 0
    acknowledged: int = 0
    awaiting_remediation: int = 0
    overdue_escalation: int = 0


class ActiveBreachSummaryResponse(BaseModel):
    scope: DashboardScopeMeta
    counts: BreachSummaryCounts
    upstream_m11_status: str = Field(default="OPERATIONAL")  # OPERATIONAL, DEGRADED, UNAVAILABLE


class ActiveBreachItem(BaseModel):
    breach_id: str
    workflow_id: Optional[str] = None
    workflow_reference: Optional[str] = None
    portfolio_id: str
    portfolio_name: Optional[str] = None
    target_entity_type: str = "PORTFOLIO"
    target_entity_id: str
    risk_limit_id: str
    breach_type: str  # VAR, VOLATILITY, DRAWDOWN, EXPOSURE, POSITION, SECTOR, LIQUIDITY
    severity: str     # WARNING, CRITICAL, EMERGENCY
    risk_metric: str
    current_value: Decimal
    limit_value: Decimal
    warning_value: Optional[Decimal] = None
    utilization: Optional[Decimal] = None
    metric_unit: str = "PERCENT"
    detected_at: datetime
    duration_minutes: int
    duration_display: str
    status: str       # OPEN, ACKNOWLEDGED, MITIGATED, CLOSED, REOPENED
    acknowledgement_status: str
    assigned_to: Optional[str] = None
    assigned_team: Optional[str] = None
    current_escalation_level: str = "LEVEL_1"
    sla_status: str = "ON_TRACK"
    is_overdue: bool = False
    related_alert_count: int = 0
    last_updated: datetime


class ActiveBreachListResponse(BaseModel):
    scope: DashboardScopeMeta
    total: int
    page: int
    page_size: int
    items: List[ActiveBreachItem]
    upstream_status: str = "OPERATIONAL"


class BreachDetailResponse(BaseModel):
    breach: ActiveBreachItem
    evaluation_reference: Optional[str] = None
    comparison_operator: str = "GREATER_THAN"
    persistence_status: str = "TRANSIENT"
    historical_observations_count: int = 0
    acknowledgement_history: List[Dict[str, Any]] = Field(default_factory=list)
    assignment_history: List[Dict[str, Any]] = Field(default_factory=list)
    escalation_history: List[Dict[str, Any]] = Field(default_factory=list)
    lifecycle_history: List[Dict[str, Any]] = Field(default_factory=list)
    related_alerts: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Feature M13.08.02 — Recent Alerts
# ============================================================================

class AlertSummaryCounts(BaseModel):
    total_alerts: int = 0
    new_alerts: int = 0
    unacknowledged: int = 0
    high_priority: int = 0
    emergency_priority: int = 0
    under_investigation: int = 0
    resolved: int = 0
    reopened: int = 0


class RecentAlertSummaryResponse(BaseModel):
    scope: DashboardScopeMeta
    counts: AlertSummaryCounts
    upstream_m12_status: str = Field(default="OPERATIONAL")


class AlertFeedItem(BaseModel):
    alert_id: str
    title: str
    category: str      # VAR, VOLATILITY, EXPOSURE, DRAWDOWN, LIQUIDITY, FEED_HEALTH, MARKET, PORTFOLIO
    alert_type: str    # THRESHOLD_ALERT, EVENT_ALERT, LIQUIDITY_ALERT, PORTFOLIO_CHANGE
    severity: str      # WARNING, CRITICAL, EMERGENCY
    priority: str      # INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL, EMERGENCY
    priority_score: Optional[Decimal] = None
    portfolio_id: str
    portfolio_name: Optional[str] = None
    instrument_id: Optional[str] = None
    symbol: Optional[str] = None
    short_description: str
    triggered_at: datetime
    status: str        # OPEN, ACKNOWLEDGED, ASSIGNED, INVESTIGATING, RESOLVED, CLOSED, REOPENED
    assigned_to: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    related_breach_id: Optional[str] = None
    source_module: str = "M12.01"
    occurrence_count: int = 1
    last_updated: datetime


class RecentAlertListResponse(BaseModel):
    scope: DashboardScopeMeta
    total: int
    page: int
    page_size: int
    items: List[AlertFeedItem]
    upstream_status: str = "OPERATIONAL"


class AlertDetailResponse(BaseModel):
    alert: AlertFeedItem
    rule_id: Optional[str] = None
    rule_code: Optional[str] = None
    source_metric: Optional[str] = None
    observed_value: Optional[Decimal] = None
    threshold_value: Optional[Decimal] = None
    metric_unit: Optional[str] = None
    currency: Optional[str] = None
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)
    workflow_state: Optional[str] = None
    workflow_cycle: int = 1
    resolution_category: Optional[str] = None
    resolution_notes: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[str] = None
    permitted_actions: List[str] = Field(default_factory=list)
    version: int = 1


class AlertTimelineEvent(BaseModel):
    event_id: str
    event_type: str     # TRIGGERED, ACKNOWLEDGED, ASSIGNED, INVESTIGATION_NOTE, RESOLVED, CLOSED, REOPENED, NOTIFICATION_SENT
    occurred_at: datetime
    actor_id: str
    actor_type: str = "USER"
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


class AlertHistoryResponse(BaseModel):
    alert_id: str
    title: str
    events: List[AlertTimelineEvent]
    total_events: int


# ============================================================================
# Feature M13.08.03 — Alert & Breach Management Actions
# ============================================================================

class AlertAcknowledgeActionRequest(BaseModel):
    comment: Optional[str] = None
    idempotency_key: Optional[str] = None


class AlertAssignActionRequest(BaseModel):
    assigned_to_user_id: str
    assigned_team_id: Optional[str] = None
    comment: Optional[str] = None
    idempotency_key: Optional[str] = None


class AlertInvestigationNoteRequest(BaseModel):
    note: str
    evidence_ref: Optional[str] = None


class AlertCloseActionRequest(BaseModel):
    resolution_category: str = Field(default="INVESTIGATED")  # INVESTIGATED, FALSE_POSITIVE, MITIGATED, RECOVERED, RETIRED
    resolution_comment: str
    idempotency_key: Optional[str] = None


class AlertReopenActionRequest(BaseModel):
    reopening_reason: str
    idempotency_key: Optional[str] = None


class BreachAcknowledgeActionRequest(BaseModel):
    review_notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class BreachAssignActionRequest(BaseModel):
    assigned_user_id: str
    assigned_team_id: Optional[str] = None
    reassignment_reason: Optional[str] = None
    idempotency_key: Optional[str] = None


class ActionExecutionResult(BaseModel):
    success: bool
    action_type: str
    target_id: str
    previous_state: str
    new_state: str
    action_timestamp: datetime
    message: str
    has_unresolved_linked_breach_warning: bool = False
    warning_message: Optional[str] = None


# ============================================================================
# Feature M13.08.04 — Preferences & Saved Views
# ============================================================================

class AlertsPreferenceCreateRequest(BaseModel):
    dashboard_name: str = "Default Alerts Dashboard"
    default_portfolio_id: Optional[str] = None
    default_severity_selection: List[str] = Field(default_factory=lambda: ["WARNING", "CRITICAL", "EMERGENCY"])
    default_alert_category_selection: List[str] = Field(default_factory=lambda: ["ALL"])
    default_time_range_preset: str = "LAST_24_HOURS"
    breaches_page_size: int = 25
    alerts_page_size: int = 50
    auto_refresh_interval_seconds: int = 30
    sound_alerts_enabled: bool = False
    display_configuration: Optional[Dict[str, Any]] = None


class AlertsPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    dashboard_name: str
    default_portfolio_id: Optional[str] = None
    default_severity_selection: List[str]
    default_alert_category_selection: List[str]
    default_time_range_preset: str
    breaches_page_size: int
    alerts_page_size: int
    auto_refresh_interval_seconds: int
    sound_alerts_enabled: bool
    display_configuration: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class AlertsSavedViewCreateRequest(BaseModel):
    view_name: str
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    selected_severities: List[str] = Field(default_factory=lambda: ["CRITICAL", "EMERGENCY"])
    selected_categories: List[str] = Field(default_factory=lambda: ["ALL"])
    selected_statuses: List[str] = Field(default_factory=lambda: ["OPEN", "ACKNOWLEDGED", "INVESTIGATING"])
    time_range_preset: str = "LAST_24_HOURS"
    is_public: bool = False


class AlertsSavedViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    view_name: str
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    selected_severities: List[str]
    selected_categories: List[str]
    selected_statuses: List[str]
    time_range_preset: str
    is_public: bool
    created_at: datetime
    updated_at: datetime
