"""
M06.03 Sector Exposure Pydantic Schemas.
Data transfer objects and request/response models for sector and industry aggregations,
weights, unclassified holdings, coverage, and benchmark-relative active exposures.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.risk_management.sector_exposure.models import (
    SectorWeightBasis,
    ClassificationCoverageStatus,
    ActiveWeightStatus,
    SectorClassificationStatus,
)


class SectorExposureCalculateRequest(BaseModel):
    as_of: Optional[datetime] = None
    knowledge_as_of: Optional[datetime] = None
    classification_scheme_code: Optional[str] = Field("GICS", description="Classification scheme taxonomy (GICS, ICB)")
    classification_version_code: Optional[str] = Field("2023", description="Scheme version code")
    reporting_currency: Optional[str] = Field("USD", description="Target reporting currency")
    weight_basis: Optional[SectorWeightBasis] = SectorWeightBasis.NAV
    custom_denominator_value: Optional[Decimal] = Field(None, description="NAV or custom denominator")
    benchmark_id: Optional[str] = Field(None, description="Optional benchmark ID for relative sector analysis")
    active_weight_neutrality_threshold: Optional[Decimal] = Field(
        Decimal("0.005000"), description="Tolerance band for active weight neutrality (e.g. 0.5% = 0.005)"
    )
    fx_rates_to_reporting: Optional[Dict[str, Decimal]] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class SectorExposureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sector_id: str
    sector_name: str
    classification_scheme_code: str
    reporting_currency: str
    long_exposure: Decimal
    absolute_short_exposure: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    long_weight: Optional[Decimal] = None
    short_weight: Optional[Decimal] = None
    gross_weight: Optional[Decimal] = None
    net_weight: Optional[Decimal] = None
    allocation_weight: Optional[Decimal] = None
    contributing_instrument_count: int


class IndustryExposureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sector_id: str
    industry_id: str
    industry_name: str
    reporting_currency: str
    long_exposure: Decimal
    absolute_short_exposure: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    long_weight: Optional[Decimal] = None
    net_weight: Optional[Decimal] = None
    parent_sector_contribution_weight: Optional[Decimal] = None
    contributing_instrument_count: int


class UnclassifiedExposureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    classification_status: str
    reason_code: str
    parent_sector_id: Optional[str] = None
    long_exposure: Decimal
    absolute_short_exposure: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    allocation_weight: Optional[Decimal] = None
    contributing_instrument_count: int
    reporting_currency: str


class ClassificationCoverageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_positions: int
    classified_positions: int
    unclassified_positions: int
    classified_gross_exposure: Decimal
    unclassified_gross_exposure: Decimal
    gross_value_coverage_pct: Decimal
    position_count_coverage_pct: Decimal
    coverage_status: str


class RelativeSectorExposureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    benchmark_id: str
    sector_id: str
    sector_name: str
    portfolio_sector_weight: Decimal
    benchmark_sector_weight: Decimal
    active_sector_weight: Decimal
    active_weight_status: str
    comparison_basis: str


class SectorExposureSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    portfolio_id: Optional[str] = None
    group_id: Optional[str] = None
    scope: str
    reporting_currency: str
    weight_basis: str
    denominator_value: Optional[Decimal] = None

    total_long_exposure: Decimal
    total_absolute_short_exposure: Decimal
    total_gross_exposure: Decimal
    total_net_exposure: Decimal

    sectors: List[SectorExposureItemResponse] = []
    industries: List[IndustryExposureItemResponse] = []
    unclassified: List[UnclassifiedExposureItemResponse] = []
    coverage: ClassificationCoverageResponse
    relative_exposures: List[RelativeSectorExposureItemResponse] = []
    completeness_status: str


class BenchmarkSectorCompositionCreateRequest(BaseModel):
    benchmark_id: str
    benchmark_name: str
    sector_id: str
    sector_name: str
    classification_scheme_code: str = "GICS"
    benchmark_weight: Decimal
    effective_date: Optional[datetime] = None
    source_reference: Optional[str] = "AUTHORITATIVE_INDEX_PROVIDER"


class BenchmarkSectorCompositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    benchmark_id: str
    benchmark_name: str
    sector_id: str
    sector_name: str
    classification_scheme_code: str
    benchmark_weight: Decimal
    effective_date: datetime
    source_reference: str

