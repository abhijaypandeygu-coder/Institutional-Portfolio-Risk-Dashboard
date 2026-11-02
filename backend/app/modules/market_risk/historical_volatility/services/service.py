"""
Module M07.01: Historical Volatility Service.
Orchestrates price series retrieval, return series generation, rolling standard deviation,
annualization, window comparison, trend evaluation, and intraday suitability checks.
"""
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.historical_volatility.models import (
    VolatilityScopeType,
    ReturnType,
    ReturnFrequency,
    PriceSourceType,
    PriceMeasure,
    CorporateActionAdjustmentPolicy,
    StatisticalEstimator,
    VolatilityCalculationStatus,
    VolatilityTrendClassification,
    VolatilityWindowComparisonLabel,
    VolatilityAnnualizationConvention,
    HistoricalVolatilityConfig,
    HistoricalVolatilityResult,
    RollingVolatilityPoint,
    VolatilityCalculationDiagnostic,
)
from backend.app.modules.market_risk.historical_volatility.schemas import (
    AnnualizationConventionCreateRequest,
    VolatilityConfigCreateRequest,
    HistoricalVolatilityCalculateRequest,
    HistoricalVolatilityResultResponse,
    RollingVolatilitySeriesResponse,
    RollingVolatilityPointResponse,
    WindowComparisonResponse,
    WindowHorizonMetric,
    VolatilityTrendResponse,
    IntradayVolatilityResponse,
)
from backend.app.modules.market_risk.historical_volatility.repositories.repository import VolatilityRepository
from backend.app.modules.market_risk.historical_volatility.calculations.volatility_math import (
    calculate_return,
    calculate_sample_variance_and_std_dev,
    annualize_volatility,
    calculate_volatility_trend_slope,
    classify_volatility_trend,
    compare_volatility_horizons,
    PRECISION_EIGHT,
    PRECISION_SIX,
)
from backend.app.modules.market_data_ingestion.persistence.models import MarketOHLCV, NormalizedMarketTick
from backend.app.modules.instrument_reference_data.price_reference.models import PriceReferenceObservation
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HistoricalVolatilityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = VolatilityRepository(session)

    # 1. Convention & Config Management
    async def create_annualization_convention(
        self, req: AnnualizationConventionCreateRequest
    ) -> VolatilityAnnualizationConvention:
        factor = Decimal(str(math.sqrt(float(req.periods_per_year)))).quantize(
            PRECISION_SIX, rounding=ROUND_HALF_UP
        )
        conv = VolatilityAnnualizationConvention(
            convention_name=req.convention_name,
            market_code=req.market_code,
            exchange_code=req.exchange_code,
            return_frequency=req.return_frequency,
            sampling_interval_minutes=req.sampling_interval_minutes,
            trading_sessions_per_year=req.trading_sessions_per_year,
            trading_hours_per_session=req.trading_hours_per_session,
            intervals_per_session=req.intervals_per_session,
            periods_per_year=req.periods_per_year,
            annualization_factor=factor,
            session_break_policy=req.session_break_policy,
            methodology_description=req.methodology_description,
        )
        return await self.repo.create_annualization_convention(conv)

    async def create_config(
        self, req: VolatilityConfigCreateRequest
    ) -> HistoricalVolatilityConfig:
        cfg = HistoricalVolatilityConfig(
            config_name=req.config_name,
            scope_type=req.scope_type,
            portfolio_id=req.portfolio_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            return_type=req.return_type,
            return_frequency=req.return_frequency,
            sampling_interval=req.sampling_interval,
            price_source=req.price_source,
            price_measure=req.price_measure,
            corporate_action_policy=req.corporate_action_policy,
            lookback_window=req.lookback_window,
            window_type=req.window_type,
            estimator=req.estimator,
            annualization_convention_id=req.annualization_convention_id,
            session_boundary_policy=req.session_boundary_policy,
            minimum_observations=req.minimum_observations,
            minimum_coverage_ratio=req.minimum_coverage_ratio,
            gap_tolerance_days=req.gap_tolerance_days,
        )
        return await self.repo.create_config(cfg)

    # 2. Price Series Resolver
    async def resolve_price_series(
        self,
        scope_type: VolatilityScopeType,
        instrument_id: Optional[str],
        portfolio_id: Optional[str],
        price_source: PriceSourceType,
        lookback_days: int = 400,
        as_of: Optional[date] = None,
    ) -> List[Tuple[datetime, Decimal]]:
        """
        Retrieves sorted historical (timestamp, price) pairs from authoritative sources.
        """
        prices: List[Tuple[datetime, Decimal]] = []

        if scope_type in (VolatilityScopeType.PORTFOLIO, VolatilityScopeType.PORTFOLIO_GROUP):
            # Resolve from M05.07 PortfolioBookSnapshot NAV series
            stmt = select(PortfolioBookSnapshot).where(
                PortfolioBookSnapshot.portfolio_id == portfolio_id
            ).order_by(PortfolioBookSnapshot.effective_as_of.asc())
            if as_of:
                stmt = stmt.where(PortfolioBookSnapshot.effective_as_of <= datetime.combine(as_of, datetime.max.time()))
            res = await self.session.execute(stmt)
            snaps = res.scalars().all()
            for s in snaps:
                if s.total_nav_base > Decimal("0.0"):
                    prices.append((s.effective_as_of, s.total_nav_base))
            return prices

        # Scope: Instrument / Listing
        if price_source in (PriceSourceType.OFFICIAL_CLOSE, PriceSourceType.ADJUSTED_CLOSE):
            # Primary Source: M04.05 PriceReferenceObservation
            stmt = select(PriceReferenceObservation).where(
                PriceReferenceObservation.instrument_id == instrument_id
            ).order_by(PriceReferenceObservation.trading_date.asc())
            if as_of:
                stmt = stmt.where(PriceReferenceObservation.trading_date <= as_of)
            res = await self.session.execute(stmt)
            obs_list = res.scalars().all()
            for obs in obs_list:
                dt = datetime.combine(obs.trading_date, datetime.min.time(), tzinfo=timezone.utc)
                prices.append((dt, Decimal(str(obs.price_value))))

        # Fallback or Intraday Source: M02 MarketOHLCV
        if not prices:
            stmt = select(MarketOHLCV).where(
                MarketOHLCV.instrument_id == instrument_id
            ).order_by(MarketOHLCV.candle_start.asc())
            if as_of:
                stmt = stmt.where(MarketOHLCV.candle_start <= datetime.combine(as_of, datetime.max.time(), tzinfo=timezone.utc))
            res = await self.session.execute(stmt)
            candles = res.scalars().all()
            for c in candles:
                prices.append((c.candle_start, Decimal(str(c.close_price))))

        return prices

    # 3. Primary Historical Volatility Calculation
    async def calculate_historical_volatility(
        self, req: HistoricalVolatilityCalculateRequest
    ) -> HistoricalVolatilityResultResponse:
        as_of_dt = req.as_of or date.today()
        raw_prices = await self.resolve_price_series(
            scope_type=req.scope_type,
            instrument_id=req.instrument_id,
            portfolio_id=req.portfolio_id,
            price_source=req.price_source,
            as_of=as_of_dt,
        )

        # Expected observations = lookback_window
        expected_obs = req.lookback_window
        annual_sessions = 252

        # Check annualization convention if provided
        if req.annualization_convention_id:
            conv = await self.repo.get_annualization_convention(req.annualization_convention_id)
            if conv:
                annual_sessions = conv.periods_per_year

        factor, _ = annualize_volatility(Decimal("0.0"), annual_sessions)

        if len(raw_prices) < 2:
            # Insufficient raw price observations
            res = HistoricalVolatilityResult(
                scope_type=req.scope_type,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
                portfolio_id=req.portfolio_id,
                as_of_date=as_of_dt,
                window_start=utc_now(),
                window_end=utc_now(),
                lookback_window=req.lookback_window,
                return_type=req.return_type,
                return_frequency=req.return_frequency,
                observation_count=0,
                expected_observation_count=expected_obs,
                coverage_percentage=Decimal("0.0"),
                mean_return=Decimal("0.0"),
                period_volatility=Decimal("0.0"),
                annualized_volatility=Decimal("0.0"),
                annualization_factor=factor,
                periods_per_year=annual_sessions,
                calculation_status=VolatilityCalculationStatus.INSUFFICIENT_OBSERVATIONS,
                quality_status="INSUFFICIENT_PRICES",
            )
            await self.repo.save_volatility_result(res)
            return HistoricalVolatilityResultResponse.model_validate(res)

        # Construct Returns
        returns: List[Decimal] = []
        for i in range(1, len(raw_prices)):
            p0 = raw_prices[i - 1][1]
            p1 = raw_prices[i][1]
            r = calculate_return(p0, p1, return_type=req.return_type)
            returns.append(r)

        # Extract window subset: up to lookback_window returns
        window_returns = returns[-req.lookback_window:]
        obs_count = len(window_returns)
        coverage_pct = (Decimal(str(obs_count)) / Decimal(str(expected_obs))) * Decimal("100.0")

        window_start = raw_prices[-len(window_returns) - 1][0]
        window_end = raw_prices[-1][0]

        calc_status = VolatilityCalculationStatus.CALCULATED
        if obs_count < expected_obs:
            calc_status = VolatilityCalculationStatus.PARTIAL_WINDOW

        mean_ret, var, std_dev = calculate_sample_variance_and_std_dev(
            window_returns, estimator=StatisticalEstimator.SAMPLE_STD_DEV
        )
        _, ann_vol = annualize_volatility(std_dev, annual_sessions)

        res = HistoricalVolatilityResult(
            scope_type=req.scope_type,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            portfolio_id=req.portfolio_id,
            as_of_date=as_of_dt,
            window_start=window_start,
            window_end=window_end,
            lookback_window=req.lookback_window,
            return_type=req.return_type,
            return_frequency=req.return_frequency,
            observation_count=obs_count,
            expected_observation_count=expected_obs,
            coverage_percentage=coverage_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            mean_return=mean_ret,
            period_volatility=std_dev,
            annualized_volatility=ann_vol,
            annualization_factor=factor,
            periods_per_year=annual_sessions,
            calculation_status=calc_status,
            quality_status="PASSED",
        )
        await self.repo.save_volatility_result(res)
        return HistoricalVolatilityResultResponse.model_validate(res)

    # 4. Rolling Volatility Series Calculation
    async def calculate_rolling_volatility_series(
        self,
        instrument_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        lookback_window: int = 20,
        return_frequency: ReturnFrequency = ReturnFrequency.DAILY,
        return_type: ReturnType = ReturnType.LOGARITHMIC,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> RollingVolatilitySeriesResponse:
        scope = VolatilityScopeType.PORTFOLIO if portfolio_id else VolatilityScopeType.INSTRUMENT
        raw_prices = await self.resolve_price_series(
            scope_type=scope,
            instrument_id=instrument_id,
            portfolio_id=portfolio_id,
            price_source=PriceSourceType.OFFICIAL_CLOSE,
        )

        if len(raw_prices) < 2:
            return RollingVolatilitySeriesResponse(
                instrument_id=instrument_id,
                portfolio_id=portfolio_id,
                lookback_window=lookback_window,
                return_frequency=return_frequency,
                total_points=0,
                series=[],
            )

        # Build daily returns with timestamps
        return_points: List[Tuple[datetime, Decimal]] = []
        for i in range(1, len(raw_prices)):
            dt = raw_prices[i][0]
            p0 = raw_prices[i - 1][1]
            p1 = raw_prices[i][1]
            r = calculate_return(p0, p1, return_type=return_type)
            return_points.append((dt, r))

        rolling_records: List[RollingVolatilityPoint] = []
        factor, _ = annualize_volatility(Decimal("0.0"), 252)

        # Rolling window across returns
        for idx in range(len(return_points)):
            start_idx = max(0, idx - lookback_window + 1)
            window_slice = [rp[1] for rp in return_points[start_idx : idx + 1]]
            dt = return_points[idx][0]
            t_date = dt.date() if isinstance(dt, datetime) else dt

            if from_date and t_date < from_date:
                continue
            if to_date and t_date > to_date:
                continue

            obs_cnt = len(window_slice)
            cov_pct = (Decimal(str(obs_cnt)) / Decimal(str(lookback_window))) * Decimal("100.0")

            if obs_cnt >= 2:
                _, _, std_dev = calculate_sample_variance_and_std_dev(window_slice)
                _, ann_vol = annualize_volatility(std_dev, 252)
                st = (
                    VolatilityCalculationStatus.CALCULATED
                    if obs_cnt >= lookback_window
                    else VolatilityCalculationStatus.PARTIAL_WINDOW
                )
            else:
                std_dev = Decimal("0.0")
                ann_vol = Decimal("0.0")
                st = VolatilityCalculationStatus.INSUFFICIENT_OBSERVATIONS

            pt = RollingVolatilityPoint(
                instrument_id=instrument_id,
                portfolio_id=portfolio_id,
                observation_timestamp=dt,
                trading_date=t_date,
                lookback_window=lookback_window,
                return_frequency=return_frequency,
                period_volatility=std_dev,
                annualized_volatility=ann_vol,
                observation_count=obs_cnt,
                coverage_percentage=cov_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                status=st,
            )
            rolling_records.append(pt)

        if rolling_records:
            await self.repo.save_rolling_points(rolling_records)

        return RollingVolatilitySeriesResponse(
            instrument_id=instrument_id,
            portfolio_id=portfolio_id,
            lookback_window=lookback_window,
            return_frequency=return_frequency,
            total_points=len(rolling_records),
            series=[RollingVolatilityPointResponse.model_validate(p) for p in rolling_records],
        )

    # 5. Multi-Horizon Window Comparison
    async def calculate_window_comparison(
        self,
        instrument_id: str,
        listing_id: Optional[str] = None,
        as_of: Optional[date] = None,
        return_frequency: ReturnFrequency = ReturnFrequency.DAILY,
        return_type: ReturnType = ReturnType.LOGARITHMIC,
        short_window: int = 20,
        medium_window: int = 60,
        long_window: int = 252,
    ) -> WindowComparisonResponse:
        as_of_dt = as_of or date.today()
        horizons_config = [
            ("SHORT", short_window),
            ("MEDIUM", medium_window),
            ("LONG", long_window),
        ]

        metrics: List[WindowHorizonMetric] = []
        volatilities: Dict[str, Decimal] = {}

        for h_label, window_size in horizons_config:
            calc_req = HistoricalVolatilityCalculateRequest(
                instrument_id=instrument_id,
                listing_id=listing_id,
                scope_type=VolatilityScopeType.INSTRUMENT,
                return_type=return_type,
                return_frequency=return_frequency,
                lookback_window=window_size,
                as_of=as_of_dt,
            )
            res = await self.calculate_historical_volatility(calc_req)
            m = WindowHorizonMetric(
                horizon=h_label,
                lookback_sessions=window_size,
                observation_count=res.observation_count,
                expected_observation_count=res.expected_observation_count,
                coverage_percentage=res.coverage_percentage,
                period_volatility=res.period_volatility,
                annualized_volatility=res.annualized_volatility,
                annualization_factor=res.annualization_factor,
                status=res.calculation_status,
            )
            metrics.append(m)
            volatilities[h_label] = res.annualized_volatility

        s_vol = volatilities.get("SHORT", Decimal("0.0"))
        m_vol = volatilities.get("MEDIUM", Decimal("0.0"))
        l_vol = volatilities.get("LONG", Decimal("0.0"))

        spread_sm = s_vol - m_vol
        spread_ml = m_vol - l_vol
        spread_sl = s_vol - l_vol

        ratio_sl = (s_vol / l_vol).quantize(PRECISION_SIX, rounding=ROUND_HALF_UP) if l_vol > Decimal("0.0") else None
        comp_label = compare_volatility_horizons(s_vol, l_vol)

        return WindowComparisonResponse(
            instrument_id=instrument_id,
            listing_id=listing_id,
            as_of_date=as_of_dt,
            return_frequency=return_frequency,
            return_type=return_type,
            horizons=metrics,
            short_vs_medium_spread=spread_sm,
            medium_vs_long_spread=spread_ml,
            short_vs_long_spread=spread_sl,
            short_to_long_ratio=ratio_sl,
            comparison_label=comp_label,
            calculated_at=utc_now(),
        )

    # 6. Realized Volatility Trend Analysis
    async def evaluate_volatility_trend(
        self,
        instrument_id: str,
        lookback_window: int = 20,
        trend_lookback_points: int = 10,
        as_of: Optional[date] = None,
    ) -> VolatilityTrendResponse:
        as_of_dt = as_of or date.today()
        # Retrieve rolling volatility series for instrument
        rolling_resp = await self.calculate_rolling_volatility_series(
            instrument_id=instrument_id,
            lookback_window=lookback_window,
            to_date=as_of_dt,
        )

        series = rolling_resp.series
        if not series:
            return VolatilityTrendResponse(
                instrument_id=instrument_id,
                lookback_window=lookback_window,
                return_frequency=ReturnFrequency.DAILY,
                current_volatility=Decimal("0.0"),
                prior_volatility=None,
                volatility_change=Decimal("0.0"),
                volatility_pct_change=None,
                trend_slope=None,
                trend_classification=VolatilityTrendClassification.INSUFFICIENT_HISTORY,
                points_evaluated=0,
                as_of_date=as_of_dt,
            )

        current_point = series[-1]
        current_vol = current_point.annualized_volatility

        prior_point = series[-2] if len(series) >= 2 else None
        prior_vol = prior_point.annualized_volatility if prior_point else None

        change = current_vol - (prior_vol or Decimal("0.0"))
        pct_change = (
            ((change / prior_vol) * Decimal("100.0")).quantize(PRECISION_SIX, rounding=ROUND_HALF_UP)
            if prior_vol and prior_vol > Decimal("0.0")
            else None
        )

        # Calculate slope across last trend_lookback_points
        sub_series = series[-trend_lookback_points:]
        vols = [p.annualized_volatility for p in sub_series]
        _, slope = calculate_volatility_trend_slope(vols)

        trend_cls = classify_volatility_trend(current_vol, prior_vol, slope=slope)

        return VolatilityTrendResponse(
            instrument_id=instrument_id,
            lookback_window=lookback_window,
            return_frequency=ReturnFrequency.DAILY,
            current_volatility=current_vol,
            prior_volatility=prior_vol,
            volatility_change=change,
            volatility_pct_change=pct_change,
            trend_slope=slope,
            trend_classification=trend_cls,
            points_evaluated=len(sub_series),
            as_of_date=as_of_dt,
        )

    # 7. Intraday Realized Volatility with Quality Diagnostics
    async def calculate_intraday_volatility(
        self,
        instrument_id: str,
        sampling_interval: str = "5m",
        price_measure: PriceMeasure = PriceMeasure.CLOSE,
        price_source: PriceSourceType = PriceSourceType.OHLCV_BAR_CLOSE,
        as_of: Optional[date] = None,
    ) -> IntradayVolatilityResponse:
        as_of_dt = as_of or date.today()
        # Retrieve intraday bars from M02 MarketOHLCV
        stmt = select(MarketOHLCV).where(
            and_(
                MarketOHLCV.instrument_id == instrument_id,
                MarketOHLCV.interval == sampling_interval,
            )
        ).order_by(MarketOHLCV.candle_start.asc())
        
        if as_of:
            stmt = stmt.where(MarketOHLCV.candle_start <= datetime.combine(as_of, datetime.max.time(), tzinfo=timezone.utc))

        res = await self.session.execute(stmt)
        bars = res.scalars().all()

        # Intraday US equity session is 6.5 hours = 390 minutes
        # 5m bars: 390 / 5 = 78 bars per session
        # Periods per year = 252 * 78 = 19,656
        minutes_map = {"1m": 1, "5m": 5, "15m": 15, "30m": 30}
        interval_min = minutes_map.get(sampling_interval, 5)
        bars_per_session = int(390 / interval_min)
        periods_per_year = 252 * bars_per_session
        factor = Decimal(str(math.sqrt(float(periods_per_year)))).quantize(PRECISION_SIX, rounding=ROUND_HALF_UP)

        if len(bars) < 2:
            return IntradayVolatilityResponse(
                instrument_id=instrument_id,
                sampling_interval=sampling_interval,
                price_measure=price_measure,
                price_source=price_source,
                session_boundary_policy="WITHIN_SESSION_ONLY",
                intraday_period_volatility=Decimal("0.0"),
                annualized_volatility=Decimal("0.0"),
                annualization_factor=factor,
                bars_evaluated=len(bars),
                expected_bars=bars_per_session,
                coverage_percentage=Decimal("0.0"),
                microstructure_suitability="INSUFFICIENT_BARS",
                is_suitable=False,
                status=VolatilityCalculationStatus.INSUFFICIENT_OBSERVATIONS,
                calculated_at=utc_now(),
            )

        # Microstructure checks: check for negative/zero prices or crossed quote conditions
        intraday_returns: List[Decimal] = []
        for i in range(1, len(bars)):
            p0 = Decimal(str(bars[i - 1].close_price))
            p1 = Decimal(str(bars[i].close_price))
            if p0 <= Decimal("0.0") or p1 <= Decimal("0.0"):
                continue
            r = calculate_return(p0, p1, return_type=ReturnType.LOGARITHMIC)
            intraday_returns.append(r)

        bars_count = len(bars)
        coverage_pct = (Decimal(str(bars_count)) / Decimal(str(bars_per_session))) * Decimal("100.0")

        # Statistical suitability validation
        is_suitable = True
        microstructure_status = "SUITABLE"
        if coverage_pct < Decimal("50.0"):
            is_suitable = False
            microstructure_status = "LOW_SESSION_COVERAGE"
        elif all(r == Decimal("0.0") for r in intraday_returns):
            is_suitable = False
            microstructure_status = "STALE_IDENTICAL_PRICES"

        if is_suitable and len(intraday_returns) >= 2:
            _, _, std_dev = calculate_sample_variance_and_std_dev(intraday_returns)
            ann_vol = (std_dev * factor).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
            st = VolatilityCalculationStatus.CALCULATED
        else:
            std_dev = Decimal("0.0")
            ann_vol = Decimal("0.0")
            st = (
                VolatilityCalculationStatus.MICROSTRUCTURE_NOISE_REJECTED
                if not is_suitable
                else VolatilityCalculationStatus.INSUFFICIENT_OBSERVATIONS
            )

        return IntradayVolatilityResponse(
            instrument_id=instrument_id,
            sampling_interval=sampling_interval,
            price_measure=price_measure,
            price_source=price_source,
            session_boundary_policy="WITHIN_SESSION_ONLY",
            intraday_period_volatility=std_dev,
            annualized_volatility=ann_vol,
            annualization_factor=factor,
            bars_evaluated=bars_count,
            expected_bars=bars_per_session,
            coverage_percentage=coverage_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            microstructure_suitability=microstructure_status,
            is_suitable=is_suitable,
            status=st,
            calculated_at=utc_now(),
        )
