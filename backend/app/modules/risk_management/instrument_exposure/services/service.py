"""
M06.04 Instrument Exposure Service.
Core engine for calculating single-name instrument exposures (long, short, gross, net),
dual portfolio weights (NAV-based and Gross Contribution), ranking holdings,
detecting dominant exposures, and comparing against historical snapshots.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.instrument_exposure.models import (
    InstrumentExposureCalculationRun,
    InstrumentExposureResult,
    InstrumentListingExposureDetail,
    InstrumentExposureComparison,
    InstrumentExposureDominanceFlag,
    InstrumentExposureSettings,
    ExposureWeightBasis,
    ExposureRankingBasis,
    ValuationQualityStatus,
    DenominatorStatus,
    ExposureLifecycleIndicator,
    DominanceSeverity,
)
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
    InstrumentExposureSummaryResponse,
    InstrumentExposureItemResponse,
    ListingExposureDetailResponse,
    InstrumentExposureRankingsResponse,
    InstrumentExposureComparisonResponse,
    InstrumentExposureComparisonItemResponse,
    InstrumentExposureDominanceFlagResponse,
)
from backend.app.modules.risk_management.instrument_exposure.repositories.repository import (
    InstrumentExposureRepository,
)
from backend.app.modules.portfolio_management.position_management.repositories.repository import (
    PositionRepository,
)
from backend.app.modules.portfolio_management.position_valuation.repositories.repository import (
    ValuationRepository,
)
from backend.app.modules.portfolio_management.portfolio_history.repositories.repository import (
    PortfolioHistoryRepository,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InstrumentExposureService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InstrumentExposureRepository(session)
        self.pos_repo = PositionRepository(session)
        self.val_repo = ValuationRepository(session)
        self.hist_repo = PortfolioHistoryRepository(session)
        self.multi_port_svc = MultiPortfolioService(session)

    async def calculate_portfolio_instrument_exposure(
        self, portfolio_id: str, request: InstrumentExposureCalculateRequest
    ) -> InstrumentExposureSummaryResponse:
        now = utc_now()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"
        weight_basis = request.weight_basis or ExposureWeightBasis.NAV
        ranking_basis = request.ranking_basis or ExposureRankingBasis.GROSS

        settings = await self.repo.get_or_create_settings(portfolio_id)

        # 1. Fetch positions & valuations
        books = await self.pos_repo.list_books_by_portfolio(portfolio_id)
        val_recs = await self.val_repo.list_position_valuations(portfolio_id)

        # Group valuations by instrument_id (latest mark)
        latest_vals: Dict[str, Any] = {}
        for v in val_recs:
            if v.instrument_id not in latest_vals:
                latest_vals[v.instrument_id] = v

        # 2. Accumulate by canonical instrument
        # Map: inst_id -> dict
        inst_aggs: Dict[str, Dict[str, Any]] = {}

        total_positions = 0
        valued_positions = 0

        for book in books:
            snap = await self.pos_repo.get_latest_snapshot(book.position_id)
            if not snap or snap.net_signed_quantity == Decimal("0.000000"):
                continue

            total_positions += 1
            inst_id = snap.instrument_id

            if inst_id not in inst_aggs:
                meta = await self.repo.get_instrument_metadata(inst_id)
                inst_aggs[inst_id] = {
                    "instrument_id": inst_id,
                    "symbol": meta.short_name if meta else inst_id,
                    "instrument_name": meta.canonical_name if meta else inst_id,
                    "exchange_code": meta.primary_market_id if meta else "UNKNOWN",
                    "asset_class": meta.asset_class if meta else "EQUITY",
                    "reporting_currency": rep_curr,
                    "long_quantity": Decimal("0.000000"),
                    "short_quantity": Decimal("0.000000"),
                    "long_market_value": Decimal("0.000000"),
                    "short_market_value": Decimal("0.000000"),
                    "valuation_status": ValuationQualityStatus.VALUED.value,
                    "price_source": None,
                    "mark_price": None,
                    "mark_price_currency": None,
                    "valuation_timestamp": None,
                    "listings": [],
                }

            val = latest_vals.get(inst_id)
            if val:
                valued_positions += 1
                inst_aggs[inst_id]["price_source"] = getattr(val, "mark_price_type", None) or "OFFICIAL_CLOSE"
                if hasattr(inst_aggs[inst_id]["price_source"], "value"):
                    inst_aggs[inst_id]["price_source"] = inst_aggs[inst_id]["price_source"].value
                inst_aggs[inst_id]["mark_price"] = val.mark_price
                inst_aggs[inst_id]["mark_price_currency"] = getattr(val, "price_currency", "USD")
                inst_aggs[inst_id]["valuation_timestamp"] = val.effective_at

                unit_price = val.mark_price
                qty = snap.net_signed_quantity
                if qty > Decimal("0.0"):
                    inst_aggs[inst_id]["long_quantity"] += qty
                    mv = qty * unit_price
                    inst_aggs[inst_id]["long_market_value"] += mv
                elif qty < Decimal("0.0"):
                    abs_qty = abs(qty)
                    inst_aggs[inst_id]["short_quantity"] += abs_qty
                    mv = abs_qty * unit_price
                    inst_aggs[inst_id]["short_market_value"] += mv
            else:
                # Mark as missing valuation
                inst_aggs[inst_id]["valuation_status"] = ValuationQualityStatus.PRICE_UNAVAILABLE.value
                qty = snap.net_signed_quantity
                if qty > Decimal("0.0"):
                    inst_aggs[inst_id]["long_quantity"] += qty
                else:
                    inst_aggs[inst_id]["short_quantity"] += abs(qty)

        # 3. Portfolio Totals
        tot_long_exp = sum((d["long_market_value"] for d in inst_aggs.values()), Decimal("0.000000"))
        tot_short_exp = sum((d["short_market_value"] for d in inst_aggs.values()), Decimal("0.000000"))
        tot_gross_exp = tot_long_exp + tot_short_exp
        tot_net_exp = tot_long_exp - tot_short_exp

        # Derive NAV from portfolio snapshot or gross exposure fallback
        port_snap = await self.val_repo.get_latest_portfolio_snapshot(portfolio_id)
        if port_snap and getattr(port_snap, "net_market_value", None) is not None and port_snap.net_market_value > Decimal("0.000000"):
            nav = port_snap.net_market_value
            denom_status = DenominatorStatus.CALCULATED.value
        elif tot_gross_exp > Decimal("0.000000"):
            nav = tot_gross_exp
            denom_status = DenominatorStatus.CALCULATED.value
        else:
            nav = Decimal("0.000000")
            denom_status = DenominatorStatus.DENOMINATOR_ZERO.value

        # Valuation coverage
        coverage_ratio = (
            Decimal(str(valued_positions)) / Decimal(str(total_positions))
            if total_positions > 0
            else Decimal("1.000000")
        )
        completeness_status = "COMPLETE" if coverage_ratio == Decimal("1.000000") else "PARTIAL"

        run_id = f"INST-RUN-{uuid.uuid4().hex[:12].upper()}"

        run = InstrumentExposureCalculationRun(
            run_id=run_id,
            portfolio_id=portfolio_id,
            entity_type="PORTFOLIO",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            nav=nav,
            total_long_exposure=tot_long_exp,
            total_short_exposure=tot_short_exp,
            total_net_exposure=tot_net_exp,
            total_gross_exposure=tot_gross_exp,
            total_instruments_count=len(inst_aggs),
            long_instruments_count=sum(1 for d in inst_aggs.values() if d["long_quantity"] > Decimal("0.0")),
            short_instruments_count=sum(1 for d in inst_aggs.values() if d["short_quantity"] > Decimal("0.0")),
            hedged_instruments_count=sum(
                1 for d in inst_aggs.values() if d["long_quantity"] > Decimal("0.0") and d["short_quantity"] > Decimal("0.0")
            ),
            valuation_coverage_ratio=coverage_ratio.quantize(Decimal("0.000001")),
            data_completeness_status=completeness_status,
            denominator_status=denom_status,
            calculated_at=now,
        )

        # 4. Compute Weights, Net MV, Gross MV & Dominance Flags
        results_list: List[InstrumentExposureResult] = []
        flags_list: List[InstrumentExposureDominanceFlag] = []

        for inst_id, d in inst_aggs.items():
            l_mv = d["long_market_value"]
            s_mv = d["short_market_value"]
            g_mv = l_mv + s_mv
            n_mv = l_mv - s_mv
            net_qty = d["long_quantity"] - d["short_quantity"]

            # NAV-based weights
            long_nav_w = (l_mv / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            short_nav_w = (s_mv / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            net_nav_w = (n_mv / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            gross_nav_w = (g_mv / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None

            # Contribution weights
            gross_contrib_w = (g_mv / tot_gross_exp).quantize(Decimal("0.000001")) if tot_gross_exp > Decimal("0.0") else None
            long_contrib_w = (l_mv / tot_long_exp).quantize(Decimal("0.000001")) if tot_long_exp > Decimal("0.0") else None
            short_contrib_w = (s_mv / tot_short_exp).quantize(Decimal("0.000001")) if tot_short_exp > Decimal("0.0") else None

            # Dominance evaluation
            severity = DominanceSeverity.NORMAL.value
            reason = None

            if gross_nav_w is not None and gross_nav_w >= settings.gross_nav_critical_threshold:
                severity = DominanceSeverity.CRITICAL.value
                reason = f"Gross NAV weight {gross_nav_w} exceeded critical threshold {settings.gross_nav_critical_threshold}"
                flags_list.append(
                    InstrumentExposureDominanceFlag(
                        portfolio_id=portfolio_id,
                        run_id=run_id,
                        instrument_id=inst_id,
                        flag_type="GROSS_NAV_CRITICAL",
                        severity=severity,
                        measured_value=gross_nav_w,
                        threshold_value=settings.gross_nav_critical_threshold,
                        weight_basis=ExposureWeightBasis.NAV.value,
                        evaluation_timestamp=now,
                    )
                )
            elif gross_nav_w is not None and gross_nav_w >= settings.gross_nav_elevated_threshold:
                severity = DominanceSeverity.ELEVATED.value
                reason = f"Gross NAV weight {gross_nav_w} exceeded elevated threshold {settings.gross_nav_elevated_threshold}"
                flags_list.append(
                    InstrumentExposureDominanceFlag(
                        portfolio_id=portfolio_id,
                        run_id=run_id,
                        instrument_id=inst_id,
                        flag_type="GROSS_NAV_ELEVATED",
                        severity=severity,
                        measured_value=gross_nav_w,
                        threshold_value=settings.gross_nav_elevated_threshold,
                        weight_basis=ExposureWeightBasis.NAV.value,
                        evaluation_timestamp=now,
                    )
                )

            res = InstrumentExposureResult(
                run_id=run_id,
                portfolio_id=portfolio_id,
                instrument_id=inst_id,
                symbol=d["symbol"],
                instrument_name=d["instrument_name"],
                exchange_code=d["exchange_code"],
                asset_class=d["asset_class"],
                reporting_currency=rep_curr,
                long_quantity=d["long_quantity"],
                short_quantity=d["short_quantity"],
                net_quantity=net_qty,
                long_market_value=l_mv,
                short_market_value=s_mv,
                net_market_value=n_mv,
                gross_market_value=g_mv,
                long_nav_weight=long_nav_w,
                short_nav_weight=short_nav_w,
                net_nav_weight=net_nav_w,
                gross_nav_weight=gross_nav_w,
                gross_contribution_weight=gross_contrib_w,
                long_contribution_weight=long_contrib_w,
                short_contribution_weight=short_contrib_w,
                valuation_status=d["valuation_status"],
                price_source=d["price_source"],
                mark_price=d["mark_price"],
                mark_price_currency=d["mark_price_currency"],
                valuation_timestamp=d["valuation_timestamp"],
                dominance_severity=severity,
                dominance_flag_reason=reason,
                calculated_at=now,
            )
            results_list.append(res)

        # 5. Calculate Ranks
        # Long rank
        sorted_long = sorted(results_list, key=lambda x: (x.long_market_value, x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_long, start=1):
            if item.long_market_value > Decimal("0.0"):
                item.long_rank = idx

        # Short rank (descending absolute short MV)
        sorted_short = sorted(results_list, key=lambda x: (x.short_market_value, x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_short, start=1):
            if item.short_market_value > Decimal("0.0"):
                item.short_rank = idx

        # Gross rank
        sorted_gross = sorted(results_list, key=lambda x: (x.gross_market_value, x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_gross, start=1):
            item.gross_rank = idx

        # Net rank (descending absolute net MV)
        sorted_net = sorted(results_list, key=lambda x: (abs(x.net_market_value), x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_net, start=1):
            item.net_rank = idx

        # Persist
        await self.repo.save_calculation_run(run, results_list, [], flags_list)

        # Build schema response
        items_resp = [
            InstrumentExposureItemResponse(
                instrument_id=r.instrument_id,
                symbol=r.symbol,
                instrument_name=r.instrument_name,
                exchange_code=r.exchange_code,
                asset_class=r.asset_class,
                reporting_currency=r.reporting_currency,
                long_quantity=r.long_quantity,
                short_quantity=r.short_quantity,
                net_quantity=r.net_quantity,
                long_market_value=r.long_market_value,
                short_market_value=r.short_market_value,
                net_market_value=r.net_market_value,
                gross_market_value=r.gross_market_value,
                long_nav_weight=r.long_nav_weight,
                short_nav_weight=r.short_nav_weight,
                net_nav_weight=r.net_nav_weight,
                gross_nav_weight=r.gross_nav_weight,
                gross_contribution_weight=r.gross_contribution_weight,
                long_contribution_weight=r.long_contribution_weight,
                short_contribution_weight=r.short_contribution_weight,
                long_rank=r.long_rank,
                short_rank=r.short_rank,
                gross_rank=r.gross_rank,
                net_rank=r.net_rank,
                valuation_status=r.valuation_status,
                price_source=r.price_source,
                mark_price=r.mark_price,
                mark_price_currency=r.mark_price_currency,
                valuation_timestamp=r.valuation_timestamp,
                dominance_severity=r.dominance_severity,
                dominance_flag_reason=r.dominance_flag_reason,
            )
            for r in results_list
        ]

        # Top instruments
        largest_g = sorted_gross[0].instrument_id if sorted_gross else None
        largest_l = sorted_long[0].instrument_id if sorted_long and sorted_long[0].long_market_value > Decimal("0.0") else None
        largest_s = sorted_short[0].instrument_id if sorted_short and sorted_short[0].short_market_value > Decimal("0.0") else None

        return InstrumentExposureSummaryResponse(
            run_id=run.run_id,
            portfolio_id=portfolio_id,
            entity_type="PORTFOLIO",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            nav=nav,
            total_long_exposure=tot_long_exp,
            total_short_exposure=tot_short_exp,
            total_net_exposure=tot_net_exp,
            total_gross_exposure=tot_gross_exp,
            total_instruments_count=run.total_instruments_count,
            long_instruments_count=run.long_instruments_count,
            short_instruments_count=run.short_instruments_count,
            hedged_instruments_count=run.hedged_instruments_count,
            valuation_coverage_ratio=run.valuation_coverage_ratio,
            data_completeness_status=run.data_completeness_status,
            denominator_status=run.denominator_status,
            largest_gross_instrument=largest_g,
            largest_long_instrument=largest_l,
            largest_short_instrument=largest_s,
            dominant_exposures_count=len(flags_list),
            instruments=items_resp,
        )

    async def calculate_group_instrument_exposure(
        self, group_id: str, request: InstrumentExposureCalculateRequest
    ) -> InstrumentExposureSummaryResponse:
        """
        Consolidates instrument exposures across member portfolios in a portfolio group
        using M05.08 group resolution.
        """
        now = utc_now()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"
        weight_basis = request.weight_basis or ExposureWeightBasis.NAV

        member_ids, _ = await self.multi_port_svc.resolve_group_portfolios(group_id, as_of)

        settings = await self.repo.get_or_create_settings(group_id)

        inst_aggs: Dict[str, Dict[str, Any]] = {}
        total_positions = 0
        valued_positions = 0
        group_nav = Decimal("0.000000")

        for port_id in member_ids:
            books = await self.pos_repo.list_books_by_portfolio(port_id)
            val_recs = await self.val_repo.list_position_valuations(port_id)
            latest_vals = {v.instrument_id: v for v in val_recs}

            port_snap = await self.val_repo.get_latest_portfolio_snapshot(port_id)
            if port_snap and getattr(port_snap, "net_market_value", None) is not None:
                group_nav += port_snap.net_market_value

            for book in books:
                snap = await self.pos_repo.get_latest_snapshot(book.position_id)
                if not snap or snap.net_signed_quantity == Decimal("0.000000"):
                    continue

                total_positions += 1
                inst_id = snap.instrument_id

                if inst_id not in inst_aggs:
                    meta = await self.repo.get_instrument_metadata(inst_id)
                    inst_aggs[inst_id] = {
                        "instrument_id": inst_id,
                        "symbol": meta.short_name if meta else inst_id,
                        "instrument_name": meta.canonical_name if meta else inst_id,
                        "exchange_code": meta.primary_market_id if meta else "UNKNOWN",
                        "asset_class": meta.asset_class if meta else "EQUITY",
                        "reporting_currency": rep_curr,
                        "long_quantity": Decimal("0.000000"),
                        "short_quantity": Decimal("0.000000"),
                        "long_market_value": Decimal("0.000000"),
                        "short_market_value": Decimal("0.000000"),
                        "valuation_status": ValuationQualityStatus.VALUED.value,
                        "price_source": None,
                        "mark_price": None,
                        "mark_price_currency": None,
                        "valuation_timestamp": None,
                    }

                val = latest_vals.get(inst_id)
                if val:
                    valued_positions += 1
                    inst_aggs[inst_id]["price_source"] = getattr(val, "mark_price_type", None) or "OFFICIAL_CLOSE"
                    if hasattr(inst_aggs[inst_id]["price_source"], "value"):
                        inst_aggs[inst_id]["price_source"] = inst_aggs[inst_id]["price_source"].value
                    inst_aggs[inst_id]["mark_price"] = val.mark_price
                    inst_aggs[inst_id]["mark_price_currency"] = getattr(val, "price_currency", "USD")
                    inst_aggs[inst_id]["valuation_timestamp"] = val.effective_at

                    qty = snap.net_signed_quantity
                    unit_price = val.mark_price
                    if qty > Decimal("0.0"):
                        inst_aggs[inst_id]["long_quantity"] += qty
                        inst_aggs[inst_id]["long_market_value"] += qty * unit_price
                    elif qty < Decimal("0.0"):
                        abs_qty = abs(qty)
                        inst_aggs[inst_id]["short_quantity"] += abs_qty
                        inst_aggs[inst_id]["short_market_value"] += abs_qty * unit_price

        tot_long_exp = sum((d["long_market_value"] for d in inst_aggs.values()), Decimal("0.000000"))
        tot_short_exp = sum((d["short_market_value"] for d in inst_aggs.values()), Decimal("0.000000"))
        tot_gross_exp = tot_long_exp + tot_short_exp
        tot_net_exp = tot_long_exp - tot_short_exp

        if group_nav == Decimal("0.000000") and tot_gross_exp > Decimal("0.000000"):
            group_nav = tot_gross_exp

        coverage_ratio = (
            Decimal(str(valued_positions)) / Decimal(str(total_positions))
            if total_positions > 0
            else Decimal("1.000000")
        )
        completeness_status = "COMPLETE" if coverage_ratio == Decimal("1.000000") else "PARTIAL"

        run_id = f"INST-RUN-{uuid.uuid4().hex[:12].upper()}"

        run = InstrumentExposureCalculationRun(
            run_id=run_id,
            portfolio_id=group_id,
            portfolio_group_id=group_id,
            entity_type="PORTFOLIO_GROUP",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            nav=group_nav,
            total_long_exposure=tot_long_exp,
            total_short_exposure=tot_short_exp,
            total_net_exposure=tot_net_exp,
            total_gross_exposure=tot_gross_exp,
            total_instruments_count=len(inst_aggs),
            long_instruments_count=sum(1 for d in inst_aggs.values() if d["long_quantity"] > Decimal("0.0")),
            short_instruments_count=sum(1 for d in inst_aggs.values() if d["short_quantity"] > Decimal("0.0")),
            hedged_instruments_count=sum(
                1 for d in inst_aggs.values() if d["long_quantity"] > Decimal("0.0") and d["short_quantity"] > Decimal("0.0")
            ),
            valuation_coverage_ratio=coverage_ratio.quantize(Decimal("0.000001")),
            data_completeness_status=completeness_status,
            denominator_status=DenominatorStatus.CALCULATED.value if group_nav > Decimal("0.0") else DenominatorStatus.DENOMINATOR_ZERO.value,
            calculated_at=now,
        )

        results_list: List[InstrumentExposureResult] = []
        flags_list: List[InstrumentExposureDominanceFlag] = []

        for inst_id, d in inst_aggs.items():
            l_mv = d["long_market_value"]
            s_mv = d["short_market_value"]
            g_mv = l_mv + s_mv
            n_mv = l_mv - s_mv
            net_qty = d["long_quantity"] - d["short_quantity"]

            long_nav_w = (l_mv / group_nav).quantize(Decimal("0.000001")) if group_nav > Decimal("0.0") else None
            short_nav_w = (s_mv / group_nav).quantize(Decimal("0.000001")) if group_nav > Decimal("0.0") else None
            net_nav_w = (n_mv / group_nav).quantize(Decimal("0.000001")) if group_nav > Decimal("0.0") else None
            gross_nav_w = (g_mv / group_nav).quantize(Decimal("0.000001")) if group_nav > Decimal("0.0") else None

            gross_contrib_w = (g_mv / tot_gross_exp).quantize(Decimal("0.000001")) if tot_gross_exp > Decimal("0.0") else None
            long_contrib_w = (l_mv / tot_long_exp).quantize(Decimal("0.000001")) if tot_long_exp > Decimal("0.0") else None
            short_contrib_w = (s_mv / tot_short_exp).quantize(Decimal("0.000001")) if tot_short_exp > Decimal("0.0") else None

            severity = DominanceSeverity.NORMAL.value
            reason = None

            if gross_nav_w is not None and gross_nav_w >= settings.gross_nav_critical_threshold:
                severity = DominanceSeverity.CRITICAL.value
                reason = f"Gross NAV weight {gross_nav_w} exceeded critical threshold {settings.gross_nav_critical_threshold}"
                flags_list.append(
                    InstrumentExposureDominanceFlag(
                        portfolio_id=group_id,
                        run_id=run_id,
                        instrument_id=inst_id,
                        flag_type="GROSS_NAV_CRITICAL",
                        severity=severity,
                        measured_value=gross_nav_w,
                        threshold_value=settings.gross_nav_critical_threshold,
                        weight_basis=ExposureWeightBasis.NAV.value,
                        evaluation_timestamp=now,
                    )
                )

            res = InstrumentExposureResult(
                run_id=run_id,
                portfolio_id=group_id,
                instrument_id=inst_id,
                symbol=d["symbol"],
                instrument_name=d["instrument_name"],
                exchange_code=d["exchange_code"],
                asset_class=d["asset_class"],
                reporting_currency=rep_curr,
                long_quantity=d["long_quantity"],
                short_quantity=d["short_quantity"],
                net_quantity=net_qty,
                long_market_value=l_mv,
                short_market_value=s_mv,
                net_market_value=n_mv,
                gross_market_value=g_mv,
                long_nav_weight=long_nav_w,
                short_nav_weight=short_nav_w,
                net_nav_weight=net_nav_w,
                gross_nav_weight=gross_nav_w,
                gross_contribution_weight=gross_contrib_w,
                long_contribution_weight=long_contrib_w,
                short_contribution_weight=short_contrib_w,
                valuation_status=d["valuation_status"],
                price_source=d["price_source"],
                mark_price=d["mark_price"],
                mark_price_currency=d["mark_price_currency"],
                valuation_timestamp=d["valuation_timestamp"],
                dominance_severity=severity,
                dominance_flag_reason=reason,
                calculated_at=now,
            )
            results_list.append(res)

        sorted_gross = sorted(results_list, key=lambda x: (x.gross_market_value, x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_gross, start=1):
            item.gross_rank = idx

        sorted_long = sorted(results_list, key=lambda x: (x.long_market_value, x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_long, start=1):
            if item.long_market_value > Decimal("0.0"):
                item.long_rank = idx

        sorted_short = sorted(results_list, key=lambda x: (x.short_market_value, x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_short, start=1):
            if item.short_market_value > Decimal("0.0"):
                item.short_rank = idx

        sorted_net = sorted(results_list, key=lambda x: (abs(x.net_market_value), x.instrument_id), reverse=True)
        for idx, item in enumerate(sorted_net, start=1):
            item.net_rank = idx

        await self.repo.save_calculation_run(run, results_list, [], flags_list)

        items_resp = [
            InstrumentExposureItemResponse(
                instrument_id=r.instrument_id,
                symbol=r.symbol,
                instrument_name=r.instrument_name,
                exchange_code=r.exchange_code,
                asset_class=r.asset_class,
                reporting_currency=r.reporting_currency,
                long_quantity=r.long_quantity,
                short_quantity=r.short_quantity,
                net_quantity=r.net_quantity,
                long_market_value=r.long_market_value,
                short_market_value=r.short_market_value,
                net_market_value=r.net_market_value,
                gross_market_value=r.gross_market_value,
                long_nav_weight=r.long_nav_weight,
                short_nav_weight=r.short_nav_weight,
                net_nav_weight=r.net_nav_weight,
                gross_nav_weight=r.gross_nav_weight,
                gross_contribution_weight=r.gross_contribution_weight,
                long_contribution_weight=r.long_contribution_weight,
                short_contribution_weight=r.short_contribution_weight,
                long_rank=r.long_rank,
                short_rank=r.short_rank,
                gross_rank=r.gross_rank,
                net_rank=r.net_rank,
                valuation_status=r.valuation_status,
                price_source=r.price_source,
                mark_price=r.mark_price,
                mark_price_currency=r.mark_price_currency,
                valuation_timestamp=r.valuation_timestamp,
                dominance_severity=r.dominance_severity,
                dominance_flag_reason=r.dominance_flag_reason,
            )
            for r in results_list
        ]

        return InstrumentExposureSummaryResponse(
            run_id=run.run_id,
            portfolio_id=group_id,
            portfolio_group_id=group_id,
            entity_type="PORTFOLIO_GROUP",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            reporting_currency=rep_curr,
            weight_basis=weight_basis.value,
            nav=group_nav,
            total_long_exposure=tot_long_exp,
            total_short_exposure=tot_short_exp,
            total_net_exposure=tot_net_exp,
            total_gross_exposure=tot_gross_exp,
            total_instruments_count=run.total_instruments_count,
            long_instruments_count=run.long_instruments_count,
            short_instruments_count=run.short_instruments_count,
            hedged_instruments_count=run.hedged_instruments_count,
            valuation_coverage_ratio=run.valuation_coverage_ratio,
            data_completeness_status=run.data_completeness_status,
            denominator_status=run.denominator_status,
            largest_gross_instrument=sorted_gross[0].instrument_id if sorted_gross else None,
            largest_long_instrument=sorted_long[0].instrument_id if sorted_long and sorted_long[0].long_market_value > Decimal("0.0") else None,
            largest_short_instrument=sorted_short[0].instrument_id if sorted_short and sorted_short[0].short_market_value > Decimal("0.0") else None,
            dominant_exposures_count=len(flags_list),
            instruments=items_resp,
        )

    async def compare_snapshots(
        self, portfolio_id: str, current_snapshot_id: str, prior_snapshot_id: str
    ) -> InstrumentExposureComparisonResponse:
        """
        Compares instrument exposures between two snapshots from M05.07.
        Calculates delta L, delta S, delta G, delta N, delta NAV weight pp,
        and derives lifecycle indicators.
        """
        curr_snap = await self.hist_repo.get_snapshot_by_id(current_snapshot_id)
        prior_snap = await self.hist_repo.get_snapshot_by_id(prior_snapshot_id)

        curr_positions = await self.hist_repo.get_snapshot_positions(current_snapshot_id)
        prior_positions = await self.hist_repo.get_snapshot_positions(prior_snapshot_id)

        curr_vals = await self.hist_repo.get_snapshot_valuations(current_snapshot_id)
        prior_vals = await self.hist_repo.get_snapshot_valuations(prior_snapshot_id)

        curr_val_map = {v.instrument_id: v for v in curr_vals}
        prior_val_map = {v.instrument_id: v for v in prior_vals}

        def build_exposures(positions, val_map):
            exps: Dict[str, Dict[str, Decimal]] = {}
            for p in positions:
                inst = p.instrument_id
                if inst not in exps:
                    exps[inst] = {"long": Decimal("0.000000"), "short": Decimal("0.000000")}
                v = val_map.get(inst)
                px = v.market_price if v else Decimal("1.000000") # fallback
                qty = p.net_signed_quantity
                if qty > Decimal("0.0"):
                    exps[inst]["long"] += qty * px
                elif qty < Decimal("0.0"):
                    exps[inst]["short"] += abs(qty) * px
            return exps

        curr_exps = build_exposures(curr_positions, curr_val_map)
        prior_exps = build_exposures(prior_positions, prior_val_map)

        all_insts = set(curr_exps.keys()).union(set(prior_exps.keys()))
        comparison_records: List[InstrumentExposureComparison] = []
        item_responses: List[InstrumentExposureComparisonItemResponse] = []

        now = utc_now()

        for inst in all_insts:
            c_l = curr_exps.get(inst, {}).get("long", Decimal("0.000000"))
            c_s = curr_exps.get(inst, {}).get("short", Decimal("0.000000"))
            c_g = c_l + c_s
            c_n = c_l - c_s

            p_l = prior_exps.get(inst, {}).get("long", Decimal("0.000000"))
            p_s = prior_exps.get(inst, {}).get("short", Decimal("0.000000"))
            p_g = p_l + p_s
            p_n = p_l - p_s

            d_l = c_l - p_l
            d_s = c_s - p_s
            d_g = c_g - p_g
            d_n = c_n - p_n

            # Percentage change
            pct_g: Optional[Decimal] = None
            if p_g > Decimal("0.0"):
                pct_g = ((c_g - p_g) / p_g * Decimal("100.0")).quantize(Decimal("0.000001"))

            # Lifecycle indicator
            indicator = ExposureLifecycleIndicator.UNCHANGED_EXPOSURE.value
            if p_g == Decimal("0.0") and c_g > Decimal("0.0"):
                indicator = ExposureLifecycleIndicator.NEW_POSITION.value
            elif p_g > Decimal("0.0") and c_g == Decimal("0.0"):
                indicator = ExposureLifecycleIndicator.CLOSED_POSITION.value
            elif (p_n > Decimal("0.0") and c_n < Decimal("0.0")) or (p_n < Decimal("0.0") and c_n > Decimal("0.0")):
                indicator = ExposureLifecycleIndicator.DIRECTION_CHANGED.value
            elif c_g > p_g:
                indicator = ExposureLifecycleIndicator.INCREASED_EXPOSURE.value
            elif c_g < p_g:
                indicator = ExposureLifecycleIndicator.REDUCED_EXPOSURE.value

            meta = await self.repo.get_instrument_metadata(inst)
            sym = meta.short_name if meta else inst
            name = meta.canonical_name if meta else inst

            rec = InstrumentExposureComparison(
                portfolio_id=portfolio_id,
                instrument_id=inst,
                current_snapshot_id=current_snapshot_id,
                prior_snapshot_id=prior_snapshot_id,
                current_long_exposure=c_l,
                prior_long_exposure=p_l,
                long_exposure_change=d_l,
                current_short_exposure=c_s,
                prior_short_exposure=p_s,
                short_exposure_change=d_s,
                current_net_exposure=c_n,
                prior_net_exposure=p_n,
                net_exposure_change=d_n,
                current_gross_exposure=c_g,
                prior_gross_exposure=p_g,
                gross_exposure_change=d_g,
                gross_percentage_change=pct_g,
                lifecycle_indicator=indicator,
                calculated_at=now,
            )
            comparison_records.append(rec)

            item_responses.append(
                InstrumentExposureComparisonItemResponse(
                    instrument_id=inst,
                    symbol=sym,
                    instrument_name=name,
                    current_long_exposure=c_l,
                    prior_long_exposure=p_l,
                    long_exposure_change=d_l,
                    current_short_exposure=c_s,
                    prior_short_exposure=p_s,
                    short_exposure_change=d_s,
                    current_net_exposure=c_n,
                    prior_net_exposure=p_n,
                    net_exposure_change=d_n,
                    current_gross_exposure=c_g,
                    prior_gross_exposure=p_g,
                    gross_exposure_change=d_g,
                    gross_percentage_change=pct_g,
                    lifecycle_indicator=indicator,
                )
            )

        await self.repo.save_comparisons(comparison_records)

        return InstrumentExposureComparisonResponse(
            portfolio_id=portfolio_id,
            current_snapshot_id=current_snapshot_id,
            prior_snapshot_id=prior_snapshot_id,
            reporting_currency="USD",
            items=item_responses,
        )
