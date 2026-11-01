"""
M06.07 Portfolio Allocation Service.

Core engine for calculating capital distribution across securities, cash, sectors, countries,
strategies, and sleeves using an explicitly declared NAV denominator. Reconciles NAV components,
calculates dual percentage weights, handles target allocation drift, and compares against historical snapshots.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.risk_management.portfolio_allocation.models import (
    PortfolioAllocationResult,
    PortfolioAllocationComponent,
    PortfolioAllocationTarget,
    PortfolioAllocationDrift,
    PortfolioAllocationComparison,
    AllocationViewType,
    AllocationGroupingDimension,
    AllocationReconciliationStatus,
    AllocationDriftStatus,
)
from backend.app.modules.risk_management.portfolio_allocation.schemas import (
    PortfolioAllocationCalculateRequest,
    PortfolioAllocationSummaryResponse,
    PortfolioAllocationComponentItemResponse,
    PortfolioAllocationTargetCreateRequest,
    PortfolioAllocationTargetResponse,
    PortfolioAllocationDriftResponse,
    PortfolioAllocationDriftItemResponse,
    PortfolioAllocationComparisonResponse,
)
from backend.app.modules.risk_management.portfolio_allocation.repositories.repository import (
    PortfolioAllocationRepository,
)

# Upstream Authoritative Integrations
from backend.app.modules.portfolio_management.cash_management.repositories.repository import (
    CashManagementRepository,
)
from backend.app.modules.portfolio_management.cash_management.services.service import (
    CashManagementService,
)
from backend.app.modules.risk_management.instrument_exposure.services.service import (
    InstrumentExposureService,
)
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
)
from backend.app.modules.risk_management.sector_exposure.services.service import (
    SectorExposureService,
)
from backend.app.modules.risk_management.sector_exposure.schemas import (
    SectorExposureCalculateRequest,
)
from backend.app.modules.risk_management.geographic_exposure.services.service import (
    GeographicExposureService,
)
from backend.app.modules.risk_management.geographic_exposure.schemas import (
    GeographicExposureCalculateRequest,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioAllocationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PortfolioAllocationRepository(session)
        self.cash_repo = CashManagementRepository(session)
        self.cash_svc = CashManagementService(session)
        self.inst_exp_svc = InstrumentExposureService(session)
        self.sector_exp_svc = SectorExposureService(session)
        self.geo_exp_svc = GeographicExposureService(session)
        self.multi_port_svc = MultiPortfolioService(session)

    async def calculate_portfolio_allocation(
        self, req: PortfolioAllocationCalculateRequest
    ) -> PortfolioAllocationSummaryResponse:
        """
        Coordinates NAV resolution, cash balances, marked security values,
        breakdown aggregation, weight calculation, and reconciliation.
        """
        # Step 1: Retrieve single-name instrument exposure from authoritative M06.04
        inst_req = InstrumentExposureCalculateRequest(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            as_of=req.as_of_date,
            reporting_currency=req.reporting_currency,
        )
        if req.portfolio_group_id:
            inst_summary = await self.inst_exp_svc.calculate_group_instrument_exposure(
                req.portfolio_group_id, inst_req
            )
        else:
            inst_summary = await self.inst_exp_svc.calculate_portfolio_instrument_exposure(
                req.portfolio_id or "", inst_req
            )

        total_long = inst_summary.total_long_exposure
        total_short = inst_summary.total_short_exposure
        net_security = inst_summary.total_net_exposure
        gross_security = inst_summary.total_gross_exposure

        # Step 2: Retrieve Cash Balances from authoritative M05.04
        cash_nav = Decimal("0.0")
        settled_cash = Decimal("0.0")
        available_cash = Decimal("0.0")
        restricted_cash = Decimal("0.0")

        # Resolve portfolio IDs (if group, resolve child portfolios)
        target_port_ids = []
        if req.portfolio_group_id:
            target_port_ids = await self.multi_port_svc.resolve_group_portfolios(req.portfolio_group_id)
        elif req.portfolio_id:
            target_port_ids = [req.portfolio_id]

        for p_id in target_port_ids:
            accounts = await self.cash_repo.list_cash_accounts_by_portfolio(p_id)
            for acc in accounts:
                c_snp = await self.cash_repo.get_latest_snapshot(p_id, acc.account_id, acc.currency)
                if c_snp:
                    cash_nav += c_snp.settled_balance  # In equity accounting, settled cash contributes to balance sheet NAV
                    settled_cash += c_snp.settled_balance
                    available_cash += c_snp.available_cash
                    restricted_cash += c_snp.restricted_cash
                else:
                    # Fallback to current explanation if snapshot not yet recorded
                    exp = await self.cash_svc.calculate_available_cash(p_id, acc.account_id, acc.currency)
                    cash_nav += exp.settled_balance
                    settled_cash += exp.settled_balance
                    available_cash += exp.final_available_cash
                    restricted_cash += exp.restricted_cash

        # Step 3: Authoritative NAV and Reconciliation
        # In institutional portfolio accounting: NAV = Net Securities (Long - Short) + Cash + Other NAV Components
        # Balance sheet NAV incorporates marked securities AND cash ledger balances
        computed_nav_sum = net_security + cash_nav
        nav_val = computed_nav_sum if computed_nav_sum > Decimal("0.0") else inst_summary.nav
        residual = (nav_val - computed_nav_sum).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        recon_status = AllocationReconciliationStatus.RECONCILED
        if nav_val == Decimal("0.0"):
            recon_status = AllocationReconciliationStatus.NAV_UNAVAILABLE
        elif abs(residual) > Decimal("0.01"):
            recon_status = AllocationReconciliationStatus.PARTIALLY_RECONCILED

        # Step 4: Aggregate Components based on grouping_dimension
        components_list: List[PortfolioAllocationComponent] = []

        if req.grouping_dimension == AllocationGroupingDimension.SECURITY:
            for item in (inst_summary.instruments or []):
                name = item.instrument_name or item.symbol or item.instrument_id
                # NAV weight = Net MV / NAV (for long-only or signed allocation)
                # If gross exposure allocation view: Gross MV / NAV
                if req.allocation_view_type == AllocationViewType.GROSS_EXPOSURE_ALLOCATION:
                    val_for_weight = item.gross_market_value
                elif req.allocation_view_type == AllocationViewType.LONG_INVESTMENT_ALLOCATION:
                    val_for_weight = item.long_market_value
                else:
                    val_for_weight = item.net_market_value

                nav_w = Decimal("0.0")
                if nav_val > Decimal("0.0"):
                    nav_w = (val_for_weight / nav_val).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

                norm_w = Decimal("0.0")
                if total_long > Decimal("0.0"):
                    norm_w = (item.long_market_value / total_long).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

                gross_w = Decimal("0.0")
                if gross_security > Decimal("0.0"):
                    gross_w = (item.gross_market_value / gross_security).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

                comp = PortfolioAllocationComponent(
                    grouping_dimension=req.grouping_dimension,
                    group_id=item.instrument_id,
                    group_key=item.instrument_id,
                    group_name=name,
                    rank=0,
                    long_market_value=item.long_market_value,
                    short_market_value=item.short_market_value,
                    net_market_value=item.net_market_value,
                    gross_market_value=item.gross_market_value,
                    cash_value=Decimal("0.0"),
                    actual_nav_weight=nav_w,
                    normalized_weight=norm_w,
                    gross_exposure_weight=gross_w,
                    source_reference=item.instrument_id,
                )
                components_list.append(comp)

        elif req.grouping_dimension in (AllocationGroupingDimension.SECTOR, AllocationGroupingDimension.INDUSTRY):
            sec_req = SectorExposureCalculateRequest(
                portfolio_id=req.portfolio_id,
                portfolio_group_id=req.portfolio_group_id,
                as_of=req.as_of_date,
                reporting_currency=req.reporting_currency,
            )
            if req.portfolio_group_id:
                sec_res = await self.sector_exp_svc.calculate_group_sector_exposure(
                    req.portfolio_group_id, sec_req
                )
            else:
                sec_res = await self.sector_exp_svc.calculate_portfolio_sector_exposure(
                    req.portfolio_id or "", sec_req
                )

            target_items = sec_res.sectors if req.grouping_dimension == AllocationGroupingDimension.SECTOR else sec_res.industries
            for item in target_items:
                gid = item.sector_code if hasattr(item, "sector_code") else item.industry_code
                gname = item.sector_name if hasattr(item, "sector_name") else item.industry_name
                val_for_weight = item.gross_exposure if req.allocation_view_type == AllocationViewType.GROSS_EXPOSURE_ALLOCATION else item.net_exposure

                nav_w = (val_for_weight / nav_val).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if nav_val > Decimal("0.0") else Decimal("0.0")
                norm_w = (item.long_exposure / total_long).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if total_long > Decimal("0.0") else Decimal("0.0")
                gross_w = (item.gross_exposure / gross_security).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if gross_security > Decimal("0.0") else Decimal("0.0")

                comp = PortfolioAllocationComponent(
                    grouping_dimension=req.grouping_dimension,
                    group_id=gid,
                    group_key=gid,
                    group_name=gname,
                    rank=0,
                    long_market_value=item.long_exposure,
                    short_market_value=item.short_exposure,
                    net_market_value=item.net_exposure,
                    gross_market_value=item.gross_exposure,
                    cash_value=Decimal("0.0"),
                    actual_nav_weight=nav_w,
                    normalized_weight=norm_w,
                    gross_exposure_weight=gross_w,
                    source_reference=f"SECTOR:{gid}",
                )
                components_list.append(comp)

        elif req.grouping_dimension in (AllocationGroupingDimension.COUNTRY, AllocationGroupingDimension.REGION):
            geo_req = GeographicExposureCalculateRequest(
                portfolio_id=req.portfolio_id,
                portfolio_group_id=req.portfolio_group_id,
                as_of=req.as_of_date,
                reporting_currency=req.reporting_currency,
            )
            if req.portfolio_group_id:
                geo_res = await self.geo_exp_svc.calculate_group_geographic_exposure(
                    req.portfolio_group_id, geo_req
                )
            else:
                geo_res = await self.geo_exp_svc.calculate_portfolio_geographic_exposure(
                    req.portfolio_id or "", geo_req
                )

            target_items = geo_res.countries if req.grouping_dimension == AllocationGroupingDimension.COUNTRY else geo_res.regions
            for item in target_items:
                gid = item.country_iso3 if hasattr(item, "country_iso3") else item.region_code
                gname = item.country_name if hasattr(item, "country_name") else item.region_name
                val_for_weight = item.gross_exposure if req.allocation_view_type == AllocationViewType.GROSS_EXPOSURE_ALLOCATION else item.net_exposure

                nav_w = (val_for_weight / nav_val).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if nav_val > Decimal("0.0") else Decimal("0.0")
                norm_w = (item.long_exposure / total_long).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if total_long > Decimal("0.0") else Decimal("0.0")
                gross_w = (item.gross_exposure / gross_security).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if gross_security > Decimal("0.0") else Decimal("0.0")

                comp = PortfolioAllocationComponent(
                    grouping_dimension=req.grouping_dimension,
                    group_id=gid,
                    group_key=gid,
                    group_name=gname,
                    rank=0,
                    long_market_value=item.long_exposure,
                    short_market_value=item.short_exposure,
                    net_market_value=item.net_exposure,
                    gross_market_value=item.gross_exposure,
                    cash_value=Decimal("0.0"),
                    actual_nav_weight=nav_w,
                    normalized_weight=norm_w,
                    gross_exposure_weight=gross_w,
                    source_reference=f"GEO:{gid}",
                )
                components_list.append(comp)

        # Append CASH component if requested or when dimension is CASH/SECURITY
        if req.include_cash_in_breakdown and cash_nav != Decimal("0.0"):
            cash_nav_w = (cash_nav / nav_val).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if nav_val > Decimal("0.0") else Decimal("0.0")
            cash_comp = PortfolioAllocationComponent(
                grouping_dimension=AllocationGroupingDimension.CASH,
                group_id="CASH_NAV",
                group_key="CASH_NAV",
                group_name="Cash & Cash Equivalents",
                rank=0,
                long_market_value=Decimal("0.0"),
                short_market_value=Decimal("0.0"),
                net_market_value=Decimal("0.0"),
                gross_market_value=Decimal("0.0"),
                cash_value=cash_nav,
                actual_nav_weight=cash_nav_w,
                normalized_weight=Decimal("0.0"),
                gross_exposure_weight=Decimal("0.0"),
                source_reference="M05.04:CASH",
            )
            components_list.append(cash_comp)

        # Sort descending by absolute NAV weight with secondary tie-break on group_key
        components_list.sort(key=lambda x: (-abs(x.actual_nav_weight), x.group_key))
        for r_idx, c in enumerate(components_list, start=1):
            c.rank = r_idx

        # Calculate high-level weights
        invested_nav_weight = (net_security / nav_val).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if nav_val > Decimal("0.0") else Decimal("0.0")
        cash_nav_weight = (cash_nav / nav_val).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if nav_val > Decimal("0.0") else Decimal("0.0")
        gross_exp_to_nav = (gross_security / nav_val).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if nav_val > Decimal("0.0") else Decimal("0.0")

        result = PortfolioAllocationResult(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            snapshot_id=req.snapshot_id,
            allocation_view_type=req.allocation_view_type,
            grouping_dimension=req.grouping_dimension,
            reporting_currency=req.reporting_currency,
            nav_value=nav_val,
            total_long_market_value=total_long,
            total_short_market_value=total_short,
            net_security_market_value=net_security,
            gross_security_exposure=gross_security,
            cash_nav_value=cash_nav,
            settled_cash_value=settled_cash,
            available_cash_value=available_cash,
            restricted_cash_value=restricted_cash,
            other_nav_components=Decimal("0.0"),
            unallocated_nav_value=Decimal("0.0"),
            reconciliation_residual=residual,
            reconciliation_status=recon_status,
            data_completeness_status="COMPLETE",
            calculation_version="v1.0",
            calculated_at=utc_now(),
        )

        for c in components_list:
            c.result_id = result.result_id
            result.components.append(c)

        await self.repo.create_result(result)

        resp = PortfolioAllocationSummaryResponse(
            result_id=result.result_id,
            portfolio_id=result.portfolio_id,
            portfolio_group_id=result.portfolio_group_id,
            snapshot_id=result.snapshot_id,
            allocation_view_type=result.allocation_view_type,
            grouping_dimension=result.grouping_dimension,
            reporting_currency=result.reporting_currency,
            nav_value=result.nav_value,
            total_long_market_value=result.total_long_market_value,
            total_short_market_value=result.total_short_market_value,
            net_security_market_value=result.net_security_market_value,
            gross_security_exposure=result.gross_security_exposure,
            cash_nav_value=result.cash_nav_value,
            settled_cash_value=result.settled_cash_value,
            available_cash_value=result.available_cash_value,
            restricted_cash_value=result.restricted_cash_value,
            other_nav_components=result.other_nav_components,
            unallocated_nav_value=result.unallocated_nav_value,
            reconciliation_residual=result.reconciliation_residual,
            invested_nav_weight=invested_nav_weight,
            cash_nav_weight=cash_nav_weight,
            gross_exposure_to_nav=gross_exp_to_nav,
            reconciliation_status=result.reconciliation_status,
            data_completeness_status=result.data_completeness_status,
            calculation_version=result.calculation_version,
            calculated_at=result.calculated_at,
            components=[
                PortfolioAllocationComponentItemResponse.model_validate(c) for c in components_list
            ],
        )
        return resp

    # -------------------------------------------------------------------------
    # Target Configuration & Drift
    # -------------------------------------------------------------------------

    async def create_allocation_target(
        self, req: PortfolioAllocationTargetCreateRequest
    ) -> PortfolioAllocationTargetResponse:
        target = PortfolioAllocationTarget(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            grouping_dimension=req.grouping_dimension,
            group_id=req.group_id,
            target_weight=req.target_weight,
            weight_denominator=req.weight_denominator,
            reporting_currency=req.reporting_currency,
            tolerance_band_pp=req.tolerance_band_pp,
            is_active=True,
            configuration_version=req.configuration_version,
            effective_from=utc_now(),
        )
        await self.repo.create_target(target)
        return PortfolioAllocationTargetResponse.model_validate(target)

    async def calculate_allocation_drift(
        self, result_id: str
    ) -> PortfolioAllocationDriftResponse:
        """
        Calculates drift comparing actual allocation weights from a result against configured targets.
        """
        res = await self.repo.get_result_by_id(result_id)
        if not res:
            raise ValueError(f"Allocation result '{result_id}' not found.")

        active_targets = await self.repo.list_active_targets(
            portfolio_id=res.portfolio_id,
            portfolio_group_id=res.portfolio_group_id,
            grouping_dimension=res.grouping_dimension,
        )

        target_map = {t.group_id: t for t in active_targets}
        drifts: List[PortfolioAllocationDrift] = []

        overweight_c = 0
        underweight_c = 0
        material_c = 0

        # Evaluate each active component against target
        for comp in (res.components or []):
            target = target_map.get(comp.group_id)
            target_w = target.target_weight if target else Decimal("0.0")
            tolerance = target.tolerance_band_pp if target else Decimal("0.050000")

            drift_pp = (comp.actual_nav_weight - target_w).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            cap_diff = (drift_pp * res.nav_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

            rel_drift = None
            if target_w > Decimal("0.0"):
                rel_drift = ((drift_pp / target_w) * Decimal("100.0")).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                )

            status = AllocationDriftStatus.WITHIN_TARGET
            if target is None and comp.actual_nav_weight > Decimal("0.0"):
                status = AllocationDriftStatus.UNPLANNED_ALLOCATION
                material_c += 1
            elif drift_pp > tolerance:
                status = AllocationDriftStatus.OVERWEIGHT
                overweight_c += 1
                if drift_pp > (tolerance * Decimal("2.0")):
                    status = AllocationDriftStatus.MATERIAL_DRIFT
                    material_c += 1
            elif drift_pp < -tolerance:
                status = AllocationDriftStatus.UNDERWEIGHT
                underweight_c += 1
                if drift_pp < (-tolerance * Decimal("2.0")):
                    status = AllocationDriftStatus.MATERIAL_DRIFT
                    material_c += 1

            drift_entry = PortfolioAllocationDrift(
                result_id=res.result_id,
                portfolio_id=res.portfolio_id,
                target_id=target.target_id if target else None,
                grouping_dimension=res.grouping_dimension,
                group_id=comp.group_id,
                group_name=comp.group_name,
                actual_weight=comp.actual_nav_weight,
                target_weight=target_w,
                absolute_drift_pp=drift_pp,
                relative_drift_percentage=rel_drift,
                capital_difference=cap_diff,
                drift_status=status,
                calculation_version="v1.0",
                calculated_at=utc_now(),
            )
            drifts.append(drift_entry)

        await self.repo.create_drifts(drifts)

        return PortfolioAllocationDriftResponse(
            result_id=res.result_id,
            portfolio_id=res.portfolio_id,
            grouping_dimension=res.grouping_dimension,
            total_drifts_count=len(drifts),
            overweight_count=overweight_c,
            underweight_count=underweight_c,
            material_drift_count=material_c,
            items=[PortfolioAllocationDriftItemResponse.model_validate(d) for d in drifts],
        )

    # -------------------------------------------------------------------------
    # Comparison & Historical Evolution
    # -------------------------------------------------------------------------

    async def compare_allocations(
        self, current_result_id: str, prior_result_id: str
    ) -> PortfolioAllocationComparisonResponse:
        """
        Point-to-point comparison between two calculation runs or historical snapshots.
        """
        curr = await self.repo.get_result_by_id(current_result_id)
        prior = await self.repo.get_result_by_id(prior_result_id)

        if not curr or not prior:
            raise ValueError("Both allocation results must exist to perform comparison.")

        comp_status = "COMPARABLE"
        if curr.grouping_dimension != prior.grouping_dimension:
            comp_status = "INCOMPATIBLE_DIMENSION"
        elif curr.reporting_currency != prior.reporting_currency:
            comp_status = "INCOMPATIBLE_CURRENCY"

        nav_change = (curr.nav_value - prior.nav_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        curr_cash_w = (curr.cash_nav_value / curr.nav_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if curr.nav_value > Decimal("0.0") else Decimal("0.0")
        prior_cash_w = (prior.cash_nav_value / prior.nav_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if prior.nav_value > Decimal("0.0") else Decimal("0.0")
        cash_change = (curr_cash_w - prior_cash_w).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        curr_inv_w = (curr.net_security_market_value / curr.nav_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if curr.nav_value > Decimal("0.0") else Decimal("0.0")
        prior_inv_w = (prior.net_security_market_value / prior.nav_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if prior.nav_value > Decimal("0.0") else Decimal("0.0")
        inv_change = (curr_inv_w - prior_inv_w).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        comp = PortfolioAllocationComparison(
            portfolio_id=curr.portfolio_id,
            current_result_id=curr.result_id,
            prior_result_id=prior.result_id,
            grouping_dimension=curr.grouping_dimension,
            reporting_currency=curr.reporting_currency,
            current_nav=curr.nav_value,
            prior_nav=prior.nav_value,
            nav_change=nav_change,
            current_cash_weight=curr_cash_w,
            prior_cash_weight=prior_cash_w,
            cash_weight_change_pp=cash_change,
            current_invested_weight=curr_inv_w,
            prior_invested_weight=prior_inv_w,
            invested_weight_change_pp=inv_change,
            comparability_status=comp_status,
            compared_at=utc_now(),
        )
        await self.repo.create_comparison(comp)
        return PortfolioAllocationComparisonResponse.model_validate(comp)
