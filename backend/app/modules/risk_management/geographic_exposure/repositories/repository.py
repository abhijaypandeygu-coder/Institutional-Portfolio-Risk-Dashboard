"""
M06.05 Geographic Exposure - Repository layer.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Sequence
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.geographic_exposure.models import (
    GeographicExposureCalculationRun,
    CountryExposureResult,
    RegionExposureResult,
    UnknownGeographicExposure,
    GeographicExposureComparison,
)


class GeographicExposureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_calculation_run(
        self,
        run: GeographicExposureCalculationRun,
        countries: List[CountryExposureResult],
        regions: List[RegionExposureResult],
        unknowns: List[UnknownGeographicExposure],
    ) -> GeographicExposureCalculationRun:
        self.session.add(run)
        await self.session.flush()

        for c in countries:
            self.session.add(c)
        for r in regions:
            self.session.add(r)
        for u in unknowns:
            self.session.add(u)

        await self.session.flush()
        return run

    async def get_latest_run(self, portfolio_id: str) -> Optional[GeographicExposureCalculationRun]:
        stmt = (
            select(GeographicExposureCalculationRun)
            .where(GeographicExposureCalculationRun.portfolio_id == portfolio_id)
            .order_by(desc(GeographicExposureCalculationRun.as_of), desc(GeographicExposureCalculationRun.id))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_country_results(self, run_id: str) -> Sequence[CountryExposureResult]:
        stmt = (
            select(CountryExposureResult)
            .where(CountryExposureResult.run_id == run_id)
            .order_by(asc(CountryExposureResult.rank))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_region_results(self, run_id: str) -> Sequence[RegionExposureResult]:
        stmt = (
            select(RegionExposureResult)
            .where(RegionExposureResult.run_id == run_id)
            .order_by(asc(RegionExposureResult.rank))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_unknown_results(self, run_id: str) -> Sequence[UnknownGeographicExposure]:
        stmt = select(UnknownGeographicExposure).where(UnknownGeographicExposure.run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def save_comparisons(self, comps: List[GeographicExposureComparison]) -> None:
        for c in comps:
            self.session.add(c)
        await self.session.flush()

    async def get_comparisons(
        self, portfolio_id: str, current_snapshot_id: str, prior_snapshot_id: str, level: str
    ) -> Sequence[GeographicExposureComparison]:
        stmt = (
            select(GeographicExposureComparison)
            .where(
                and_(
                    GeographicExposureComparison.portfolio_id == portfolio_id,
                    GeographicExposureComparison.current_snapshot_id == current_snapshot_id,
                    GeographicExposureComparison.prior_snapshot_id == prior_snapshot_id,
                    GeographicExposureComparison.geographic_level == level,
                )
            )
            .order_by(desc(GeographicExposureComparison.gross_exposure_change))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()
