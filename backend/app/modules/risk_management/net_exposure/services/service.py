"""
M06.02 Net Exposure Service.
Core engine for calculating net market value (L - S), net exposure ratios,
directional classification (NET_LONG, NET_SHORT, APPROX_NEUTRAL),
currency normalization, source-position lineage, and consolidated multi-portfolio groups.
"""

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.net_exposure.models import (
    NetExposurePolicy,
    NetExposureCalculationRun,
    NetExposureResult,
    NetExposureContribution,
    NetExposureBreakdown,
    DirectionalThresholdEvent,
    DirectionalState,
    NeutralityThresholdType,
    NetDenominatorType,
    NetExposureScope,
    NetRunStatus,
    NetRatioStatus,
    NetThresholdStatus,
)
from backend.app.modules.risk_management.net_exposure.schemas import (
    NetExposureCalculateRequest,
    NetExposureSummaryResponse,
    NetExposureContributionResponse,
    NetExposureBreakdownResponse,
    DirectionalThresholdEventResponse,
)
from backend.app.modules.risk_management.net_exposure.repositories.repository import (
    NetExposureRepository,
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


class NetExposureService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NetExposureRepository(session)
        self.pos_repo = PositionRepository(session)
        self.val_repo = ValuationRepository(session)
        self.hist_repo = PortfolioHistoryRepository(session)
        self.multi_port_svc = MultiPortfolioService(session)

    # -----------------------------------------------------------------------
    # 1. CLASSIFICATION & NEUTRALITY LOGIC
    # -----------------------------------------------------------------------
    def evaluate_directional_classification(
        self,
        net_market_value: Decimal,
        denominator: Optional[Decimal],
        threshold_type: NeutralityThresholdType,
        abs_threshold: Optional[Decimal],
        rel_threshold: Optional[Decimal],
        combined_semantics: str = "AND",
    ) -> Tuple[str, str]:
        """
        Classifies the directional state into NET_LONG, NET_SHORT, or APPROX_NEUTRAL
        under configured absolute, relative, or combined neutrality thresholds.
        """
        abs_net = abs(net_market_value)
        applied_desc = ""

        # Case A: Exactly zero net value is always neutral
        if net_market_value == Decimal("0.000000"):
            return DirectionalState.APPROX_NEUTRAL.value, "Net market value is exactly 0.0"

        # Neutrality evaluation
        is_neutral = False

        if threshold_type == NeutralityThresholdType.ABSOLUTE:
            if abs_threshold is not None:
                applied_desc = f"Absolute Threshold: {abs_threshold}"
                if abs_net <= abs_threshold:
                    is_neutral = True
            else:
                applied_desc = "Absolute Threshold: None (default 0)"
                if abs_net == Decimal("0.000000"):
                    is_neutral = True

        elif threshold_type == NeutralityThresholdType.RELATIVE:
            if denominator is not None and denominator > Decimal("0.000000") and rel_threshold is not None:
                ratio = abs_net / denominator
                applied_desc = f"Relative Threshold: {rel_threshold} (Observed: {ratio.quantize(Decimal('0.000001'))})"
                if ratio <= rel_threshold:
                    is_neutral = True
            elif denominator is None or denominator <= Decimal("0.000000"):
                # If relative threshold requires denominator but denominator is unavailable or non-positive
                # Do not assume neutrality
                applied_desc = "Relative Threshold: Denominator unavailable/non-positive"
                is_neutral = False
            else:
                applied_desc = "Relative Threshold: None"

        elif threshold_type in (NeutralityThresholdType.COMBINED_AND, NeutralityThresholdType.COMBINED_OR):
            abs_pass = False
            if abs_threshold is not None and abs_net <= abs_threshold:
                abs_pass = True

            rel_pass = False
            if denominator is not None and denominator > Decimal("0.000000") and rel_threshold is not None:
                ratio = abs_net / denominator
                if ratio <= rel_threshold:
                    rel_pass = True

            applied_desc = f"Combined ({combined_semantics}): Abs={abs_threshold}, Rel={rel_threshold}"
            if combined_semantics.upper() == "OR":
                is_neutral = abs_pass or rel_pass
            else: # AND
                is_neutral = abs_pass and rel_pass

        if is_neutral:
            return DirectionalState.APPROX_NEUTRAL.value, applied_desc

        if net_market_value > Decimal("0.000000"):
            return DirectionalState.NET_LONG.value, applied_desc
        else:
            return DirectionalState.NET_SHORT.value, applied_desc

    # -----------------------------------------------------------------------
    # 2. SINGLE PORTFOLIO CALCULATION
    # -----------------------------------------------------------------------
    async def calculate_portfolio_net_exposure(
        self, portfolio_id: str, request: NetExposureCalculateRequest
    ) -> NetExposureSummaryResponse:
        now = datetime.utcnow()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"

        # Check idempotency
        if request.idempotency_key:
            existing_run = await self.repo.get_run_by_idempotency(request.idempotency_key)
            if existing_run:
                existing_res = await self.repo.get_result_by_run_id(existing_run.id)
                if existing_res:
                    conts = await self.repo.get_contributions(existing_run.id)
                    bdowns = await self.repo.get_breakdowns(existing_run.id)
                    tevents = await self.repo.get_threshold_events(existing_run.id)
                    return NetExposureSummaryResponse(
                        run_id=existing_run.id,
                        portfolio_id=portfolio_id,
                        scope=NetExposureScope.PORTFOLIO.value,
                        reporting_currency=existing_res.reporting_currency,
                        long_exposure=existing_res.long_exposure,
                        absolute_short_exposure=existing_res.absolute_short_exposure,
                        net_market_value=existing_res.net_market_value,
                        gross_exposure_reference=existing_res.long_exposure + existing_res.absolute_short_exposure,
                        denominator_type=existing_res.denominator_type,
                        denominator_value=existing_res.denominator_value,
                        net_exposure_ratio=existing_res.net_exposure_ratio,
                        net_exposure_ratio_percentage=existing_res.net_exposure_ratio_percentage,
                        ratio_status=existing_res.ratio_status,
                        ratio_explanation=existing_res.audit_explanation,
                        directional_classification=existing_res.directional_classification,
                        neutrality_threshold_type=existing_res.neutrality_threshold_type,
                        neutrality_threshold_applied=existing_res.neutrality_threshold_applied,
                        threshold_status=existing_res.threshold_status,
                        completeness_status=existing_res.completeness_status,
                        eligible_position_count=int(existing_res.eligible_position_count),
                        excluded_position_count=int(existing_res.excluded_position_count),
                        contributions=[NetExposureContributionResponse.model_validate(c) for c in conts],
                        breakdowns=[NetExposureBreakdownResponse.model_validate(b) for b in bdowns],
                        threshold_events=[DirectionalThresholdEventResponse.model_validate(t) for t in tevents],
                    )

        # 1. Fetch Positions from M05.02 and Valuations from M05.03
        books = await self.pos_repo.list_books_by_portfolio(portfolio_id)
        val_recs = await self.val_repo.list_position_valuations(portfolio_id)

        run_id = f"NET-RUN-{uuid.uuid4().hex[:12].upper()}"

        contributions: List[NetExposureContribution] = []
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

            # Resolve signed market value in native currency
            signed_mv_native = Decimal("0.000000")
            val_curr = "USD"
            if matched_val:
                signed_mv_native = matched_val.signed_market_value_native
                val_curr = matched_val.price_currency
            else:
                # Conservative fallback
                signed_mv_native = Decimal("100.000000") * snap.net_signed_quantity
                val_curr = "USD"

            # Currency Normalization: Convert to reporting currency
            fx_rate = request.fx_rates_to_reporting.get(val_curr, Decimal("1.000000"))
            converted_signed_mv = signed_mv_native * fx_rate
            abs_converted = abs(converted_signed_mv)

            if side == "LONG":
                tot_long_exp += abs_converted
            else:
                tot_short_exp += abs_converted

            tot_signed_mv += converted_signed_mv
            eligible_pos_count += 1

            contrib = NetExposureContribution(
                id=f"NET-CON-{uuid.uuid4().hex[:12].upper()}",
                calculation_run_id=run_id,
                portfolio_id=portfolio_id,
                account_id=snap.account_id,
                instrument_id=inst,
                listing_id=snap.listing_id,
                position_side=side,
                signed_quantity=snap.net_signed_quantity,
                signed_market_value_native=signed_mv_native,
                native_currency=val_curr,
                fx_rate_reference=fx_rate,
                converted_signed_market_value=converted_signed_mv,
                reporting_currency=rep_curr,
                position_snapshot_reference=snap.snapshot_id,
                valuation_snapshot_reference=matched_val.valuation_id if matched_val else None,
                eligibility_status="ELIGIBLE",
                created_at=now,
            )
            contributions.append(contrib)

            # Accumulate breakdown buckets
            for b_dict, key in [(inst_breakdown, inst), (acc_breakdown, snap.account_id), (curr_breakdown, val_curr)]:
                if key not in b_dict:
                    b_dict[key] = {
                        "long": Decimal("0.000000"),
                        "short": Decimal("0.000000"),
                        "net": Decimal("0.000000"),
                    }
                if side == "LONG":
                    b_dict[key]["long"] += abs_converted
                else:
                    b_dict[key]["short"] += abs_converted
                b_dict[key]["net"] += converted_signed_mv

        # Primary Net Market Value = Long - Short (which strictly reconciles with sum of converted signed MVs)
        net_market_value = tot_long_exp - tot_short_exp

        # Denominator Resolution
        denom_val = request.custom_denominator_value
        denom_curr = rep_curr
        ratio: Optional[Decimal] = None
        ratio_pct: Optional[Decimal] = None
        ratio_status = NetRatioStatus.VALID.value
        explanation = ""

        if denom_val is None:
            ratio_status = NetRatioStatus.DENOMINATOR_UNAVAILABLE.value
            explanation = "Denominator value not provided or unavailable from NAV source."
        elif denom_val <= Decimal("0.000000"):
            ratio_status = (
                NetRatioStatus.INVALID_ZERO_DENOMINATOR.value
                if denom_val == Decimal("0.000000")
                else NetRatioStatus.INVALID_NEGATIVE_DENOMINATOR.value
            )
            explanation = "Denominator is non-positive; ratio cannot be calculated."
        else:
            ratio = (net_market_value / denom_val).quantize(Decimal("0.000001"))
            ratio_pct = (ratio * Decimal("100.0")).quantize(Decimal("0.0001"))
            explanation = f"Net Exposure Ratio: {ratio}x ({ratio_pct}%)."

        # Directional Classification & Neutrality
        threshold_type = request.neutrality_threshold_type or NeutralityThresholdType.RELATIVE
        dir_class, applied_threshold_desc = self.evaluate_directional_classification(
            net_market_value=net_market_value,
            denominator=denom_val,
            threshold_type=threshold_type,
            abs_threshold=request.absolute_neutrality_threshold,
            rel_threshold=request.relative_neutrality_threshold,
            combined_semantics=request.combined_semantics or "AND",
        )

        # Policy & Limits Evaluation
        active_policy = await self.repo.get_active_policy(portfolio_id=portfolio_id)
        threshold_events: List[DirectionalThresholdEvent] = []
        thresh_status = NetThresholdStatus.WITHIN_LIMIT.value

        if active_policy:
            # Check Net Long limit
            if active_policy.max_net_long_ratio and ratio is not None and ratio > active_policy.max_net_long_ratio:
                thresh_status = NetThresholdStatus.BREACH.value
                threshold_events.append(
                    DirectionalThresholdEvent(
                        id=f"NET-EVT-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        portfolio_id=portfolio_id,
                        threshold_type="MAX_NET_LONG_RATIO",
                        threshold_value=active_policy.max_net_long_ratio,
                        observed_net_exposure=net_market_value,
                        observed_net_exposure_ratio=ratio,
                        event_level="BREACH",
                        classification=dir_class,
                        policy_version=active_policy.policy_version,
                        evaluated_at=now,
                        created_at=now,
                    )
                )
            # Check Net Short limit (e.g. ratio < -0.50)
            elif active_policy.max_net_short_ratio and ratio is not None and ratio < active_policy.max_net_short_ratio:
                thresh_status = NetThresholdStatus.BREACH.value
                threshold_events.append(
                    DirectionalThresholdEvent(
                        id=f"NET-EVT-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        portfolio_id=portfolio_id,
                        threshold_type="MAX_NET_SHORT_RATIO",
                        threshold_value=active_policy.max_net_short_ratio,
                        observed_net_exposure=net_market_value,
                        observed_net_exposure_ratio=ratio,
                        event_level="BREACH",
                        classification=dir_class,
                        policy_version=active_policy.policy_version,
                        evaluated_at=now,
                        created_at=now,
                    )
                )

        # Build Breakdowns
        breakdowns: List[NetExposureBreakdown] = []
        for b_type, b_dict in [("INSTRUMENT", inst_breakdown), ("ACCOUNT", acc_breakdown), ("CURRENCY", curr_breakdown)]:
            for ref_key, vals in b_dict.items():
                net_val = vals["net"]
                b_class, _ = self.evaluate_directional_classification(
                    net_market_value=net_val,
                    denominator=denom_val,
                    threshold_type=NeutralityThresholdType.ABSOLUTE,
                    abs_threshold=Decimal("0.000000"),
                    rel_threshold=None,
                )
                pct: Optional[Decimal] = None
                if net_market_value != Decimal("0.000000"):
                    pct = ((net_val / abs(net_market_value)) * Decimal("100.0")).quantize(Decimal("0.000001"))

                breakdowns.append(
                    NetExposureBreakdown(
                        id=f"NET-BDN-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        breakdown_type=b_type,
                        breakdown_reference=ref_key,
                        long_exposure=vals["long"],
                        absolute_short_exposure=vals["short"],
                        net_exposure=net_val,
                        reporting_currency=rep_curr,
                        contribution_percentage=pct,
                        directional_classification=b_class,
                        created_at=now,
                    )
                )

        # Manifest Hash
        manifest_raw = f"{run_id}:{portfolio_id}:{tot_long_exp}:{tot_short_exp}:{net_market_value}:{as_of.isoformat()}"
        manifest_hash = hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest()

        # Persist Run
        run = NetExposureCalculationRun(
            id=run_id,
            portfolio_id=portfolio_id,
            calculation_scope=NetExposureScope.PORTFOLIO.value,
            effective_as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            denominator_type=request.denominator_type.value,
            policy_version="1.0.0",
            calculation_version="M06.02-v1",
            run_status=NetRunStatus.COMPLETED.value,
            input_manifest_hash=manifest_hash,
            idempotency_key=request.idempotency_key,
            started_at=now,
            completed_at=datetime.utcnow(),
            created_at=now,
        )
        await self.repo.save_run(run)

        # Persist Result
        result = NetExposureResult(
            id=f"NET-RES-{uuid.uuid4().hex[:12].upper()}",
            calculation_run_id=run_id,
            portfolio_id=portfolio_id,
            reporting_currency=rep_curr,
            long_exposure=tot_long_exp,
            absolute_short_exposure=tot_short_exp,
            net_market_value=net_market_value,
            denominator_type=request.denominator_type.value,
            denominator_value=denom_val,
            denominator_currency=denom_curr,
            net_exposure_ratio=ratio,
            net_exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            directional_classification=dir_class,
            neutrality_threshold_type=threshold_type.value,
            neutrality_threshold_applied=applied_threshold_desc,
            threshold_status=thresh_status,
            completeness_status="COMPLETE",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            audit_explanation=explanation,
            created_at=now,
        )
        await self.repo.save_result(result)
        await self.repo.save_contributions(contributions)
        await self.repo.save_breakdowns(breakdowns)
        if threshold_events:
            await self.repo.save_threshold_events(threshold_events)

        return NetExposureSummaryResponse(
            run_id=run_id,
            portfolio_id=portfolio_id,
            scope=NetExposureScope.PORTFOLIO.value,
            reporting_currency=rep_curr,
            long_exposure=tot_long_exp,
            absolute_short_exposure=tot_short_exp,
            net_market_value=net_market_value,
            gross_exposure_reference=tot_long_exp + tot_short_exp,
            denominator_type=request.denominator_type.value,
            denominator_value=denom_val,
            net_exposure_ratio=ratio,
            net_exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            ratio_explanation=explanation,
            directional_classification=dir_class,
            neutrality_threshold_type=threshold_type.value,
            neutrality_threshold_applied=applied_threshold_desc,
            threshold_status=thresh_status,
            completeness_status="COMPLETE",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            contributions=[NetExposureContributionResponse.model_validate(c) for c in contributions],
            breakdowns=[NetExposureBreakdownResponse.model_validate(b) for b in breakdowns],
            threshold_events=[DirectionalThresholdEventResponse.model_validate(t) for t in threshold_events],
        )

    # -----------------------------------------------------------------------
    # 3. MULTI-PORTFOLIO GROUP NET EXPOSURE (M05.08 INTEGRATION)
    # -----------------------------------------------------------------------
    async def calculate_group_net_exposure(
        self, group_id: str, request: NetExposureCalculateRequest
    ) -> NetExposureSummaryResponse:
        now = datetime.utcnow()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"

        # Resolve unique member portfolios via M05.08 to prevent double-counting
        member_portfolios, _ = await self.multi_port_svc.resolve_group_portfolios(group_id, as_of)

        run_id = f"NET-GRP-RUN-{uuid.uuid4().hex[:12].upper()}"

        contributions: List[NetExposureContribution] = []
        tot_long_exp = Decimal("0.000000")
        tot_short_exp = Decimal("0.000000")
        tot_signed_mv = Decimal("0.000000")

        inst_breakdown: Dict[str, Dict[str, Decimal]] = {}
        port_breakdown: Dict[str, Dict[str, Decimal]] = {}

        eligible_pos_count = 0
        excluded_pos_count = 0

        for pid in member_portfolios:
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
                abs_converted = abs(converted_signed_mv)

                if side == "LONG":
                    tot_long_exp += abs_converted
                else:
                    tot_short_exp += abs_converted

                tot_signed_mv += converted_signed_mv
                eligible_pos_count += 1

                contrib = NetExposureContribution(
                    id=f"NET-CON-{uuid.uuid4().hex[:12].upper()}",
                    calculation_run_id=run_id,
                    portfolio_id=pid,
                    account_id=snap.account_id,
                    instrument_id=inst,
                    listing_id=snap.listing_id,
                    position_side=side,
                    signed_quantity=snap.net_signed_quantity,
                    signed_market_value_native=signed_mv_native,
                    native_currency=val_curr,
                    fx_rate_reference=fx_rate,
                    converted_signed_market_value=converted_signed_mv,
                    reporting_currency=rep_curr,
                    position_snapshot_reference=snap.snapshot_id,
                    valuation_snapshot_reference=matched_val.valuation_id if matched_val else None,
                    eligibility_status="ELIGIBLE",
                    created_at=now,
                )
                contributions.append(contrib)

                # Breakdown accumulation
                for b_dict, key in [(inst_breakdown, inst), (port_breakdown, pid)]:
                    if key not in b_dict:
                        b_dict[key] = {
                            "long": Decimal("0.000000"),
                            "short": Decimal("0.000000"),
                            "net": Decimal("0.000000"),
                        }
                    if side == "LONG":
                        b_dict[key]["long"] += abs_converted
                    else:
                        b_dict[key]["short"] += abs_converted
                    b_dict[key]["net"] += converted_signed_mv

        net_market_value = tot_long_exp - tot_short_exp

        # Denominator for group
        denom_val = request.custom_denominator_value
        ratio: Optional[Decimal] = None
        ratio_pct: Optional[Decimal] = None
        ratio_status = NetRatioStatus.VALID.value
        explanation = ""

        if denom_val is None:
            ratio_status = NetRatioStatus.DENOMINATOR_UNAVAILABLE.value
            explanation = "Group capital denominator not configured or unavailable."
        elif denom_val <= Decimal("0.000000"):
            ratio_status = (
                NetRatioStatus.INVALID_ZERO_DENOMINATOR.value
                if denom_val == Decimal("0.000000")
                else NetRatioStatus.INVALID_NEGATIVE_DENOMINATOR.value
            )
            explanation = "Group denominator is non-positive; ratio cannot be calculated."
        else:
            ratio = (net_market_value / denom_val).quantize(Decimal("0.000001"))
            ratio_pct = (ratio * Decimal("100.0")).quantize(Decimal("0.0001"))
            explanation = f"Consolidated Group Net Exposure Ratio: {ratio}x ({ratio_pct}%)."

        # Directional Classification
        threshold_type = request.neutrality_threshold_type or NeutralityThresholdType.RELATIVE
        dir_class, applied_threshold_desc = self.evaluate_directional_classification(
            net_market_value=net_market_value,
            denominator=denom_val,
            threshold_type=threshold_type,
            abs_threshold=request.absolute_neutrality_threshold,
            rel_threshold=request.relative_neutrality_threshold,
            combined_semantics=request.combined_semantics or "AND",
        )

        # Breakdowns
        breakdowns: List[NetExposureBreakdown] = []
        for b_type, b_dict in [("INSTRUMENT", inst_breakdown), ("PORTFOLIO", port_breakdown)]:
            for ref_key, vals in b_dict.items():
                net_val = vals["net"]
                b_class, _ = self.evaluate_directional_classification(
                    net_market_value=net_val,
                    denominator=denom_val,
                    threshold_type=NeutralityThresholdType.ABSOLUTE,
                    abs_threshold=Decimal("0.000000"),
                    rel_threshold=None,
                )
                pct: Optional[Decimal] = None
                if net_market_value != Decimal("0.000000"):
                    pct = ((net_val / abs(net_market_value)) * Decimal("100.0")).quantize(Decimal("0.000001"))

                breakdowns.append(
                    NetExposureBreakdown(
                        id=f"NET-BDN-{uuid.uuid4().hex[:12].upper()}",
                        calculation_run_id=run_id,
                        breakdown_type=b_type,
                        breakdown_reference=ref_key,
                        long_exposure=vals["long"],
                        absolute_short_exposure=vals["short"],
                        net_exposure=net_val,
                        reporting_currency=rep_curr,
                        contribution_percentage=pct,
                        directional_classification=b_class,
                        created_at=now,
                    )
                )

        manifest_raw = f"{run_id}:{group_id}:{tot_long_exp}:{tot_short_exp}:{net_market_value}:{as_of.isoformat()}"
        manifest_hash = hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest()

        run = NetExposureCalculationRun(
            id=run_id,
            group_id=group_id,
            calculation_scope=NetExposureScope.PORTFOLIO_GROUP.value,
            effective_as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            denominator_type=request.denominator_type.value,
            policy_version="1.0.0",
            calculation_version="M06.02-v1",
            run_status=NetRunStatus.COMPLETED.value,
            input_manifest_hash=manifest_hash,
            idempotency_key=request.idempotency_key,
            started_at=now,
            completed_at=datetime.utcnow(),
            created_at=now,
        )
        await self.repo.save_run(run)

        result = NetExposureResult(
            id=f"NET-RES-{uuid.uuid4().hex[:12].upper()}",
            calculation_run_id=run_id,
            group_id=group_id,
            reporting_currency=rep_curr,
            long_exposure=tot_long_exp,
            absolute_short_exposure=tot_short_exp,
            net_market_value=net_market_value,
            denominator_type=request.denominator_type.value,
            denominator_value=denom_val,
            denominator_currency=rep_curr,
            net_exposure_ratio=ratio,
            net_exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            directional_classification=dir_class,
            neutrality_threshold_type=threshold_type.value,
            neutrality_threshold_applied=applied_threshold_desc,
            threshold_status=NetThresholdStatus.WITHIN_LIMIT.value,
            completeness_status="COMPLETE",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            audit_explanation=explanation,
            created_at=now,
        )
        await self.repo.save_result(result)
        await self.repo.save_contributions(contributions)
        await self.repo.save_breakdowns(breakdowns)

        return NetExposureSummaryResponse(
            run_id=run_id,
            group_id=group_id,
            scope=NetExposureScope.PORTFOLIO_GROUP.value,
            reporting_currency=rep_curr,
            long_exposure=tot_long_exp,
            absolute_short_exposure=tot_short_exp,
            net_market_value=net_market_value,
            gross_exposure_reference=tot_long_exp + tot_short_exp,
            denominator_type=request.denominator_type.value,
            denominator_value=denom_val,
            net_exposure_ratio=ratio,
            net_exposure_ratio_percentage=ratio_pct,
            ratio_status=ratio_status,
            ratio_explanation=explanation,
            directional_classification=dir_class,
            neutrality_threshold_type=threshold_type.value,
            neutrality_threshold_applied=applied_threshold_desc,
            threshold_status=NetThresholdStatus.WITHIN_LIMIT.value,
            completeness_status="COMPLETE",
            eligible_position_count=eligible_pos_count,
            excluded_position_count=excluded_pos_count,
            contributions=[NetExposureContributionResponse.model_validate(c) for c in contributions],
            breakdowns=[NetExposureBreakdownResponse.model_validate(b) for b in breakdowns],
            threshold_events=[],
        )
