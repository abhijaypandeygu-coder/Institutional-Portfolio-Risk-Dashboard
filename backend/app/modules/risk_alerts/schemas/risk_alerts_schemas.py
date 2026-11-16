"""
Pydantic schemas for M12 Risk Alerts & Notification Engine.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AlertThresholdInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comparison_operator: str = Field("GREATER_THAN_OR_EQUAL", description="GREATER_THAN_OR_EQUAL, LESS_THAN_OR_EQUAL")
    warning_threshold: Decimal
    critical_threshold: Decimal
    recovery_threshold: Optional[Decimal] = None
    metric_unit: str = "NAV_PERCENTAGE"
    currency: str = "USD"


class AlertRuleCreateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_code: str
    name: str
    description: Optional[str] = None
    metric_category: str = Field(..., description="VAR, VOLATILITY, EXPOSURE, DRAWDOWN, LIQUIDITY, FEED_HEALTH")
    metric_identifier: str = Field(..., description="e.g. var_95, realized_vol_20d, gross_exposure, drawdown")
    scope_type: str = "ALL"
    scope_id: Optional[str] = None
    priority: str = "MEDIUM"
    created_by: str
    threshold: AlertThresholdInput


class ThresholdMetricEvaluateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    metric_category: str
    metric_identifier: str
    current_value: Decimal
    previous_value: Optional[Decimal] = None
    metric_unit: str = "NAV_PERCENTAGE"
    currency: str = "USD"
    instrument_id: Optional[str] = None
    source_module: str = "M07.02"
    source_timestamp: Optional[datetime] = None
    data_quality_status: str = "VALID"  # VALID, STALE, MISSING


class EventAlertCreateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_type: str = Field(..., description="EVENT_ALERT, FEED_HEALTH, LIQUIDITY_ALERT, PORTFOLIO_CHANGE")
    alert_category: str = Field(..., description="BREACH, PRETRADE, SCENARIO, FACTOR, SPREAD, CASH")
    source_module: str
    source_event_id: Optional[str] = None
    portfolio_id: str
    instrument_id: Optional[str] = None
    title: str
    description: str
    priority: str = "HIGH"
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)


class AlertAcknowledgeInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    acknowledged_by_user_id: str
    action_note: Optional[str] = None


class AlertAssignInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assigned_user_id: str
    assigned_by_user_id: str
    action_note: Optional[str] = None


class AlertResolveInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resolved_by_user_id: str
    resolution_reason: str
    action_note: Optional[str] = None


class AlertReopenInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reopened_by_user_id: str
    reopen_reason: str


class NotificationPreferenceUpdateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled_channels: List[str] = ["IN_APP"]
    min_priority: str = "MEDIUM"
    subscribed_categories: List[str] = ["ALL"]
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


# Response Schemas

class AlertThresholdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    comparison_operator: str
    warning_threshold: Decimal
    critical_threshold: Decimal
    recovery_threshold: Optional[Decimal] = None
    metric_unit: str
    currency: str


class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_code: str
    name: str
    description: Optional[str] = None
    metric_category: str
    metric_identifier: str
    scope_type: str
    scope_id: Optional[str] = None
    priority: str
    status: str
    current_version: int
    created_by: str
    created_at: datetime


class AlertEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    metric_value: Decimal
    threshold_value: Decimal
    metric_unit: str
    currency: str
    evidence_payload: Dict[str, Any]
    source_timestamp: datetime
    created_at: datetime


class AlertEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_type: str
    alert_category: str
    source_module: str
    source_event_id: Optional[str] = None
    portfolio_id: str
    instrument_id: Optional[str] = None
    rule_id: Optional[str] = None
    title: str
    description: str
    priority: str
    status: str
    deduplication_key: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_user_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    evidence: List[AlertEvidenceResponse] = Field(default_factory=list)


class ThresholdEvaluationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_triggered: bool
    state_changed: bool
    current_state: str  # NORMAL, APPROACHING, WARNING, CRITICAL, RECOVERED, STALE
    current_value: Decimal
    warning_threshold: Decimal
    critical_threshold: Decimal
    proximity_pct: Decimal
    alert: Optional[AlertEventResponse] = None


class AlertDashboardSummary(BaseModel):
    total_active_alerts: int
    open_alerts: int
    acknowledged_alerts: int
    resolved_alerts: int
    priority_breakdown: Dict[str, int]
    category_breakdown: Dict[str, int]
    unacknowledged_critical_count: int
