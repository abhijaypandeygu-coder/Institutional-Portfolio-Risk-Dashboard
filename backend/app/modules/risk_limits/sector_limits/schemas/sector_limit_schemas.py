"""
Pydantic schemas for M11.03 Sector Limits.
Conforms strictly to Pydantic v2.0 conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class SectorLimitConfigCreate(BaseModel):
    limit_code: str = Field(..., max_length=64)
    limit_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    classification_system: str = "GICS"
    classification_version: str = "2026.1"
    sector_id: Optional[str] = None
    sector_name: Optional[str] = None
    industry_id: Optional[str] = None
    industry_name: Optional[str] = None
    limit_type: str = Field(..., description="MAX_SECTOR_WEIGHT, MAX_INDUSTRY_WEIGHT, MAX_ACTIVE_SECTOR_OVERWEIGHT, MAX_ACTIVE_SECTOR_UNDERWEIGHT")
    direction: str = Field("GROSS", description="GROSS, NET, LONG, SHORT")
    threshold_value: Decimal = Field(..., description="Upper threshold or cap")
    warning_threshold: Decimal = Field(..., description="Warning threshold")
    lower_threshold: Optional[Decimal] = None
    threshold_unit: str = "PERCENT_NAV"
    benchmark_id: Optional[str] = None
    precedence: int = 1
    created_by: str = "risk_admin"


class SectorLimitConfigResponse(SectorLimitConfigCreate):
    id: str
    profile_id: Optional[str] = None
    status: str
    approval_status: str
    version: int
    effective_from: datetime
    effective_to: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SectorProfileCreate(BaseModel):
    profile_code: str = Field(..., max_length=64)
    profile_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    profile_tier: str = "STANDARD"
    classification_system: str = "GICS"
    base_currency: str = "USD"
    created_by: str = "risk_admin"
    initial_limits: Optional[List[SectorLimitConfigCreate]] = None


class SectorProfileResponse(BaseModel):
    id: str
    profile_code: str
    profile_name: str
    description: Optional[str] = None
    profile_tier: str
    classification_system: str
    base_currency: str
    status: str
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    configurations: List[SectorLimitConfigResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SectorAssignmentCreate(BaseModel):
    profile_id: str
    target_type: str = "PORTFOLIO"
    target_id: str
    precedence: int = 1
    assigned_by: str = "risk_admin"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class SectorAssignmentResponse(SectorAssignmentCreate):
    id: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SectorPositionInput(BaseModel):
    instrument_id: str
    symbol: Optional[str] = None
    sector_id: Optional[str] = None
    sector_name: Optional[str] = None
    industry_id: Optional[str] = None
    industry_name: Optional[str] = None
    quantity: Decimal
    market_value: Decimal
    currency: str = "USD"


class SectorEvaluationRequest(BaseModel):
    portfolio_id: str
    portfolio_nav: Decimal
    base_currency: str = "USD"
    benchmark_id: Optional[str] = None
    benchmark_weights: Optional[Dict[str, Decimal]] = None # e.g. {"TECH": Decimal("22.0"), "FIN": Decimal("15.0")}
    positions: List[SectorPositionInput] = []
    evaluation_type: str = "PORTFOLIO_WIDE"
    evaluator: str = "system"


class SectorEvaluationResultItem(BaseModel):
    limit_id: Optional[str] = None
    limit_code: str
    limit_type: str
    classification_level: str
    sector_id: Optional[str] = None
    industry_id: Optional[str] = None
    actual_exposure: Decimal
    benchmark_exposure: Optional[Decimal] = None
    active_weight_pct: Optional[Decimal] = None
    warning_threshold: Decimal
    hard_threshold: Decimal
    threshold_unit: str
    warning_utilization_pct: Decimal
    hard_utilization_pct: Decimal
    remaining_capacity: Decimal
    breach_amount: Decimal
    evaluation_status: str
    details: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class SectorEvaluationResponse(BaseModel):
    id: str
    portfolio_id: str
    evaluation_type: str
    evaluation_timestamp: datetime
    portfolio_nav: Decimal
    base_currency: str
    total_eligible_exposure: Decimal
    classified_exposure: Decimal
    unclassified_exposure: Decimal
    classification_coverage_pct: Decimal
    overall_status: str
    total_sectors_evaluated: int
    total_industries_evaluated: int
    warning_breaches_count: int
    hard_breaches_count: int
    results: List[SectorEvaluationResultItem] = []
    execution_duration_ms: int

    model_config = ConfigDict(from_attributes=True)

