"""
M06.04 Instrument Exposure - Repository layer.
Handles database queries for calculation runs, instrument exposures, listing details,
historical comparisons, and dominance flags.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Sequence
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.instrument_exposure.models import (
    InstrumentExposureCalculationRun,
    InstrumentExposureResult,
    InstrumentListingExposureDetail,
    InstrumentExposureComparison,
    InstrumentExposureDominanceFlag,
    InstrumentExposureSettings,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument, InstrumentListing


class InstrumentExposureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_settings(self, portfolio_id: Optional[str] = None) -> InstrumentExposureSettings:
        stmt = select(InstrumentExposureSettings).where(InstrumentExposureSettings.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        settings = res.scalar_one_or_none()
        if not settings:
            settings = InstrumentExposureSettings(
                portfolio_id=portfolio_id,
                reporting_currency="USD",
                gross_nav_elevated_threshold=Decimal("0.100000"),
                gross_nav_critical_threshold=Decimal("0.200000"),
                long_nav_elevated_threshold=Decimal("0.080000"),
                short_nav_elevated_threshold=Decimal("0.050000"),
                gross_contribution_threshold=Decimal("0.150000"),
            )
            self.session.add(settings)
            await self.session.flush()
        return settings

    async def save_calculation_run(
        self,
        run: InstrumentExposureCalculationRun,
        results: List[InstrumentExposureResult],
        listings: List[InstrumentListingExposureDetail],
        flags: List[InstrumentExposureDominanceFlag],
    ) -> InstrumentExposureCalculationRun:
        self.session.add(run)
        await self.session.flush()

        for r in results:
            self.session.add(r)
        for l in listings:
            self.session.add(l)
        for f in flags:
            self.session.add(f)

        await self.session.flush()
        return run

    async def get_latest_run(self, portfolio_id: str) -> Optional[InstrumentExposureCalculationRun]:
        stmt = (
            select(InstrumentExposureCalculationRun)
            .where(InstrumentExposureCalculationRun.portfolio_id == portfolio_id)
            .order_by(desc(InstrumentExposureCalculationRun.as_of), desc(InstrumentExposureCalculationRun.id))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_run_results(self, run_id: str) -> Sequence[InstrumentExposureResult]:
        stmt = (
            select(InstrumentExposureResult)
            .where(InstrumentExposureResult.run_id == run_id)
            .order_by(asc(InstrumentExposureResult.gross_rank))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_run_listings(self, run_id: str, instrument_id: str) -> Sequence[InstrumentListingExposureDetail]:
        stmt = (
            select(InstrumentListingExposureDetail)
            .where(
                and_(
                    InstrumentListingExposureDetail.run_id == run_id,
                    InstrumentListingExposureDetail.instrument_id == instrument_id,
                )
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_run_flags(self, run_id: str) -> Sequence[InstrumentExposureDominanceFlag]:
        stmt = select(InstrumentExposureDominanceFlag).where(InstrumentExposureDominanceFlag.run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_instrument_metadata(self, instrument_id: str) -> Optional[Instrument]:
        stmt = select(Instrument).where(Instrument.instrument_id == instrument_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_comparisons(self, comps: List[InstrumentExposureComparison]) -> None:
        for c in comps:
            self.session.add(c)
        await self.session.flush()

    async def get_comparisons(
        self, portfolio_id: str, current_snapshot_id: str, prior_snapshot_id: str
    ) -> Sequence[InstrumentExposureComparison]:
        stmt = (
            select(InstrumentExposureComparison)
            .where(
                and_(
                    InstrumentExposureComparison.portfolio_id == portfolio_id,
                    InstrumentExposureComparison.current_snapshot_id == current_snapshot_id,
                    InstrumentExposureComparison.prior_snapshot_id == prior_snapshot_id,
                )
            )
            .order_by(desc(InstrumentExposureComparison.gross_exposure_change))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()
