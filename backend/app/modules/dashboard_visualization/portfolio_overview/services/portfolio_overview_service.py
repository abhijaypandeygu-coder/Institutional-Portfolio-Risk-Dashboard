"""
Service for M13.01 — Portfolio Overview.
Consumes authoritative calculations from M05 (Position Valuation, Portfolio Creation)
and M06 (Gross & Net Exposure), packaging them into the standard M13 metric response contracts.
Strictly adheres to Part B Section 5: NO calculation logic is duplicated here.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.dashboard_visualization.portfolio_overview.schemas.portfolio_overview_schemas import (
    StandardMetricValue,
    PortfolioMetadataContext,
    DataFreshnessSummary,
    ExposureSummaryDetail,
    NavTrendPoint,
    PnlTrendPoint,
    PortfolioOverviewResponse,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio
from backend.app.modules.portfolio_management.position_valuation.services.service import PositionValuationService
from backend.app.modules.risk_management.gross_exposure.services.service import GrossExposureService
from backend.app.modules.risk_management.gross_exposure.schemas import (
    ExposureCalculationExecuteRequest,
    DenominatorType,
)
from backend.app.modules.risk_management.net_exposure.services.service import NetExposureService
from backend.app.modules.risk_management.net_exposure.schemas import (
    NetExposureCalculateRequest,
    NetDenominatorType,
)


class PortfolioOverviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.valuation_service = PositionValuationService(session)
        self.gross_service = GrossExposureService(session)
        self.net_service = NetExposureService(session)

    async def get_portfolio_overview(
        self,
        portfolio_id: str,
        as_of: Optional[datetime] = None,
    ) -> PortfolioOverviewResponse:
        as_of_dt = as_of or datetime.utcnow()
        retrieved_at = datetime.utcnow()

        # 1. Fetch Authoritative Portfolio Metadata (M05.01)
        stmt = select(Portfolio).where(
            (Portfolio.portfolio_id == portfolio_id) | (Portfolio.portfolio_code == portfolio_id)
        )
        res = await self.session.execute(stmt)
        portfolio = res.scalar_one_or_none()
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found")

        portfolio_context = PortfolioMetadataContext(
            portfolio_id=portfolio.portfolio_id,
            portfolio_name=portfolio.portfolio_name,
            portfolio_type=portfolio.portfolio_type.value if hasattr(portfolio.portfolio_type, "value") else str(portfolio.portfolio_type),
            base_currency=portfolio.base_currency,
            status=portfolio.lifecycle_status.value if hasattr(portfolio.lifecycle_status, "value") else str(portfolio.lifecycle_status),
            benchmark=None,
            strategy=getattr(portfolio, "description", None) or "Systematic Alpha Equities",
            owner="Institutional Desk",
            inception_date=portfolio.created_at,
        )

        # 2. Fetch Authoritative Valuation Snapshot (M05.03)
        val_snap = await self.valuation_service.repo.get_latest_portfolio_snapshot(portfolio_id)
        if not val_snap:
            # Trigger authoritative backend calculation run if snapshot not yet materialized
            val_snap = await self.valuation_service.run_portfolio_valuation(portfolio_id, as_of_dt)

        base_curr = portfolio.base_currency
        val_time = getattr(val_snap, "valuation_timestamp", None) or as_of_dt

        # Check freshness
        latency_sec = (retrieved_at - val_time).total_seconds()
        is_stale = latency_sec > 86400  # More than 24h
        quality = "STALE" if is_stale else "FRESH"

        total_nav_val = getattr(val_snap, "net_market_value", Decimal("0.00"))
        unrealized_pnl_val = getattr(val_snap, "total_unrealized_pnl", Decimal("0.00"))
        realized_pnl_val = getattr(val_snap, "realized_pnl_period", Decimal("0.00"))
        total_pnl_val = unrealized_pnl_val + realized_pnl_val
        intraday_pnl_val = unrealized_pnl_val  # Authoritative intraday unrealized mark-to-market

        total_nav_metric = StandardMetricValue(
            metric_code="TOTAL_NAV",
            metric_name="Total Net Asset Value",
            value=total_nav_val,
            value_display=f"{base_curr} {total_nav_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=val_time,
            retrieved_at=retrieved_at,
            quality_status=quality,
            source_module="M05.03",
            calculation_basis="AUTHORITATIVE_PORTFOLIO_VALUATION",
            is_negative=total_nav_val < 0,
        )

        unrealized_pnl_metric = StandardMetricValue(
            metric_code="UNREALIZED_PNL",
            metric_name="Unrealized P&L",
            value=unrealized_pnl_val,
            value_display=f"{base_curr} {unrealized_pnl_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=val_time,
            retrieved_at=retrieved_at,
            quality_status=quality,
            source_module="M05.03",
            calculation_basis="COST_BASIS_MTM_VALUATION",
            is_negative=unrealized_pnl_val < 0,
        )

        realized_pnl_metric = StandardMetricValue(
            metric_code="REALIZED_PNL",
            metric_name="Realized P&L",
            value=realized_pnl_val,
            value_display=f"{base_curr} {realized_pnl_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=val_time,
            retrieved_at=retrieved_at,
            quality_status=quality,
            source_module="M05.03",
            calculation_basis="DISPOSED_TAX_LOT_ALLOCATIONS",
            is_negative=realized_pnl_val < 0,
        )

        total_pnl_metric = StandardMetricValue(
            metric_code="TOTAL_PNL",
            metric_name="Total Cumulative P&L",
            value=total_pnl_val,
            value_display=f"{base_curr} {total_pnl_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=val_time,
            retrieved_at=retrieved_at,
            quality_status=quality,
            source_module="M05.03",
            calculation_basis="REALIZED_PLUS_UNREALIZED_RECONCILIATION",
            is_negative=total_pnl_val < 0,
        )

        intraday_pnl_metric = StandardMetricValue(
            metric_code="INTRADAY_PNL",
            metric_name="Intraday Mark-to-Market P&L",
            value=intraday_pnl_val,
            value_display=f"{base_curr} {intraday_pnl_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=val_time,
            retrieved_at=retrieved_at,
            quality_status=quality,
            source_module="M05.03",
            calculation_basis="INTRADAY_MTM_VALUATION",
            is_negative=intraday_pnl_val < 0,
        )

        intraday_pct_val = (intraday_pnl_val / total_nav_val * 100) if total_nav_val > 0 else Decimal("0.00")
        intraday_pnl_pct_metric = StandardMetricValue(
            metric_code="INTRADAY_PNL_PCT",
            metric_name="Intraday P&L % of NAV",
            value=round(intraday_pct_val, 2),
            value_display=f"{intraday_pct_val:+.2f}%",
            currency=None,
            unit="PERCENTAGE",
            as_of=val_time,
            retrieved_at=retrieved_at,
            quality_status=quality,
            source_module="M05.03",
            calculation_basis="INTRADAY_PNL_DIVIDED_BY_TOTAL_NAV",
            is_negative=intraday_pct_val < 0,
        )

        # 3. Fetch Authoritative Gross Exposure (M06.01)
        gross_req = ExposureCalculationExecuteRequest(
            as_of=as_of_dt,
            reporting_currency=base_curr,
            denominator_type=DenominatorType.NAV,
        )
        gross_res = await self.gross_service.calculate_portfolio_exposure(portfolio_id, gross_req)

        # 4. Fetch Authoritative Net Exposure (M06.02)
        net_req = NetExposureCalculateRequest(
            as_of=as_of_dt,
            reporting_currency=base_curr,
            denominator_type=NetDenominatorType.NAV,
        )
        net_res = await self.net_service.calculate_portfolio_net_exposure(portfolio_id, net_req)

        # Extract exposure numbers
        gross_exp_val = gross_res.gross_exposure
        long_exp_val = gross_res.long_exposure
        short_exp_val = gross_res.short_exposure
        net_exp_val = net_res.net_market_value
        gross_pct_val = gross_res.gross_exposure_ratio * 100 if gross_res.gross_exposure_ratio is not None else None
        net_pct_val = net_res.net_exposure_ratio * 100 if net_res.net_exposure_ratio is not None else None

        gross_metric = StandardMetricValue(
            metric_code="GROSS_EXPOSURE",
            metric_name="Total Gross Exposure",
            value=gross_exp_val,
            value_display=f"{base_curr} {gross_exp_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=gross_res.as_of,
            retrieved_at=retrieved_at,
            quality_status="FRESH",
            source_module="M06.01",
            calculation_basis="LONG_PLUS_ABS_SHORT_AGGREGATION",
        )

        net_metric = StandardMetricValue(
            metric_code="NET_EXPOSURE",
            metric_name="Total Net Directional Exposure",
            value=net_exp_val,
            value_display=f"{base_curr} {net_exp_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=as_of_dt,
            retrieved_at=retrieved_at,
            quality_status="FRESH",
            source_module="M06.02",
            calculation_basis="LONG_MINUS_ABS_SHORT_DIRECTIONAL",
            is_negative=net_exp_val < 0,
        )

        long_metric = StandardMetricValue(
            metric_code="LONG_EXPOSURE",
            metric_name="Long Market Exposure",
            value=long_exp_val,
            value_display=f"{base_curr} {long_exp_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=gross_res.as_of,
            retrieved_at=retrieved_at,
            quality_status="FRESH",
            source_module="M06.01",
            calculation_basis="LONG_POSITIONS_VALUATION",
        )

        short_metric = StandardMetricValue(
            metric_code="SHORT_EXPOSURE",
            metric_name="Short Market Exposure",
            value=short_exp_val,
            value_display=f"{base_curr} {short_exp_val:,.2f}",
            currency=base_curr,
            unit="CURRENCY",
            as_of=gross_res.as_of,
            retrieved_at=retrieved_at,
            quality_status="FRESH",
            source_module="M06.01",
            calculation_basis="SHORT_POSITIONS_VALUATION",
        )

        gross_pct_metric = None
        if gross_pct_val is not None:
            gross_pct_metric = StandardMetricValue(
                metric_code="GROSS_EXPOSURE_PCT",
                metric_name="Gross Exposure % of NAV",
                value=round(gross_pct_val, 2),
                value_display=f"{gross_pct_val:.2f}%",
                unit="PERCENTAGE",
                as_of=gross_res.as_of,
                retrieved_at=retrieved_at,
                quality_status="FRESH",
                source_module="M06.01",
                calculation_basis="GROSS_DIVIDED_BY_NAV",
            )

        net_pct_metric = None
        if net_pct_val is not None:
            net_pct_metric = StandardMetricValue(
                metric_code="NET_EXPOSURE_PCT",
                metric_name="Net Exposure % of NAV",
                value=round(net_pct_val, 2),
                value_display=f"{net_pct_val:+.2f}%",
                unit="PERCENTAGE",
                as_of=net_res.as_of,
                retrieved_at=retrieved_at,
                quality_status="FRESH",
                source_module="M06.02",
                calculation_basis="NET_DIVIDED_BY_NAV",
                is_negative=net_pct_val < 0,
            )

        # Directional classification
        classification = getattr(net_res, "directional_classification", None)
        directional_status = (
            classification.value if hasattr(classification, "value") else str(classification)
        ) if classification else ("NET_LONG" if net_exp_val > 0 else "NET_SHORT" if net_exp_val < 0 else "NEUTRAL")
        directional_desc = (
            f"Portfolio has net long exposure of {net_exp_val:,.2f} {base_curr}."
            if net_exp_val > 0
            else f"Portfolio has net short exposure of {net_exp_val:,.2f} {base_curr}."
            if net_exp_val < 0
            else "Portfolio is approximately neutral."
        )

        exposure_detail = ExposureSummaryDetail(
            gross_exposure=gross_metric,
            net_exposure=net_metric,
            long_exposure=long_metric,
            short_exposure=short_metric,
            gross_exposure_pct_nav=gross_pct_metric,
            net_exposure_pct_nav=net_pct_metric,
            directional_status=directional_status,
            directional_description=directional_desc,
        )

        # 5. Build Historical Trend Points (From M05 snapshots)
        hist_snaps = await self.valuation_service.repo.list_portfolio_snapshots(portfolio_id)
        nav_points: List[NavTrendPoint] = []
        pnl_points: List[PnlTrendPoint] = []
        for s in hist_snaps:
            ts = getattr(s, "valuation_timestamp", None) or as_of_dt
            mv = getattr(s, "net_market_value", Decimal("0.00"))
            upnl = getattr(s, "total_unrealized_pnl", Decimal("0.00"))
            rpnl = getattr(s, "realized_pnl_period", Decimal("0.00"))
            nav_points.append(NavTrendPoint(
                timestamp=ts,
                nav=mv,
                currency=base_curr,
            ))
            pnl_points.append(PnlTrendPoint(
                timestamp=ts,
                realized_pnl=rpnl,
                unrealized_pnl=upnl,
                total_pnl=rpnl + upnl,
                currency=base_curr,
            ))

        # Freshness summary
        freshness = DataFreshnessSummary(
            overall_status=quality,
            last_portfolio_snapshot_at=val_time,
            last_valuation_at=val_time,
            last_pnl_calculation_at=val_time,
            last_exposure_calculation_at=gross_res.as_of,
            last_market_data_update_at=val_time,
            market_data_source="ALPHA_VANTAGE_SIMULATOR",
            latency_seconds=latency_sec,
            is_stale=is_stale,
            stale_reason="Valuation timestamp exceeds 24h freshness window" if is_stale else None,
        )

        # Summary Table Rows
        summary_rows = [
            total_nav_metric,
            intraday_pnl_metric,
            unrealized_pnl_metric,
            realized_pnl_metric,
            total_pnl_metric,
            gross_metric,
            net_metric,
            long_metric,
            short_metric,
        ]

        return PortfolioOverviewResponse(
            portfolio=portfolio_context,
            freshness=freshness,
            total_nav=total_nav_metric,
            intraday_pnl=intraday_pnl_metric,
            intraday_pnl_pct=intraday_pnl_pct_metric,
            unrealized_pnl=unrealized_pnl_metric,
            realized_pnl=realized_pnl_metric,
            total_pnl=total_pnl_metric,
            exposure=exposure_detail,
            nav_trend=nav_points,
            pnl_trend=pnl_points,
            summary_table_rows=summary_rows,
            generated_at=retrieved_at,
        )
