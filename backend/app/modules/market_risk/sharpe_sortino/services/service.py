"""
M07.08 Sharpe & Sortino Service Layer.
Integrates M07.01 return resolution, M05.07 Portfolio NAV snapshots, and M04 Instrument references.
Orchestrates:
- Currency-aware Risk-Free Rate resolution and daily compounding conversion
- Excess return computation and Sharpe ratio calculation
- Minimum Acceptable Return (MAR) shortfall analysis and Sortino ratio calculation
- Rolling Sharpe & Sortino time series analytics
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.market_risk.sharpe_sortino.models import (
    RiskFreeRateSeries,
    RiskFreeRateObservation,
    SharpeRatioResult,
    SortinoRatioResult,
    SharpeDenominatorPolicy,
    SortinoTargetPolicy,
    SortinoDenominatorPolicy,
    RateConvention,
    DayCountConvention,
    RateMissingPolicy,
    RatioCalculationStatus,
)
from backend.app.modules.market_risk.sharpe_sortino.schemas import (
    SharpeRatioRequest,
    SharpeRatioResponse,
    SortinoRatioRequest,
    SortinoRatioResponse,
    CombinedRatiosRequest,
    CombinedRatiosResponse,
    RollingRatiosRequest,
    RollingRatiosResponse,
    RollingRatioPoint,
)
from backend.app.modules.market_risk.sharpe_sortino.calculations.ratio_math import (
    convert_rate_to_period_return,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)
from backend.app.modules.market_risk.sharpe_sortino.repositories.repository import SharpeSortinoRepository
from backend.app.modules.market_risk.historical_volatility.services.service import HistoricalVolatilityService
from backend.app.modules.market_risk.historical_volatility.models import (
    VolatilityScopeType,
    PriceSourceType,
    ReturnType,
)
from backend.app.modules.market_risk.historical_volatility.calculations.volatility_math import calculate_return
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio


class SharpeSortinoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SharpeSortinoRepository(session)
        self.vol_service = HistoricalVolatilityService(session)

    async def _resolve_entity_currency(self, scope: str, entity_id: str) -> str:
        if scope.upper() == "SECURITY":
            stmt = select(Instrument.issue_currency).where(Instrument.instrument_id == entity_id)
            res = await self.session.execute(stmt)
            curr = res.scalar_one_or_none()
            return curr if curr else "INR"
        else:
            stmt = select(Portfolio.base_currency).where(Portfolio.portfolio_id == entity_id)
            res = await self.session.execute(stmt)
            curr = res.scalar_one_or_none()
            return curr if curr else "INR"

    async def _resolve_returns_for_entity(
        self, scope: str, entity_id: str, as_of: Optional[date] = None
    ) -> List[Tuple[date, Decimal]]:
        if scope.upper() == "SECURITY":
            prices = await self.vol_service.resolve_price_series(
                scope_type=VolatilityScopeType.INSTRUMENT,
                instrument_id=entity_id,
                portfolio_id=None,
                price_source=PriceSourceType.OFFICIAL_CLOSE,
                as_of=as_of,
            )
        else:
            prices = await self.vol_service.resolve_price_series(
                scope_type=VolatilityScopeType.PORTFOLIO,
                instrument_id=None,
                portfolio_id=entity_id,
                price_source=PriceSourceType.PORTFOLIO_NAV,
                as_of=as_of,
            )

        if len(prices) < 2:
            return []

        returns = []
        for i in range(1, len(prices)):
            p_prev = prices[i - 1][1]
            p_curr = prices[i][1]
            d_curr = prices[i][0]
            ret = calculate_return(p_prev, p_curr, return_type=ReturnType.LOGARITHMIC)
            d_out = d_curr.date() if isinstance(d_curr, datetime) else d_curr
            returns.append((d_out, ret))

        return returns

    async def resolve_or_create_rate_series(
        self, currency: str, series_code: Optional[str] = None
    ) -> RiskFreeRateSeries:
        if series_code:
            series = await self.repo.get_rate_series_by_code(series_code)
            if series:
                return series

        series = await self.repo.get_default_series_for_currency(currency)
        if series:
            return series

        # Autocreate default rate series if none exists
        default_code = f"RF_{currency.upper()}_3M"
        series = RiskFreeRateSeries(
            series_code=default_code,
            rate_name=f"{currency.upper()} 3M Risk Free Benchmark Rate",
            currency=currency.upper(),
            market="INDIA" if currency.upper() == "INR" else "US",
            provider="CENTRAL_BANK",
            rate_convention=RateConvention.EFFECTIVE_ANNUAL_RATE,
            day_count_convention=DayCountConvention.ACTUAL_365,
            is_active=True,
        )
        return await self.repo.create_rate_series(series)

    async def _resolve_aligned_rf_returns(
        self,
        series: RiskFreeRateSeries,
        return_dates: List[date],
    ) -> List[float]:
        """
        Resolves effective period risk-free returns aligned with the given dates.
        Applies carry-forward policy for dates without a published rate.
        Fallback default rate: 6.5% for INR, 4.5% for USD.
        """
        if not return_dates:
            return []

        obs_list = await self.repo.get_rate_observations(
            series_id=series.id,
            start_date=return_dates[0],
            end_date=return_dates[-1],
        )
        obs_map = {o.rate_date: float(o.annualized_rate) for o in obs_list}

        default_annual = 0.065 if series.currency == "INR" else 0.045
        latest_rate = default_annual

        rf_returns = []
        for d in return_dates:
            if d in obs_map:
                latest_rate = obs_map[d]
            rf_ret = convert_rate_to_period_return(
                annualized_rate=latest_rate,
                rate_convention=series.rate_convention,
                day_count=series.day_count_convention,
                days_in_period=1,
            )
            rf_returns.append(rf_ret)

        return rf_returns

    async def calculate_sharpe(self, req: SharpeRatioRequest) -> SharpeRatioResponse:
        as_of_dt = datetime.combine(req.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)
        curr = await self._resolve_entity_currency(req.scope, req.entity_id)

        # 1. Resolve entity returns
        ret_series = await self._resolve_returns_for_entity(req.scope, req.entity_id, req.as_of)
        if req.lookback_days and len(ret_series) > req.lookback_days:
            ret_series = ret_series[-req.lookback_days:]

        ret_dates = [r[0] for r in ret_series]
        rp_arr = np.array([float(r[1]) for r in ret_series], dtype=np.float64)

        # 2. Resolve risk free series
        rf_series = await self.resolve_or_create_rate_series(currency=curr, series_code=req.risk_free_series_code)
        rf_arr = np.array(await self._resolve_aligned_rf_returns(rf_series, ret_dates), dtype=np.float64)

        # 3. Compute Sharpe
        ann_factor = float(req.annualization_factor)
        calc = calculate_sharpe_ratio(
            returns_portfolio=rp_arr,
            returns_risk_free=rf_arr,
            denominator_policy=req.denominator_policy,
            annualization_factor=ann_factor,
        )

        calc_code = f"SHARPE_{uuid4().hex[:12].upper()}"
        res = SharpeRatioResult(
            calculation_code=calc_code,
            scope=req.scope.upper(),
            entity_id=req.entity_id,
            as_of_date=as_of_dt,
            lookback_days=req.lookback_days,
            currency=curr,
            mean_return_period=calc["mean_return"],
            mean_risk_free_period=calc["mean_risk_free"],
            mean_excess_return_period=calc["mean_excess_return"],
            return_volatility_period=calc["volatility"],
            period_sharpe=calc["period_sharpe"],
            annualized_sharpe=calc["annualized_sharpe"],
            annualization_factor=ann_factor,
            sample_size=calc["sample_size"],
            denominator_policy=req.denominator_policy,
            status=calc["status"],
        )
        await self.repo.save_sharpe_result(res)

        return SharpeRatioResponse(
            calculation_code=calc_code,
            scope=req.scope.upper(),
            entity_id=req.entity_id,
            as_of_date=as_of_dt,
            lookback_days=req.lookback_days,
            currency=curr,
            mean_return_period=Decimal(str(round(calc["mean_return"], 8))),
            mean_risk_free_period=Decimal(str(round(calc["mean_risk_free"], 8))),
            mean_excess_return_period=Decimal(str(round(calc["mean_excess_return"], 8))),
            return_volatility_period=Decimal(str(round(calc["volatility"], 8))),
            period_sharpe=Decimal(str(round(calc["period_sharpe"], 6))) if calc["period_sharpe"] is not None else None,
            annualized_sharpe=Decimal(str(round(calc["annualized_sharpe"], 6))) if calc["annualized_sharpe"] is not None else None,
            annualization_factor=req.annualization_factor,
            sample_size=calc["sample_size"],
            denominator_policy=req.denominator_policy,
            status=calc["status"],
        )

    async def calculate_sortino(self, req: SortinoRatioRequest) -> SortinoRatioResponse:
        as_of_dt = datetime.combine(req.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)
        curr = await self._resolve_entity_currency(req.scope, req.entity_id)

        # 1. Resolve entity returns
        ret_series = await self._resolve_returns_for_entity(req.scope, req.entity_id, req.as_of)
        if req.lookback_days and len(ret_series) > req.lookback_days:
            ret_series = ret_series[-req.lookback_days:]

        ret_dates = [r[0] for r in ret_series]
        rp_arr = np.array([float(r[1]) for r in ret_series], dtype=np.float64)

        # 2. Resolve Target Returns
        ann_factor = float(req.annualization_factor)
        if req.target_policy == SortinoTargetPolicy.CONSTANT_PERIOD_TARGET or req.target_policy == SortinoTargetPolicy.ANNUAL_TARGET_CONVERTED_TO_PERIOD:
            mar_ann = float(req.constant_mar_annual) if req.constant_mar_annual is not None else 0.05
            period_mar = convert_rate_to_period_return(mar_ann, RateConvention.EFFECTIVE_ANNUAL_RATE, DayCountConvention.ACTUAL_365, 1)
            target_arr = np.full(len(rp_arr), period_mar, dtype=np.float64)
        else:
            rf_series = await self.resolve_or_create_rate_series(currency=curr, series_code=req.risk_free_series_code)
            target_arr = np.array(await self._resolve_aligned_rf_returns(rf_series, ret_dates), dtype=np.float64)

        # 3. Compute Sortino
        calc = calculate_sortino_ratio(
            returns_portfolio=rp_arr,
            returns_target=target_arr,
            denominator_policy=req.denominator_policy,
            annualization_factor=ann_factor,
        )

        calc_code = f"SORTINO_{uuid4().hex[:12].upper()}"
        res = SortinoRatioResult(
            calculation_code=calc_code,
            scope=req.scope.upper(),
            entity_id=req.entity_id,
            as_of_date=as_of_dt,
            lookback_days=req.lookback_days,
            currency=curr,
            mean_return_period=calc["mean_return"],
            target_return_period=calc["target_return"],
            mean_excess_over_target_period=calc["mean_excess_over_target"],
            downside_deviation_period=calc["downside_deviation"],
            period_sortino=calc["period_sortino"],
            annualized_sortino=calc["annualized_sortino"],
            annualization_factor=ann_factor,
            sample_size=calc["sample_size"],
            downside_periods_count=calc["downside_periods_count"],
            downside_percentage=calc["downside_percentage"],
            target_policy=req.target_policy,
            denominator_policy=req.denominator_policy,
            status=calc["status"],
        )
        await self.repo.save_sortino_result(res)

        return SortinoRatioResponse(
            calculation_code=calc_code,
            scope=req.scope.upper(),
            entity_id=req.entity_id,
            as_of_date=as_of_dt,
            lookback_days=req.lookback_days,
            currency=curr,
            mean_return_period=Decimal(str(round(calc["mean_return"], 8))),
            target_return_period=Decimal(str(round(calc["target_return"], 8))),
            mean_excess_over_target_period=Decimal(str(round(calc["mean_excess_over_target"], 8))),
            downside_deviation_period=Decimal(str(round(calc["downside_deviation"], 8))),
            period_sortino=Decimal(str(round(calc["period_sortino"], 6))) if calc["period_sortino"] is not None else None,
            annualized_sortino=Decimal(str(round(calc["annualized_sortino"], 6))) if calc["annualized_sortino"] is not None else None,
            annualization_factor=req.annualization_factor,
            sample_size=calc["sample_size"],
            downside_periods_count=calc["downside_periods_count"],
            downside_percentage=Decimal(str(round(calc["downside_percentage"], 2))),
            target_policy=req.target_policy,
            denominator_policy=req.denominator_policy,
            status=calc["status"],
        )

    async def calculate_combined(self, req: CombinedRatiosRequest) -> CombinedRatiosResponse:
        sharpe_res = await self.calculate_sharpe(
            SharpeRatioRequest(
                scope=req.scope,
                entity_id=req.entity_id,
                risk_free_series_code=req.risk_free_series_code,
                lookback_days=req.lookback_days,
                as_of=req.as_of,
                denominator_policy=req.sharpe_denominator_policy,
                annualization_factor=req.annualization_factor,
            )
        )
        target_policy = SortinoTargetPolicy.CONSTANT_PERIOD_TARGET if req.constant_mar_annual is not None else SortinoTargetPolicy.RISK_FREE_RATE
        sortino_res = await self.calculate_sortino(
            SortinoRatioRequest(
                scope=req.scope,
                entity_id=req.entity_id,
                risk_free_series_code=req.risk_free_series_code,
                target_policy=target_policy,
                constant_mar_annual=req.constant_mar_annual,
                lookback_days=req.lookback_days,
                as_of=req.as_of,
                denominator_policy=req.sortino_denominator_policy,
                annualization_factor=req.annualization_factor,
            )
        )
        return CombinedRatiosResponse(sharpe=sharpe_res, sortino=sortino_res)

    async def calculate_rolling_ratios(self, req: RollingRatiosRequest) -> RollingRatiosResponse:
        ret_series = await self._resolve_returns_for_entity(req.scope, req.entity_id, req.as_of)
        if len(ret_series) < req.window_days:
            return RollingRatiosResponse(
                scope=req.scope,
                entity_id=req.entity_id,
                window_days=req.window_days,
                annualization_factor=req.annualization_factor,
                points=[],
            )

        curr = await self._resolve_entity_currency(req.scope, req.entity_id)
        rf_series = await self.resolve_or_create_rate_series(currency=curr, series_code=req.risk_free_series_code)
        ret_dates = [r[0] for r in ret_series]
        rf_all = np.array(await self._resolve_aligned_rf_returns(rf_series, ret_dates), dtype=np.float64)
        rp_all = np.array([float(r[1]) for r in ret_series], dtype=np.float64)

        points: List[RollingRatioPoint] = []
        ann_factor = float(req.annualization_factor)

        for i in range(req.window_days, len(ret_series) + 1):
            w_dates = ret_dates[i - req.window_days : i]
            w_rp = rp_all[i - req.window_days : i]
            w_rf = rf_all[i - req.window_days : i]

            sharpe_calc = calculate_sharpe_ratio(
                returns_portfolio=w_rp,
                returns_risk_free=w_rf,
                annualization_factor=ann_factor,
                min_observations=req.window_days // 2,
            )
            sortino_calc = calculate_sortino_ratio(
                returns_portfolio=w_rp,
                returns_target=w_rf,
                annualization_factor=ann_factor,
                min_observations=req.window_days // 2,
            )

            pt_date = w_dates[-1]
            points.append(
                RollingRatioPoint(
                    point_date=pt_date,
                    period_sharpe=Decimal(str(round(sharpe_calc["period_sharpe"], 6))) if sharpe_calc["period_sharpe"] is not None else None,
                    annualized_sharpe=Decimal(str(round(sharpe_calc["annualized_sharpe"], 6))) if sharpe_calc["annualized_sharpe"] is not None else None,
                    period_sortino=Decimal(str(round(sortino_calc["period_sortino"], 6))) if sortino_calc["period_sortino"] is not None else None,
                    annualized_sortino=Decimal(str(round(sortino_calc["annualized_sortino"], 6))) if sortino_calc["annualized_sortino"] is not None else None,
                    volatility=Decimal(str(round(sharpe_calc["volatility"], 8))),
                    downside_deviation=Decimal(str(round(sortino_calc["downside_deviation"], 8))),
                    sample_size=sharpe_calc["sample_size"],
                    status=sharpe_calc["status"],
                )
            )

        return RollingRatiosResponse(
            scope=req.scope,
            entity_id=req.entity_id,
            window_days=req.window_days,
            annualization_factor=req.annualization_factor,
            points=points,
        )
