"""
Pydantic schemas for M13.07 — Stress Testing Dashboard.

Provides robust institutional data contracts for:
1. Scenario library & selection metadata (historical, hypothetical, crash, sector, liquidity, MC)
2. Stressed portfolio results (baseline NAV, stressed NAV, stressed P&L, % return, position outcomes)
3. Monte Carlo loss distribution & quantiles (histogram, CDF, tail VaR/ES, diagnostics)
4. Scenario comparison (side-by-side impact table, assumption comparison, rankings)
5. Stress loss attribution (position, sector, industry, factor, residual reconciliation)
6. Preferences, Saved Views, and Scenario Annotation Workflows
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# 1. Scenario Library & Selection
# ---------------------------------------------------------------------------
class ScenarioMetadataItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    scenario_code: str
    scenario_name: str
    category: str  # HISTORICAL, HYPOTHETICAL, MARKET_CRASH, SECTOR_SHOCK, CORRELATION_SHOCK, LIQUIDITY_STRESS, MONTE_CARLO
    description: Optional[str] = None
    horizon_days: Optional[int] = None
    affected_markets: Optional[str] = "ALL"
    status: str = "ACTIVE"
    version: str = "1.0.0"
    created_at: datetime
    latest_calculation_id: Optional[str] = None
    latest_calculation_status: Optional[str] = None


class ScenarioDefinitionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    scenario_code: str
    scenario_name: str
    category: str
    description: Optional[str] = None
    event_start_date: Optional[datetime] = None
    event_end_date: Optional[datetime] = None
    affected_markets: Optional[str] = "ALL"
    primary_reference_index: Optional[str] = None
    shock_variables: Dict[str, Any] = Field(default_factory=dict)
    volatility_assumptions: Dict[str, Any] = Field(default_factory=dict)
    correlation_assumptions: Dict[str, Any] = Field(default_factory=dict)
    liquidity_assumptions: Dict[str, Any] = Field(default_factory=dict)
    model_configuration: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    created_by: str = "SYSTEM"
    created_at: datetime


# ---------------------------------------------------------------------------
# 2. Stressed Portfolio Results & Positions
# ---------------------------------------------------------------------------
class PositionStressResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    exchange: Optional[str] = None
    position_side: str = "LONG"
    quantity: Decimal
    baseline_price: Decimal
    stressed_price: Decimal
    baseline_market_value: Decimal
    stressed_market_value: Decimal
    stressed_pnl: Decimal
    percentage_change: Decimal
    contribution_to_loss_pct: Optional[Decimal] = None
    sector: Optional[str] = "Unclassified"
    quality_status: str = "VALID"


class ScenarioResultSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    scenario_name: str
    category: str
    calculation_id: str
    portfolio_id: str
    portfolio_snapshot_id: Optional[str] = None
    calculation_timestamp: datetime
    calculation_status: str = "COMPLETED"  # COMPLETED, PARTIAL, FAILED, RUNNING
    
    base_currency: str = "USD"
    baseline_nav: Decimal
    stressed_nav: Decimal
    stressed_pnl: Decimal
    return_percentage: Decimal
    
    # Expanded KPI & Attribution fields
    percentage_loss: Optional[Decimal] = None
    worst_performing_instrument: Optional[str] = None
    best_performing_instrument: Optional[str] = None
    number_of_affected_positions: Optional[int] = None
    top_sector_contributors: List[Dict[str, Any]] = Field(default_factory=list)
    long_loss_contribution: Optional[Decimal] = None
    short_loss_contribution: Optional[Decimal] = None
    data_coverage_status: Optional[str] = "FULL_COVERAGE"
    scenario_assumptions: Dict[str, Any] = Field(default_factory=dict)

    # Coverage metrics
    eligible_holdings: int
    excluded_holdings: int = 0
    coverage_percentage: Decimal = Decimal("100.0")
    quality_status: str = "VALID"
    model_version: str = "1.0.0"
    warnings: List[str] = Field(default_factory=list)


class ScenarioDetailResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: ScenarioResultSummary
    definition: ScenarioDefinitionDetail
    positions: List[PositionStressResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Monte Carlo Loss Distribution & Quantiles
# ---------------------------------------------------------------------------
class DistributionHistogramBin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bin_index: int
    lower_bound: Decimal
    upper_bound: Decimal
    count: int
    frequency_pct: Decimal


class MonteCarloDistributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    simulation_id: str
    scenario_id: str
    calculation_id: str
    portfolio_id: str
    scenario_name: Optional[str] = None
    horizon_days: int
    n_paths: int
    outcome_measure: str = "PORTFOLIO_PNL"  # PORTFOLIO_PNL, TERMINAL_NAV, RETURN_PCT
    currency: str = "USD"
    
    # Descriptive moments
    mean_pnl: Decimal
    median_pnl: Decimal
    std_pnl: Decimal
    skewness: float
    excess_kurtosis: float
    probability_of_loss: float
    min_pnl: Decimal
    max_pnl: Decimal
    
    # Quantiles (p01, p05, p10, p25, p50, p75, p90, p95, p99)
    quantiles: Dict[str, Decimal] = Field(default_factory=dict)
    
    # Downside tail risk measures (VaR & ES / CVaR)
    var_95_loss: Decimal
    cvar_95_loss: Decimal
    var_99_loss: Decimal
    cvar_99_loss: Decimal
    
    # Diagnostics & Histogram
    generator_algorithm: str = "PCG64"
    matrix_was_repaired: bool = False
    random_seed: int
    histogram_bins: List[DistributionHistogramBin] = Field(default_factory=list)
    simulation_paths: List[List[float]] = Field(default_factory=list)
    benchmark_path: List[float] = Field(default_factory=list)
    
    # Simulation Reliability & Quality Indicators
    valid_paths_count: Optional[int] = None
    rejected_paths_count: Optional[int] = 0
    standard_error: Optional[float] = None
    tail_confidence_interval: Dict[str, float] = Field(default_factory=dict)
    convergence_diagnostic: Optional[str] = "CONVERGED"
    var_es_coincidence_reason: Optional[str] = None
    dataset_version: Optional[str] = "v2.4.0"

    # Portfolio Visualizer percentile curves & analytics
    percentile_curves: Dict[str, List[float]] = Field(default_factory=dict)
    summary_metrics: Dict[str, Any] = Field(default_factory=dict)
    
    quality_status: str = "VALID"


# ---------------------------------------------------------------------------
# 7. Portfolio Visualizer Simulation Request Schema
# ---------------------------------------------------------------------------
class AssetAllocationItem(BaseModel):
    asset_id: str
    asset_name: str
    allocation_pct: float

class SimulationModelConfigRequest(BaseModel):
    portfolio_mode: str = "PORTFOLIO_RISK"  # PORTFOLIO_RISK (Institutional) or WEALTH_PROJECTION (Multi-Asset)
    portfolio_type: str = "Asset Classes"  # Asset Classes, Tickers
    portfolio_id: Optional[str] = "Global Equity Long/Short"
    position_selection: Optional[str] = "ALL_HOLDINGS"  # ALL_HOLDINGS, SELECTED_HOLDINGS
    benchmark: Optional[str] = "SPY"  # SPY, NIFTY 50, CUSTOM
    valuation_source: Optional[str] = "M05_VALUATION"
    holding_period_days: Optional[int] = 1  # 1, 5, 10, 20, 252 (trading days)
    lookback_period_days: Optional[int] = 252
    return_frequency: Optional[str] = "DAILY"  # DAILY, WEEKLY, MONTHLY
    random_seed: Optional[int] = 42
    confidence_level: Optional[float] = 0.95  # 0.95, 0.99
    
    # Risk assumptions
    volatility_model: Optional[str] = "STUDENT_T"  # HISTORICAL, PARAMETRIC, STUDENT_T, BOOTSTRAP
    correlation_assumption: Optional[str] = "HISTORICAL"  # HISTORICAL, STRESSED_CORRELATION
    factor_shock: Optional[str] = "NONE"
    liquidity_shock: Optional[str] = "STANDARD"
    transaction_cost_bps: Optional[float] = 5.0
    market_regime: Optional[str] = "STANDARD"

    initial_amount: float = 1000000.0
    cashflows: str = "Withdraw fixed amount periodically"  # None, Contribute, Withdraw
    withdrawal_amount: float = 45000.0
    inflation_adjusted: bool = True
    withdrawal_frequency: str = "Annually"  # Annually, Monthly
    simulation_period_years: int = 30
    tax_treatment: str = "Pre-tax Returns"
    simulation_model: str = "Historical Returns"  # Historical Returns, Parametric, Regime Switching
    use_full_history: bool = True
    bootstrap_model: str = "Single Year"  # Single Year, Block
    sequence_of_returns_risk: str = "No Adjustments"  # No Adjustments, Front-load Bad Years
    inflation_model: str = "Historical Inflation"
    rebalancing: str = "Rebalance annually"
    intervals: str = "Defaults"
    allocations: List[AssetAllocationItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 4. Scenario Comparison
# ---------------------------------------------------------------------------
class ScenarioComparisonItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    scenario_name: str
    category: str
    calculation_id: str
    baseline_nav: Decimal
    stressed_nav: Decimal
    stressed_pnl: Decimal
    return_percentage: Decimal
    loss_rank: int
    status: str
    assumptions_summary: Dict[str, Any] = Field(default_factory=dict)
    is_compatible: bool = True
    compatibility_warning: Optional[str] = None


class ScenarioComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of_date: datetime
    base_currency: str
    scenarios: List[ScenarioComparisonItem] = Field(default_factory=list)
    worst_scenario_name: Optional[str] = None
    best_scenario_name: Optional[str] = None
    max_loss_pnl: Optional[Decimal] = None
    max_loss_percentage: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# 5. Stress Loss Attribution
# ---------------------------------------------------------------------------
class ContributorItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension_name: str  # symbol, sector name, factor name
    dimension_type: str  # POSITION, SECTOR, INDUSTRY, FACTOR
    baseline_exposure: Decimal
    stressed_pnl: Decimal
    contribution_to_loss: Decimal
    contribution_percentage: Decimal  # Can be negative or > 100 if gains offset losses
    attribution_method: str = "EXACT_DECOMPOSITION"


class StressAttributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attribution_id: str
    calculation_id: str
    portfolio_id: str
    scenario_name: str
    scenario_type: str
    total_stressed_pnl: Decimal
    explained_pnl: Decimal
    residual_amount: Decimal = Decimal("0.0")
    is_reconciled: bool = True
    loss_hhi: float = 0.0
    effective_contributor_count: float = 0.0
    
    position_contributors: List[ContributorItem] = Field(default_factory=list)
    sector_contributors: List[ContributorItem] = Field(default_factory=list)
    factor_contributors: List[ContributorItem] = Field(default_factory=list)
    reconciliation_status: str = "RECONCILED"  # RECONCILED, RESIDUAL_EXISTS, UNRECONCILED
    quality_status: str = "VALID"


# ---------------------------------------------------------------------------
# 6. Preferences, Saved Views, and Scenario Annotation Schemas
# ---------------------------------------------------------------------------
class StressPreferenceCreateRequest(BaseModel):
    dashboard_name: Optional[str] = "Default Stress Testing Dashboard"
    default_portfolio_id: Optional[str] = None
    default_scenario_category: Optional[str] = "ALL"
    preferred_currency_display: Optional[str] = "BASE"
    default_comparison_limit: Optional[int] = 5
    default_quantile_selection: Optional[List[str]] = None
    display_configuration: Optional[Dict[str, Any]] = None


class StressPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    dashboard_name: str
    default_portfolio_id: Optional[str]
    default_scenario_category: str
    preferred_currency_display: str
    default_comparison_limit: int
    default_quantile_selection: List[str]
    display_configuration: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class StressSavedViewCreateRequest(BaseModel):
    view_name: str
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    selected_scenario_ids: List[str]
    selected_calculation_ids: Optional[List[str]] = None
    filter_configuration: Optional[Dict[str, Any]] = None
    display_configuration: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = False


class StressSavedViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    view_name: str
    description: Optional[str]
    portfolio_id: Optional[str]
    selected_scenario_ids: List[str]
    selected_calculation_ids: List[str]
    filter_configuration: Dict[str, Any]
    display_configuration: Dict[str, Any]
    is_public: bool
    created_at: datetime
    updated_at: datetime


class StressAnnotationCreateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    scenario_id: str
    calculation_id: Optional[str] = None
    annotation_type: Optional[str] = "INVESTIGATION"
    severity: Optional[str] = "MEDIUM"
    title: str
    notes: str
    metrics_snapshot: Optional[Dict[str, Any]] = None


class StressAnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    portfolio_id: Optional[str]
    scenario_id: str
    calculation_id: Optional[str]
    annotation_type: str
    severity: str
    status: str
    title: str
    notes: str
    metrics_snapshot: Optional[Dict[str, Any]]
    signoff_by: Optional[str]
    signoff_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
