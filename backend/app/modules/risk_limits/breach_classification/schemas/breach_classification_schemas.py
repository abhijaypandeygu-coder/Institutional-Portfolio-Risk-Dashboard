"""
Pydantic schemas for M11.07 — Breach Classification.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------
# Rule & Policy Schemas
# -------------------------------------------------------------

class ClassificationRuleCreate(BaseModel):
    rule_code: str = Field(..., max_length=64)
    rule_name: str = Field(..., max_length=128)
    target_metric_code: str = Field(default="ALL", max_length=64)
    target_limit_type: str = Field(default="ALL", max_length=32)
    condition_operator: str = Field(default="GREATER_THAN", max_length=32)
    threshold_value: Decimal
    upper_threshold_value: Optional[Decimal] = None
    unit: str = Field(default="PERCENT", max_length=32)
    target_severity: str = Field(..., max_length=16, description="WARNING, CRITICAL, EMERGENCY")
    priority: int = Field(default=100, ge=1, le=1000)
    persistence_requirement: Optional[str] = None
    immediate_classification: bool = False
    materiality_requirement: Optional[Decimal] = None
    enabled: bool = True


class ClassificationRuleResponse(ClassificationRuleCreate):
    id: str
    policy_version_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClassificationPolicyVersionCreate(BaseModel):
    configuration_json: Dict[str, Any] = Field(default_factory=dict)
    severity_mapping: Dict[str, Any] = Field(default_factory=dict)
    precedence_configuration: Dict[str, Any] = Field(default_factory=dict)
    materiality_configuration: Dict[str, Any] = Field(default_factory=dict)
    persistence_configuration: Dict[str, Any] = Field(default_factory=dict)
    emergency_rules: Dict[str, Any] = Field(default_factory=dict)
    rules: List[ClassificationRuleCreate] = Field(default_factory=list)


class ClassificationPolicyVersionResponse(BaseModel):
    id: str
    policy_id: str
    version_number: int
    configuration_json: Dict[str, Any] = Field(default_factory=dict)
    approval_status: str
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    rules: List[ClassificationRuleResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ClassificationPolicyCreate(BaseModel):
    policy_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    scope_type: str = Field(default="ALL", max_length=32)
    scope_id: Optional[str] = None
    risk_category: str = Field(default="ALL", max_length=64)
    priority: int = Field(default=100, ge=1, le=1000)
    created_by: str = Field(..., max_length=64)
    initial_version: Optional[ClassificationPolicyVersionCreate] = None


class ClassificationPolicyResponse(BaseModel):
    id: str
    policy_code: str
    name: str
    description: Optional[str] = None
    scope_type: str
    scope_id: Optional[str] = None
    risk_category: str
    priority: int
    lifecycle_status: str
    current_version: int
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    versions: List[ClassificationPolicyVersionResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class PolicyApprovalRequest(BaseModel):
    approved_by: str = Field(..., max_length=64)
    comments: Optional[str] = None


# -------------------------------------------------------------
# Classification Operation Schemas
# -------------------------------------------------------------

class ClassifyBreachRequest(BaseModel):
    breach_event_id: str = Field(..., max_length=64)
    portfolio_nav: Optional[Decimal] = None
    policy_code: Optional[str] = None


class BatchClassifyRequest(BaseModel):
    items: List[ClassifyBreachRequest] = Field(..., min_length=1)


class ReclassificationRequest(BaseModel):
    new_severity: str = Field(..., max_length=16, description="WARNING, CRITICAL, EMERGENCY")
    reason_code: str = Field(..., max_length=64)
    reason_text: Optional[str] = None
    changed_by: str = Field(..., max_length=64)


class ClassificationEvidenceResponse(BaseModel):
    id: str
    classification_id: str
    evidence_type: str
    source_module: str
    source_record_id: Optional[str] = None
    metric_code: str
    observed_value: Decimal
    threshold_value: Decimal
    unit: str
    source_timestamp: datetime
    evidence_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClassificationHistoryResponse(BaseModel):
    id: str
    classification_id: str
    previous_severity: str
    new_severity: str
    change_type: str
    reason_code: str
    reason_text: Optional[str] = None
    policy_version: int
    triggering_event_id: Optional[str] = None
    changed_by: str
    changed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BreachClassificationResponse(BaseModel):
    id: str
    classification_reference: str
    breach_event_id: str
    breach_episode_id: str
    portfolio_id: str
    risk_limit_id: str
    metric_code: str
    target_entity_type: str
    target_entity_id: str
    severity: str
    classification_status: str
    classification_reason: str
    policy_id: str
    policy_version: int
    observed_value: Decimal
    applied_threshold: Decimal
    breach_magnitude: Decimal
    utilization: Decimal
    persistence_status: str
    materiality_value: Optional[Decimal] = None
    materiality_status: str
    effective_limit_snapshot_id: Optional[str] = None
    classified_at: datetime
    created_at: datetime
    evidence: List[ClassificationEvidenceResponse] = Field(default_factory=list)
    history: List[ClassificationHistoryResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Monitoring & Audit Schemas
# -------------------------------------------------------------

class ClassificationOverviewResponse(BaseModel):
    total_warning_events: int
    total_critical_events: int
    total_emergency_events: int
    total_active_classifications: int
    total_upgraded_events: int
    total_downgraded_events: int


class ClassificationAuditEventResponse(BaseModel):
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
