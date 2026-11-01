"""
M06.04 Instrument Exposure - Pydantic 2.x Request & Response Schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.risk_management.instrument_exposure.models import (
    ExposureWeightBasis,
    ExposureRankingBasis,
    ValuationQualityStatus,
    DenominatorStatus,
    ExposureLifecycleIndicator,
    DominanceSeverity,
)


class InstrumentExposureCalculateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    as_of: Optional[datetime] = None
    knowledge_as_of: Optional[datetime] = None
    reporting_currency: Optional[str] = "USD"
    weight_basis: Optional[ExposureWeightBasis] = ExposureWeightBasis.NAV
    ranking_basis: Optional[ExposureRankingBasis] = ExposureRankingBasis.GROSS


class InstrumentExposureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: Optional[str] = None
    instrument_name: Optional[str] = None
    exchange_code: Optional[str] = None
    asset_class: str = "EQUITY"
    reporting_currency: str

    long_quantity: Decimal
    short_quantity: Decimal
    net_quantity: Decimal

    long_market_value: Decimal
    short_market_value: Decimal
    net_market_value: Decimal
    gross_market_value: Decimal

    long_nav_weight: Optional[Decimal] = None
    short_nav_weight: Optional[Decimal] = None
    net_nav_weight: Optional[Decimal] = None
    gross_nav_weight: Optional[Decimal] = None

    gross_contribution_weight: Optional[Decimal] = None
    long_contribution_weight: Optional[Decimal] = None
    short_contribution_weight: Optional[Decimal] = None

    long_rank: Optional[int] = None
    short_rank: Optional[int] = None
    gross_rank: Optional[int] = None
    net_rank: Optional[int] = None

    valuation_status: str
    price_source: Optional[str] = None
    mark_price: Optional[Decimal] = None
    mark_price_currency: Optional[str] = None
    valuation_timestamp: Optional[datetime] = None

    dominance_severity: str
    dominance_flag_reason: Optional[str] = None


class ListingExposureDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    listing_id: str
    exchange_code: str
    native_currency: str
    quantity: Decimal
    mark_price: Decimal
    native_market_value: Decimal
    reporting_currency_market_value: Decimal
    fx_rate: Optional[Decimal] = None
    fx_pair: Optional[str] = None
    valuation_status: str


class InstrumentExposureSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    portfolio_id: str
    portfolio_group_id: Optional[str] = None
    entity_type: str
    snapshot_id: Optional[str] = None
    as_of: datetime
    reporting_currency: str
    weight_basis: str

    nav: Decimal
    total_long_exposure: Decimal
    total_short_exposure: Decimal
    total_net_exposure: Decimal
    total_gross_exposure: Decimal

    total_instruments_count: int
    long_instruments_count: int
    short_instruments_count: int
    hedged_instruments_count: int

    valuation_coverage_ratio: Decimal
    data_completeness_status: str
    denominator_status: str

    largest_gross_instrument: Optional[str] = None
    largest_long_instrument: Optional[str] = None
    largest_short_instrument: Optional[str] = None

    dominant_exposures_count: int
    instruments: List[InstrumentExposureItemResponse] = Field(default_factory=list)


class InstrumentExposureRankingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ranking_basis: ExposureRankingBasis
    weight_basis: ExposureWeightBasis
    items: List[InstrumentExposureItemResponse]


class InstrumentExposureComparisonItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: Optional[str] = None
    instrument_name: Optional[str] = None

    current_long_exposure: Decimal
    prior_long_exposure: Decimal
    long_exposure_change: Decimal

    current_short_exposure: Decimal
    prior_short_exposure: Decimal
    short_exposure_change: Decimal

    current_net_exposure: Decimal
    prior_net_exposure: Decimal
    net_exposure_change: Decimal

    current_gross_exposure: Decimal
    prior_gross_exposure: Decimal
    gross_exposure_change: Decimal

    gross_percentage_change: Optional[Decimal] = None
    nav_weight_change_pp: Optional[Decimal] = None
    gross_contribution_change_pp: Optional[Decimal] = None

    lifecycle_indicator: str


class InstrumentExposureComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    current_snapshot_id: str
    prior_snapshot_id: str
    reporting_currency: str
    items: List[InstrumentExposureComparisonItemResponse]


class InstrumentExposureDominanceFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    flag_type: str
    severity: str
    measured_value: Decimal
    threshold_value: Decimal
    weight_basis: str
    evaluation_timestamp: datetime


class InstrumentExposureSettingsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: Optional[str] = None
    reporting_currency: str = "USD"
    default_weight_basis: ExposureWeightBasis = ExposureWeightBasis.NAV
    default_ranking_basis: ExposureRankingBasis = ExposureRankingBasis.GROSS

    gross_nav_elevated_threshold: Decimal = Decimal("0.100000")
    gross_nav_critical_threshold: Decimal = Decimal("0.200000")
    long_nav_elevated_threshold: Decimal = Decimal("0.080000")
    short_nav_elevated_threshold: Decimal = Decimal("0.050000")
    gross_contribution_threshold: Decimal = Decimal("0.150000")

