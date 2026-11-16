"""
Pydantic v2 schemas for M12.05 — Alert Prioritization.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class AlertPriorityPolicyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_name: str = Field(..., max_length=128)
    policy_type: str = Field("DEFAULT", max_length=64)
    alert_category: Optional[str] = None
    event_type: Optional[str] = None
    source_module: Optional[str] = None

    severity_rules: Dict[str, Any] = Field(default_factory=dict)
    urgency_rules: Dict[str, Any] = Field(default_factory=dict)
    impact_weights: Dict[str, Any] = Field(default_factory=lambda: {"F": 0.45, "R": 0.40, "B": 0.15})
    priority_weights: Dict[str, Any] = Field(default_factory=lambda: {"S": 0.35, "U": 0.30, "I": 0.25, "P": 0.10})
    priority_band_config: Dict[str, Any] = Field(default_factory=dict)
    priority_floor_config: Dict[str, Any] = Field(default_factory=lambda: {"EMERGENCY": 90.0, "CRITICAL": 50.0})

    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    policy_version: int = 1
    enabled: bool = True
    created_by: str = "SYSTEM"


class AlertPriorityPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_name: str
    policy_type: str
    alert_category: Optional[str]
    event_type: Optional[str]
    source_module: Optional[str]
    severity_rules: Dict[str, Any]
    urgency_rules: Dict[str, Any]
    impact_weights: Dict[str, Any]
    priority_weights: Dict[str, Any]
    priority_band_config: Dict[str, Any]
    priority_floor_config: Dict[str, Any]
    effective_from: datetime
    effective_to: Optional[datetime]
    policy_version: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AlertPrioritizationRequest(BaseModel):
    """
    Input payload for prioritizing or re-prioritizing an alert.
    """
    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    source_module: str = "M12.01"
    category: str = "PORTFOLIO"
    event_type: str = "PORTFOLIO_LOSS"
    portfolio_id: str
    instrument_id: Optional[str] = None
    entity_scope: Optional[str] = "PORTFOLIO"
    condition_id: Optional[str] = None

    # Severity & Urgency
    source_severity: Optional[str] = None  # If M11 authoritative or upstream provided
    is_authoritative_severity: bool = False
    observed_value: Optional[Decimal] = None
    previous_value: Optional[Decimal] = None
    dt_seconds: Optional[float] = 60.0
    deadline_remaining_seconds: Optional[float] = None

    # Financial Impact
    affected_value: Optional[Decimal] = None
    nav: Optional[Decimal] = None
    currency: str = "USD"

    # Risk Impact
    limit_utilization_pct: Optional[Decimal] = None
    var_increase_pct: Optional[Decimal] = None
    stress_loss_pct_nav: Optional[Decimal] = None

    # Breadth Impact
    affected_instruments: int = 1
    total_instruments: int = 10
    affected_portfolios: int = 1
    affected_sectors: int = 1

    # Idempotency & Occurrences
    idempotency_key: Optional[str] = None
    source_event_id: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)


class AlertPriorityEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    group_id: Optional[str]
    severity: str
    severity_score: float
    is_authoritative_severity: bool
    severity_source: str
    urgency: str
    urgency_score: float
    time_to_action_label: str
    recommended_action_window_minutes: Optional[int]
    affected_value: Optional[Decimal]
    affected_currency: str
    affected_value_pct_nav: Optional[Decimal]
    financial_impact_score: float
    risk_impact_score: float
    breadth_impact_score: float
    composite_impact_score: float
    persistence_score: float
    priority_score: float
    priority_band: str
    priority_floor_applied: bool
    priority_floor_reason: Optional[str]
    confidence: str
    quality_status: str
    policy_version: int
    scoring_model_version: str
    explanation_summary: Optional[str]
    evidence_json: Dict[str, Any]
    evaluated_at: datetime


class AlertPriorityHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    previous_priority_score: float
    new_priority_score: float
    previous_priority_band: str
    new_priority_band: str
    previous_severity: str
    new_severity: str
    previous_urgency: str
    new_urgency: str
    trigger_event_id: Optional[str]
    change_reason: str
    policy_version: int
    created_at: datetime


class AlertGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    group_key: str
    group_type: str
    parent_group_id: Optional[str]
    primary_alert_id: Optional[str]
    current_priority_score: float
    current_priority_band: str
    maximum_severity: str
    maximum_priority_score: float
    active_child_count: int
    occurrence_count: int
    group_status: str
    created_at: datetime
    updated_at: datetime


class AlertOccurrenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    group_id: Optional[str]
    source_event_id: Optional[str]
    idempotency_key: Optional[str]
    observed_value: Optional[Decimal]
    severity: str
    urgency: str
    priority_score: float
    event_timestamp: datetime
    received_at: datetime
    evidence_reference: Dict[str, Any]
    created_at: datetime


class AlertEscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    group_id: Optional[str]
    previous_severity: str
    new_severity: str
    previous_priority_score: float
    new_priority_score: float
    previous_urgency: str
    new_urgency: str
    escalation_reason: str
    source_event_id: Optional[str]
    policy_version: int
    created_at: datetime


class PrioritizationSummaryAnalytics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_evaluations: int
    active_groups_count: int
    total_occurrences_recorded: int
    total_escalations_recorded: int
    priority_band_distribution: Dict[str, int]
    severity_distribution: Dict[str, int]
    urgency_distribution: Dict[str, int]
    deduplication_rate_pct: float
    emergency_unacknowledged_count: int

