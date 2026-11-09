"""
M10.05 Correlation Shock Pydantic Schemas.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

from backend.app.modules.scenario_analysis.correlation_shock.models import (
    ScenarioScope,
    ScenarioCategory,
    ScenarioStatus,
    VolatilityMode,
    ExecutionStatus,
)
from backend.app.modules.scenario_analysis.correlation_shock.calculations import (
    MatrixValidationStatus,
    MatrixRepairMethod,
    CorrelationTransformationMethod,
)


class PairRuleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_a_id: str = Field(..., description="First asset or factor identifier")
    entity_b_id: str = Field(..., description="Second asset or factor identifier")
    entity_type: str = Field("INSTRUMENT", description="INSTRUMENT or FACTOR")
    baseline_correlation: Optional[float] = Field(None, ge=-1.0, le=1.0)
    target_correlation: Optional[float] = Field(None, ge=-1.0, le=1.0)
    stress_intensity: float = Field(1.0, ge=0.0, le=1.0)
    transformation_method: CorrelationTransformationMethod = CorrelationTransformationMethod.CUSTOM_TARGET


class PairRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_version_id: str
    entity_a_id: str
    entity_b_id: str
    entity_type: str
    baseline_correlation: Optional[float] = None
    target_correlation: Optional[float] = None
    stress_intensity: float
    transformation_method: str
    resulting_correlation: Optional[float] = None


class ScopeMemberCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope_type: str = Field(..., description="INSTRUMENT, SECTOR, INDUSTRY, or FACTOR")
    instrument_id: Optional[str] = None
    factor_id: Optional[str] = None
    group_id: Optional[str] = None
    membership_source: Optional[str] = "M04.02"


class ScopeMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_version_id: str
    scope_type: str
    instrument_id: Optional[str] = None
    factor_id: Optional[str] = None
    group_id: Optional[str] = None
    effective_at: datetime


class CorrelationShockScenarioCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    scenario_scope: ScenarioScope = ScenarioScope.FULL_PORTFOLIO
    portfolio_id: Optional[str] = None
    scenario_category: ScenarioCategory = ScenarioCategory.HYPOTHETICAL
    transformation_method: CorrelationTransformationMethod = CorrelationTransformationMethod.CONVERGENCE_TO_ONE
    stress_target: Optional[float] = Field(None, ge=-1.0, le=1.0)
    stress_intensity: float = Field(0.5, ge=0.0, le=1.0)
    volatility_mode: VolatilityMode = VolatilityMode.HOLD_CONSTANT
    matrix_repair_method: MatrixRepairMethod = MatrixRepairMethod.EIGENVALUE_CLIPPING
    repair_parameters: Optional[Dict[str, Any]] = None
    scope_members: Optional[List[ScopeMemberCreate]] = None
    pair_rules: Optional[List[PairRuleCreate]] = None
    created_by: Optional[str] = "analyst"


class CorrelationShockScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_code: str
    name: str
    description: Optional[str] = None
    scenario_scope: ScenarioScope
    portfolio_id: Optional[str] = None
    scenario_category: ScenarioCategory
    status: ScenarioStatus
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    latest_version_number: int = 1


class MatrixValidateRequest(BaseModel):
    matrix_data: List[List[float]] = Field(..., description="N x N correlation matrix")
    asset_ids: Optional[List[str]] = None
    symmetry_tol: float = 1e-6
    psd_tol: float = 1e-7


class MatrixValidateResponse(BaseModel):
    status: MatrixValidationStatus
    is_symmetric: bool
    diagonal_valid: bool
    bounds_valid: bool
    is_psd: bool
    minimum_eigenvalue: float
    maximum_eigenvalue: float
    matrix_rank: int
    condition_number: Optional[float] = None
    negative_eigenvalue_count: int
    warnings: List[str] = []


class ExecuteScenarioRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: Optional[str] = None
    portfolio_snapshot_id: Optional[str] = None
    baseline_matrix_id: Optional[str] = None
    executed_by: Optional[str] = "analyst"

    # Optional custom inputs if executing against ad-hoc holding/matrix snapshot
    custom_weights: Optional[Dict[str, float]] = None  # {asset_id: weight}
    custom_volatilities: Optional[Dict[str, float]] = None  # {asset_id: vol}
    custom_matrix_data: Optional[List[List[float]]] = None
    custom_asset_ids: Optional[List[str]] = None
    custom_asset_symbols: Optional[List[str]] = None


class RiskContributionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_id: str
    symbol: str
    weight: float
    standalone_volatility: float
    baseline_contribution: Optional[float] = None
    stressed_contribution: Optional[float] = None
    absolute_change: Optional[float] = None
    percentage_change: Optional[float] = None
    baseline_contribution_share: Optional[float] = None
    stressed_contribution_share: Optional[float] = None


class RiskResultSummary(BaseModel):
    baseline_volatility: float
    stressed_volatility: float
    absolute_volatility_change: float
    percentage_volatility_change: float
    baseline_variance: float
    stressed_variance: float
    absolute_variance_change: float
    percentage_variance_change: float
    baseline_average_correlation: float
    stressed_average_correlation: float
    average_correlation_change: float
    baseline_diversification_benefit: float
    stressed_diversification_benefit: float
    diversification_benefit_change: float
    baseline_diversification_ratio: Optional[float] = None
    stressed_diversification_ratio: Optional[float] = None
    top_contributor: Optional[str] = None
    narrative: str


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: str
    execution_code: str
    scenario_id: str
    version_number: int
    portfolio_id: Optional[str] = None
    execution_status: ExecutionStatus
    execution_duration_ms: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Matrices
    asset_ids: List[str] = []
    asset_symbols: List[str] = []
    baseline_matrix: Optional[List[List[float]]] = None
    stressed_matrix: Optional[List[List[float]]] = None
    repaired_matrix: Optional[List[List[float]]] = None

    # Diagnostics & Repair Audit
    baseline_diagnostics: Optional[MatrixValidateResponse] = None
    stressed_diagnostics: Optional[MatrixValidateResponse] = None
    repaired_diagnostics: Optional[MatrixValidateResponse] = None
    repair_summary: Optional[Dict[str, Any]] = None

    # Risk Metrics & Comparisons
    risk_summary: Optional[RiskResultSummary] = None
    contributions: List[RiskContributionItem] = []
    error_message: Optional[str] = None
