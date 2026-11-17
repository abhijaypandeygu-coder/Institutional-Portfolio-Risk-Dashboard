from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.operational_safety.models.safety_models import (
    SafetyStateCategory,
    KillSwitchScopeType,
    KillSwitchState,
    IncidentSeverity,
    IncidentStatus,
    ExecutionDecisionOutcome,
)


class KillSwitchActivateRequest(BaseModel):
    switch_code: str = Field(default="GLOBAL_EXECUTION")
    scope_type: KillSwitchScopeType = Field(default=KillSwitchScopeType.GLOBAL)
    scope_id: Optional[str] = None
    reason: str = Field(..., min_length=5, max_length=500)
    activated_by: Optional[str] = "operator"
    confirm_action: bool = Field(..., description="Must explicitly confirm activation")


class KillSwitchReactivateRequest(BaseModel):
    switch_code: str = Field(default="GLOBAL_EXECUTION")
    reason: str = Field(..., min_length=5, max_length=500)
    requested_by: Optional[str] = "operator"


class KillSwitchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    switch_code: str
    switch_name: str
    scope_type: KillSwitchScopeType
    scope_id: Optional[str] = None
    state: KillSwitchState
    activation_reason: Optional[str] = None
    activated_by: Optional[str] = None
    activated_at: Optional[datetime] = None
    revision: int
    updated_at: datetime


class ExecutionPrecheckRequest(BaseModel):
    instrument_id: str
    requested_quantity: float
    side: str = Field(..., pattern="^(BUY|SELL)$")
    adapter_id: str = "default_broker_adapter"
    order_type: str = "LIMIT"
    price: Optional[float] = None


class ExecutionPrecheckResponse(BaseModel):
    allowed: bool
    decision: ExecutionDecisionOutcome
    reason_codes: List[str]
    scope: str
    evaluated_at: datetime
    safety_state_revision: int
    policy_version: str
    risk_decision_reference: Optional[str] = None


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., max_length=256)
    description: Optional[str] = None
    severity: IncidentSeverity = IncidentSeverity.SEV3_MEDIUM
    affected_scope: str = "GLOBAL"
    detected_by: Optional[str] = "operator"


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_reference: str
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity
    status: IncidentStatus
    affected_scope: str
    detected_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class OperationalSafetyOverviewResponse(BaseModel):
    overall_safety_state: SafetyStateCategory
    global_execution_enabled: bool
    active_kill_switches_count: int
    active_incidents_count: int
    safety_policy_version: str
    kill_switches: List[KillSwitchResponse]
    incidents: List[IncidentResponse]
    timestamp: datetime
