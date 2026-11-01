"""Pydantic 2.x Schemas for M05.01 Portfolio Creation."""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.portfolio_management.portfolio_creation.models import (
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
    CreationSourceEnum,
    MarketScopeEnum,
    OwnershipTypeEnum,
    HierarchyTypeEnum,
    BenchmarkTypeEnum,
    ValuationFrequencyEnum,
    AccountingBasisEnum,
    CostBasisMethodEnum,
    DividendAccrualMethodEnum,
    LimitCategoryEnum,
    LimitScopeEnum,
    LimitThresholdTypeEnum,
    LimitStatusEnum,
)


# ---------------------------------------------------------------------------
# PORTFOLIO REGISTRATION SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioCreateRequest(BaseModel):
    portfolio_code: str = Field(..., min_length=2, max_length=64)
    portfolio_name: str = Field(..., min_length=2, max_length=128)
    short_name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None
    portfolio_type: PortfolioTypeEnum = PortfolioTypeEnum.DISCRETIONARY
    creation_source: CreationSourceEnum = CreationSourceEnum.MANUAL_ADMINISTRATION
    base_currency: str = Field(..., min_length=3, max_length=3) # e.g. 'USD', 'INR'
    market_scope: MarketScopeEnum = MarketScopeEnum.INDIA_AND_US
    asset_class_scope: str = "EQUITIES"
    effective_from: Optional[date] = None


class PortfolioUpdateRequest(BaseModel):
    portfolio_name: Optional[str] = Field(None, min_length=2, max_length=128)
    short_name: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = None
    market_scope: Optional[MarketScopeEnum] = None
    asset_class_scope: Optional[str] = None


class BaseCurrencyChangeRequest(BaseModel):
    new_base_currency: str = Field(..., min_length=3, max_length=3)
    effective_date: date
    change_reason: str = Field(..., min_length=3, max_length=256)
    fx_policy_reference: Optional[str] = "DAILY_OFFICIAL_FX"


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    portfolio_code: str
    portfolio_name: str
    short_name: str
    description: Optional[str] = None
    portfolio_type: PortfolioTypeEnum
    lifecycle_status: PortfolioLifecycleStatus
    creation_source: CreationSourceEnum
    base_currency: str
    market_scope: MarketScopeEnum
    asset_class_scope: str
    current_configuration_version: int
    effective_from: date
    effective_to: Optional[date] = None
    created_by: str
    approved_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# STRATEGY & MANDATE SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioStrategyCreateRequest(BaseModel):
    strategy_code: str = Field(..., min_length=2, max_length=64)
    strategy_name: str = Field(..., min_length=2, max_length=128)
    strategy_family: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = None
    supported_asset_classes: str = "EQUITIES"
    supported_markets: str = "INDIA_AND_US"


class PortfolioStrategyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_code: str
    strategy_name: str
    strategy_family: str
    description: Optional[str] = None
    supported_asset_classes: str
    supported_markets: str
    is_active: bool
    created_at: datetime


class PortfolioStrategyAssignRequest(BaseModel):
    strategy_code: str = Field(..., min_length=2, max_length=64)
    is_primary: bool = True
    assignment_reason: Optional[str] = None
    effective_from: Optional[date] = None


class PortfolioStrategyAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    strategy_code: str
    is_primary: bool
    assignment_reason: Optional[str] = None
    effective_from: date
    effective_to: Optional[date] = None
    recorded_at: datetime


class PortfolioMandateCreateRequest(BaseModel):
    mandate_code: str = Field(..., min_length=2, max_length=64)
    mandate_name: str = Field(..., min_length=2, max_length=128)
    mandate_type: str = "LONG_ONLY_EQUITY"
    investment_objective: str = Field(..., min_length=5)
    permitted_markets: str = "INDIA_AND_US"
    permitted_asset_classes: str = "EQUITIES"
    short_selling_permitted: bool = False
    leverage_permitted: bool = False
    configuration_json: Optional[str] = None


class PortfolioMandateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mandate_code: str
    mandate_name: str
    mandate_type: str
    investment_objective: str
    permitted_markets: str
    permitted_asset_classes: str
    short_selling_permitted: bool
    leverage_permitted: bool
    policy_version: int
    is_active: bool
    created_by: str
    created_at: datetime


class PortfolioMandateAssignRequest(BaseModel):
    mandate_code: str = Field(..., min_length=2, max_length=64)
    effective_from: Optional[date] = None


class PortfolioMandateAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    mandate_code: str
    effective_from: date
    effective_to: Optional[date] = None
    assigned_by: str
    recorded_at: datetime


# ---------------------------------------------------------------------------
# BENCHMARK SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioBenchmarkAssignRequest(BaseModel):
    benchmark_reference_id: str = Field(..., min_length=2, max_length=64)
    benchmark_name: str = Field(..., min_length=2, max_length=128)
    benchmark_type: BenchmarkTypeEnum = BenchmarkTypeEnum.PRIMARY_BENCHMARK
    benchmark_currency: str = Field(..., min_length=3, max_length=3)
    is_primary: bool = True
    benchmark_weight: float = 1.0000
    effective_from: Optional[date] = None
    source_reference: Optional[str] = None


class PortfolioBenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    association_id: str
    portfolio_id: str
    benchmark_reference_id: str
    benchmark_name: str
    benchmark_type: BenchmarkTypeEnum
    benchmark_currency: str
    is_primary: bool
    benchmark_weight: float
    effective_from: date
    effective_to: Optional[date] = None
    source_reference: Optional[str] = None
    recorded_at: datetime


# ---------------------------------------------------------------------------
# OWNERSHIP SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioOwnershipAssignRequest(BaseModel):
    ownership_type: OwnershipTypeEnum = OwnershipTypeEnum.INDIVIDUAL
    owner_entity_id: str = Field(..., min_length=2, max_length=64)
    owner_name: str = Field(..., min_length=2, max_length=128)
    ownership_role: str = "PORTFOLIO_MANAGER"
    is_primary_owner: bool = True
    effective_from: Optional[date] = None


class PortfolioOwnershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ownership_id: str
    portfolio_id: str
    ownership_type: OwnershipTypeEnum
    owner_entity_id: str
    owner_name: str
    ownership_role: str
    is_primary_owner: bool
    effective_from: date
    effective_to: Optional[date] = None
    assigned_by: str
    recorded_at: datetime


# ---------------------------------------------------------------------------
# HIERARCHY SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioHierarchyAssignRequest(BaseModel):
    child_portfolio_id: str = Field(..., min_length=2, max_length=64)
    relationship_type: HierarchyTypeEnum = HierarchyTypeEnum.SLEEVE
    allocation_weight: Optional[float] = None
    aggregation_method: str = "PRO_RATA_WEIGHTED"
    effective_from: Optional[date] = None


class PortfolioHierarchyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relationship_id: str
    parent_portfolio_id: str
    child_portfolio_id: str
    relationship_type: HierarchyTypeEnum
    allocation_weight: Optional[float] = None
    aggregation_method: str
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool
    created_by: str
    recorded_at: datetime


# ---------------------------------------------------------------------------
# VALUATION & ACCOUNTING SETTINGS SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioValuationSettingsRequest(BaseModel):
    valuation_calendar_id: str = "DEFAULT_DAILY_CALENDAR"
    valuation_frequency: ValuationFrequencyEnum = ValuationFrequencyEnum.DAILY
    cutoff_time: str = "16:00:00"
    cutoff_timezone: str = "UTC"
    price_selection_policy_id: str = "OFFICIAL_CLOSE_FALLBACK_PREV"
    currency_conversion_policy_id: str = "DAILY_OFFICIAL_FX"
    effective_from: Optional[date] = None


class PortfolioValuationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    valuation_calendar_id: str
    valuation_frequency: ValuationFrequencyEnum
    cutoff_time: str
    cutoff_timezone: str
    price_selection_policy_id: str
    currency_conversion_policy_id: str
    effective_from: date
    effective_to: Optional[date] = None
    configuration_version: int
    recorded_at: datetime


class PortfolioAccountingSettingsRequest(BaseModel):
    trade_accounting_basis: AccountingBasisEnum = AccountingBasisEnum.TRADE_DATE
    cost_basis_method: CostBasisMethodEnum = CostBasisMethodEnum.FIFO
    dividend_accrual_method: DividendAccrualMethodEnum = DividendAccrualMethodEnum.ACCRUAL_ON_ENTITLEMENT
    corporate_action_policy_id: str = "STANDARD_ADJUSTMENT_FACTOR"
    rounding_precision_places: int = 4
    effective_from: Optional[date] = None


class PortfolioAccountingSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    trade_accounting_basis: AccountingBasisEnum
    cost_basis_method: CostBasisMethodEnum
    dividend_accrual_method: DividendAccrualMethodEnum
    corporate_action_policy_id: str
    rounding_precision_places: int
    effective_from: date
    effective_to: Optional[date] = None
    policy_version: int
    recorded_at: datetime


# ---------------------------------------------------------------------------
# LIMIT SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioLimitCreateRequest(BaseModel):
    limit_code: str = Field(..., min_length=2, max_length=64)
    limit_name: str = Field(..., min_length=2, max_length=128)
    limit_category: LimitCategoryEnum
    limit_scope: LimitScopeEnum = LimitScopeEnum.PORTFOLIO_LEVEL
    scope_reference: Optional[str] = None
    comparison_operator: str = "<="
    threshold_value: float
    threshold_unit: LimitThresholdTypeEnum = LimitThresholdTypeEnum.PERCENTAGE
    currency: Optional[str] = None
    warning_threshold: Optional[float] = None
    hard_threshold: Optional[float] = None
    effective_from: Optional[date] = None


class PortfolioLimitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    limit_id: str
    portfolio_id: str
    limit_code: str
    limit_name: str
    limit_category: LimitCategoryEnum
    limit_scope: LimitScopeEnum
    scope_reference: Optional[str] = None
    comparison_operator: str
    threshold_value: float
    threshold_unit: LimitThresholdTypeEnum
    currency: Optional[str] = None
    warning_threshold: Optional[float] = None
    hard_threshold: Optional[float] = None
    limit_status: LimitStatusEnum
    effective_from: date
    effective_to: Optional[date] = None
    policy_version: int
    created_by: str
    recorded_at: datetime


# ---------------------------------------------------------------------------
# CONFIGURATION SNAPSHOT & LIFECYCLE SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioConfigurationSnapshotResponse(BaseModel):
    portfolio_id: str
    version_number: int
    valid_from: date
    valid_to: Optional[date] = None
    recorded_at: datetime
    created_by: str
    change_reason: Optional[str] = None
    snapshot: Dict[str, Any]


class LifecycleTransitionRequest(BaseModel):
    reason: Optional[str] = None
    approval_reference: Optional[str] = None
    effective_date: Optional[date] = None


class LifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    portfolio_id: str
    previous_status: PortfolioLifecycleStatus
    new_status: PortfolioLifecycleStatus
    effective_date: date
    recorded_at: datetime
    actor_id: str
    reason: Optional[str] = None
    approval_reference: Optional[str] = None


class PortfolioOperationalMetricsResponse(BaseModel):
    total_portfolios: int
    active_portfolios: int
    draft_portfolios: int
    suspended_portfolios: int
    closed_portfolios: int
    portfolios_by_currency: Dict[str, int]
    portfolios_by_type: Dict[str, int]
    portfolios_by_market: Dict[str, int]

