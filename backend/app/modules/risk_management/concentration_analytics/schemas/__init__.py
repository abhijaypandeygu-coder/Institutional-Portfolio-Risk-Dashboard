"""
Pydantic 2.x Schemas for M06.06 Concentration Analytics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.risk_management.concentration_analytics.models import (
    ConcentrationGroupingDimension,
    ConcentrationExposureBasis,
    ConcentrationCalculationStatus,
    ConcentrationTrendStatus,
    ConcentrationInterpretationLevel,
)


class ConcentrationCalculateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    grouping_dimension: ConcentrationGroupingDimension = ConcentrationGroupingDimension.INSTRUMENT
    exposure_basis: ConcentrationExposureBasis = ConcentrationExposureBasis.GROSS_EXPOSURE
    reporting_currency: str = "USD"
    as_of_date: Optional[datetime] = None
    snapshot_id: Optional[str] = None
    custom_top_n: Optional[List[int]] = Field(default_factory=lambda: [1, 3, 5, 10, 20])


class ConcentrationContributorItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contributor_id: str
    group_id: str
    group_key: str
    group_name: str
    grouping_dimension: ConcentrationGroupingDimension
    rank: int

    long_exposure: Decimal
    short_exposure: Decimal
    net_exposure: Decimal
    gross_exposure: Decimal

    exposure_value: Decimal
    exposure_share: Decimal
    cumulative_share: Decimal
    source_exposure_reference: Optional[str] = None
    classification_status: str


class ConcentrationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    snapshot_id: Optional[str] = None

    grouping_dimension: ConcentrationGroupingDimension
    exposure_basis: ConcentrationExposureBasis
    weighting_methodology: str
    reporting_currency: str

    total_exposure: Decimal
    denominator_exposure: Decimal
    eligible_group_count: int

    top_1_ratio: Decimal
    top_3_ratio: Decimal
    top_5_ratio: Decimal
    top_10_ratio: Decimal
    top_20_ratio: Decimal

    hhi_decimal: Decimal
    hhi_10000: Decimal
    effective_number_of_groups: Decimal

    classification_coverage: Decimal
    unknown_exposure_share: Decimal

    calculation_status: ConcentrationCalculationStatus
    calculation_version: str
    calculated_at: datetime

    interpretation_level: Optional[ConcentrationInterpretationLevel] = None
    active_flags: Optional[List[str]] = None
    top_contributors: Optional[List[ConcentrationContributorItemResponse]] = None


class ConcentrationRatiosResponse(BaseModel):
    result_id: str
    grouping_dimension: ConcentrationGroupingDimension
    exposure_basis: ConcentrationExposureBasis
    ratios: Dict[str, Decimal]  # e.g. {"CR1": Decimal("0.25"), "CR5": Decimal("0.65")}
    eligible_group_count: int
    calculation_status: ConcentrationCalculationStatus


class ConcentrationHHIResponse(BaseModel):
    result_id: str
    grouping_dimension: ConcentrationGroupingDimension
    exposure_basis: ConcentrationExposureBasis
    hhi_decimal: Decimal
    hhi_10000: Decimal
    effective_number_of_groups: Decimal
    eligible_group_count: int
    scale_interpretation: str
    calculation_status: ConcentrationCalculationStatus


class ConcentrationCompareRequest(BaseModel):
    base_result_id: str
    comparison_result_id: str


class ConcentrationComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comparison_id: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None

    current_result_id: str
    prior_result_id: str

    grouping_dimension: ConcentrationGroupingDimension
    exposure_basis: ConcentrationExposureBasis
    weighting_methodology: str

    current_hhi_decimal: Decimal
    prior_hhi_decimal: Decimal
    hhi_decimal_change: Decimal

    current_hhi_10000: Decimal
    prior_hhi_10000: Decimal
    hhi_10000_change: Decimal

    current_cr5: Decimal
    prior_cr5: Decimal
    cr5_change_pp: Decimal

    current_cr10: Decimal
    prior_cr10: Decimal
    cr10_change_pp: Decimal

    current_effective_groups: Decimal
    prior_effective_groups: Decimal
    effective_groups_change: Decimal

    trend_status: ConcentrationTrendStatus
    comparability_status: str
    compared_at: datetime


class ConcentrationPolicyCreateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    grouping_dimension: ConcentrationGroupingDimension
    exposure_basis: ConcentrationExposureBasis

    top_1_warning: Decimal = Decimal("0.20")
    top_1_critical: Decimal = Decimal("0.30")
    cr5_warning: Decimal = Decimal("0.50")
    cr5_critical: Decimal = Decimal("0.70")
    hhi_10000_warning: Decimal = Decimal("1500.0")
    hhi_10000_critical: Decimal = Decimal("2500.0")
    min_effective_groups_warning: Decimal = Decimal("8.0")
    min_effective_groups_critical: Decimal = Decimal("4.0")

    interpretation_policy: str = "STANDARD_INSTITUTIONAL"
    policy_version: str = "v1.0"


class ConcentrationPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    grouping_dimension: ConcentrationGroupingDimension
    exposure_basis: ConcentrationExposureBasis

    top_1_warning: Decimal
    top_1_critical: Decimal
    cr5_warning: Decimal
    cr5_critical: Decimal
    hhi_10000_warning: Decimal
    hhi_10000_critical: Decimal
    min_effective_groups_warning: Decimal
    min_effective_groups_critical: Decimal

    interpretation_policy: str
    is_active: bool
    policy_version: str
    effective_from: datetime

