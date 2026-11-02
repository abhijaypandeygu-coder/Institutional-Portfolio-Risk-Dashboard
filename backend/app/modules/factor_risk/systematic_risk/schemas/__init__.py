"""
Pydantic v2 Schemas for M08.05 Systematic Risk Analytics.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.systematic_risk.models import (
    CovarianceMethod,
    SystematicTargetType,
    SystematicRunStatus,
    ModelCoverageStatus,
    CoverageTier,
    ScenarioType,
    ShockUnit,
)
from backend.app.modules.factor_risk.factor_definition.models import FactorLifecycleStatus


# ============================================================================
# 1. RISK CONFIGURATION SCHEMAS
# ============================================================================

class CreateRiskConfigRequest(BaseModel):
    config_code: str = Field(..., max_length=64)
    config_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    covariance_method: CovarianceMethod = CovarianceMethod.SAMPLE
    observation_frequency: str = "DAILY"
    annualization_factor: Decimal = Decimal("252.00")
    decay_factor: Optional[Decimal] = Decimal("0.94")
    minimum_observations: int = 20
    coverage_threshold_pct: Decimal = Decimal("80.00")
    currency_basis: str = "INR"


class FactorRiskConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    config_code: str
    config_name: str
    description: Optional[str]
    factor_model_id: str
    factor_model_version_id: str
    covariance_method: CovarianceMethod
    observation_frequency: str
    annualization_factor: Decimal
    decay_factor: Optional[Decimal]
    minimum_observations: int
    coverage_threshold_pct: Decimal
    currency_basis: str
    config_hash: str
    status: FactorLifecycleStatus
    created_at: datetime


# ============================================================================
# 2. FACTOR COVARIANCE SCHEMAS
# ============================================================================

class EstimateFactorCovarianceRequest(BaseModel):
    factor_model_version_id: str
    as_of_date: date
    lookback_days: int = 252
    covariance_method: CovarianceMethod = CovarianceMethod.SAMPLE
    decay_factor: Optional[Decimal] = Decimal("0.94")
    annualization_factor: Decimal = Decimal("252.00")


class FactorCovarianceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    factor_model_id: str
    factor_model_version_id: str
    covariance_method: CovarianceMethod
    observation_frequency: str
    estimation_window_start: date
    estimation_window_end: date
    observation_count: int
    effective_sample_size: Decimal
    annualization_factor: Decimal
    factor_names_ordered: List[str]
    covariance_matrix: List[List[float]]
    correlation_matrix: Optional[List[List[float]]]
    is_positive_semidefinite: bool
    min_eigenvalue: Decimal
    max_eigenvalue: Decimal
    condition_number: Decimal
    matrix_rank: int
    result_hash: str
    created_at: datetime


# ============================================================================
# 3. INSTRUMENT & PORTFOLIO SYSTEMATIC RISK SCHEMAS
# ============================================================================

class RunInstrumentSystematicRiskRequest(BaseModel):
    instrument_id: str
    config_id: str
    as_of_date: date
    listing_id: Optional[str] = None
    lookback_days: int = 252


class InstrumentSystematicRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    instrument_id: str
    listing_id: Optional[str]
    factor_loadings: Dict[str, float]
    systematic_variance_period: Decimal
    systematic_volatility_period: Decimal
    systematic_variance_annualized: Decimal
    systematic_volatility_annualized: Decimal
    residual_variance_annualized: Optional[Decimal]
    total_modeled_variance_annualized: Optional[Decimal]
    total_modeled_volatility_annualized: Optional[Decimal]
    systematic_variance_share: Optional[Decimal]
    model_coverage_status: ModelCoverageStatus
    created_at: datetime


class RunPortfolioSystematicRiskRequest(BaseModel):
    portfolio_id: str
    config_id: str
    as_of_date: date
    portfolio_snapshot_id: Optional[str] = None
    lookback_days: int = 252


class PortfolioSystematicRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    portfolio_id: str
    portfolio_snapshot_id: Optional[str]
    portfolio_betas: Dict[str, float]
    systematic_variance_period: Decimal
    systematic_volatility_period: Decimal
    systematic_variance_annualized: Decimal
    systematic_volatility_annualized: Decimal
    cross_security_variance_discrepancy: Decimal
    is_cross_security_reconciled: bool
    residual_variance_annualized: Optional[Decimal]
    total_modeled_variance_annualized: Optional[Decimal]
    total_modeled_volatility_annualized: Optional[Decimal]
    systematic_variance_share: Optional[Decimal]
    total_absolute_market_value: Decimal
    covered_absolute_market_value: Decimal
    uncovered_absolute_market_value: Decimal
    coverage_percentage: Decimal
    coverage_tier: CoverageTier
    total_holding_count: int
    covered_holding_count: int
    uncovered_holding_count: int
    factor_coverage_percentages: Dict[str, float]
    created_at: datetime


# ============================================================================
# 4. SCENARIO SENSITIVITY SCHEMAS
# ============================================================================

class FactorScenarioShockItem(BaseModel):
    factor_code: str
    shock_value: Decimal
    shock_unit: ShockUnit = ShockUnit.PERCENTAGE
    standard_deviation_multiple: Optional[Decimal] = None


class CreateFactorScenarioRequest(BaseModel):
    scenario_code: str = Field(..., max_length=64)
    scenario_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    scenario_type: ScenarioType = ScenarioType.MULTI_FACTOR
    shock_unit: ShockUnit = ShockUnit.PERCENTAGE
    shocks: List[FactorScenarioShockItem]


class FactorScenarioConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    scenario_code: str
    scenario_name: str
    description: Optional[str]
    factor_model_id: str
    factor_model_version_id: str
    scenario_type: ScenarioType
    shock_unit: ShockUnit
    status: FactorLifecycleStatus
    created_at: datetime


class RunFactorScenarioRequest(BaseModel):
    scenario_id: Optional[str] = None
    factor_model_version_id: Optional[str] = None
    target_type: SystematicTargetType = SystematicTargetType.PORTFOLIO
    target_id: str
    as_of_date: date
    custom_shocks: Optional[Dict[str, Decimal]] = None
    portfolio_nav: Optional[Decimal] = None
    currency: str = "INR"


class FactorScenarioComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_code: str
    factor_shock: Decimal
    factor_exposure: Decimal
    estimated_return_contribution: Decimal
    estimated_monetary_contribution: Optional[Decimal]


class FactorScenarioRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    scenario_id: str
    target_type: SystematicTargetType
    target_id: str
    percentage_impact: Decimal
    monetary_impact: Optional[Decimal]
    currency: str
    model_limitation_warning: bool
    coverage_percentage: Decimal
    calculation_timestamp: datetime
    components: List[FactorScenarioComponentResponse]


# ============================================================================
# 5. MODEL COVERAGE SCHEMAS
# ============================================================================

class ModelCoverageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    instrument_id: str
    coverage_status: ModelCoverageStatus
    signed_market_value: Decimal
    absolute_market_value: Decimal
    absolute_weight_pct: Decimal
    missing_factor_codes: Optional[List[str]]
    reason_description: Optional[str]
    as_of_date: date


class PortfolioCoverageSummaryResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    portfolio_coverage_percentage: Decimal
    coverage_tier: CoverageTier
    total_absolute_market_value: Decimal
    covered_absolute_market_value: Decimal
    uncovered_absolute_market_value: Decimal
    total_holding_count: int
    covered_holding_count: int
    uncovered_holding_count: int
    factor_coverage_percentages: Dict[str, float]
    holdings: List[ModelCoverageRecordResponse]

