"""
Pydantic schemas for M11.06 — Breach Detection.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------
# Metric Ingestion Schemas
# -------------------------------------------------------------

class RiskMetricInput(BaseModel):
    portfolio_id: str = Field(..., max_length=64)
    target_entity_type: str = Field(default="PORTFOLIO", max_length=32)
    target_entity_id: str = Field(..., max_length=64)
    metric_code: str = Field(..., max_length=64)
    metric_source_module: str = Field(default="M07_MARKET_RISK", max_length=64)
    metric_value: Decimal
    metric_unit: str = Field(default="PERCENT", max_length=32)
    metric_currency: Optional[str] = Field(None, max_length=16)
    metric_timestamp: datetime
    input_quality_status: str = Field(default="VALID", max_length=32)
    source_event_reference: Optional[str] = None
    correlation_id: Optional[str] = None


class BatchMetricInput(BaseModel):
    metrics: List[RiskMetricInput] = Field(..., min_length=1)


# -------------------------------------------------------------
# Evaluation Schemas
# -------------------------------------------------------------

class BreachEvaluationResponse(BaseModel):
    id: str
    evaluation_reference: str
    portfolio_id: str
    target_entity_type: str
    target_entity_id: str
    metric_code: str
    metric_source_module: str
    metric_value: Decimal
    metric_unit: str
    metric_currency: Optional[str] = None
    metric_timestamp: datetime
    processing_timestamp: datetime
    input_quality_status: str
    active_limit_id: Optional[str] = None
    effective_limit_snapshot_id: Optional[str] = None
    warning_threshold: Optional[Decimal] = None
    hard_threshold: Decimal
    applied_threshold: Decimal
    comparison_operator: str
    evaluation_status: str
    severity: str
    breach_magnitude: Decimal
    utilization: Decimal
    detection_rule_version: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Breach Event Schemas
# -------------------------------------------------------------

class BreachEventResponse(BaseModel):
    id: str
    event_reference: str
    breach_episode_id: str
    portfolio_id: str
    target_entity_type: str
    target_entity_id: str
    risk_limit_id: str
    metric_code: str
    event_type: str
    severity: str
    observed_value: Decimal
    threshold_value: Decimal
    warning_threshold: Optional[Decimal] = None
    hard_threshold: Decimal
    metric_unit: str
    metric_currency: Optional[str] = None
    breach_magnitude: Decimal
    utilization: Decimal
    metric_timestamp: datetime
    detected_at: datetime
    persistence_status: str
    evaluation_id: str
    effective_limit_snapshot_id: Optional[str] = None
    source_event_reference: Optional[str] = None
    correlation_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Breach Episode Schemas
# -------------------------------------------------------------

class BreachObservationResponse(BaseModel):
    id: str
    episode_id: str
    evaluation_id: str
    metric_value: Decimal
    threshold_value: Decimal
    warning_threshold: Optional[Decimal] = None
    hard_threshold: Decimal
    comparison_result: str
    quality_status: str
    metric_timestamp: datetime
    processing_timestamp: datetime
    observation_sequence: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BreachEpisodeResponse(BaseModel):
    id: str
    portfolio_id: str
    risk_limit_id: str
    target_entity_type: str
    target_entity_id: str
    metric_code: str
    limit_version: Optional[str] = None
    episode_status: str
    first_violation_at: datetime
    breach_detected_at: datetime
    recovery_started_at: Optional[datetime] = None
    recovered_at: Optional[datetime] = None
    maximum_breach_magnitude: Decimal
    maximum_observed_value: Decimal
    first_evaluation_id: str
    latest_evaluation_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Detection Rule Schemas
# -------------------------------------------------------------

class DetectionRuleCreate(BaseModel):
    rule_code: str = Field(..., max_length=64)
    rule_name: str = Field(..., max_length=128)
    metric_code: str = Field(..., max_length=64)
    applicable_scope: str = Field(default="ALL", max_length=32)
    persistence_mode: str = Field(default="DURATION", max_length=32)
    required_duration_seconds: int = Field(default=300, ge=0)
    required_consecutive_observations: int = Field(default=3, ge=1)
    observation_window_seconds: int = Field(default=600, ge=0)
    required_observation_count: int = Field(default=3, ge=1)
    permitted_gap_seconds: int = Field(default=120, ge=0)
    recovery_duration_seconds: int = Field(default=180, ge=0)
    immediate_breach: bool = False
    hysteresis_config: Dict[str, Any] = Field(default_factory=dict)
    missing_data_behavior: str = Field(default="SUPPRESS_PASS", max_length=32)


class DetectionRuleResponse(BaseModel):
    id: str
    rule_code: str
    rule_name: str
    metric_code: str
    applicable_scope: str
    persistence_mode: str
    required_duration_seconds: int
    required_consecutive_observations: int
    observation_window_seconds: int
    required_observation_count: int
    permitted_gap_seconds: int
    recovery_duration_seconds: int
    immediate_breach: bool
    hysteresis_config: Dict[str, Any] = Field(default_factory=dict)
    missing_data_behavior: str
    rule_version: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DetectionRuleApprovalRequest(BaseModel):
    approved_by: str = Field(..., max_length=64)
    comments: Optional[str] = None


# -------------------------------------------------------------
# Monitoring & Audit Schemas
# -------------------------------------------------------------

class BreachMonitoringOverviewResponse(BaseModel):
    total_active_warnings: int
    total_active_hard_breaches: int
    total_persistent_breaches: int
    total_transient_breaches: int
    total_recovering_breaches: int
    total_stale_inputs: int
    total_invalid_inputs: int
    total_episodes_active: int


class BreachAuditEventResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    event_type: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    actor_id: str
    reason: Optional[str] = None
    correlation_id: str
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)
