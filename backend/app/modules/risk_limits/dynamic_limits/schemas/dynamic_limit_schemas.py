"""
Pydantic schemas for M11.05 — Dynamic Limits.

Defines request/response schemas for:
- Policies & Policy Versions
- Conditions & Hysteresis rules
- Trading Session Schedules
- Manual Overrides (Maker-Checker workflow)
- Evaluation Requests & Lineage
- Effective Limit Snapshots
- Audit Trail Events
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------
# Base / Shared Models
# -------------------------------------------------------------

class ConditionBase(BaseModel):
    rule_name: str = Field(..., max_length=128)
    priority: int = Field(default=100, ge=1, le=1000)
    is_active: bool = True
    metric_source: str = Field(..., max_length=64, description="VOLATILITY, LIQUIDITY, REGIME, DRAWDOWN")
    metric_name: str = Field(..., max_length=64)
    operator: str = Field(default="GREATER_THAN", max_length=32)
    threshold_low: Decimal
    threshold_high: Optional[Decimal] = None
    hysteresis_entry: Optional[Decimal] = None
    hysteresis_exit: Optional[Decimal] = None
    hysteresis_direction: str = Field(default="UP", max_length=8)
    persistence_minutes: int = Field(default=0, ge=0)
    regime_match: Optional[str] = None
    adjustment_type: str = Field(default="MULTIPLICATIVE", max_length=32)
    adjustment_value: Decimal
    description: Optional[str] = None


class ConditionCreate(ConditionBase):
    pass


class ConditionResponse(ConditionBase):
    id: str
    version_id: str
    model_config = ConfigDict(from_attributes=True)


class ScheduleBase(BaseModel):
    session_name: str = Field(..., max_length=32)
    market: str = Field(default="IN", max_length=16)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    adjustment_type: str = Field(default="MULTIPLICATIVE", max_length=32)
    adjustment_value: Decimal
    is_active: bool = True


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleResponse(ScheduleBase):
    id: str
    version_id: str
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Policy Version Schemas
# -------------------------------------------------------------

class PolicyVersionCreate(BaseModel):
    target_limit_code: str = Field(..., max_length=64)
    limit_nature: str = Field(default="CAP", max_length=16)
    base_limit_value: Decimal
    restrictive_only: bool = True
    min_allowed_value: Optional[Decimal] = None
    max_allowed_value: Optional[Decimal] = None
    authored_by: str = Field(..., max_length=64)
    change_reason: Optional[str] = None
    conditions: List[ConditionCreate] = Field(default_factory=list)
    schedules: List[ScheduleCreate] = Field(default_factory=list)


class PolicyVersionResponse(BaseModel):
    id: str
    policy_id: str
    version_number: int
    target_limit_code: str
    limit_nature: str
    base_limit_value: Decimal
    restrictive_only: bool
    min_allowed_value: Optional[Decimal] = None
    max_allowed_value: Optional[Decimal] = None
    status: str
    authored_by: str
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    change_reason: Optional[str] = None
    created_at: datetime
    conditions: List[ConditionResponse] = Field(default_factory=list)
    schedules: List[ScheduleResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Policy Schemas
# -------------------------------------------------------------

class PolicyCreate(BaseModel):
    policy_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    portfolio_id: Optional[str] = Field(None, max_length=64)
    market: Optional[str] = Field(default="IN", max_length=16)
    asset_class: str = Field(default="EQUITY", max_length=32)
    created_by: str = Field(..., max_length=64)
    initial_version: Optional[PolicyVersionCreate] = None


class PolicyResponse(BaseModel):
    id: str
    policy_code: str
    name: str
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    market: Optional[str] = None
    asset_class: str
    status: str
    current_version_id: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    versions: List[PolicyVersionResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class PolicyApprovalRequest(BaseModel):
    approved_by: str = Field(..., max_length=64)
    comments: Optional[str] = None


# -------------------------------------------------------------
# Override Schemas (Maker-Checker)
# -------------------------------------------------------------

class OverrideCreate(BaseModel):
    policy_id: str = Field(..., max_length=64)
    target_limit_code: str = Field(..., max_length=64)
    override_value: Decimal
    reason_code: str = Field(..., max_length=64)
    justification: str
    effective_from: datetime
    effective_to: datetime
    requested_by: str = Field(..., max_length=64)


class OverrideApprovalRequest(BaseModel):
    approved_by: str = Field(..., max_length=64)
    comments: Optional[str] = None


class OverrideRejectRequest(BaseModel):
    rejected_by: str = Field(..., max_length=64)
    rejection_reason: str


class OverrideRevokeRequest(BaseModel):
    revoked_by: str = Field(..., max_length=64)
    revocation_reason: str


class OverrideResponse(BaseModel):
    id: str
    policy_id: str
    target_limit_code: str
    override_value: Decimal
    reason_code: str
    justification: str
    effective_from: datetime
    effective_to: datetime
    status: str
    requested_by: str
    requested_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    revoked_by: Optional[str] = None
    revoked_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Evaluation & Snapshot Schemas
# -------------------------------------------------------------

class DynamicLimitEvaluationRequest(BaseModel):
    portfolio_id: Optional[str] = None
    market: str = Field(default="IN", max_length=16)
    as_of_time: Optional[datetime] = None
    current_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="e.g. {'PORTFOLIO_VOLATILITY': 0.28, 'MARKET_REGIME': 'HIGH_VOLATILITY', 'LIQUIDITY_DEPTH': 450000}"
    )


class EffectiveLimitSnapshotResponse(BaseModel):
    id: str
    policy_id: str
    policy_version_id: str
    portfolio_id: Optional[str] = None
    target_limit_code: str
    base_limit_value: Decimal
    effective_limit_value: Decimal
    limit_nature: str
    active_regime: Optional[str] = None
    active_session: Optional[str] = None
    condition_adjustment_applied: Optional[str] = None
    override_applied_id: Optional[str] = None
    as_of_time: datetime
    snapshot_hash: str
    lineage_metadata: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)


class DynamicLimitAuditEventResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    performed_by: str
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)
