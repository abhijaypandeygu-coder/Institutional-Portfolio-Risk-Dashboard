"""
Pydantic 2.x Schemas for M06.07 Portfolio Allocation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.risk_management.portfolio_allocation.models import (
    AllocationViewType,
    AllocationGroupingDimension,
    AllocationReconciliationStatus,
    AllocationDriftStatus,
)


class PortfolioAllocationCalculateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    allocation_view_type: AllocationViewType = AllocationViewType.NAV_CAPITAL_ALLOCATION
    grouping_dimension: AllocationGroupingDimension = AllocationGroupingDimension.SECURITY
    reporting_currency: str = "USD"
    as_of_date: Optional[datetime] = None
    snapshot_id: Optional[str] = None
    include_cash_in_breakdown: bool = True


class PortfolioAllocationComponentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    component_id: str
    grouping_dimension: AllocationGroupingDimension
    group_id: str
    group_key: str
    group_name: str
    rank: int

    long_market_value: Decimal
    short_market_value: Decimal
    net_market_value: Decimal
    gross_market_value: Decimal
    cash_value: Decimal

    actual_nav_weight: Decimal
    normalized_weight: Decimal
    gross_exposure_weight: Decimal

    allocation_status: str
    source_reference: Optional[str] = None


class PortfolioAllocationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    snapshot_id: Optional[str] = None

    allocation_view_type: AllocationViewType
    grouping_dimension: AllocationGroupingDimension
    reporting_currency: str

    nav_value: Decimal
    total_long_market_value: Decimal
    total_short_market_value: Decimal
    net_security_market_value: Decimal
    gross_security_exposure: Decimal

    cash_nav_value: Decimal
    settled_cash_value: Decimal
    available_cash_value: Decimal
    restricted_cash_value: Decimal

    other_nav_components: Decimal
    unallocated_nav_value: Decimal
    reconciliation_residual: Decimal

    invested_nav_weight: Decimal = Decimal("0.0")
    cash_nav_weight: Decimal = Decimal("0.0")
    gross_exposure_to_nav: Decimal = Decimal("0.0")

    reconciliation_status: AllocationReconciliationStatus
    data_completeness_status: str
    calculation_version: str
    calculated_at: datetime

    components: Optional[List[PortfolioAllocationComponentItemResponse]] = None


class PortfolioAllocationTargetCreateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    grouping_dimension: AllocationGroupingDimension
    group_id: str
    target_weight: Decimal
    weight_denominator: str = "NAV"
    reporting_currency: str = "USD"
    tolerance_band_pp: Decimal = Decimal("0.050000")
    configuration_version: str = "v1.0"


class PortfolioAllocationTargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    grouping_dimension: AllocationGroupingDimension
    group_id: str
    target_weight: Decimal
    weight_denominator: str
    reporting_currency: str
    tolerance_band_pp: Decimal
    is_active: bool
    configuration_version: str
    effective_from: datetime


class PortfolioAllocationDriftItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    drift_id: str
    result_id: str
    portfolio_id: Optional[str] = None
    grouping_dimension: AllocationGroupingDimension
    group_id: str
    group_name: str

    actual_weight: Decimal
    target_weight: Decimal
    absolute_drift_pp: Decimal
    relative_drift_percentage: Optional[Decimal] = None
    capital_difference: Decimal
    drift_status: AllocationDriftStatus
    calculated_at: datetime


class PortfolioAllocationDriftResponse(BaseModel):
    result_id: str
    portfolio_id: Optional[str] = None
    grouping_dimension: AllocationGroupingDimension
    total_drifts_count: int
    overweight_count: int
    underweight_count: int
    material_drift_count: int
    items: List[PortfolioAllocationDriftItemResponse]


class PortfolioAllocationCompareRequest(BaseModel):
    base_result_id: str
    comparison_result_id: str


class PortfolioAllocationComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comparison_id: str
    portfolio_id: Optional[str] = None
    current_result_id: str
    prior_result_id: str

    grouping_dimension: AllocationGroupingDimension
    reporting_currency: str

    current_nav: Decimal
    prior_nav: Decimal
    nav_change: Decimal

    current_cash_weight: Decimal
    prior_cash_weight: Decimal
    cash_weight_change_pp: Decimal

    current_invested_weight: Decimal
    prior_invested_weight: Decimal
    invested_weight_change_pp: Decimal

    comparability_status: str
    compared_at: datetime
