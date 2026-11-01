"""
M04 Geographic Reference Data - Service layer.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.instrument_reference_data.geographic_classification.models import (
    GeographicCountry,
    GeographicRegion,
    CountryRegionAssignment,
    IssuerGeographicAssignment,
    IssuerRevenueGeography,
    GeographicAttributeType,
)
from backend.app.modules.instrument_reference_data.geographic_classification.schemas import (
    CountryCreateRequest,
    CountryResponse,
    RegionCreateRequest,
    RegionResponse,
    CountryRegionAssignRequest,
    IssuerGeographicAssignRequest,
    IssuerRevenueGeographyCreateRequest,
)
from backend.app.modules.instrument_reference_data.geographic_classification.repositories.repository import (
    GeographicReferenceRepository,
)


class GeographicReferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GeographicReferenceRepository(session)

    async def register_country(self, req: CountryCreateRequest) -> CountryResponse:
        c = GeographicCountry(
            country_id=req.country_id.upper(),
            iso_alpha2=req.iso_alpha2.upper(),
            canonical_name=req.canonical_name,
            numeric_code=req.numeric_code,
        )
        saved = await self.repo.get_or_create_country(c)
        return CountryResponse.model_validate(saved)

    async def register_region(self, req: RegionCreateRequest) -> RegionResponse:
        r = GeographicRegion(
            region_id=req.region_id,
            region_code=req.region_code,
            region_name=req.region_name,
            description=req.description,
            taxonomy_scheme_code=req.taxonomy_scheme_code,
            taxonomy_version=req.taxonomy_version,
            parent_region_id=req.parent_region_id,
            hierarchy_level=req.hierarchy_level,
        )
        saved = await self.repo.get_or_create_region(r)
        return RegionResponse.model_validate(saved)

    async def assign_country_to_region(self, req: CountryRegionAssignRequest) -> CountryRegionAssignment:
        assignment = CountryRegionAssignment(
            country_id=req.country_id.upper(),
            region_id=req.region_id,
            allocation_weight=req.allocation_weight,
            taxonomy_scheme_code=req.taxonomy_scheme_code,
            taxonomy_version=req.taxonomy_version,
        )
        return await self.repo.assign_country_to_region(assignment)

    async def assign_issuer_geography(self, req: IssuerGeographicAssignRequest) -> IssuerGeographicAssignment:
        assignment = IssuerGeographicAssignment(
            instrument_id=req.instrument_id,
            issuer_id=req.issuer_id,
            attribute_type=req.attribute_type.value,
            country_id=req.country_id.upper(),
            allocation_weight=req.allocation_weight,
            source_reference=req.source_reference,
        )
        return await self.repo.assign_issuer_geography(assignment)

    async def add_revenue_geography(self, req: IssuerRevenueGeographyCreateRequest) -> IssuerRevenueGeography:
        rev = IssuerRevenueGeography(
            instrument_id=req.instrument_id,
            issuer_id=req.issuer_id,
            country_id=req.country_id.upper() if req.country_id else None,
            region_id=req.region_id,
            geographic_segment_code=req.geographic_segment_code,
            fiscal_period=req.fiscal_period,
            fiscal_period_end=req.fiscal_period_end,
            revenue_percentage=req.revenue_percentage,
            allocation_weight=req.allocation_weight,
            revenue_amount=req.revenue_amount,
            revenue_currency=req.revenue_currency,
            source_reference=req.source_reference,
        )
        return await self.repo.add_revenue_geography(rev)
