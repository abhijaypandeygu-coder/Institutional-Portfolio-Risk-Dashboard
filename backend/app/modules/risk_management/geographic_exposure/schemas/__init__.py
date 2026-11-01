"""
M06.05 Geographic Exposure - Pydantic 2.x Request & Response Schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.instrument_reference_data.geographic_classification.models import (
    GeographicAttributeType,
)
from backend.app.modules.risk_management.geographic_exposure.models import (
    GeographicLevel,
    GeographicCoverageStatus,
)


class GeographicExposureCalculateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    as_of: Optional[datetime] = None
    knowledge_as_of: Optional[datetime] = None
    reporting_currency: Optional[str] = "USD"
    geographic_attribute: Optional[GeographicAttributeType] = GeographicAttributeType.ISSUER_DOMICILE
    taxonomy_scheme_code: Optional[str] = "STANDARD"


class CountryExposureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_id: str
    country_name: str
    iso_alpha2: Optional[str] = None
    region_id: Optional[str] = None
    region_name: Optional[str] = None

    long_exposure: Decimal
    short_exposure: Decimal
    net_exposure: Decimal
    gross_exposure: Decimal

    long_nav_weight: Optional[Decimal] = None
    short_nav_weight: Optional[Decimal] = None
    net_nav_weight: Optional[Decimal] = None
    gross_nav_weight: Optional[Decimal] = None
    gross_contribution_weight: Optional[Decimal] = None

    instrument_count: int
    rank: Optional[int] = None


class RegionExposureItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_id: str
    region_code: str
    region_name: str
    taxonomy_scheme_code: str
    hierarchy_level: int

    long_exposure: Decimal
    short_exposure: Decimal
    net_exposure: Decimal
    gross_exposure: Decimal

    long_nav_weight: Optional[Decimal] = None
    short_nav_weight: Optional[Decimal] = None
    net_nav_weight: Optional[Decimal] = None
    gross_nav_weight: Optional[Decimal] = None
    gross_contribution_weight: Optional[Decimal] = None

    instrument_count: int
    rank: Optional[int] = None


class UnknownGeographicItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    reason_code: str
    unmapped_gross_exposure: Decimal
    unmapped_weight: Decimal


class GeographicExposureSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    portfolio_id: str
    portfolio_group_id: Optional[str] = None
    entity_type: str
    snapshot_id: Optional[str] = None
    as_of: datetime
    reporting_currency: str
    geographic_attribute: str
    taxonomy_scheme_code: str

    nav: Decimal
    total_long_exposure: Decimal
    total_short_exposure: Decimal
    total_net_exposure: Decimal
    total_gross_exposure: Decimal

    classified_gross_exposure: Decimal
    unknown_gross_exposure: Decimal
    coverage_ratio: Decimal
    coverage_status: str

    dominant_country_id: Optional[str] = None
    dominant_region_id: Optional[str] = None

    countries: List[CountryExposureItemResponse] = Field(default_factory=list)
    regions: List[RegionExposureItemResponse] = Field(default_factory=list)
    unknown_holdings: List[UnknownGeographicItemResponse] = Field(default_factory=list)


class GeographicComparisonItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_id: str
    entity_name: str
    current_gross_exposure: Decimal
    prior_gross_exposure: Decimal
    gross_exposure_change: Decimal
    gross_percentage_change: Optional[Decimal] = None
    nav_weight_change_pp: Optional[Decimal] = None
    lifecycle_status: str


class GeographicComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    current_snapshot_id: str
    prior_snapshot_id: str
    geographic_level: str
    items: List[GeographicComparisonItemResponse]
