"""
M07.09 Risk Contribution Pydantic Schemas.
Request and response models for risk decomposition, holding breakdown,
group attribution, Euler reconciliation, and what-if scenario perturbation.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.market_risk.risk_contribution.models import (
    RiskContributionStatus,
    ReconciliationStatus,
    WeightBasis,
    GroupingDimension,
)


class RiskContributionCalculateRequest(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio identifier")
    as_of_date: Optional[date] = Field(None, description="Observation as-of date (default latest)")
    weight_basis: WeightBasis = Field(WeightBasis.MARKET_VALUE, description="Weighting denominator basis")
    annualization_factor: Decimal = Field(Decimal("252.0"), description="Annualization factor for volatility")
    lookback_days: int = Field(252, ge=20, le=1260, description="Covariance lookback window in calendar days")
    verify_finite_difference: bool = Field(True, description="Verify MRC with central finite difference")
    custom_weights: Optional[Dict[str, Decimal]] = Field(
        None, description="Optional override weights by instrument_id"
    )
    model_config = ConfigDict(from_attributes=True)


class HoldingContributionItem(BaseModel):
    instrument_id: str
    symbol: str
    market_value: Decimal
    portfolio_weight: Decimal
    standalone_volatility: Decimal
    marginal_risk_contribution: Decimal
    marginal_variance_contribution: Decimal
    component_risk_contribution: Decimal
    component_variance_contribution: Decimal
    percentage_risk_contribution: Decimal
    percentage_variance_contribution: Decimal
    correlation_with_portfolio: Optional[Decimal] = None
    finite_difference_mrc: Optional[Decimal] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    geography: Optional[str] = None
    strategy_sleeve: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class GroupContributionItem(BaseModel):
    dimension: GroupingDimension
    group_name: str
    holding_count: int
    total_market_value: Decimal
    total_weight: Decimal
    component_risk_contribution: Decimal
    component_variance_contribution: Decimal
    percentage_risk_contribution: Decimal
    percentage_variance_contribution: Decimal
    model_config = ConfigDict(from_attributes=True)


class ReconciliationDetails(BaseModel):
    reconciliation_status: ReconciliationStatus
    portfolio_variance: Decimal
    sum_component_variance: Decimal
    variance_residual: Decimal
    portfolio_volatility: Decimal
    sum_component_volatility: Decimal
    volatility_residual: Decimal
    relative_residual: Decimal
    finite_difference_max_error: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True)


class RiskContributionResponse(BaseModel):
    calculation_id: str
    portfolio_id: str
    as_of_date: date
    calculated_at: datetime
    weight_basis: WeightBasis
    covariance_matrix_id: Optional[str] = None
    covariance_estimator: str
    annualization_factor: Decimal
    num_assets: int

    # Portfolio Totals
    portfolio_total_value: Decimal
    portfolio_gross_exposure: Decimal
    portfolio_net_exposure: Decimal
    portfolio_variance: Decimal
    portfolio_volatility: Decimal
    annualized_portfolio_volatility: Decimal

    # Euler Reconciliation
    reconciliation: ReconciliationDetails

    # Holdings breakdown
    holdings: List[HoldingContributionItem]

    # Group breakdown (if requested / computed)
    groups: Optional[List[GroupContributionItem]] = None

    status: RiskContributionStatus
    calculation_lineage: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)


class GroupBreakdownResponse(BaseModel):
    calculation_id: str
    portfolio_id: str
    as_of_date: date
    dimension: GroupingDimension
    groups: List[GroupContributionItem]
    sum_group_risk_contribution: Decimal
    portfolio_volatility: Decimal
    discrepancy: Decimal
    model_config = ConfigDict(from_attributes=True)


class ScenarioPerturbationRequest(BaseModel):
    portfolio_id: str
    as_of_date: Optional[date] = None
    weight_deltas: Dict[str, Decimal] = Field(
        ..., description="Proposed weight delta per instrument_id (+0.05, -0.02, etc.)"
    )
    model_config = ConfigDict(from_attributes=True)


class ScenarioPerturbationResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    base_volatility: Decimal
    perturbed_volatility: Decimal
    exact_delta_volatility: Decimal
    taylor_predicted_delta_volatility: Decimal
    taylor_approximation_error: Decimal
    instrument_impacts: List[Dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)
