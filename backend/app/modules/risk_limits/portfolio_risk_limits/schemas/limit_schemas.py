"""
Pydantic schemas for M11.01 Portfolio Risk Limits.
Conforms to Pydantic v2.0 conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class RiskLimitCreate(BaseModel):
    limit_code: str = Field(..., max_length=64)
    limit_name: str = Field(..., max_length=128)
    risk_category: str = Field(..., description="VAR, VOLATILITY, DRAWDOWN")
    metric_identifier: str = Field(..., description="VAR_95_1D, REALIZED_VOL_30D, DRAWDOWN_MAX")
    limit_type: str = Field("ABSOLUTE", description="ABSOLUTE, NAV_RELATIVE, PERCENTAGE")
    warning_threshold: Decimal = Field(..., gt=0)
    hard_threshold: Decimal = Field(..., gt=0)
    threshold_unit: str = "USD"
    comparison_operator: str = "GREATER_THAN_OR_EQUAL"
    confidence_level: Optional[float] = None
    risk_horizon_days: Optional[int] = None
    risk_methodology: Optional[str] = None
    volatility_type: Optional[str] = None
    return_frequency: Optional[str] = "DAILY"
    annualization_factor: Optional[float] = 252.0
    estimation_window_days: Optional[int] = None
    drawdown_methodology: Optional[str] = "PEAK_TO_TROUGH"


class RiskLimitResponse(RiskLimitCreate):
    id: str
    profile_version_id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileCreate(BaseModel):
    profile_code: str = Field(..., max_length=64)
    profile_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    profile_category: str = "STANDARD"
    mandate_type: Optional[str] = None
    portfolio_type: Optional[str] = None
    base_currency_policy: str = "USD"
    owner_id: str = "risk_admin"
    initial_limits: Optional[List[RiskLimitCreate]] = None


class ProfileVersionResponse(BaseModel):
    id: str
    profile_id: str
    version_number: int
    version_status: str
    change_summary: Optional[str] = None
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    effective_from: datetime
    effective_to: Optional[datetime] = None
    limits: List[RiskLimitResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProfileResponse(BaseModel):
    id: str
    profile_code: str
    profile_name: str
    description: Optional[str] = None
    profile_category: str
    mandate_type: Optional[str] = None
    portfolio_type: Optional[str] = None
    base_currency_policy: str
    status: str
    owner_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    active_version: Optional[ProfileVersionResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AssignmentCreate(BaseModel):
    profile_id: str
    target_type: str = "PORTFOLIO"
    target_id: str
    precedence: int = 1
    assigned_by: str = "risk_admin"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class AssignmentResponse(BaseModel):
    id: str
    profile_id: str
    profile_version_id: str
    target_type: str
    target_id: str
    assignment_status: str
    precedence: int
    assigned_by: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationRequest(BaseModel):
    portfolio_id: str
    observed_var_monetary: Optional[Decimal] = None
    observed_volatility_annualized: Optional[Decimal] = None
    observed_drawdown_magnitude: Optional[Decimal] = None
    portfolio_nav: Optional[Decimal] = None


class LimitUtilizationResponse(BaseModel):
    limit_id: str
    limit_code: str
    risk_category: str
    metric_identifier: str
    observed_metric_value: Decimal
    warning_threshold: Decimal
    hard_threshold: Decimal
    warning_utilization_pct: Decimal
    hard_utilization_pct: Decimal
    headroom: Decimal
    unit: str
    evaluation_status: str
    details: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class PortfolioEvaluationResponse(BaseModel):
    portfolio_id: str
    profile_code: str
    profile_version_number: int
    evaluated_at: datetime
    overall_status: str
    utilizations: List[LimitUtilizationResponse] = []
    narrative: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

