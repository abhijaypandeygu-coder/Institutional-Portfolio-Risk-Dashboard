"""
M06.02 Net Exposure Pydantic Schemas.
Data transfer objects and request/response models for net exposure calculations,
directional classifications, and lineage tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.risk_management.net_exposure.models import (
    DirectionalState,
    NeutralityThresholdType,
    NetDenominatorType,
    NetExposureScope,
    NetRunStatus,
    NetRatioStatus,
    NetThresholdStatus,
)


class NetExposureCalculateRequest(BaseModel):
    as_of: Optional[datetime] = None
    knowledge_as_of: Optional[datetime] = None
    reporting_currency: Optional[str] = Field("USD", description="ISO 4217 Currency Code")
    denominator_type: NetDenominatorType = NetDenominatorType.NAV
    custom_denominator_value: Optional[Decimal] = Field(None, description="Explicitly configured capital or NAV denominator")
    neutrality_threshold_type: Optional[NeutralityThresholdType] = NeutralityThresholdType.RELATIVE
    absolute_neutrality_threshold: Optional[Decimal] = Field(None, description="Monetary neutrality cutoff")
    relative_neutrality_threshold: Optional[Decimal] = Field(Decimal("0.020000"), description="Relative percentage cutoff (e.g. 0.02 = 2%)")
    combined_semantics: Optional[str] = Field("AND", description="AND or OR for combined thresholds")
    fx_rates_to_reporting: Optional[Dict[str, Decimal]] = Field(default_factory=dict, description="Currency -> FX multiplier to reporting currency")
    idempotency_key: Optional[str] = None


class NetExposureContributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    position_side: str
    signed_quantity: Decimal
    signed_market_value_native: Decimal
    native_currency: str
    fx_rate_reference: Decimal
    converted_signed_market_value: Decimal
    reporting_currency: str
    position_snapshot_reference: Optional[str] = None
    valuation_snapshot_reference: Optional[str] = None
    eligibility_status: str
    exclusion_reason: Optional[str] = None


class NetExposureBreakdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    breakdown_type: str
    breakdown_reference: str
    long_exposure: Decimal
    absolute_short_exposure: Decimal
    net_exposure: Decimal
    reporting_currency: str
    contribution_percentage: Optional[Decimal] = None
    directional_classification: str


class DirectionalThresholdEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    threshold_type: str
    threshold_value: Decimal
    observed_net_exposure: Decimal
    observed_net_exposure_ratio: Optional[Decimal] = None
    event_level: str
    classification: str
    evaluated_at: datetime


class NetExposureSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    portfolio_id: Optional[str] = None
    group_id: Optional[str] = None
    scope: str
    reporting_currency: str
    
    # Financial Aggregations
    long_exposure: Decimal
    absolute_short_exposure: Decimal
    net_market_value: Decimal
    gross_exposure_reference: Optional[Decimal] = None
    
    # Denominator & Ratios
    denominator_type: str
    denominator_value: Optional[Decimal] = None
    net_exposure_ratio: Optional[Decimal] = None
    net_exposure_ratio_percentage: Optional[Decimal] = None
    ratio_status: str
    ratio_explanation: Optional[str] = None
    
    # Directional Classification & Neutrality
    directional_classification: str
    neutrality_threshold_type: str
    neutrality_threshold_applied: str
    threshold_status: str
    
    # Lineage and breakdowns
    completeness_status: str
    eligible_position_count: int
    excluded_position_count: int
    contributions: List[NetExposureContributionResponse] = []
    breakdowns: List[NetExposureBreakdownResponse] = []
    threshold_events: List[DirectionalThresholdEventResponse] = []


class NetExposurePolicyCreateRequest(BaseModel):
    policy_name: str
    portfolio_id: Optional[str] = None
    group_id: Optional[str] = None
    reporting_currency: str = "USD"
    denominator_type: NetDenominatorType = NetDenominatorType.NAV
    neutrality_threshold_type: NeutralityThresholdType = NeutralityThresholdType.RELATIVE
    absolute_neutrality_threshold: Optional[Decimal] = None
    relative_neutrality_threshold: Optional[Decimal] = Decimal("0.020000")
    combined_threshold_semantics: str = "AND"
    max_net_long_ratio: Optional[Decimal] = None
    max_net_short_ratio: Optional[Decimal] = None
    warning_buffer_pct: Optional[Decimal] = Decimal("5.0")


class NetExposurePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_name: str
    portfolio_id: Optional[str] = None
    group_id: Optional[str] = None
    reporting_currency: str
    denominator_type: str
    neutrality_threshold_type: str
    absolute_neutrality_threshold: Optional[Decimal] = None
    relative_neutrality_threshold: Optional[Decimal] = None
    combined_threshold_semantics: str
    max_net_long_ratio: Optional[Decimal] = None
    max_net_short_ratio: Optional[Decimal] = None
    policy_version: str
    approval_status: str
    created_at: datetime
