"""
Sector Shock Simulation Pydantic v2 Schemas (M10.04).
Type-safe schemas for:
- Direct sector & industry shock definitions
- Spillover relationships (sector-to-sector, sector-to-factor)
- Scenario creation & versioning
- Execution requests & granular position/group/attribution outputs
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------------------
# Sector & Industry Shock Config
# -------------------------------------------------------------------------

class SectorShockGroupConfig(BaseModel):
    group_identifier: str = Field(..., description="Canonical sector or industry identifier, e.g. FINANCIALS, TECHNOLOGY, SOFTWARE")
    group_type: str = Field("SECTOR", description="SECTOR, INDUSTRY_GROUP, INDUSTRY, SUB_INDUSTRY")
    classification_system: str = Field("GICS", description="GICS, ICB, NIC")
    classification_version: str = Field("2026.1", description="Classification release version")
    shock_method: str = Field("PERCENTAGE", description="PERCENTAGE, TARGET_LEVEL, POINT_CHANGE")
    shock_value: Decimal = Field(..., description="Return shock e.g. -0.25 for -25%")
    shock_unit: str = Field("RATIO", description="RATIO, PERCENTAGE, POINTS")
    baseline_index_reference: Optional[str] = None
    shock_priority: int = Field(1, ge=1)
    application_method: str = Field("UNIFORM", description="UNIFORM, SENSITIVITY_ADJUSTED, ANALYST_EXPLICIT")

    model_config = ConfigDict(from_attributes=True)


class SpilloverRelationshipConfig(BaseModel):
    relationship_code: str = Field(..., min_length=3, max_length=64)
    source_type: str = Field("SECTOR", description="SECTOR, INDUSTRY")
    source_identifier: str = Field(..., description="e.g. FINANCIALS, ENERGY")
    target_type: str = Field("SECTOR", description="SECTOR, INDUSTRY, FACTOR")
    target_identifier: str = Field(..., description="e.g. REAL_ESTATE, INDUSTRIALS, VALUE_FACTOR")
    relationship_method: str = Field("ANALYST_DEFINED", description="ANALYST_DEFINED, CORRELATION_INFORMED, REGRESSION_BETA, FACTOR_SENSITIVITY")
    spillover_coefficient: Decimal = Field(..., description="Transmission coefficient e.g. 0.30")
    direction: str = Field("DIRECTED", description="DIRECTED, BIDIRECTIONAL")
    calibration_source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Scenario Management Schemas
# -------------------------------------------------------------------------

class SectorShockScenarioCreate(BaseModel):
    scenario_code: str = Field(..., min_length=3, max_length=64)
    scenario_name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    category: str = Field("CONCENTRATED_SECTOR", description="CONCENTRATED_SECTOR, INDUSTRY_DISLOCATION, MULTI_SECTOR_CASCADE, CROSS_SECTOR_CONTAGION")
    portfolio_id: Optional[str] = None
    visibility: str = Field("PRIVATE", description="PRIVATE, TEAM, ORGANIZATION")
    author_id: Optional[str] = None
    owner_id: Optional[str] = None

    group_shocks: List[SectorShockGroupConfig] = Field(..., min_length=1)
    spillover_relationships: Optional[List[SpilloverRelationshipConfig]] = None

    model_config = ConfigDict(from_attributes=True)


class SectorShockScenarioResponse(BaseModel):
    id: str
    scenario_code: str
    scenario_name: str
    description: Optional[str]
    category: str
    portfolio_id: Optional[str]
    visibility: str
    author_id: Optional[str]
    owner_id: Optional[str]
    current_version: int
    status: str
    created_at: datetime
    updated_at: datetime

    group_shocks: Optional[List[SectorShockGroupConfig]] = None
    spillover_relationships: Optional[List[SpilloverRelationshipConfig]] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Execution Request & Output Schemas
# -------------------------------------------------------------------------

class SectorPositionInput(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    signed_quantity: Decimal = Field(..., description="Positive for long, negative for short")
    baseline_price: Decimal = Field(..., gt=0)
    currency: str = Field("USD", description="Currency of instrument")
    sector: Optional[str] = None
    industry: Optional[str] = None
    sector_sensitivity: Optional[Decimal] = Field(None, description="beta_{i,s} to sector index")
    factor_betas: Optional[Dict[str, Decimal]] = Field(None, description="{factor_id: beta_{i,k}}")
    manual_adjustment: Optional[Decimal] = Field(None, description="Direct analyst return adjustment")
    fx_return: Optional[Decimal] = Field(Decimal("0"), description="Simulated FX return against portfolio base currency")

    model_config = ConfigDict(from_attributes=True)


class SectorSimulationExecutionRequest(BaseModel):
    scenario_name: str
    portfolio_id: str
    portfolio_snapshot_id: Optional[str] = None
    scenario_id: Optional[str] = None
    base_currency: str = Field("USD", description="Portfolio base currency")
    baseline_nav: Decimal = Field(..., gt=0, description="Authoritative portfolio baseline NAV")
    conflict_resolution_policy: str = Field("MOST_SPECIFIC_WINS", description="MOST_SPECIFIC_WINS, REJECT_CONFLICT, DIRECT_SHOCK_WINS, ADDITIVE_INCREMENTAL")
    composition_policy: str = Field("ADDITIVE", description="ADDITIVE, COMPOUND")
    missing_data_policy: str = Field("STRICT", description="STRICT, PARTIAL, EXCLUDE_UNSUPPORTED")

    group_shocks: List[SectorShockGroupConfig] = Field(..., min_length=1)
    spillover_relationships: Optional[List[SpilloverRelationshipConfig]] = None
    positions: List[SectorPositionInput] = Field(..., min_length=1)

    model_config = ConfigDict(from_attributes=True)


class SectorPositionResultResponse(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: str
    signed_quantity: Decimal
    baseline_price: Decimal
    scenario_price: Decimal
    baseline_market_value: Decimal
    scenario_market_value: Decimal
    direct_sector_return: Decimal
    industry_return: Decimal
    sensitivity_adjustment: Decimal
    spillover_adjustment: Decimal
    factor_adjustment: Decimal
    manual_adjustment: Decimal
    final_scenario_return: Decimal
    scenario_pnl: Decimal
    scenario_loss: Decimal
    portfolio_contribution: Decimal
    mapping_status: str
    classification_status: str

    model_config = ConfigDict(from_attributes=True)


class SectorGroupResultResponse(BaseModel):
    group_type: str
    group_identifier: str
    baseline_exposure: Decimal
    direct_shock: Decimal
    spillover_shock: Decimal
    total_scenario_return: Decimal
    scenario_pnl: Decimal
    scenario_loss: Decimal
    portfolio_contribution: Decimal
    position_count: int
    classification_coverage: Decimal

    model_config = ConfigDict(from_attributes=True)


class SectorAttributionResultResponse(BaseModel):
    attribution_type: str
    attribution_identifier: str
    direct_impact: Decimal
    spillover_impact: Decimal
    factor_impact: Decimal
    manual_impact: Decimal
    total_impact: Decimal
    contribution_percentage: Decimal
    reconciliation_residual: Decimal

    model_config = ConfigDict(from_attributes=True)


class SectorWarningResponse(BaseModel):
    warning_code: str
    severity: str
    category: str
    message: str
    instrument_id: Optional[str] = None
    group_identifier: Optional[str] = None
    details_json: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class SectorSimulationSummaryResponse(BaseModel):
    simulation_id: str
    simulation_code: str
    scenario_id: Optional[str] = None
    portfolio_id: str
    base_currency: str
    run_status: str
    baseline_nav: Decimal
    scenario_nav: Decimal
    scenario_pnl: Decimal
    scenario_loss: Decimal
    scenario_return: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    direct_exposure_coverage: Decimal
    spillover_exposure_coverage: Decimal
    classification_coverage: Decimal
    sensitivity_coverage: Decimal
    affected_positions: int
    started_at: datetime
    completed_at: Optional[datetime] = None

    position_results: Optional[List[SectorPositionResultResponse]] = None
    group_results: Optional[List[SectorGroupResultResponse]] = None
    attribution_results: Optional[List[SectorAttributionResultResponse]] = None
    warnings: Optional[List[SectorWarningResponse]] = None

    model_config = ConfigDict(from_attributes=True)
