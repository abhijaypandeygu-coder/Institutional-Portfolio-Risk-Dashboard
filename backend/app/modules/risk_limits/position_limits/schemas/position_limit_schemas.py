"""
Pydantic schemas for M11.02 Position Limits.
Conforms strictly to Pydantic v2.0 conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ConfigurationCreate(BaseModel):
    limit_code: str = Field(..., max_length=64)
    limit_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    issuer_id: Optional[str] = None
    limit_type: str = Field(..., description="MAX_POSITION_WEIGHT, MAX_ABSOLUTE_NOTIONAL, MAX_LONG_WEIGHT, MAX_SHORT_WEIGHT, MAX_LONG_NOTIONAL, MAX_SHORT_NOTIONAL, MAX_ISSUER_WEIGHT, MAX_ISSUER_NOTIONAL")
    direction: str = Field("ANY", description="LONG, SHORT, ANY, GROSS, NET")
    aggregation_level: str = Field("INSTRUMENT", description="INSTRUMENT, LISTING, ISSUER")
    threshold_value: Decimal = Field(..., gt=0)
    warning_threshold: Decimal = Field(..., gt=0)
    threshold_unit: str = Field("PERCENT_NAV", description="PERCENT_NAV, USD, INR")
    limit_currency: Optional[str] = "USD"
    comparison_operator: str = "GREATER_THAN_OR_EQUAL"
    precedence: int = 1
    created_by: str = "risk_admin"


class ConfigurationResponse(ConfigurationCreate):
    id: str
    profile_id: Optional[str] = None
    status: str
    approval_status: str
    version: int
    effective_from: datetime
    effective_to: Optional[datetime] = None
    approved_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileCreate(BaseModel):
    profile_code: str = Field(..., max_length=64)
    profile_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    profile_tier: str = Field("STANDARD", description="STANDARD, CONSERVATIVE, MODERATE, AGGRESSIVE")
    base_currency: str = "USD"
    created_by: str = "risk_admin"
    initial_limits: Optional[List[ConfigurationCreate]] = None


class ProfileResponse(BaseModel):
    id: str
    profile_code: str
    profile_name: str
    description: Optional[str] = None
    profile_tier: str
    base_currency: str
    status: str
    is_active: bool
    created_by: str
    approved_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    configurations: List[ConfigurationResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AssignmentCreate(BaseModel):
    profile_id: str
    target_type: str = Field("PORTFOLIO", description="PORTFOLIO, MANDATE, ISSUER")
    target_id: str
    precedence: int = 1
    assigned_by: str = "risk_admin"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class AssignmentResponse(AssignmentCreate):
    id: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PositionInput(BaseModel):
    instrument_id: str
    symbol: Optional[str] = None
    issuer_id: Optional[str] = None
    quantity: Decimal
    market_value: Decimal
    currency: str = "USD"
    price: Optional[Decimal] = None


class PortfolioEvaluationRequest(BaseModel):
    portfolio_id: str
    portfolio_nav: Decimal
    base_currency: str = "USD"
    positions: List[PositionInput] = []
    evaluation_type: str = "PORTFOLIO_WIDE"
    evaluator: str = "system"


class ProposedOrderRequest(BaseModel):
    portfolio_id: str
    portfolio_nav: Decimal
    instrument_id: str
    symbol: Optional[str] = None
    issuer_id: Optional[str] = None
    order_side: str = Field(..., description="BUY or SELL")
    order_quantity: Decimal = Field(..., gt=0)
    reference_price: Decimal = Field(..., gt=0)
    fx_rate: Decimal = Decimal("1.0")
    base_currency: str = "USD"
    current_quantity: Decimal = Decimal("0.0")
    current_market_value: Decimal = Decimal("0.0")
    evaluator: str = "pretrade_risk_officer"


class EvaluationResultItem(BaseModel):
    limit_id: Optional[str] = None
    limit_code: str
    limit_type: str
    instrument_id: Optional[str] = None
    symbol: Optional[str] = None
    issuer_id: Optional[str] = None
    position_direction: str
    actual_exposure: Decimal
    exposure_currency: str
    warning_threshold: Decimal
    hard_threshold: Decimal
    threshold_unit: str
    warning_utilization_pct: Decimal
    hard_utilization_pct: Decimal
    remaining_capacity: Decimal
    breach_amount: Decimal
    evaluation_status: str
    reason_code: Optional[str] = None
    details: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class PortfolioEvaluationResponse(BaseModel):
    id: str
    portfolio_id: str
    evaluation_type: str
    evaluation_timestamp: datetime
    portfolio_nav: Decimal
    base_currency: str
    overall_status: str
    total_positions_evaluated: int
    warning_breaches_count: int
    hard_breaches_count: int
    results: List[EvaluationResultItem] = []
    execution_duration_ms: int

    model_config = ConfigDict(from_attributes=True)


class ProposedOrderEvaluationResponse(BaseModel):
    portfolio_id: str
    instrument_id: str
    symbol: Optional[str] = None
    order_side: str
    order_quantity: Decimal
    reference_price: Decimal
    current_market_value: Decimal
    projected_market_value: Decimal
    current_weight_pct: Decimal
    projected_weight_pct: Decimal
    projected_notional: Decimal
    overall_status: str
    evaluations: List[EvaluationResultItem] = []
    is_pretrade_approved: bool

    model_config = ConfigDict(from_attributes=True)
