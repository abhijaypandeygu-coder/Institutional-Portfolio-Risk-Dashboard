"""
M04 Geographic Reference Data - Repository layer.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Sequence
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.instrument_reference_data.geographic_classification.models import (
    GeographicCountry,
    GeographicRegion,
    CountryRegionAssignment,
    IssuerGeographicAssignment,
    IssuerRevenueGeography,
    GeographicAttributeType,
)


class GeographicReferenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_country(self, country: GeographicCountry) -> GeographicCountry:
        stmt = select(GeographicCountry).where(GeographicCountry.country_id == country.country_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing
        self.session.add(country)
        await self.session.flush()
        return country

    async def get_country(self, country_id: str) -> Optional[GeographicCountry]:
        stmt = select(GeographicCountry).where(GeographicCountry.country_id == country_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_or_create_region(self, region: GeographicRegion) -> GeographicRegion:
        stmt = select(GeographicRegion).where(GeographicRegion.region_id == region.region_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing
        self.session.add(region)
        await self.session.flush()
        return region

    async def get_region(self, region_id: str) -> Optional[GeographicRegion]:
        stmt = select(GeographicRegion).where(GeographicRegion.region_id == region_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def assign_country_to_region(self, assignment: CountryRegionAssignment) -> CountryRegionAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_country_region(self, country_id: str, taxonomy_scheme: str = "STANDARD") -> Optional[GeographicRegion]:
        stmt = (
            select(GeographicRegion)
            .join(CountryRegionAssignment, CountryRegionAssignment.region_id == GeographicRegion.region_id)
            .where(
                and_(
                    CountryRegionAssignment.country_id == country_id,
                    CountryRegionAssignment.taxonomy_scheme_code == taxonomy_scheme,
                )
            )
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def assign_issuer_geography(self, assignment: IssuerGeographicAssignment) -> IssuerGeographicAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_issuer_geography(
        self, instrument_id: str, attribute_type: str = GeographicAttributeType.ISSUER_DOMICILE.value
    ) -> Sequence[IssuerGeographicAssignment]:
        stmt = (
            select(IssuerGeographicAssignment)
            .where(
                and_(
                    IssuerGeographicAssignment.instrument_id == instrument_id,
                    IssuerGeographicAssignment.attribute_type == attribute_type,
                )
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def add_revenue_geography(self, rev: IssuerRevenueGeography) -> IssuerRevenueGeography:
        self.session.add(rev)
        await self.session.flush()
        return rev

    async def get_revenue_geography(self, instrument_id: str) -> Sequence[IssuerRevenueGeography]:
        stmt = select(IssuerRevenueGeography).where(IssuerRevenueGeography.instrument_id == instrument_id)
        res = await self.session.execute(stmt)
        return res.scalars().all()
