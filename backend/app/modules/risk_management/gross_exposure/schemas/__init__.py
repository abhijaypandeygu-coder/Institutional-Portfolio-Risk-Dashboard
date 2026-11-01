"""
M06.01 Gross Exposure Schemas.
Pydantic contracts for exposure requests, calculation runs, line-item contributions,
ratios, breakdowns, and threshold alerts.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.modules.risk_management.gross_exposure.models import (
    DenominatorType,
    ExposureCalculationScope,
    ExposureRunStatus,
    RatioStatus,
    ThresholdStatus,
)


class ExposureContributionResponse(BaseModel):
    id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    position_side: str
    signed_quantity: Decimal
    signed_market_value: Decimal
    absolute_exposure_contribution: Decimal
    native_currency: str
    reporting_currency: str
    converted_exposure_contribution: Decimal
    position_snapshot_reference: Optional[str] = None
    valuation_snapshot_reference: Optional[str] = None
    eligibility_status: str
    exclusion_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class ExposureBreakdownResponse(BaseModel):
    id: str
    breakdown_type: str
    breakdown_reference: str
    long_exposure: Decimal
    short_exposure: Decimal
    gross_exposure: Decimal
    contribution_percentage: Decimal
    reporting_currency: str

    model_config = {"from_attributes": True}


class ExposureThresholdEventResponse(BaseModel):
    id: str
    threshold_type: str
    threshold_value: Decimal
    observed_value: Decimal
    status: str
    policy_version: str
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class ExposureResultResponse(BaseModel):
    id: str
    calculation_run_id: str
    portfolio_id: Optional[str] = None
    group_id: Optional[str] = None
    reporting_currency: str
    long_exposure: Decimal
    short_exposure: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    denominator_value: Optional[Decimal] = None
    denominator_currency: Optional[str] = None
    denominator_type: str
    denominator_timestamp: Optional[datetime] = None
    gross_exposure_ratio: Optional[Decimal] = None
    exposure_ratio_percentage: Optional[Decimal] = None
    ratio_status: str
    completeness_status: str
    eligible_position_count: int
    excluded_position_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExposureCalculationExecuteRequest(BaseModel):
    as_of: Optional[datetime] = None
    knowledge_as_of: Optional[datetime] = None
    reporting_currency: Optional[str] = None
    denominator_type: DenominatorType = DenominatorType.NAV
    custom_denominator_value: Optional[Decimal] = None  # Allows passing explicit approved capital if NAV uncomputed
    fx_rates_to_reporting: Dict[str, Decimal] = Field(default_factory=dict)
    include_breakdowns: bool = True
    include_contributors: bool = True


class GrossExposureSummaryResponse(BaseModel):
    scope: str
    entity_id: str
    reporting_currency: str
    as_of: datetime
    knowledge_as_of: datetime
    long_exposure: Decimal
    short_exposure: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    denominator_type: str
    denominator_value: Optional[Decimal] = None
    gross_exposure_ratio: Optional[Decimal] = None
    exposure_ratio_percentage: Optional[Decimal] = None
    ratio_status: str
    completeness_status: str
    eligible_position_count: int
    excluded_position_count: int
    threshold_status: str
    breakdowns: List[ExposureBreakdownResponse] = Field(default_factory=list)
    contributions: List[ExposureContributionResponse] = Field(default_factory=list)
    threshold_events: List[ExposureThresholdEventResponse] = Field(default_factory=list)
    ratio_explanation: str

