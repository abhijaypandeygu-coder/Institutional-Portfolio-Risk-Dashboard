"""
Module M07.01: Volatility Repository.
Transaction-managed persistence for configurations, conventions, return series,
volatility results, rolling series, and diagnostics.
"""
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.historical_volatility.models import (
    VolatilityAnnualizationConvention,
    HistoricalVolatilityConfig,
    HistoricalReturnObservation,
    HistoricalVolatilityResult,
    RollingVolatilityPoint,
    VolatilityCalculationDiagnostic,
)


class VolatilityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Conventions
    async def create_annualization_convention(
        self, convention: VolatilityAnnualizationConvention
    ) -> VolatilityAnnualizationConvention:
        self.session.add(convention)
        await self.session.commit()
        await self.session.refresh(convention)
        return convention

    async def get_annualization_convention(
        self, convention_id: str
    ) -> Optional[VolatilityAnnualizationConvention]:
        stmt = select(VolatilityAnnualizationConvention).where(
            VolatilityAnnualizationConvention.convention_id == convention_id
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_annualization_conventions(
        self, market_code: Optional[str] = None
    ) -> List[VolatilityAnnualizationConvention]:
        stmt = select(VolatilityAnnualizationConvention).where(
            VolatilityAnnualizationConvention.is_active == True
        )
        if market_code:
            stmt = stmt.where(VolatilityAnnualizationConvention.market_code == market_code)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Configs
    async def create_config(
        self, config: HistoricalVolatilityConfig
    ) -> HistoricalVolatilityConfig:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def get_config(
        self, config_id: str
    ) -> Optional[HistoricalVolatilityConfig]:
        stmt = select(HistoricalVolatilityConfig).where(
            HistoricalVolatilityConfig.config_id == config_id
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configs(
        self, instrument_id: Optional[str] = None, portfolio_id: Optional[str] = None
    ) -> List[HistoricalVolatilityConfig]:
        stmt = select(HistoricalVolatilityConfig).where(
            HistoricalVolatilityConfig.is_active == True
        )
        if instrument_id:
            stmt = stmt.where(HistoricalVolatilityConfig.instrument_id == instrument_id)
        if portfolio_id:
            stmt = stmt.where(HistoricalVolatilityConfig.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Results
    async def save_volatility_result(
        self, result: HistoricalVolatilityResult
    ) -> HistoricalVolatilityResult:
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_latest_volatility_result(
        self,
        instrument_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        lookback_window: Optional[int] = None,
    ) -> Optional[HistoricalVolatilityResult]:
        stmt = select(HistoricalVolatilityResult).order_by(
            desc(HistoricalVolatilityResult.calculated_at)
        )
        if instrument_id:
            stmt = stmt.where(HistoricalVolatilityResult.instrument_id == instrument_id)
        if portfolio_id:
            stmt = stmt.where(HistoricalVolatilityResult.portfolio_id == portfolio_id)
        if lookback_window:
            stmt = stmt.where(HistoricalVolatilityResult.lookback_window == lookback_window)
        stmt = stmt.limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # Rolling Points
    async def save_rolling_points(
        self, points: List[RollingVolatilityPoint]
    ) -> List[RollingVolatilityPoint]:
        self.session.add_all(points)
        await self.session.commit()
        return points

    async def list_rolling_points(
        self,
        instrument_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        lookback_window: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 252,
    ) -> List[RollingVolatilityPoint]:
        stmt = select(RollingVolatilityPoint).order_by(
            RollingVolatilityPoint.observation_timestamp.asc()
        )
        if instrument_id:
            stmt = stmt.where(RollingVolatilityPoint.instrument_id == instrument_id)
        if portfolio_id:
            stmt = stmt.where(RollingVolatilityPoint.portfolio_id == portfolio_id)
        if lookback_window:
            stmt = stmt.where(RollingVolatilityPoint.lookback_window == lookback_window)
        if from_date:
            stmt = stmt.where(RollingVolatilityPoint.trading_date >= from_date)
        if to_date:
            stmt = stmt.where(RollingVolatilityPoint.trading_date <= to_date)
        stmt = stmt.limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Diagnostics
    async def record_diagnostic(
        self, diagnostic: VolatilityCalculationDiagnostic
    ) -> VolatilityCalculationDiagnostic:
        self.session.add(diagnostic)
        await self.session.commit()
        return diagnostic

    async def list_diagnostics(
        self, result_id: Optional[str] = None, instrument_id: Optional[str] = None
    ) -> List[VolatilityCalculationDiagnostic]:
        stmt = select(VolatilityCalculationDiagnostic).order_by(
            desc(VolatilityCalculationDiagnostic.created_at)
        )
        if result_id:
            stmt = stmt.where(VolatilityCalculationDiagnostic.result_id == result_id)
        if instrument_id:
            stmt = stmt.where(VolatilityCalculationDiagnostic.instrument_id == instrument_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
