"""
M13.02 — Risk Overview Services.

Implements presentation layer aggregation:
1. VaRPresentationService: Consumes M07.02 (VaRService)
2. ExpectedShortfallPresentationService: Consumes M07.03 (ExpectedShortfallService)
3. VolatilityPresentationService: Consumes M07.01 (HistoricalVolatilityService)
4. DrawdownPresentationService: Consumes M07.04 (DrawdownAnalyticsService)
5. RiskOverviewService: Orchestrates consolidated multi-metric responses with failure isolation.

Adheres strictly to the architectural boundary:
NO risk calculations (VaR, ES, Volatility, Drawdown) are performed here.
All metrics are fetched from M07 or presented with appropriate error/unavailable states.
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.dashboard_visualization.risk_overview.schemas.risk_overview_schemas import (
    MetricState,
    MetricUnit,
    VolatilityType,
    VaRMetricCard,
    ExpectedShortfallMetricCard,
    VolatilityMetricCard,
    DrawdownMetricCard,
    VaRMethodologyDetails,
    ESMethodologyDetails,
    VolatilityMethodologyDetails,
    DrawdownMethodologyDetails,
    VaRESComparisonItem,
    HistoricalTrendPoint,
    UnderwaterChartPoint,
    DrawdownEpisodeSummary,
    DataQualitySummary,
    RiskOverviewResponse,
    RiskHistoryResponse,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio
from backend.app.modules.portfolio_management.position_valuation.models import PortfolioValuationSnapshot
from backend.app.modules.market_risk.value_at_risk.services.service import VaRService
from backend.app.modules.market_risk.value_at_risk.schemas import VaRCalculateRequest
from backend.app.modules.market_risk.value_at_risk.models import VaRMethodology
from backend.app.modules.market_risk.expected_shortfall.services.service import ExpectedShortfallService
from backend.app.modules.market_risk.expected_shortfall.schemas import ESCalculateRequest
from backend.app.modules.market_risk.historical_volatility.services.service import HistoricalVolatilityService
from backend.app.modules.market_risk.historical_volatility.schemas import HistoricalVolatilityCalculateRequest
from backend.app.modules.market_risk.historical_volatility.models import VolatilityScopeType, ReturnFrequency
from backend.app.modules.market_risk.drawdown_analytics.services.service import DrawdownAnalyticsService
from backend.app.modules.market_risk.drawdown_analytics.models import DrawdownScopeType

logger = logging.getLogger(__name__)


class VaRPresentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.var_service = VaRService(session)

    async def get_var_card(
        self,
        portfolio_id: str,
        confidence_level: Decimal = Decimal("0.99"),
        horizon_days: int = 1,
        methodology: str = "HISTORICAL_SIMULATION",
        as_of: Optional[date] = None,
        base_currency: str = "USD",
        portfolio_nav: Optional[Decimal] = None,
    ) -> VaRMetricCard:
        try:
            m07_method = (
                VaRMethodology.HISTORICAL
                if "HISTORICAL" in methodology.upper()
                else VaRMethodology.PARAMETRIC
                if "PARAMETRIC" in methodology.upper()
                else VaRMethodology.MONTE_CARLO
            )

            req = VaRCalculateRequest(
                portfolio_id=portfolio_id,
                methodology=m07_method,
                confidence_level=confidence_level,
                holding_horizon_days=horizon_days,
                reporting_currency=base_currency,
                as_of=as_of,
            )
            res = await self.var_service.calculate_var(req)

            var_amount = res.var_monetary_amount
            var_pct = res.var_return_percentage

            # If pct is missing but amount & nav present, calculate for presentation only
            if var_pct is None and var_amount is not None and portfolio_nav and portfolio_nav > 0:
                var_pct = (var_amount / portfolio_nav) * Decimal("100")

            currency = res.reporting_currency or base_currency
            conf_str = f"{confidence_level * 100:.1f}".rstrip("0").rstrip(".") + "%"

            methodology_details = VaRMethodologyDetails(
                method=res.methodology.value if hasattr(res.methodology, "value") else str(res.methodology),
                return_definition="LOGARITHMIC",
                confidence_level=res.confidence_level,
                horizon_days=res.holding_horizon_days,
                horizon_label=f"{res.holding_horizon_days} trading day{'s' if res.holding_horizon_days > 1 else ''}",
                lookback_window=res.lookback_observations or 252,
                observation_frequency="DAILY",
                valuation_base_type="PORTFOLIO_NAV",
                distribution_assumption=str(res.distribution_assumption) if res.distribution_assumption else None,
                model_version=res.calculation_version or "1.0",
                calculation_timestamp=res.calculated_at or datetime.now(timezone.utc),
                assumptions_summary=f"Calculated via {m07_method.value} with {conf_str} confidence over {horizon_days} day horizon.",
            )

            return VaRMetricCard(
                metric_id="VAR",
                value=var_amount,
                value_display=f"{currency} {var_amount:,.2f}" if var_amount is not None else None,
                currency=currency,
                percentage_of_nav=var_pct,
                percentage_display=f"{var_pct:.2f}%" if var_pct is not None else None,
                confidence_level=res.confidence_level,
                confidence_display=conf_str,
                horizon_days=res.holding_horizon_days,
                horizon_display=f"{res.holding_horizon_days} trading day{'s' if res.holding_horizon_days > 1 else ''}",
                methodology=m07_method.value,
                status=MetricState.VALID,
                calculation_timestamp=res.calculated_at,
                data_quality_status=res.data_quality_status or "FRESH",
                source_module="M07.02",
                methodology_details=methodology_details,
            )
        except Exception as exc:
            logger.warning(f"Error fetching M07.02 VaR for {portfolio_id}: {exc}")
            return VaRMetricCard(
                metric_id="VAR",
                value=None,
                value_display=None,
                currency=base_currency,
                confidence_level=confidence_level,
                confidence_display=f"{confidence_level * 100:.1f}%",
                horizon_days=horizon_days,
                horizon_display=f"{horizon_days} trading day",
                methodology=methodology,
                status=MetricState.ERROR,
                data_quality_status="ERROR",
                source_module="M07.02",
            )


class ExpectedShortfallPresentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.es_service = ExpectedShortfallService(session)

    async def get_es_card(
        self,
        portfolio_id: str,
        confidence_level: Decimal = Decimal("0.99"),
        horizon_days: int = 1,
        methodology: str = "HISTORICAL_SIMULATION",
        as_of: Optional[date] = None,
        base_currency: str = "USD",
        portfolio_nav: Optional[Decimal] = None,
    ) -> ExpectedShortfallMetricCard:
        try:
            req = ESCalculateRequest(
                portfolio_id=portfolio_id,
                methodology=methodology,
                confidence_level=confidence_level,
                holding_horizon_days=horizon_days,
                reporting_currency=base_currency,
                as_of=as_of,
            )
            res = await self.es_service.calculate_expected_shortfall(req)

            es_amount = res.es_monetary_amount
            es_pct = res.es_return_percentage

            if es_pct is None and es_amount is not None and portfolio_nav and portfolio_nav > 0:
                es_pct = (es_amount / portfolio_nav) * Decimal("100")

            currency = res.reporting_currency or base_currency
            conf_str = f"{confidence_level * 100:.1f}".rstrip("0").rstrip(".") + "%"

            methodology_details = ESMethodologyDetails(
                method=str(res.methodology),
                confidence_level=res.confidence_level,
                horizon_days=res.holding_horizon_days,
                horizon_label=f"{res.holding_horizon_days} trading day{'s' if res.holding_horizon_days > 1 else ''}",
                tail_definition="E[L | L >= VaR]",
                tail_weighting_method=str(res.tail_weighting_method or "EQUAL_WEIGHTED"),
                observation_frequency="DAILY",
                estimation_window=res.total_observations_count or 252,
                model_version=res.calculation_version or "1.0",
                calculation_timestamp=res.calculated_at or datetime.now(timezone.utc),
            )

            return ExpectedShortfallMetricCard(
                metric_id="EXPECTED_SHORTFALL",
                value=es_amount,
                value_display=f"{currency} {es_amount:,.2f}" if es_amount is not None else None,
                currency=currency,
                percentage_of_nav=es_pct,
                percentage_display=f"{es_pct:.2f}%" if es_pct is not None else None,
                confidence_level=res.confidence_level,
                confidence_display=conf_str,
                horizon_days=res.holding_horizon_days,
                horizon_display=f"{res.holding_horizon_days} trading day{'s' if res.holding_horizon_days > 1 else ''}",
                methodology=str(res.methodology),
                status=MetricState.VALID,
                calculation_timestamp=res.calculated_at,
                data_quality_status=res.data_quality_status or "FRESH",
                source_module="M07.03",
                methodology_details=methodology_details,
            )
        except Exception as exc:
            logger.warning(f"Error fetching M07.03 ES for {portfolio_id}: {exc}")
            return ExpectedShortfallMetricCard(
                metric_id="EXPECTED_SHORTFALL",
                value=None,
                value_display=None,
                currency=base_currency,
                confidence_level=confidence_level,
                confidence_display=f"{confidence_level * 100:.1f}%",
                horizon_days=horizon_days,
                horizon_display=f"{horizon_days} trading day",
                methodology=methodology,
                status=MetricState.ERROR,
                data_quality_status="ERROR",
                source_module="M07.03",
            )


class VolatilityPresentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vol_service = HistoricalVolatilityService(session)

    async def get_volatility_card(
        self,
        portfolio_id: str,
        lookback_window: int = 60,
        volatility_type: VolatilityType = VolatilityType.REALIZED,
        as_of: Optional[date] = None,
    ) -> VolatilityMetricCard:
        try:
            req = HistoricalVolatilityCalculateRequest(
                portfolio_id=portfolio_id,
                scope_type=VolatilityScopeType.PORTFOLIO,
                lookback_window=lookback_window,
                return_frequency=ReturnFrequency.DAILY,
                as_of=as_of,
            )
            res = await self.vol_service.calculate_historical_volatility(req)

            annualized_vol = res.annualized_volatility
            # Format percentage display (e.g. 18.40%)
            vol_disp = f"{annualized_vol:.2f}%" if annualized_vol is not None else None

            methodology_details = VolatilityMethodologyDetails(
                volatility_type=volatility_type,
                calculation_method=str(res.estimator or "SAMPLE_STD_DEV"),
                return_frequency=str(res.return_frequency or "DAILY"),
                lookback_window=res.lookback_window or lookback_window,
                annualization_factor=res.annualization_factor or Decimal("15.8745"),
                periods_per_year=res.periods_per_year or 252,
                sample_count=res.observation_count or lookback_window,
                model_version=res.calculation_version or "1.0",
                calculation_timestamp=res.calculated_at or datetime.now(timezone.utc),
            )

            return VolatilityMetricCard(
                metric_id="VOLATILITY",
                value=annualized_vol,
                value_display=vol_disp,
                volatility_type=volatility_type,
                is_annualized=True,
                lookback_window=res.lookback_window or lookback_window,
                return_frequency=str(res.return_frequency or "DAILY"),
                estimator=str(res.estimator or "SAMPLE_STD_DEV"),
                status=MetricState.VALID,
                calculation_timestamp=res.calculated_at,
                data_quality_status=res.quality_status or "FRESH",
                source_module="M07.01",
                methodology_details=methodology_details,
            )
        except Exception as exc:
            logger.warning(f"Error fetching M07.01 Volatility for {portfolio_id}: {exc}")
            return VolatilityMetricCard(
                metric_id="VOLATILITY",
                value=None,
                value_display=None,
                volatility_type=volatility_type,
                is_annualized=True,
                lookback_window=lookback_window,
                return_frequency="DAILY",
                estimator="SAMPLE_STD_DEV",
                status=MetricState.ERROR,
                data_quality_status="ERROR",
                source_module="M07.01",
            )


class DrawdownPresentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.dd_service = DrawdownAnalyticsService(session)

    async def get_drawdown_card(
        self,
        portfolio_id: str,
        measurement_period: str = "1_year",
        as_of: Optional[date] = None,
        base_currency: str = "USD",
    ) -> DrawdownMetricCard:
        try:
            summary = await self.dd_service.get_drawdown_summary(
                scope_type=DrawdownScopeType.PORTFOLIO,
                portfolio_id=portfolio_id,
                as_of=as_of,
            )
            curr = summary.current_drawdown
            mdd = summary.maximum_drawdown

            # Sign conventions: preserve negative percentage convention (e.g. -2.40%)
            curr_pct = curr.current_drawdown_percentage
            if curr_pct is not None and curr_pct > 0:
                curr_pct = -curr_pct

            mdd_pct = mdd.maximum_drawdown_percentage
            if mdd_pct is not None and mdd_pct > 0:
                mdd_pct = -mdd_pct

            curr_disp = f"{curr_pct:.2f}%" if curr_pct is not None else None
            mdd_disp = f"{mdd_pct:.2f}%" if mdd_pct is not None else None

            curr_amt = curr.current_drawdown_amount
            curr_amt_disp = f"{base_currency} {curr_amt:,.2f}" if curr_amt is not None else None

            mdd_amt = mdd.maximum_drawdown_amount

            methodology_details = DrawdownMethodologyDetails(
                measurement_period=measurement_period,
                valuation_frequency="DAILY",
                high_water_mark_policy="RUNNING_PEAK",
                nav_basis="NET_ASSET_VALUE",
                cash_flow_adjusted=True,
                calculation_timestamp=curr.latest_observation_timestamp or datetime.now(timezone.utc),
            )

            return DrawdownMetricCard(
                metric_id="DRAWDOWN",
                current_drawdown_pct=curr_pct,
                current_drawdown_display=curr_disp,
                current_drawdown_amount=curr_amt,
                current_drawdown_amount_display=curr_amt_disp,
                maximum_drawdown_pct=mdd_pct,
                maximum_drawdown_display=mdd_disp,
                maximum_drawdown_amount=mdd_amt,
                high_water_mark=curr.running_high_water_mark,
                peak_date=curr.high_water_mark_timestamp,
                trough_date=mdd.trough_timestamp,
                recovery_status=str(mdd.recovery_status) if mdd.recovery_status else "RECOVERING",
                measurement_period=measurement_period,
                status=MetricState.VALID,
                calculation_timestamp=curr.latest_observation_timestamp,
                data_quality_status=curr.data_quality_status or "FRESH",
                source_module="M07.04",
                methodology_details=methodology_details,
            )
        except Exception as exc:
            logger.warning(f"Error fetching M07.04 Drawdown for {portfolio_id}: {exc}")
            return DrawdownMetricCard(
                metric_id="DRAWDOWN",
                current_drawdown_pct=None,
                current_drawdown_display=None,
                maximum_drawdown_pct=None,
                maximum_drawdown_display=None,
                measurement_period=measurement_period,
                status=MetricState.ERROR,
                data_quality_status="ERROR",
                source_module="M07.04",
            )


# ---------------------------------------------------------------------------
# Consolidated Risk Overview Service
# ---------------------------------------------------------------------------

class RiskOverviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.var_service = VaRPresentationService(session)
        self.es_service = ExpectedShortfallPresentationService(session)
        self.vol_service = VolatilityPresentationService(session)
        self.dd_service = DrawdownPresentationService(session)

    async def get_risk_overview(
        self,
        portfolio_id: str,
        as_of: Optional[date] = None,
        confidence_level: Decimal = Decimal("0.99"),
        horizon_days: int = 1,
        var_methodology: str = "HISTORICAL_SIMULATION",
        volatility_lookback: int = 60,
        volatility_type: VolatilityType = VolatilityType.REALIZED,
        drawdown_period: str = "1_year",
    ) -> RiskOverviewResponse:
        # 1. Resolve Portfolio Context
        stmt = select(Portfolio).where(Portfolio.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        portfolio = res.scalar_one_or_none()
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        base_curr = portfolio.base_currency or "USD"
        now_utc = datetime.now(timezone.utc)

        # Retrieve latest portfolio valuation NAV
        snap_stmt = (
            select(PortfolioValuationSnapshot)
            .where(PortfolioValuationSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioValuationSnapshot.valuation_timestamp.desc())
            .limit(1)
        )
        snap_res = await self.session.execute(snap_stmt)
        snap = snap_res.scalar_one_or_none()
        portfolio_nav = snap.net_market_value if snap else None
        last_val_time = snap.valuation_timestamp if snap else None

        # 2. Fetch Metric Cards independently (Failure Isolation)
        var_card = await self.var_service.get_var_card(
            portfolio_id=portfolio_id,
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            methodology=var_methodology,
            as_of=as_of,
            base_currency=base_curr,
            portfolio_nav=portfolio_nav,
        )

        es_card = await self.es_service.get_es_card(
            portfolio_id=portfolio_id,
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            methodology=var_methodology,
            as_of=as_of,
            base_currency=base_curr,
            portfolio_nav=portfolio_nav,
        )

        vol_card = await self.vol_service.get_volatility_card(
            portfolio_id=portfolio_id,
            lookback_window=volatility_lookback,
            volatility_type=volatility_type,
            as_of=as_of,
        )

        dd_card = await self.dd_service.get_drawdown_card(
            portfolio_id=portfolio_id,
            measurement_period=drawdown_period,
            as_of=as_of,
            base_currency=base_curr,
        )

        # 3. VaR vs ES Comparison Component
        is_compatible = (
            var_card.confidence_level == es_card.confidence_level
            and var_card.horizon_days == es_card.horizon_days
            and var_card.status == MetricState.VALID
            and es_card.status == MetricState.VALID
        )
        compat_note = None if is_compatible else "VaR and Expected Shortfall configurations or statuses do not match."

        tail_excess_amt = (
            (es_card.value - var_card.value)
            if (es_card.value is not None and var_card.value is not None)
            else None
        )
        tail_excess_pct = (
            (es_card.percentage_of_nav - var_card.percentage_of_nav)
            if (es_card.percentage_of_nav is not None and var_card.percentage_of_nav is not None)
            else None
        )
        es_to_var_ratio = (
            (es_card.value / var_card.value)
            if (es_card.value is not None and var_card.value is not None and var_card.value > 0)
            else None
        )

        var_es_comparison = VaRESComparisonItem(
            portfolio_id=portfolio_id,
            reporting_currency=base_curr,
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            var_monetary_amount=var_card.value,
            var_percentage_of_nav=var_card.percentage_of_nav,
            es_monetary_amount=es_card.value,
            es_percentage_of_nav=es_card.percentage_of_nav,
            tail_excess_amount=tail_excess_amt,
            tail_excess_pct=tail_excess_pct,
            es_to_var_ratio=es_to_var_ratio,
            is_compatible=is_compatible,
            compatibility_note=compat_note,
        )

        # 4. Data Quality Summary
        stale_list = []
        failed_list = []
        quality_notes = []

        for name, card in [("VaR", var_card), ("Expected Shortfall", es_card), ("Volatility", vol_card), ("Drawdown", dd_card)]:
            if card.status == MetricState.ERROR:
                failed_list.append(name)
            elif card.status == MetricState.STALE or card.data_quality_status == "STALE":
                stale_list.append(name)

        overall_status = MetricState.ERROR if len(failed_list) == 4 else (
            MetricState.INCOMPLETE if failed_list else (
                MetricState.STALE if stale_list else MetricState.VALID
            )
        )

        if failed_list:
            quality_notes.append(f"Authoritative calculations failed for: {', '.join(failed_list)}")
        if stale_list:
            quality_notes.append(f"Stale data detected for: {', '.join(stale_list)}")

        quality_summary = DataQualitySummary(
            overall_status=overall_status,
            last_valuation_timestamp=last_val_time,
            last_risk_run_timestamp=now_utc,
            stale_metrics=stale_list,
            failed_metrics=failed_list,
            quality_notes=quality_notes,
        )

        return RiskOverviewResponse(
            portfolio_id=portfolio_id,
            portfolio_name=portfolio.portfolio_name,
            base_currency=base_curr,
            as_of=last_val_time or now_utc,
            generated_at=now_utc,
            valuation_nav=portfolio_nav,
            var=var_card,
            expected_shortfall=es_card,
            volatility=vol_card,
            drawdown=dd_card,
            var_es_comparison=var_es_comparison,
            quality_summary=quality_summary,
        )

    async def get_metric_history(
        self,
        portfolio_id: str,
        metric: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        confidence_level: Decimal = Decimal("0.99"),
        horizon_days: int = 1,
        lookback_window: int = 60,
    ) -> RiskHistoryResponse:
        metric_upper = metric.upper()
        stmt = select(Portfolio).where(Portfolio.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        portfolio = res.scalar_one_or_none()
        base_curr = portfolio.base_currency if portfolio else "USD"

        points: List[HistoricalTrendPoint] = []
        underwater_points: Optional[List[UnderwaterChartPoint]] = None
        episodes: Optional[List[DrawdownEpisodeSummary]] = None

        if metric_upper == "VAR":
            try:
                hist_res = await self.var_service.var_service.get_var_history_trend(
                    portfolio_id=portfolio_id,
                    from_date=start_date,
                    to_date=end_date,
                )
                for pt in hist_res.points:
                    points.append(
                        HistoricalTrendPoint(
                            observation_date=pt.as_of_date,
                            value=pt.var_monetary_amount,
                            percentage=pt.var_return_percentage,
                            currency=base_curr,
                            methodology=str(pt.methodology),
                            confidence_level=pt.confidence_level,
                            horizon_days=pt.holding_horizon_days,
                            status=MetricState.VALID,
                        )
                    )
            except Exception as exc:
                logger.warning(f"Error fetching VaR history for {portfolio_id}: {exc}")

        elif metric_upper in ("EXPECTED_SHORTFALL", "ES"):
            try:
                hist_res = await self.es_service.es_service.get_historical_trend(
                    portfolio_id=portfolio_id,
                    lookback_points=30,
                )
                for pt in hist_res.points:
                    points.append(
                        HistoricalTrendPoint(
                            observation_date=pt.as_of_date,
                            value=pt.es_monetary_amount,
                            percentage=pt.es_return_percentage,
                            currency=base_curr,
                            methodology=str(pt.methodology),
                            confidence_level=pt.confidence_level,
                            horizon_days=pt.holding_horizon_days,
                            status=MetricState.VALID,
                        )
                    )
            except Exception as exc:
                logger.warning(f"Error fetching ES history for {portfolio_id}: {exc}")

        elif metric_upper == "VOLATILITY":
            try:
                hist_res = await self.vol_service.vol_service.calculate_rolling_volatility_series(
                    portfolio_id=portfolio_id,
                    lookback_window=lookback_window,
                    from_date=start_date,
                    to_date=end_date,
                )
                for pt in hist_res.points:
                    points.append(
                        HistoricalTrendPoint(
                            observation_date=pt.as_of_date,
                            value=pt.annualized_volatility,
                            percentage=pt.annualized_volatility,
                            currency=None,
                            methodology="ROLLING_HISTORICAL",
                            status=MetricState.VALID,
                        )
                    )
            except Exception as exc:
                logger.warning(f"Error fetching Volatility history for {portfolio_id}: {exc}")

        elif metric_upper == "DRAWDOWN":
            try:
                hist_res = await self.dd_service.dd_service.get_drawdown_history(
                    scope_type=DrawdownScopeType.PORTFOLIO,
                    portfolio_id=portfolio_id,
                    as_of=end_date,
                    limit=252,
                )
                underwater_points = []
                for pt in hist_res.points:
                    dd_pct = pt.drawdown_percentage
                    if dd_pct is not None and dd_pct > 0:
                        dd_pct = -dd_pct
                    underwater_points.append(
                        UnderwaterChartPoint(
                            observation_date=pt.observation_timestamp.date() if isinstance(pt.observation_timestamp, datetime) else pt.observation_timestamp,
                            portfolio_nav=pt.value,
                            high_water_mark=pt.high_water_mark,
                            drawdown_pct=dd_pct or Decimal("0"),
                            drawdown_amount=pt.drawdown_amount or Decimal("0"),
                            is_peak=pt.is_peak,
                            is_trough=pt.is_trough,
                            is_recovered=pt.is_recovered,
                            episode_id=pt.episode_id,
                        )
                    )
            except Exception as exc:
                logger.warning(f"Error fetching Drawdown history for {portfolio_id}: {exc}")

        return RiskHistoryResponse(
            portfolio_id=portfolio_id,
            metric=metric_upper,
            reporting_currency=base_curr,
            points=points,
            underwater_points=underwater_points,
            episodes=episodes,
        )
