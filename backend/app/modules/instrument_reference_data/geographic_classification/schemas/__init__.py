"""
M04 Geographic Reference Data - Pydantic 2.x Schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.instrument_reference_data.geographic_classification.models import (
    GeographicAttributeType,
    GeographicMappingStatus,
)


class CountryCreateRequest(BaseModel):
    country_id: str = Field(..., min_length=2, max_length=3, description="ISO-3 or ISO-2 code")
    iso_alpha2: str = Field(..., min_length=2, max_length=2)
    canonical_name: str
    numeric_code: Optional[str] = None


class CountryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_id: str
    iso_alpha2: str
    canonical_name: str
    numeric_code: Optional[str] = None
    is_active: bool


class RegionCreateRequest(BaseModel):
    region_id: str
    region_code: str
    region_name: str
    description: Optional[str] = None
    taxonomy_scheme_code: str = "STANDARD"
    taxonomy_version: str = "1.0.0"
    parent_region_id: Optional[str] = None
    hierarchy_level: int = 1


class RegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_id: str
    region_code: str
    region_name: str
    taxonomy_scheme_code: str
    taxonomy_version: str
    parent_region_id: Optional[str] = None
    hierarchy_level: int
    is_active: bool


class CountryRegionAssignRequest(BaseModel):
    country_id: str
    region_id: str
    allocation_weight: Decimal = Decimal("1.000000")
    taxonomy_scheme_code: str = "STANDARD"
    taxonomy_version: str = "1.0.0"


class IssuerGeographicAssignRequest(BaseModel):
    instrument_id: str
    issuer_id: Optional[str] = None
    attribute_type: GeographicAttributeType = GeographicAttributeType.ISSUER_DOMICILE
    country_id: str
    allocation_weight: Decimal = Decimal("1.000000")
    source_reference: Optional[str] = None


class IssuerRevenueGeographyCreateRequest(BaseModel):
    instrument_id: str
    issuer_id: Optional[str] = None
    country_id: Optional[str] = None
    region_id: Optional[str] = None
    geographic_segment_code: str
    fiscal_period: str = "FY2024"
    fiscal_period_end: datetime
    revenue_percentage: Decimal
    allocation_weight: Decimal
    revenue_amount: Optional[Decimal] = None
    revenue_currency: Optional[str] = "USD"
    source_reference: Optional[str] = None
