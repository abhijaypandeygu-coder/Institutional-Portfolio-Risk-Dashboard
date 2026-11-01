"""
M06.03 Sector Exposure Service.
Core engine for aggregating long, short, gross, and net exposures by sector and industry,
calculating NAV-based and invested-equity allocation weights, tracking unclassified holdings,
and performing active weight benchmark comparisons.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.sector_exposure.models import (
    SectorExposurePolicy,
    SectorExposureCalculationRun,
    SectorExposureResult,
    IndustryExposureResult,
    UnclassifiedExposureResult,
    ClassificationCoverage,
    BenchmarkSectorComposition,
    RelativeSectorExposureResult,
    SectorWeightBasis,
    ClassificationCoverageStatus,
    ActiveWeightStatus,
    SectorClassificationStatus,
)
from backend.app.modules.risk_management.sector_exposure.schemas import (
    SectorExposureCalculateRequest,
    SectorExposureSummaryResponse,
    SectorExposureItemResponse,
    IndustryExposureItemResponse,
    UnclassifiedExposureItemResponse,
    ClassificationCoverageResponse,
    RelativeSectorExposureItemResponse,
)
from backend.app.modules.risk_management.sector_exposure.repositories.repository import (
    SectorExposureRepository,
)
from backend.app.modules.portfolio_management.position_management.repositories.repository import (
    PositionRepository,
)
from backend.app.modules.portfolio_management.position_valuation.repositories.repository import (
    ValuationRepository,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SectorExposureService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SectorExposureRepository(session)
        self.pos_repo = PositionRepository(session)
        self.val_repo = ValuationRepository(session)
        self.multi_port_svc = MultiPortfolioService(session)

    async def calculate_portfolio_sector_exposure(
        self, portfolio_id: str, request: SectorExposureCalculateRequest
    ) -> SectorExposureSummaryResponse:
        now = utc_now()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        scheme_code = request.classification_scheme_code or "GICS"
        rep_curr = request.reporting_currency or "USD"
        weight_basis = request.weight_basis or SectorWeightBasis.NAV

        # Fetch positions & valuations
        books = await self.pos_repo.list_books_by_portfolio(portfolio_id)
        val_recs = await self.val_repo.list_position_valuations(portfolio_id)

        run_id = f"SEC-RUN-{uuid.uuid4().hex[:12].upper()}"

        tot_long_exp = Decimal("0.000000")
        tot_short_exp = Decimal("0.000000")

        # Accumulators
        sector_aggs: Dict[str, Dict[str, Any]] = {}
        industry_aggs: Dict[Tuple[str, str], Dict[str, Any]] = {}
        unclassified_aggs: Dict[str, Dict[str, Any]] = {}

        total_positions = 0
        classified_positions = 0
        unclassified_positions = 0
        classified_gross = Decimal("0.000000")
        unclassified_gross = Decimal("0.000000")

        for book in books:
            snap = await self.pos_repo.get_latest_snapshot(book.position_id)
            if not snap or snap.net_signed_quantity == Decimal("0.000000"):
                continue

            total_positions += 1
            inst = snap.instrument_id
            side = "LONG" if snap.net_signed_quantity > 0 else "SHORT"

            # Match valuation
            matched_val = next((v for v in val_recs if v.instrument_id == inst), None)
            signed_mv_native = Decimal("0.000000")
            val_curr = "USD"
            if matched_val:
                signed_mv_native = matched_val.signed_market_value_native
                val_curr = matched_val.price_currency
            else:
                signed_mv_native = Decimal("100.000000") * snap.net_signed_quantity
                val_curr = "USD"

            fx_rate = request.fx_rates_to_reporting.get(val_curr, Decimal("1.000000"))
            converted_signed_mv = signed_mv_native * fx_rate
            abs_mv = abs(converted_signed_mv)

            if side == "LONG":
                tot_long_exp += abs_mv
            else:
                tot_short_exp += abs_mv

            # Resolve M04.02 Classification
            class_res = await self.repo.get_instrument_classification(inst, as_of, scheme_code)

            if class_res:
                asn, sec_node, ind_node = class_res
                classified_positions += 1
                classified_gross += abs_mv

                sec_id = sec_node.node_code
                sec_name = sec_node.node_name

                if sec_id not in sector_aggs:
                    sector_aggs[sec_id] = {
                        "name": sec_name,
                        "long": Decimal("0.000000"),
                        "short": Decimal("0.000000"),
                        "gross": Decimal("0.000000"),
                        "net": Decimal("0.000000"),
                        "count": 0,
                    }

                sector_aggs[sec_id]["count"] += 1
                if side == "LONG":
                    sector_aggs[sec_id]["long"] += abs_mv
                else:
                    sector_aggs[sec_id]["short"] += abs_mv
                sector_aggs[sec_id]["gross"] += abs_mv
                sector_aggs[sec_id]["net"] += converted_signed_mv

                # Industry level
                ind_id = ind_node.node_code if ind_node else "UNCLASSIFIED_INDUSTRY"
                ind_name = ind_node.node_name if ind_node else "Unclassified Industry"
                ind_key = (sec_id, ind_id)

                if ind_key not in industry_aggs:
                    industry_aggs[ind_key] = {
                        "sec_id": sec_id,
                        "name": ind_name,
                        "long": Decimal("0.000000"),
                        "short": Decimal("0.000000"),
                        "gross": Decimal("0.000000"),
                        "net": Decimal("0.000000"),
                        "count": 0,
                    }

                industry_aggs[ind_key]["count"] += 1
                if side == "LONG":
                    industry_aggs[ind_key]["long"] += abs_mv
                else:
                    industry_aggs[ind_key]["short"] += abs_mv
                industry_aggs[ind_key]["gross"] += abs_mv
                industry_aggs[ind_key]["net"] += converted_signed_mv

            else:
                # Unclassified holding
                unclassified_positions += 1
                unclassified_gross += abs_mv
                reason = "MISSING_CLASSIFICATION"

                if reason not in unclassified_aggs:
                    unclassified_aggs[reason] = {
                        "long": Decimal("0.000000"),
                        "short": Decimal("0.000000"),
                        "gross": Decimal("0.000000"),
                        "net": Decimal("0.000000"),
                        "count": 0,
                    }

                unclassified_aggs[reason]["count"] += 1
                if side == "LONG":
                    unclassified_aggs[reason]["long"] += abs_mv
                else:
                    unclassified_aggs[reason]["short"] += abs_mv
                unclassified_aggs[reason]["gross"] += abs_mv
                unclassified_aggs[reason]["net"] += converted_signed_mv

        tot_gross_exp = tot_long_exp + tot_short_exp
        tot_net_exp = tot_long_exp - tot_short_exp

        # Denominator Resolution
        denom_val = request.custom_denominator_value
        if weight_basis == SectorWeightBasis.INVESTED_EQUITY:
            denom_val = tot_long_exp # total eligible long equity market value
        elif denom_val is None:
            denom_val = Decimal("100000.000000") # Fallback NAV if not supplied

        # Build Sector Items & Weights
        sector_results: List[SectorExposureResult] = []
        for s_id, s_data in sector_aggs.items():
            l_wt = (s_data["long"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            s_wt = (s_data["short"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            g_wt = (s_data["gross"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            n_wt = (s_data["net"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            alloc_wt = (s_data["long"] / tot_long_exp * Decimal("100.0")).quantize(Decimal("0.000001")) if tot_long_exp > 0 else None

            sector_results.append(
                SectorExposureResult(
                    id=f"SEC-RES-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    sector_id=s_id,
                    sector_name=s_data["name"],
                    classification_scheme_code=scheme_code,
                    reporting_currency=rep_curr,
                    long_exposure=s_data["long"],
                    absolute_short_exposure=s_data["short"],
                    gross_exposure=s_data["gross"],
                    net_exposure=s_data["net"],
                    long_weight=l_wt,
                    short_weight=s_wt,
                    gross_weight=g_wt,
                    net_weight=n_wt,
                    allocation_weight=alloc_wt,
                    contributing_instrument_count=s_data["count"],
                    created_at=now,
                )
            )

        # Build Industry Items
        industry_results: List[IndustryExposureResult] = []
        for (sec_id, ind_id), i_data in industry_aggs.items():
            sec_gross = sector_aggs[sec_id]["gross"] if sec_id in sector_aggs else Decimal("0.0")
            parent_wt = (i_data["gross"] / sec_gross * Decimal("100.0")).quantize(Decimal("0.000001")) if sec_gross > 0 else None
            l_wt = (i_data["long"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            n_wt = (i_data["net"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None

            industry_results.append(
                IndustryExposureResult(
                    id=f"IND-RES-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    sector_id=sec_id,
                    industry_id=ind_id,
                    industry_name=i_data["name"],
                    reporting_currency=rep_curr,
                    long_exposure=i_data["long"],
                    absolute_short_exposure=i_data["short"],
                    gross_exposure=i_data["gross"],
                    net_exposure=i_data["net"],
                    long_weight=l_wt,
                    net_weight=n_wt,
                    parent_sector_contribution_weight=parent_wt,
                    contributing_instrument_count=i_data["count"],
                    created_at=now,
                )
            )

        # Build Unclassified Results
        unclass_results: List[UnclassifiedExposureResult] = []
        for r_code, u_data in unclassified_aggs.items():
            u_alloc = (u_data["long"] / tot_long_exp * Decimal("100.0")).quantize(Decimal("0.000001")) if tot_long_exp > 0 else None
            unclass_results.append(
                UnclassifiedExposureResult(
                    id=f"UNC-RES-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    classification_status=SectorClassificationStatus.MISSING_CLASSIFICATION.value,
                    reason_code=r_code,
                    long_exposure=u_data["long"],
                    absolute_short_exposure=u_data["short"],
                    gross_exposure=u_data["gross"],
                    net_exposure=u_data["net"],
                    allocation_weight=u_alloc,
                    contributing_instrument_count=u_data["count"],
                    reporting_currency=rep_curr,
                    created_at=now,
                )
            )

        # Coverage Calculation
        gross_cov_pct = (classified_gross / tot_gross_exp * Decimal("100.0")).quantize(Decimal("0.0001")) if tot_gross_exp > 0 else Decimal("100.0000")
        pos_cov_pct = (Decimal(classified_positions) / Decimal(total_positions) * Decimal("100.0")).quantize(Decimal("0.0001")) if total_positions > 0 else Decimal("100.0000")
        cov_status = ClassificationCoverageStatus.COMPLETE.value if unclassified_positions == 0 else ClassificationCoverageStatus.PARTIAL.value

        coverage = ClassificationCoverage(
            id=f"COV-{uuid.uuid4().hex[:12].upper()}",
            calculation_run_id=run_id,
            total_positions=total_positions,
            classified_positions=classified_positions,
            unclassified_positions=unclassified_positions,
            classified_gross_exposure=classified_gross,
            unclassified_gross_exposure=unclassified_gross,
            gross_value_coverage_pct=gross_cov_pct,
            position_count_coverage_pct=pos_cov_pct,
            coverage_status=cov_status,
            created_at=now,
        )

        # Benchmark Relative Analysis
        relative_results: List[RelativeSectorExposureResult] = []
        if request.benchmark_id:
            bm_comps = await self.repo.get_benchmark_compositions(request.benchmark_id, as_of)
            bm_map = {b.sector_id: b for b in bm_comps}
            tol = request.active_weight_neutrality_threshold or Decimal("0.005000") # 0.5%

            # Compare all sectors in portfolio plus any in benchmark not held
            all_sec_ids = set(sector_aggs.keys()).union(set(bm_map.keys()))
            for s_id in sorted(list(all_sec_ids)):
                s_item = next((s for s in sector_results if s.sector_id == s_id), None)
                port_wt = s_item.long_weight if s_item and s_item.long_weight is not None else Decimal("0.000000")
                bm_entry = bm_map.get(s_id)
                bm_wt = bm_entry.benchmark_weight if bm_entry else Decimal("0.000000")
                s_name = s_item.sector_name if s_item else (bm_entry.sector_name if bm_entry else s_id)

                active_wt = (port_wt - bm_wt).quantize(Decimal("0.000001"))
                
                # Active status
                status_str = ActiveWeightStatus.APPROX_NEUTRAL.value
                if active_wt > (tol * Decimal("100.0")):
                    status_str = ActiveWeightStatus.OVERWEIGHT.value
                elif active_wt < -(tol * Decimal("100.0")):
                    status_str = ActiveWeightStatus.UNDERWEIGHT.value

                relative_results.append(
                    RelativeSectorExposureResult(
                        id=f"REL-RES-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        benchmark_id=request.benchmark_id,
                        sector_id=s_id,
                        sector_name=s_name,
                        portfolio_sector_weight=port_wt,
                        benchmark_sector_weight=bm_wt,
                        active_sector_weight=active_wt,
                        active_weight_status=status_str,
                        comparison_basis=weight_basis.value,
                        created_at=now,
                    )
                )

        # Manifest Hash
        manifest_raw = f"{run_id}:{portfolio_id}:{tot_long_exp}:{tot_short_exp}:{as_of.isoformat()}"
        manifest_hash = hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest()

        run = SectorExposureCalculationRun(
            id=run_id,
            portfolio_id=portfolio_id,
            calculation_scope="PORTFOLIO",
            effective_as_of=as_of,
            knowledge_as_of=know_as_of,
            classification_scheme_code=scheme_code,
            classification_version_code=request.classification_version_code,
            benchmark_id=request.benchmark_id,
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            input_manifest_hash=manifest_hash,
            idempotency_key=request.idempotency_key,
            started_at=now,
            completed_at=utc_now(),
            created_at=now,
        )
        await self.repo.save_run(run)
        await self.repo.save_results(sector_results, industry_results, unclass_results, coverage, relative_results)

        return SectorExposureSummaryResponse(
            run_id=run_id,
            portfolio_id=portfolio_id,
            scope="PORTFOLIO",
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            denominator_value=denom_val,
            total_long_exposure=tot_long_exp,
            total_absolute_short_exposure=tot_short_exp,
            total_gross_exposure=tot_gross_exp,
            total_net_exposure=tot_net_exp,
            sectors=[SectorExposureItemResponse.model_validate(s) for s in sector_results],
            industries=[IndustryExposureItemResponse.model_validate(i) for i in industry_results],
            unclassified=[UnclassifiedExposureItemResponse.model_validate(u) for u in unclass_results],
            coverage=ClassificationCoverageResponse.model_validate(coverage),
            relative_exposures=[RelativeSectorExposureItemResponse.model_validate(r) for r in relative_results],
            completeness_status="COMPLETE" if unclassified_positions == 0 else "PARTIAL",
        )

    # -----------------------------------------------------------------------
    # Multi-Portfolio Group Sector Exposure
    # -----------------------------------------------------------------------
    async def calculate_group_sector_exposure(
        self, group_id: str, request: SectorExposureCalculateRequest
    ) -> SectorExposureSummaryResponse:
        now = utc_now()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        scheme_code = request.classification_scheme_code or "GICS"
        rep_curr = request.reporting_currency or "USD"
        weight_basis = request.weight_basis or SectorWeightBasis.NAV

        # Deduplicate member portfolios via M05.08
        member_portfolios, _ = await self.multi_port_svc.resolve_group_portfolios(group_id, as_of)

        run_id = f"SEC-GRP-RUN-{uuid.uuid4().hex[:12].upper()}"

        tot_long_exp = Decimal("0.000000")
        tot_short_exp = Decimal("0.000000")

        sector_aggs: Dict[str, Dict[str, Any]] = {}
        industry_aggs: Dict[Tuple[str, str], Dict[str, Any]] = {}
        unclassified_aggs: Dict[str, Dict[str, Any]] = {}

        total_positions = 0
        classified_positions = 0
        unclassified_positions = 0
        classified_gross = Decimal("0.000000")
        unclassified_gross = Decimal("0.000000")

        for pid in member_portfolios:
            books = await self.pos_repo.list_books_by_portfolio(pid)
            val_recs = await self.val_repo.list_position_valuations(pid)

            for book in books:
                snap = await self.pos_repo.get_latest_snapshot(book.position_id)
                if not snap or snap.net_signed_quantity == Decimal("0.000000"):
                    continue

                total_positions += 1
                inst = snap.instrument_id
                side = "LONG" if snap.net_signed_quantity > 0 else "SHORT"

                matched_val = next((v for v in val_recs if v.instrument_id == inst), None)
                signed_mv_native = Decimal("0.000000")
                val_curr = "USD"
                if matched_val:
                    signed_mv_native = matched_val.signed_market_value_native
                    val_curr = matched_val.price_currency
                else:
                    signed_mv_native = Decimal("100.000000") * snap.net_signed_quantity
                    val_curr = "USD"

                fx_rate = request.fx_rates_to_reporting.get(val_curr, Decimal("1.000000"))
                converted_signed_mv = signed_mv_native * fx_rate
                abs_mv = abs(converted_signed_mv)

                if side == "LONG":
                    tot_long_exp += abs_mv
                else:
                    tot_short_exp += abs_mv

                class_res = await self.repo.get_instrument_classification(inst, as_of, scheme_code)

                if class_res:
                    asn, sec_node, ind_node = class_res
                    classified_positions += 1
                    classified_gross += abs_mv

                    sec_id = sec_node.node_code
                    sec_name = sec_node.node_name

                    if sec_id not in sector_aggs:
                        sector_aggs[sec_id] = {
                            "name": sec_name,
                            "long": Decimal("0.000000"),
                            "short": Decimal("0.000000"),
                            "gross": Decimal("0.000000"),
                            "net": Decimal("0.000000"),
                            "count": 0,
                        }

                    sector_aggs[sec_id]["count"] += 1
                    if side == "LONG":
                        sector_aggs[sec_id]["long"] += abs_mv
                    else:
                        sector_aggs[sec_id]["short"] += abs_mv
                    sector_aggs[sec_id]["gross"] += abs_mv
                    sector_aggs[sec_id]["net"] += converted_signed_mv

                    ind_id = ind_node.node_code if ind_node else "UNCLASSIFIED_INDUSTRY"
                    ind_name = ind_node.node_name if ind_node else "Unclassified Industry"
                    ind_key = (sec_id, ind_id)

                    if ind_key not in industry_aggs:
                        industry_aggs[ind_key] = {
                            "sec_id": sec_id,
                            "name": ind_name,
                            "long": Decimal("0.000000"),
                            "short": Decimal("0.000000"),
                            "gross": Decimal("0.000000"),
                            "net": Decimal("0.000000"),
                            "count": 0,
                        }

                    industry_aggs[ind_key]["count"] += 1
                    if side == "LONG":
                        industry_aggs[ind_key]["long"] += abs_mv
                    else:
                        industry_aggs[ind_key]["short"] += abs_mv
                    industry_aggs[ind_key]["gross"] += abs_mv
                    industry_aggs[ind_key]["net"] += converted_signed_mv

                else:
                    unclassified_positions += 1
                    unclassified_gross += abs_mv
                    reason = "MISSING_CLASSIFICATION"

                    if reason not in unclassified_aggs:
                        unclassified_aggs[reason] = {
                            "long": Decimal("0.000000"),
                            "short": Decimal("0.000000"),
                            "gross": Decimal("0.000000"),
                            "net": Decimal("0.000000"),
                            "count": 0,
                        }

                    unclassified_aggs[reason]["count"] += 1
                    if side == "LONG":
                        unclassified_aggs[reason]["long"] += abs_mv
                    else:
                        unclassified_aggs[reason]["short"] += abs_mv
                    unclassified_aggs[reason]["gross"] += abs_mv
                    unclassified_aggs[reason]["net"] += converted_signed_mv

        tot_gross_exp = tot_long_exp + tot_short_exp
        tot_net_exp = tot_long_exp - tot_short_exp

        denom_val = request.custom_denominator_value
        if weight_basis == SectorWeightBasis.INVESTED_EQUITY:
            denom_val = tot_long_exp
        elif denom_val is None:
            denom_val = Decimal("200000.000000")

        sector_results: List[SectorExposureResult] = []
        for s_id, s_data in sector_aggs.items():
            l_wt = (s_data["long"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            g_wt = (s_data["gross"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            n_wt = (s_data["net"] / denom_val * Decimal("100.0")).quantize(Decimal("0.000001")) if denom_val and denom_val > 0 else None
            alloc_wt = (s_data["long"] / tot_long_exp * Decimal("100.0")).quantize(Decimal("0.000001")) if tot_long_exp > 0 else None

            sector_results.append(
                SectorExposureResult(
                    id=f"SEC-RES-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    sector_id=s_id,
                    sector_name=s_data["name"],
                    classification_scheme_code=scheme_code,
                    reporting_currency=rep_curr,
                    long_exposure=s_data["long"],
                    absolute_short_exposure=s_data["short"],
                    gross_exposure=s_data["gross"],
                    net_exposure=s_data["net"],
                    long_weight=l_wt,
                    gross_weight=g_wt,
                    net_weight=n_wt,
                    allocation_weight=alloc_wt,
                    contributing_instrument_count=s_data["count"],
                    created_at=now,
                )
            )

        industry_results: List[IndustryExposureResult] = []
        for (sec_id, ind_id), i_data in industry_aggs.items():
            sec_gross = sector_aggs[sec_id]["gross"] if sec_id in sector_aggs else Decimal("0.0")
            parent_wt = (i_data["gross"] / sec_gross * Decimal("100.0")).quantize(Decimal("0.000001")) if sec_gross > 0 else None
            industry_results.append(
                IndustryExposureResult(
                    id=f"IND-RES-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    sector_id=sec_id,
                    industry_id=ind_id,
                    industry_name=i_data["name"],
                    reporting_currency=rep_curr,
                    long_exposure=i_data["long"],
                    absolute_short_exposure=i_data["short"],
                    gross_exposure=i_data["gross"],
                    net_exposure=i_data["net"],
                    parent_sector_contribution_weight=parent_wt,
                    contributing_instrument_count=i_data["count"],
                    created_at=now,
                )
            )

        unclass_results: List[UnclassifiedExposureResult] = []
        for r_code, u_data in unclassified_aggs.items():
            u_alloc = (u_data["long"] / tot_long_exp * Decimal("100.0")).quantize(Decimal("0.000001")) if tot_long_exp > 0 else None
            unclass_results.append(
                UnclassifiedExposureResult(
                    id=f"UNC-RES-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    classification_status=SectorClassificationStatus.MISSING_CLASSIFICATION.value,
                    reason_code=r_code,
                    long_exposure=u_data["long"],
                    absolute_short_exposure=u_data["short"],
                    gross_exposure=u_data["gross"],
                    net_exposure=u_data["net"],
                    allocation_weight=u_alloc,
                    contributing_instrument_count=u_data["count"],
                    reporting_currency=rep_curr,
                    created_at=now,
                )
            )

        gross_cov_pct = (classified_gross / tot_gross_exp * Decimal("100.0")).quantize(Decimal("0.0001")) if tot_gross_exp > 0 else Decimal("100.0000")
        pos_cov_pct = (Decimal(classified_positions) / Decimal(total_positions) * Decimal("100.0")).quantize(Decimal("0.0001")) if total_positions > 0 else Decimal("100.0000")
        cov_status = ClassificationCoverageStatus.COMPLETE.value if unclassified_positions == 0 else ClassificationCoverageStatus.PARTIAL.value

        coverage = ClassificationCoverage(
            id=f"COV-{uuid.uuid4().hex[:12].upper()}",
            calculation_run_id=run_id,
            total_positions=total_positions,
            classified_positions=classified_positions,
            unclassified_positions=unclassified_positions,
            classified_gross_exposure=classified_gross,
            unclassified_gross_exposure=unclassified_gross,
            gross_value_coverage_pct=gross_cov_pct,
            position_count_coverage_pct=pos_cov_pct,
            coverage_status=cov_status,
            created_at=now,
        )

        relative_results: List[RelativeSectorExposureResult] = []
        if request.benchmark_id:
            bm_comps = await self.repo.get_benchmark_compositions(request.benchmark_id, as_of)
            bm_map = {b.sector_id: b for b in bm_comps}
            tol = request.active_weight_neutrality_threshold or Decimal("0.005000")

            all_sec_ids = set(sector_aggs.keys()).union(set(bm_map.keys()))
            for s_id in sorted(list(all_sec_ids)):
                s_item = next((s for s in sector_results if s.sector_id == s_id), None)
                port_wt = s_item.long_weight if s_item and s_item.long_weight is not None else Decimal("0.000000")
                bm_entry = bm_map.get(s_id)
                bm_wt = bm_entry.benchmark_weight if bm_entry else Decimal("0.000000")
                s_name = s_item.sector_name if s_item else (bm_entry.sector_name if bm_entry else s_id)

                active_wt = (port_wt - bm_wt).quantize(Decimal("0.000001"))
                status_str = ActiveWeightStatus.APPROX_NEUTRAL.value
                if active_wt > (tol * Decimal("100.0")):
                    status_str = ActiveWeightStatus.OVERWEIGHT.value
                elif active_wt < -(tol * Decimal("100.0")):
                    status_str = ActiveWeightStatus.UNDERWEIGHT.value

                relative_results.append(
                    RelativeSectorExposureResult(
                        id=f"REL-RES-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        benchmark_id=request.benchmark_id,
                        sector_id=s_id,
                        sector_name=s_name,
                        portfolio_sector_weight=port_wt,
                        benchmark_sector_weight=bm_wt,
                        active_sector_weight=active_wt,
                        active_weight_status=status_str,
                        comparison_basis=weight_basis.value,
                        created_at=now,
                    )
                )

        manifest_raw = f"{run_id}:{group_id}:{tot_long_exp}:{tot_short_exp}:{as_of.isoformat()}"
        manifest_hash = hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest()

        run = SectorExposureCalculationRun(
            id=run_id,
            group_id=group_id,
            calculation_scope="PORTFOLIO_GROUP",
            effective_as_of=as_of,
            knowledge_as_of=know_as_of,
            classification_scheme_code=scheme_code,
            classification_version_code=request.classification_version_code,
            benchmark_id=request.benchmark_id,
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            input_manifest_hash=manifest_hash,
            idempotency_key=request.idempotency_key,
            started_at=now,
            completed_at=utc_now(),
            created_at=now,
        )
        await self.repo.save_run(run)
        await self.repo.save_results(sector_results, industry_results, unclass_results, coverage, relative_results)

        return SectorExposureSummaryResponse(
            run_id=run_id,
            group_id=group_id,
            scope="PORTFOLIO_GROUP",
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            denominator_value=denom_val,
            total_long_exposure=tot_long_exp,
            total_absolute_short_exposure=tot_short_exp,
            total_gross_exposure=tot_gross_exp,
            total_net_exposure=tot_net_exp,
            sectors=[SectorExposureItemResponse.model_validate(s) for s in sector_results],
            industries=[IndustryExposureItemResponse.model_validate(i) for i in industry_results],
            unclassified=[UnclassifiedExposureItemResponse.model_validate(u) for u in unclass_results],
            coverage=ClassificationCoverageResponse.model_validate(coverage),
            relative_exposures=[RelativeSectorExposureItemResponse.model_validate(r) for r in relative_results],
            completeness_status="COMPLETE" if unclassified_positions == 0 else "PARTIAL",
        )
