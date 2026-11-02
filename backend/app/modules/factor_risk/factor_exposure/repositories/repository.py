"""
M08.02 Factor Exposure Repository Layer.
Handles database queries and persistence for:
- Factor return series and observations
- Factor exposure estimation configurations
- Factor loading execution runs
- Security-level instrument factor loadings
- Portfolio factor exposure snapshots
- Exposure change attributions
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_exposure.models import (
    FactorReturnSeries,
    FactorReturnObservation,
    FactorExposureEstimationConfig,
    FactorLoadingRun,
    InstrumentFactorLoading,
    PortfolioFactorExposureSnapshot,
    FactorExposureNormalization,
    FactorExposureChangeAttribution,
    WeightingBasis,
    RestatementStatus,
)


class FactorExposureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 1. Factor Returns
    async def get_or_create_series(
        self,
        factor_id: str,
        factor_code: str,
        version_id: str,
        market_scope: str,
        currency: str,
        frequency: str = "DAILY",
        return_convention: str = "SIMPLE",
    ) -> FactorReturnSeries:
        stmt = (
            select(FactorReturnSeries)
            .where(
                and_(
                    FactorReturnSeries.factor_id == factor_id,
                    FactorReturnSeries.version_id == version_id,
                    FactorReturnSeries.frequency == frequency,
                    FactorReturnSeries.currency == currency,
                )
            )
            .options(selectinload(FactorReturnSeries.observations))
        )
        res = await self.session.execute(stmt)
        series = res.scalars().first()
        if not series:
            series = FactorReturnSeries(
                factor_id=factor_id,
                factor_code=factor_code,
                version_id=version_id,
                market_scope=market_scope,
                currency=currency,
                frequency=frequency,
                return_convention=return_convention,
            )
            self.session.add(series)
            await self.session.commit()
        return series

    async def get_series_by_code_and_version(
        self, factor_code: str, version_id: str
    ) -> Optional[FactorReturnSeries]:
        stmt = (
            select(FactorReturnSeries)
            .where(
                and_(
                    FactorReturnSeries.factor_code == factor_code,
                    FactorReturnSeries.version_id == version_id,
                )
            )
            .options(selectinload(FactorReturnSeries.observations))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_series_by_id(self, series_id: str) -> Optional[FactorReturnSeries]:
        stmt = (
            select(FactorReturnSeries)
            .where(FactorReturnSeries.series_id == series_id)
            .options(selectinload(FactorReturnSeries.observations))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_observation(self, obs: FactorReturnObservation) -> FactorReturnObservation:
        self.session.add(obs)
        await self.session.commit()
        return obs

    async def get_observations_in_window(
        self, series_id: str, start_date: date, end_date: date
    ) -> List[FactorReturnObservation]:
        stmt = (
            select(FactorReturnObservation)
            .where(
                and_(
                    FactorReturnObservation.series_id == series_id,
                    FactorReturnObservation.trading_date >= start_date,
                    FactorReturnObservation.trading_date <= end_date,
                )
            )
            .order_by(FactorReturnObservation.trading_date)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # 2. Estimation Configuration
    async def save_config(self, config: FactorExposureEstimationConfig) -> FactorExposureEstimationConfig:
        self.session.add(config)
        await self.session.commit()
        return config

    async def get_config_by_id(self, config_id: str) -> Optional[FactorExposureEstimationConfig]:
        stmt = select(FactorExposureEstimationConfig).where(FactorExposureEstimationConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_config_by_code(self, config_code: str) -> Optional[FactorExposureEstimationConfig]:
        stmt = select(FactorExposureEstimationConfig).where(FactorExposureEstimationConfig.config_code == config_code)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_configs(self) -> List[FactorExposureEstimationConfig]:
        stmt = select(FactorExposureEstimationConfig).order_by(FactorExposureEstimationConfig.config_code)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # 3. Factor Loading Run
    async def save_run(self, run: FactorLoadingRun) -> FactorLoadingRun:
        self.session.add(run)
        await self.session.commit()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[FactorLoadingRun]:
        stmt = (
            select(FactorLoadingRun)
            .where(FactorLoadingRun.run_id == run_id)
            .options(selectinload(FactorLoadingRun.loadings))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_runs(self, limit: int = 50) -> List[FactorLoadingRun]:
        stmt = (
            select(FactorLoadingRun)
            .order_by(desc(FactorLoadingRun.started_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # 4. Instrument Loadings
    async def save_loading(self, loading: InstrumentFactorLoading) -> InstrumentFactorLoading:
        self.session.add(loading)
        await self.session.commit()
        return loading

    async def get_instrument_loadings_by_run(
        self, run_id: str, instrument_id: str
    ) -> List[InstrumentFactorLoading]:
        stmt = (
            select(InstrumentFactorLoading)
            .where(
                and_(
                    InstrumentFactorLoading.run_id == run_id,
                    InstrumentFactorLoading.instrument_id == instrument_id,
                )
            )
            .order_by(InstrumentFactorLoading.factor_position)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_latest_instrument_loadings(
        self, instrument_id: str, factor_model_version_id: Optional[str] = None
    ) -> List[InstrumentFactorLoading]:
        stmt = (
            select(InstrumentFactorLoading)
            .join(FactorLoadingRun, InstrumentFactorLoading.run_id == FactorLoadingRun.run_id)
            .where(InstrumentFactorLoading.instrument_id == instrument_id)
        )
        if factor_model_version_id:
            stmt = stmt.where(FactorLoadingRun.factor_model_version_id == factor_model_version_id)
        stmt = stmt.order_by(desc(FactorLoadingRun.as_of_date), InstrumentFactorLoading.factor_position)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # 5. Portfolio Factor Exposure Snapshots
    async def save_portfolio_exposure(
        self, exposure: PortfolioFactorExposureSnapshot
    ) -> PortfolioFactorExposureSnapshot:
        self.session.add(exposure)
        await self.session.commit()
        return exposure

    async def get_portfolio_exposures_by_date(
        self,
        portfolio_id: str,
        as_of_date: date,
        weighting_basis: WeightingBasis = WeightingBasis.NAV_WEIGHTED,
        factor_model_version_id: Optional[str] = None,
    ) -> List[PortfolioFactorExposureSnapshot]:
        stmt = select(PortfolioFactorExposureSnapshot).where(
            and_(
                PortfolioFactorExposureSnapshot.portfolio_id == portfolio_id,
                PortfolioFactorExposureSnapshot.as_of_date == as_of_date,
                PortfolioFactorExposureSnapshot.weighting_basis == weighting_basis,
            )
        )
        if factor_model_version_id:
            stmt = stmt.where(PortfolioFactorExposureSnapshot.factor_model_version_id == factor_model_version_id)
        stmt = stmt.order_by(PortfolioFactorExposureSnapshot.factor_position)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_portfolio_exposure_history(
        self,
        portfolio_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        factor_code: Optional[str] = None,
        factor_model_version_id: Optional[str] = None,
        weighting_basis: WeightingBasis = WeightingBasis.NAV_WEIGHTED,
    ) -> List[PortfolioFactorExposureSnapshot]:
        stmt = select(PortfolioFactorExposureSnapshot).where(
            and_(
                PortfolioFactorExposureSnapshot.portfolio_id == portfolio_id,
                PortfolioFactorExposureSnapshot.weighting_basis == weighting_basis,
            )
        )
        if start_date:
            stmt = stmt.where(PortfolioFactorExposureSnapshot.as_of_date >= start_date)
        if end_date:
            stmt = stmt.where(PortfolioFactorExposureSnapshot.as_of_date <= end_date)
        if factor_code:
            stmt = stmt.where(PortfolioFactorExposureSnapshot.factor_code == factor_code)
        if factor_model_version_id:
            stmt = stmt.where(PortfolioFactorExposureSnapshot.factor_model_version_id == factor_model_version_id)
        stmt = stmt.order_by(PortfolioFactorExposureSnapshot.as_of_date, PortfolioFactorExposureSnapshot.factor_position)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # 6. Change Attribution
    async def save_attribution(
        self, attr: FactorExposureChangeAttribution
    ) -> FactorExposureChangeAttribution:
        self.session.add(attr)
        await self.session.commit()
        return attr

