"""
Pydantic schemas for M10.08 Scenario Comparison.
Conforms to Pydantic v2.0 conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ScenarioMemberCreate(BaseModel):
    scenario_id: str
    scenario_run_id: str
    scenario_type: str
    scenario_name: str
    scenario_version: int = 1
    scenario_configuration_hash: Optional[str] = None
    display_order: int = 0


class ScenarioMemberResponse(ScenarioMemberCreate):
    id: str
    comparison_id: str
    inclusion_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComparisonCreate(BaseModel):
    comparison_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    portfolio_id: str
    baseline_snapshot_id: Optional[str] = None
    base_currency: str = "USD"
    ranking_metric: str = "loss_amount"
    ranking_direction: str = "DESCENDING"
    normalization_method: str = "MIN_MAX"
    weights_json: Optional[Dict[str, float]] = None
    initial_members: Optional[List[ScenarioMemberCreate]] = None


class ComparisonUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ranking_metric: Optional[str] = None
    ranking_direction: Optional[str] = None
    normalization_method: Optional[str] = None
    weights_json: Optional[Dict[str, float]] = None
    is_active: Optional[bool] = None


class ComparisonResponse(BaseModel):
    id: str
    comparison_code: str
    name: str
    description: Optional[str] = None
    portfolio_id: str
    baseline_snapshot_id: Optional[str] = None
    base_currency: str
    comparison_status: str
    configuration_version: int
    ranking_metric: str
    ranking_direction: str
    normalization_method: str
    weights_json: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    members: List[ScenarioMemberResponse] = []

    model_config = ConfigDict(from_attributes=True)


class MetricResultResponse(BaseModel):
    scenario_run_id: str
    scenario_name: str
    scenario_type: str
    baseline_nav: Decimal
    scenario_nav: Decimal
    pnl: Decimal
    return_pct: Decimal
    loss_amount: Decimal
    loss_pct: Decimal
    var_95_amount: Optional[Decimal] = None
    cvar_95_amount: Optional[Decimal] = None
    max_drawdown_pct: Optional[Decimal] = None
    liquidity_cost_amount: Optional[Decimal] = None
    quality_status: str
    currency: str

    model_config = ConfigDict(from_attributes=True)


class RankingResponse(BaseModel):
    scenario_run_id: str
    scenario_name: str
    ranking_metric: str
    ranking_direction: str
    rank_position: int
    raw_metric_value: Decimal
    normalized_score: float
    composite_score: Optional[float] = None
    tie_group: int
    eligibility_status: str
    exclusion_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SensitivityResponse(BaseModel):
    parameter_code: str
    parameter_name: str
    scenario_a_run_id: str
    scenario_b_run_id: str
    scenario_a_value: Optional[str] = None
    scenario_b_value: Optional[str] = None
    absolute_difference: Optional[float] = None
    relative_difference: Optional[float] = None
    sensitivity_method: str
    is_material: bool

    model_config = ConfigDict(from_attributes=True)


class AttributionResponse(BaseModel):
    scenario_a_run_id: str
    scenario_b_run_id: str
    attribution_dimension: str
    component_reference: str
    scenario_a_value: Decimal
    scenario_b_value: Decimal
    difference_value: Decimal
    reconciliation_residual: Decimal

    model_config = ConfigDict(from_attributes=True)


class ComparisonExecutionRequest(BaseModel):
    baseline_nav_override: Optional[Decimal] = None
    ranking_metric_override: Optional[str] = None
    ranking_direction_override: Optional[str] = None
    sensitivity_pairs: Optional[List[List[str]]] = None # List of [scenario_a_run_id, scenario_b_run_id]
    attribution_pairs: Optional[List[List[str]]] = None


class ComparisonRunResponse(BaseModel):
    id: str
    comparison_id: str
    run_code: str
    configuration_version: int
    baseline_snapshot_id: str
    execution_status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int
    application_version: str
    calculation_engine_version: str
    validation_summary: Dict[str, Any]
    metric_results: List[MetricResultResponse] = []
    rankings: List[RankingResponse] = []
    sensitivities: List[SensitivityResponse] = []
    attributions: List[AttributionResponse] = []
    narrative: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

