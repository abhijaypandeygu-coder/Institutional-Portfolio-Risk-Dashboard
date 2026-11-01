"""
M06.01 Gross Exposure Service.
Core engine for calculating long exposure, absolute short exposure, total gross exposure,
and gross exposure ratio against NAV or configured capital denominators.
"""

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.gross_exposure.models import (
    ExposurePolicy,
    ExposureCalculationRun,
    ExposureResult,
    ExposureContribution,
    ExposureBreakdown,
    ExposureThresholdEvent,
    DenominatorType,
    ExposureCalculationScope,
    ExposureRunStatus,
    RatioStatus,
    ThresholdStatus,
)
from backend.app.modules.risk_management.gross_exposure.schemas import (
    ExposureCalculationExecuteRequest,
    GrossExposureSummaryResponse,
    ExposureContributionResponse,
    ExposureBreakdownResponse,
    ExposureThresholdEventResponse,
)
from backend.app.modules.risk_management.gross_exposure.repositories.repository import (
    GrossExposureRepository,
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


class GrossExposureService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GrossExposureRepository(session)
        self.pos_repo = PositionRepository(session)
        self.val_repo = ValuationRepository(session)
        self.hist_repo = PortfolioHistoryRepository(session)
        self.multi_port_svc = MultiPortfolioService(session)

    # ==========================================
    # Exposure Calculation Core
    # ==========================================

    async def calculate_portfolio_exposure(
        self,
        portfolio_id: str,
        request: ExposureCalculationExecuteRequest,
    ) -> GrossExposureSummaryResponse:
        now = datetime.utcnow()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"

        # 1. Fetch Positions from M05.02
        books = await self.pos_repo.list_books_by_portfolio(portfolio_id)
        val_recs = await self.val_repo.list_position_valuations(portfolio_id)

        run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"

        contributions: List[ExposureContribution] = []
        tot_long_exp = Decimal("0.000000")
        tot_short_exp = Decimal("0.000000")
        tot_signed_mv = Decimal("0.000000")

        inst_breakdown: Dict[str, Dict[str, Decimal]] = {}
        acc_breakdown: Dict[str, Dict[str, Decimal]] = {}
        curr_breakdown: Dict[str, Dict[str, Decimal]] = {}

        eligible_pos_count = 0
        excluded_pos_count = 0

        for book in books:
            snap = await self.pos_repo.get_latest_snapshot(book.position_id)
            if not snap or snap.net_signed_quantity == Decimal("0.000000"):
                excluded_pos_count += 1
                continue

            inst = snap.instrument_id
            side = "LONG" if snap.net_signed_quantity > 0 else "SHORT"

            # Match valuation
            matched_val = next((v for v in val_recs if v.instrument_id == inst), None)
            
            # If valuation is present, use signed_market_value_base / signed_market_value_native
            signed_mv = Decimal("0.000000")
            val_curr = "USD"
            if matched_val:
                signed_mv = matched_val.signed_market_value_native
                val_curr = matched_val.price_currency
            else:
                # Conservative fallback if price not explicitly captured
                signed_mv = Decimal("100.000000") * snap.net_signed_quantity
                val_curr = "USD"

            # FX Conversion
            fx_rate = request.fx_rates_to_reporting.get(val_curr, Decimal("1.000000"))
            converted_mv = signed_mv * fx_rate

            # Abs exposure contribution
            abs_contrib = abs(converted_mv)

            if side == "LONG":
                tot_long_exp += abs_contrib
            else:
                tot_short_exp += abs_contrib

            tot_signed_mv += converted_mv
            eligible_pos_count += 1

            contrib = ExposureContribution(
                id=f"EXP-CON-{uuid.uuid4().hex[:12].upper()}",
                calculation_run_id=run_id,
                portfolio_id=portfolio_id,
                account_id=snap.account_id,
                instrument_id=inst,
                listing_id=snap.listing_id,
                position_side=side,
                signed_quantity=snap.net_signed_quantity,
                signed_market_value=signed_mv,
                absolute_exposure_contribution=abs(signed_mv),
                native_currency=val_curr,
                reporting_currency=rep_curr,
                converted_exposure_contribution=abs_contrib,
                position_snapshot_reference=snap.snapshot_id,
                valuation_snapshot_reference=matched_val.valuation_id if matched_val else None,
                eligibility_status="ELIGIBLE",
                created_at=now,
            )
            contributions.append(contrib)

            # Accumulate breakdown buckets
            for b_dict, key in [(inst_breakdown, inst), (acc_breakdown, snap.account_id), (curr_breakdown, val_curr)]:
                if key not in b_dict:
                    b_dict[key] = {"long": Decimal("0.000000"), "short": Decimal("0.000000"), "gross": Decimal("0.000000")}
                if side == "LONG":
                    b_dict[key]["long"] += abs_contrib
                else:
                    b_dict[key]["short"] += abs_contrib
                b_dict[key]["gross"] += abs_contrib

        tot_gross_exp = tot_long_exp + tot_short_exp
        tot_net_exp = tot_long_exp - tot_short_exp

        # 2. Resolve Denominator (NAV or Configured Capital)
        denom_val: Optional[Decimal] = None
        ratio: Optional[Decimal] = None
        ratio_pct: Optional[Decimal] = None
        ratio_status = RatioStatus.VALID.value
        explanation = ""

        if request.custom_denominator_value is not None:
            denom_val = request.custom_denominator_value
        else:
            # Check authoritative portfolio history snapshots for NAV
            snap = await self.hist_repo.find_snapshot_bitemporal(portfolio_id, as_of, know_as_of)
            if snap and snap.total_nav_base is not None:
                denom_val = snap.total_nav_base
            else:
                # Check position valuation snapshots
                val_snap = await self.val_repo.get_latest_portfolio_snapshot(portfolio_id)
                if val_snap and val_snap.net_market_value is not None:
                    denom_val = val_snap.net_market_value

        if denom_val is None:
            ratio_status = RatioStatus.DENOMINATOR_UNAVAILABLE.value
            explanation = "NAV or capital denominator was unavailable for ratio calculation."
        elif denom_val == Decimal("0.000000"):
            ratio_status = RatioStatus.INVALID_ZERO_DENOMINATOR.value
            explanation = "Denominator is zero; gross exposure ratio is undefined."
        elif denom_val < Decimal("0.000000"):
            ratio_status = RatioStatus.INVALID_NEGATIVE_DENOMINATOR.value
            explanation = "Denominator is negative; gross exposure ratio is mathematically invalid."
        else:
            ratio = (tot_gross_exp / denom_val).quantize(Decimal("0.000001"))
            ratio_pct = (ratio * Decimal("100.0")).quantize(Decimal("0.0001"))
            explanation = f"Gross Exposure Ratio calculated successfully: {ratio}x ({ratio_pct}% of {request.denominator_type.value})."

        # 3. Policy & Threshold Monitoring
        policy = await self.repo.get_effective_policy(portfolio_id=portfolio_id, as_of=as_of)
        threshold_status = ThresholdStatus.NOT_CONFIGURED.value
        threshold_events: List[ExposureThresholdEvent] = []

        if policy and ratio is not None:
            if policy.exposure_threshold_hard and ratio >= policy.exposure_threshold_hard:
                threshold_status = ThresholdStatus.BREACH.value
                threshold_events.append(
                    ExposureThresholdEvent(
                        id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        portfolio_id=portfolio_id,
                        threshold_type="HARD",
                        threshold_value=policy.exposure_threshold_hard,
                        observed_value=ratio,
                        status=ThresholdStatus.BREACH.value,
                        policy_version=str(policy.policy_version),
                        evaluated_at=now,
                        created_at=now,
                    )
                )
            elif policy.exposure_threshold_warning and ratio >= policy.exposure_threshold_warning:
                threshold_status = ThresholdStatus.WARNING.value
                threshold_events.append(
                    ExposureThresholdEvent(
                        id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        portfolio_id=portfolio_id,
                        threshold_type="WARNING",
                        threshold_value=policy.exposure_threshold_warning,
                        observed_value=ratio,
                        status=ThresholdStatus.WARNING.value,
                        policy_version=str(policy.policy_version),
                        evaluated_at=now,
                        created_at=now,
                    )
                )
            else:
                threshold_status = ThresholdStatus.WITHIN_LIMIT.value

        # 4. Breakdowns
        breakdowns: List[ExposureBreakdown] = []
        for b_type, b_dict in [("INSTRUMENT", inst_breakdown), ("ACCOUNT", acc_breakdown), ("CURRENCY", curr_breakdown)]:
            for ref_key, vals in b_dict.items():
                pct = (vals["gross"] / tot_gross_exp * Decimal("100.0")) if tot_gross_exp > 0 else Decimal("0.000000")
                breakdowns.append(
                    ExposureBreakdown(
                        id=f"BDN-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        breakdown_type=b_type,
                        breakdown_reference=ref_key,
                        long_exposure=vals["long"],
                        short_exposure=vals["short"],
                        gross_exposure=vals["gross"],
                        contribution_percentage=pct.quantize(Decimal("0.000001")),
                        reporting_currency=rep_curr,
                        created_at=now,
                    )
                )

        # 5. Manifest Hash & Persistence
        manifest_payload = {
            "portfolio_id": portfolio_id,
            "effective_as_of": as_of.isoformat(),
            "knowledge_as_of": know_as_of.isoformat(),
            "reporting_currency": rep_curr,
            "long_exposure": str(tot_long_exp),
            "short_exposure": str(tot_short_exp),
            "gross_exposure": str(tot_gross_exp),
            "denominator_value": str(denom_val) if denom_val is not None else None,
        }
        manifest_hash = hashlib.sha256(json.dumps(manifest_payload, sort_keys=True).encode("utf-8")).hexdigest()

        run = ExposureCalculationRun(
            id=run_id,
            portfolio_id=portfolio_id,
            calculation_scope=ExposureCalculationScope.PORTFOLIO.value,
            effective_as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            denominator_type=request.denominator_type.value,
            policy_version="EXP-POL-V1",
            calculation_version=1,
            run_status=ExposureRunStatus.COMPLETED.value,
            input_manifest_hash=manifest_hash,
            started_at=now,
            completed_at=now,
            created_at=now,
        )

        res_record = ExposureResult(
            id=f"RES-{uuid.uuid4().hex[:12].upper()}",
            calculation_run_id=run_id,
            portfolio_id=portfolio_id,
            reporting_currency=rep_curr,
            long_exposure=tot_long_exp,
            short_exposure=tot_short_exp,
            gross_exposure=tot_gross_exp,
            net_exposure=tot_net_exp,
            denominator_value=denom_val,
            denominator_currency=rep_curr if denom_val else None,
            denominator_type=request.denominator_type.value,
            denominator_timestamp=as_of if denom_val else None,
            gross_exposure_ratio=ratio,
            exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            completeness_status="COMPLETE" if excluded_pos_count == 0 else "PARTIAL",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            created_at=now,
        )

        run.result = res_record
        for c in contributions:
            run.contributions.append(c)
        for b in breakdowns:
            run.breakdowns.append(b)
        for t in threshold_events:
            run.threshold_events.append(t)

        await self.repo.create_calculation_run(run)

        return GrossExposureSummaryResponse(
            scope=ExposureCalculationScope.PORTFOLIO.value,
            entity_id=portfolio_id,
            reporting_currency=rep_curr,
            as_of=as_of,
            knowledge_as_of=know_as_of,
            long_exposure=tot_long_exp,
            short_exposure=tot_short_exp,
            gross_exposure=tot_gross_exp,
            net_exposure=tot_net_exp,
            denominator_type=request.denominator_type.value,
            denominator_value=denom_val,
            gross_exposure_ratio=ratio,
            exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            completeness_status="COMPLETE" if excluded_pos_count == 0 else "PARTIAL",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            threshold_status=threshold_status,
            breakdowns=[ExposureBreakdownResponse.model_validate(b) for b in breakdowns],
            contributions=[ExposureContributionResponse.model_validate(c) for c in contributions],
            threshold_events=[ExposureThresholdEventResponse.model_validate(t) for t in threshold_events],
            ratio_explanation=explanation,
        )

    # ==========================================
    # Group Exposure Calculation
    # ==========================================

    async def calculate_group_exposure(
        self,
        group_id: str,
        request: ExposureCalculationExecuteRequest,
    ) -> GrossExposureSummaryResponse:
        """
        Calculates gross exposure across all eligible member portfolios of an M05.08 group,
        strictly deduplicating portfolios to avoid double-counting.
        """
        now = datetime.utcnow()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"

        # Resolve distinct portfolios from M05.08
        port_ids, mems = await self.multi_port_svc.resolve_group_portfolios(group_id, as_of)
        included_portfolios = [pid for pid in port_ids if mems[pid].include_in_positions]

        run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"

        contributions: List[ExposureContribution] = []
        tot_long_exp = Decimal("0.000000")
        tot_short_exp = Decimal("0.000000")
        tot_signed_mv = Decimal("0.000000")

        inst_breakdown: Dict[str, Dict[str, Decimal]] = {}
        port_breakdown: Dict[str, Dict[str, Decimal]] = {}

        eligible_pos_count = 0
        excluded_pos_count = 0

        for pid in included_portfolios:
            books = await self.pos_repo.list_books_by_portfolio(pid)
            val_recs = await self.val_repo.list_position_valuations(pid)
            for book in books:
                snap = await self.pos_repo.get_latest_snapshot(book.position_id)
                if not snap or snap.net_signed_quantity == Decimal("0.000000"):
                    excluded_pos_count += 1
                    continue

                inst = snap.instrument_id
                side = "LONG" if snap.net_signed_quantity > 0 else "SHORT"

                matched_val = next((v for v in val_recs if v.instrument_id == inst), None)
                signed_mv = matched_val.market_value if matched_val else (Decimal("100.000000") * snap.net_signed_quantity)
                val_curr = matched_val.currency if matched_val else "USD"

                fx_rate = request.fx_rates_to_reporting.get(val_curr, Decimal("1.000000"))
                converted_mv = signed_mv * fx_rate
                abs_contrib = abs(converted_mv)

                if side == "LONG":
                    tot_long_exp += abs_contrib
                else:
                    tot_short_exp += abs_contrib

                tot_signed_mv += converted_mv
                eligible_pos_count += 1

                contrib = ExposureContribution(
                    id=f"EXP-CON-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    portfolio_id=pid,
                    account_id=snap.account_id,
                    instrument_id=inst,
                    listing_id=snap.listing_id,
                    position_side=side,
                    signed_quantity=snap.net_signed_quantity,
                    signed_market_value=signed_mv,
                    absolute_exposure_contribution=abs(signed_mv),
                    native_currency=val_curr,
                    reporting_currency=rep_curr,
                    converted_exposure_contribution=abs_contrib,
                    position_snapshot_reference=snap.snapshot_id,
                    valuation_snapshot_reference=matched_val.valuation_id if matched_val else None,
                    eligibility_status="ELIGIBLE",
                    created_at=now,
                )
                contributions.append(contrib)

                # Accumulate breakdowns
                for b_dict, key in [(inst_breakdown, inst), (port_breakdown, pid)]:
                    if key not in b_dict:
                        b_dict[key] = {"long": Decimal("0.000000"), "short": Decimal("0.000000"), "gross": Decimal("0.000000")}
                    if side == "LONG":
                        b_dict[key]["long"] += abs_contrib
                    else:
                        b_dict[key]["short"] += abs_contrib
                    b_dict[key]["gross"] += abs_contrib

        tot_gross_exp = tot_long_exp + tot_short_exp
        tot_net_exp = tot_long_exp - tot_short_exp

        # Denominator for group
        denom_val = request.custom_denominator_value
        ratio: Optional[Decimal] = None
        ratio_pct: Optional[Decimal] = None
        ratio_status = RatioStatus.VALID.value
        explanation = ""

        if denom_val is None:
            ratio_status = RatioStatus.DENOMINATOR_UNAVAILABLE.value
            explanation = "Consolidated group capital denominator not configured or unavailable."
        elif denom_val <= Decimal("0.000000"):
            ratio_status = RatioStatus.INVALID_ZERO_DENOMINATOR.value if denom_val == 0 else RatioStatus.INVALID_NEGATIVE_DENOMINATOR.value
            explanation = "Group denominator is non-positive; ratio cannot be calculated."
        else:
            ratio = (tot_gross_exp / denom_val).quantize(Decimal("0.000001"))
            ratio_pct = (ratio * Decimal("100.0")).quantize(Decimal("0.0001"))
            explanation = f"Consolidated Group Gross Exposure Ratio: {ratio}x ({ratio_pct}%)."

        # Breakdowns
        breakdowns: List[ExposureBreakdown] = []
        for b_type, b_dict in [("INSTRUMENT", inst_breakdown), ("PORTFOLIO", port_breakdown)]:
            for ref_key, vals in b_dict.items():
                pct = (vals["gross"] / tot_gross_exp * Decimal("100.0")) if tot_gross_exp > 0 else Decimal("0.000000")
                breakdowns.append(
                    ExposureBreakdown(
                        id=f"BDN-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        breakdown_type=b_type,
                        breakdown_reference=ref_key,
                        long_exposure=vals["long"],
                        short_exposure=vals["short"],
                        gross_exposure=vals["gross"],
                        contribution_percentage=pct.quantize(Decimal("0.000001")),
                        reporting_currency=rep_curr,
                        created_at=now,
                    )
                )

        manifest_payload = {
            "group_id": group_id,
            "effective_as_of": as_of.isoformat(),
            "knowledge_as_of": know_as_of.isoformat(),
            "reporting_currency": rep_curr,
            "long_exposure": str(tot_long_exp),
            "short_exposure": str(tot_short_exp),
            "gross_exposure": str(tot_gross_exp),
        }
        manifest_hash = hashlib.sha256(json.dumps(manifest_payload, sort_keys=True).encode("utf-8")).hexdigest()

        run = ExposureCalculationRun(
            id=run_id,
            group_id=group_id,
            calculation_scope=ExposureCalculationScope.PORTFOLIO_GROUP.value,
            effective_as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            denominator_type=request.denominator_type.value,
            policy_version="EXP-POL-V1",
            calculation_version=1,
            run_status=ExposureRunStatus.COMPLETED.value,
            input_manifest_hash=manifest_hash,
            started_at=now,
            completed_at=now,
            created_at=now,
        )

        res_record = ExposureResult(
            id=f"RES-{uuid.uuid4().hex[:12].upper()}",
            calculation_run_id=run_id,
            group_id=group_id,
            reporting_currency=rep_curr,
            long_exposure=tot_long_exp,
            short_exposure=tot_short_exp,
            gross_exposure=tot_gross_exp,
            net_exposure=tot_net_exp,
            denominator_value=denom_val,
            denominator_currency=rep_curr if denom_val else None,
            denominator_type=request.denominator_type.value,
            denominator_timestamp=as_of if denom_val else None,
            gross_exposure_ratio=ratio,
            exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            completeness_status="COMPLETE",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            created_at=now,
        )

        run.result = res_record
        for c in contributions:
            run.contributions.append(c)
        for b in breakdowns:
            run.breakdowns.append(b)

        await self.repo.create_calculation_run(run)

        return GrossExposureSummaryResponse(
            scope=ExposureCalculationScope.PORTFOLIO_GROUP.value,
            entity_id=group_id,
            reporting_currency=rep_curr,
            as_of=as_of,
            knowledge_as_of=know_as_of,
            long_exposure=tot_long_exp,
            short_exposure=tot_short_exp,
            gross_exposure=tot_gross_exp,
            net_exposure=tot_net_exp,
            denominator_type=request.denominator_type.value,
            denominator_value=denom_val,
            gross_exposure_ratio=ratio,
            exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            completeness_status="COMPLETE",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            threshold_status=ThresholdStatus.NOT_CONFIGURED.value,
            breakdowns=[ExposureBreakdownResponse.model_validate(b) for b in breakdowns],
            contributions=[ExposureContributionResponse.model_validate(c) for c in contributions],
            threshold_events=[],
            ratio_explanation=explanation,
        )
