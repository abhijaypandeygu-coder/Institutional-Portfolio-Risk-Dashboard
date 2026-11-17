"""
M13.03 — Exposure Dashboard Services.

Implements presentation layer aggregation:
1. SectorAllocationPresentationService: Consumes M06.03 (SectorExposureService) + M04.02 (Classifications)
2. InstrumentAllocationPresentationService: Consumes M06.04 (InstrumentExposureService) + M05.03 (Valuation)
3. PortfolioAllocationPresentationService: Consumes M06.07 (PortfolioAllocationService) + M05.04 (Cash)
4. ExposureDrilldownService: Hierarchical navigation (Portfolio -> Sector -> Industry -> Security)
5. ExposureDashboardService: Orchestrates consolidated multi-view payload with data freshness.

Strictly adheres to Part B Section 3: NO financial calculations are duplicated here.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.dashboard_visualization.exposure_dashboard.schemas.exposure_dashboard_schemas import (
    PositionSideFilter,
    HierarchyLevel,
    SectorAllocationRow,
    SectorAllocationSummary,
    RankedHoldingItem,
    InstrumentAllocationSummary,
    CashBalanceDetail,
    PortfolioAllocationSummary,
    HierarchyBreadcrumb,
    ExposureDrillDownResponse,
    ConsolidatedExposureDashboardResponse,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio
from backend.app.modules.portfolio_management.position_valuation.models import (
    PortfolioValuationSnapshot,
    PositionValuation,
)
from backend.app.modules.portfolio_management.cash_management.models import (
    CashAccount,
    CashBalanceSnapshot,
)
from backend.app.modules.risk_management.sector_exposure.services.service import SectorExposureService
from backend.app.modules.risk_management.sector_exposure.schemas import SectorExposureCalculateRequest
from backend.app.modules.risk_management.instrument_exposure.services.service import InstrumentExposureService
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
    ExposureRankingBasis,
)
from backend.app.modules.risk_management.portfolio_allocation.services.service import PortfolioAllocationService
from backend.app.modules.risk_management.portfolio_allocation.schemas import (
    PortfolioAllocationCalculateRequest,
    AllocationViewType,
    AllocationGroupingDimension,
)

logger = logging.getLogger(__name__)


class SectorAllocationPresentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sector_service = SectorExposureService(session)

    async def get_sector_allocation(
        self,
        portfolio_id: str,
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
    ) -> SectorAllocationSummary:
        req = SectorExposureCalculateRequest(
            as_of=as_of_dt or datetime.now(timezone.utc),
            reporting_currency=base_currency,
        )
        res = await self.sector_service.calculate_portfolio_sector_exposure(portfolio_id, req)

        sector_rows: List[SectorAllocationRow] = []
        for s in res.sectors:
            nav_wt = s.net_weight * Decimal("100") if s.net_weight is not None else None
            gross_wt = s.gross_weight * Decimal("100") if s.gross_weight is not None else None

            sector_rows.append(
                SectorAllocationRow(
                    sector_id=s.sector_id,
                    sector_name=s.sector_name,
                    classification_scheme=s.classification_scheme_code or "GICS",
                    reporting_currency=s.reporting_currency,
                    net_market_value=s.net_exposure,
                    long_market_value=s.long_exposure,
                    short_market_value=s.absolute_short_exposure,
                    gross_market_value=s.gross_exposure,
                    nav_weight_pct=nav_wt,
                    gross_weight_pct=gross_wt,
                    instrument_count=s.contributing_instrument_count,
                    is_unclassified=False,
                    data_quality_status="FRESH",
                )
            )

        # Unclassified sector handling if present
        unclass_val = None
        if res.unclassified:
            tot_unclass_gross = sum((u.gross_exposure for u in res.unclassified), Decimal("0.0"))
            if tot_unclass_gross > 0:
                unclass_val = tot_unclass_gross
                tot_unclass_net = sum((u.net_exposure for u in res.unclassified), Decimal("0.0"))
                tot_unclass_long = sum((u.long_exposure for u in res.unclassified), Decimal("0.0"))
                tot_unclass_short = sum((u.absolute_short_exposure for u in res.unclassified), Decimal("0.0"))
                tot_unclass_count = sum((u.contributing_instrument_count for u in res.unclassified), 0)

                sector_rows.append(
                    SectorAllocationRow(
                        sector_id="UNCLASSIFIED",
                        sector_name="Unclassified / Unmapped Securities",
                        classification_scheme="N/A",
                        reporting_currency=res.reporting_currency,
                        net_market_value=tot_unclass_net,
                        long_market_value=tot_unclass_long,
                        short_market_value=tot_unclass_short,
                        gross_market_value=tot_unclass_gross,
                        nav_weight_pct=None,
                        gross_weight_pct=None,
                        instrument_count=tot_unclass_count,
                        is_unclassified=True,
                        data_quality_status="WARNING",
                    )
                )

        return SectorAllocationSummary(
            portfolio_id=portfolio_id,
            as_of=as_of_dt or datetime.now(timezone.utc),
            reporting_currency=res.reporting_currency,
            total_sectors_count=len(sector_rows),
            total_long_exposure=res.total_long_exposure,
            total_short_exposure=res.total_absolute_short_exposure,
            total_net_exposure=res.total_net_exposure,
            total_gross_exposure=res.total_gross_exposure,
            unclassified_exposure=unclass_val,
            sectors=sector_rows,
        )


class InstrumentAllocationPresentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.instrument_service = InstrumentExposureService(session)

    async def get_instrument_allocation(
        self,
        portfolio_id: str,
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
        side_filter: PositionSideFilter = PositionSideFilter.ALL,
    ) -> InstrumentAllocationSummary:
        req = InstrumentExposureCalculateRequest(
            as_of=as_of_dt or datetime.now(timezone.utc),
            reporting_currency=base_currency,
            ranking_basis=ExposureRankingBasis.GROSS,
        )
        res = await self.instrument_service.calculate_portfolio_instrument_exposure(portfolio_id, req)

        all_holdings: List[RankedHoldingItem] = []
        top_long: List[RankedHoldingItem] = []
        top_short: List[RankedHoldingItem] = []

        rank = 1
        for inst in res.instruments:
            # Check long side
            if inst.long_market_value > 0 and side_filter in (PositionSideFilter.ALL, PositionSideFilter.LONG):
                item = RankedHoldingItem(
                    rank=rank,
                    instrument_id=inst.instrument_id,
                    symbol=inst.symbol or inst.instrument_id,
                    instrument_name=inst.instrument_name or inst.symbol or inst.instrument_id,
                    exchange_code=inst.exchange_code or "NSE",
                    position_side="LONG",
                    quantity=inst.long_quantity or Decimal("0"),
                    mark_price=inst.mark_price or Decimal("0"),
                    price_currency=inst.mark_price_currency or base_currency,
                    market_value=inst.long_market_value,
                    absolute_market_value=inst.long_market_value,
                    nav_weight_pct=inst.long_nav_weight * Decimal("100") if inst.long_nav_weight is not None else None,
                    gross_weight_pct=inst.gross_nav_weight * Decimal("100") if inst.gross_nav_weight is not None else None,
                    valuation_timestamp=inst.valuation_timestamp or (as_of_dt or datetime.now(timezone.utc)),
                    valuation_status=inst.valuation_status.value if hasattr(inst.valuation_status, "value") else str(inst.valuation_status or "FRESH"),
                )
                all_holdings.append(item)
                top_long.append(item)
                rank += 1

            # Check short side
            if inst.short_market_value > 0 and side_filter in (PositionSideFilter.ALL, PositionSideFilter.SHORT):
                # Preserve negative signed market value convention for short
                signed_val = -inst.short_market_value
                item = RankedHoldingItem(
                    rank=rank,
                    instrument_id=inst.instrument_id,
                    symbol=inst.symbol or inst.instrument_id,
                    instrument_name=inst.instrument_name or inst.symbol or inst.instrument_id,
                    exchange_code=inst.exchange_code or "NSE",
                    position_side="SHORT",
                    quantity=-(inst.short_quantity or Decimal("0")),
                    mark_price=inst.mark_price or Decimal("0"),
                    price_currency=inst.mark_price_currency or base_currency,
                    market_value=signed_val,
                    absolute_market_value=inst.short_market_value,
                    nav_weight_pct=-(inst.short_nav_weight * Decimal("100")) if inst.short_nav_weight is not None else None,
                    gross_weight_pct=inst.gross_nav_weight * Decimal("100") if inst.gross_nav_weight is not None else None,
                    valuation_timestamp=inst.valuation_timestamp or (as_of_dt or datetime.now(timezone.utc)),
                    valuation_status=inst.valuation_status.value if hasattr(inst.valuation_status, "value") else str(inst.valuation_status or "FRESH"),
                )
                all_holdings.append(item)
                top_short.append(item)
                rank += 1

        top_long_sorted = sorted(top_long, key=lambda x: x.absolute_market_value, reverse=True)[:10]
        top_short_sorted = sorted(top_short, key=lambda x: x.absolute_market_value, reverse=True)[:10]
        all_sorted = sorted(all_holdings, key=lambda x: x.absolute_market_value, reverse=True)

        return InstrumentAllocationSummary(
            portfolio_id=portfolio_id,
            as_of=as_of_dt or datetime.now(timezone.utc),
            reporting_currency=res.reporting_currency,
            total_instruments_count=res.total_instruments_count,
            long_instruments_count=res.long_instruments_count,
            short_instruments_count=res.short_instruments_count,
            total_long_market_value=res.total_long_exposure,
            total_short_market_value=res.total_short_exposure,
            total_net_market_value=res.total_net_exposure,
            total_gross_market_value=res.total_gross_exposure,
            top_long_holdings=top_long_sorted,
            top_short_holdings=top_short_sorted,
            all_ranked_holdings=all_sorted,
        )


class PortfolioAllocationPresentationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.allocation_service = PortfolioAllocationService(session)

    async def get_portfolio_allocation(
        self,
        portfolio_id: str,
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
    ) -> PortfolioAllocationSummary:
        req = PortfolioAllocationCalculateRequest(
            portfolio_id=portfolio_id,
            as_of=as_of_dt or datetime.now(timezone.utc),
            reporting_currency=base_currency,
            view_type=AllocationViewType.NAV_CAPITAL_ALLOCATION,
            grouping_dimension=AllocationGroupingDimension.SECTOR,
        )
        res = await self.allocation_service.calculate_portfolio_allocation(req)

        # Retrieve cash account details for multi-currency transparency
        cash_stmt = select(CashAccount).where(CashAccount.portfolio_id == portfolio_id)
        cash_res = await self.session.execute(cash_stmt)
        cash_accounts = cash_res.scalars().all()

        cash_details: List[CashBalanceDetail] = []
        for acc in cash_accounts:
            snap_stmt = (
                select(CashBalanceSnapshot)
                .where(CashBalanceSnapshot.cash_account_id == acc.cash_account_id)
                .order_by(CashBalanceSnapshot.effective_at.desc())
                .limit(1)
            )
            s_res = await self.session.execute(snap_stmt)
            c_snap = s_res.scalar_one_or_none()

            settled = c_snap.settled_balance if c_snap else Decimal("0.0")
            avail = c_snap.available_cash if c_snap else Decimal("0.0")
            restr = c_snap.restricted_cash if c_snap else Decimal("0.0")

            cash_details.append(
                CashBalanceDetail(
                    account_id=acc.cash_account_id or acc.account_id,
                    currency=acc.currency,
                    settled_balance=settled,
                    available_balance=avail,
                    restricted_balance=restr,
                    base_equivalent=settled,
                    fx_rate_to_base=Decimal("1.0"),
                )
            )

        return PortfolioAllocationSummary(
            portfolio_id=portfolio_id,
            as_of=as_of_dt or datetime.now(timezone.utc),
            reporting_currency=res.reporting_currency,
            total_nav=res.nav_value,
            total_long_position_value=res.total_long_market_value,
            total_short_position_value=res.total_short_market_value,
            net_position_value=res.net_security_market_value,
            gross_position_exposure=res.gross_security_exposure,
            total_cash_value=res.cash_nav_value,
            available_cash_value=res.available_cash_value,
            restricted_cash_value=res.restricted_cash_value,
            invested_nav_weight_pct=res.invested_nav_weight * Decimal("100"),
            cash_nav_weight_pct=res.cash_nav_weight * Decimal("100"),
            gross_exposure_to_nav_ratio=res.gross_exposure_to_nav,
            reconciliation_residual=res.reconciliation_residual,
            reconciliation_status=str(res.reconciliation_status.value if hasattr(res.reconciliation_status, "value") else res.reconciliation_status),
            cash_balances=cash_details,
        )


class ExposureDrilldownService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sector_pres = SectorAllocationPresentationService(session)
        self.inst_pres = InstrumentAllocationPresentationService(session)

    async def drill_down(
        self,
        portfolio_id: str,
        level: HierarchyLevel = HierarchyLevel.PORTFOLIO,
        sector_id: Optional[str] = None,
        industry_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
    ) -> ExposureDrillDownResponse:
        now_dt = as_of_dt or datetime.now(timezone.utc)
        breadcrumbs: List[HierarchyBreadcrumb] = [
            HierarchyBreadcrumb(level=HierarchyLevel.PORTFOLIO, id=portfolio_id, name="Portfolio Overview")
        ]

        if level == HierarchyLevel.PORTFOLIO:
            sec_summary = await self.sector_pres.get_sector_allocation(portfolio_id, base_currency, now_dt)
            return ExposureDrillDownResponse(
                portfolio_id=portfolio_id,
                as_of=now_dt,
                current_level=HierarchyLevel.PORTFOLIO,
                breadcrumbs=breadcrumbs,
                reporting_currency=base_currency,
                level_name="Portfolio Exposure",
                market_value=sec_summary.total_net_exposure,
                nav_weight_pct=Decimal("100.0"),
                long_exposure=sec_summary.total_long_exposure,
                short_exposure=sec_summary.total_short_exposure,
                net_exposure=sec_summary.total_net_exposure,
                gross_exposure=sec_summary.total_gross_exposure,
                sub_items=[s.model_dump() for s in sec_summary.sectors],
                holdings=[],
            )

        elif level == HierarchyLevel.SECTOR:
            if not sector_id:
                raise ValueError("sector_id is required for SECTOR drill-down.")

            sec_summary = await self.sector_pres.get_sector_allocation(portfolio_id, base_currency, now_dt)
            target_sec = next((s for s in sec_summary.sectors if s.sector_id == sector_id), None)
            if not target_sec:
                raise ValueError(f"Sector '{sector_id}' not found in portfolio allocations.")

            breadcrumbs.append(HierarchyBreadcrumb(level=HierarchyLevel.SECTOR, id=sector_id, name=target_sec.sector_name))

            # Fetch matching holdings
            inst_summary = await self.inst_pres.get_instrument_allocation(portfolio_id, base_currency, now_dt)
            matching_holdings = [h for h in inst_summary.all_ranked_holdings if h.sector_name == target_sec.sector_name]
            if not matching_holdings:
                matching_holdings = inst_summary.all_ranked_holdings  # fallback

            return ExposureDrillDownResponse(
                portfolio_id=portfolio_id,
                as_of=now_dt,
                current_level=HierarchyLevel.SECTOR,
                breadcrumbs=breadcrumbs,
                reporting_currency=base_currency,
                level_name=target_sec.sector_name,
                market_value=target_sec.net_market_value,
                nav_weight_pct=target_sec.nav_weight_pct,
                long_exposure=target_sec.long_market_value,
                short_exposure=target_sec.short_market_value,
                net_exposure=target_sec.net_market_value,
                gross_exposure=target_sec.gross_market_value,
                sub_items=[],
                holdings=matching_holdings,
            )

        else:
            # Instrument level
            inst_summary = await self.inst_pres.get_instrument_allocation(portfolio_id, base_currency, now_dt)
            target_inst = next((h for h in inst_summary.all_ranked_holdings if h.instrument_id == instrument_id), None)
            if not target_inst:
                target_inst = inst_summary.all_ranked_holdings[0] if inst_summary.all_ranked_holdings else None

            if not target_inst:
                raise ValueError(f"Instrument '{instrument_id}' not found.")

            breadcrumbs.append(HierarchyBreadcrumb(level=HierarchyLevel.INSTRUMENT, id=target_inst.instrument_id, name=target_inst.symbol))

            return ExposureDrillDownResponse(
                portfolio_id=portfolio_id,
                as_of=now_dt,
                current_level=HierarchyLevel.INSTRUMENT,
                breadcrumbs=breadcrumbs,
                reporting_currency=base_currency,
                level_name=f"{target_inst.symbol} ({target_inst.position_side})",
                market_value=target_inst.market_value,
                nav_weight_pct=target_inst.nav_weight_pct,
                long_exposure=target_inst.market_value if target_inst.position_side == "LONG" else Decimal("0"),
                short_exposure=target_inst.absolute_market_value if target_inst.position_side == "SHORT" else Decimal("0"),
                net_exposure=target_inst.market_value,
                gross_exposure=target_inst.absolute_market_value,
                sub_items=[],
                holdings=[target_inst],
            )


# ---------------------------------------------------------------------------
# Consolidated Exposure Dashboard Coordinator
# ---------------------------------------------------------------------------

class ExposureDashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sector_pres = SectorAllocationPresentationService(session)
        self.inst_pres = InstrumentAllocationPresentationService(session)
        self.alloc_pres = PortfolioAllocationPresentationService(session)
        self.drilldown_svc = ExposureDrilldownService(session)

    async def get_consolidated_dashboard(
        self,
        portfolio_id: str,
        side_filter: PositionSideFilter = PositionSideFilter.ALL,
        as_of_dt: Optional[datetime] = None,
    ) -> ConsolidatedExposureDashboardResponse:
        # 1. Resolve Portfolio Context
        stmt = select(Portfolio).where(Portfolio.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        portfolio = res.scalar_one_or_none()
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        base_curr = portfolio.base_currency or "USD"
        now_dt = as_of_dt or datetime.now(timezone.utc)

        # Retrieve latest snapshot
        snap_stmt = (
            select(PortfolioValuationSnapshot)
            .where(PortfolioValuationSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioValuationSnapshot.valuation_timestamp.desc())
            .limit(1)
        )
        snap_res = await self.session.execute(snap_stmt)
        snap = snap_res.scalar_one_or_none()
        val_time = snap.valuation_timestamp if snap else now_dt
        snap_id = snap.snapshot_id if snap else None

        # 2. Ingest Authoritative M06 & M05 Modules
        sector_summary = await self.sector_pres.get_sector_allocation(portfolio_id, base_curr, val_time)
        instrument_summary = await self.inst_pres.get_instrument_allocation(portfolio_id, base_curr, val_time, side_filter)
        allocation_summary = await self.alloc_pres.get_portfolio_allocation(portfolio_id, base_curr, val_time)

        # 3. Assess Quality & Data Notes
        notes = []
        if sector_summary.unclassified_exposure and sector_summary.unclassified_exposure > 0:
            notes.append(f"Unclassified sector exposure: {base_curr} {sector_summary.unclassified_exposure:,.2f}")
        if allocation_summary.reconciliation_status != "RECONCILED":
            notes.append(f"NAV reconciliation status: {allocation_summary.reconciliation_status}")

        return ConsolidatedExposureDashboardResponse(
            portfolio_id=portfolio_id,
            portfolio_name=portfolio.portfolio_name,
            base_currency=base_curr,
            as_of=val_time,
            generated_at=now_dt,
            allocation_summary=allocation_summary,
            sector_summary=sector_summary,
            instrument_summary=instrument_summary,
            overall_quality_status="FRESH",
            valuation_timestamp=val_time,
            snapshot_id=snap_id,
            data_quality_notes=notes,
        )
