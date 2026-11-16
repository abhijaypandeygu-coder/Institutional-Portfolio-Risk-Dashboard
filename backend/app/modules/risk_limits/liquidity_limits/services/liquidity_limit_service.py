"""
Service layer for M11.04 Liquidity Limits.
Coordinates:
1. Liquidity limit configuration & profile lifecycle.
2. Position-level liquidity evaluation across score, depth, ADV, cost, and horizon.
3. Portfolio-level aggregation & concentration analysis.
4. Stressed liquidity transformations & comparisons.
5. Proposed-order simulation (M11.07 pre-trade feed).
6. Breach detection and data quality exception emission (M11.08 feed).
"""

from datetime import datetime
from decimal import Decimal
import time
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.liquidity_limits.models.liquidity_limit_models import (
    LiquidityLimitConfiguration,
    LiquidityLimitProfile,
    LiquidityLimitAssignment,
    LiquidityLimitEvaluation,
    PositionLiquidityEvaluationResult,
    LiquidityLimitBreachEvent,
    LiquidityDataExceptionRecord,
)
from backend.app.modules.risk_limits.liquidity_limits.schemas.liquidity_limit_schemas import (
    LiquidityLimitConfigCreate,
    LiquidityProfileCreate,
    LiquidityAssignmentCreate,
    LiquidityEvaluationRequest,
    PositionLiquidityInput,
    ProposedOrderLiquidityRequest,
    ProposedOrderLiquidityResponse,
)
from backend.app.modules.risk_limits.liquidity_limits.repositories.liquidity_limit_repository import (
    LiquidityLimitRepository,
)
from backend.app.modules.risk_limits.liquidity_limits.calculations.liquidity_limit_math import (
    calculate_adv,
    calculate_adtv,
    calculate_liquidation_horizon,
    calculate_liquidation_cost_metrics,
    evaluate_minimum_limit,
    evaluate_maximum_limit,
    apply_stressed_liquidity_shocks,
    calculate_liquidity_headroom_and_capacity,
    simulate_proposed_order,
)


class LiquidityLimitService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LiquidityLimitRepository(session)

    # Configuration Management
    async def create_configuration(self, payload: LiquidityLimitConfigCreate) -> LiquidityLimitConfiguration:
        existing = await self.repo.get_configuration_by_code(payload.limit_code)
        if existing:
            raise ValueError(f"Liquidity limit configuration '{payload.limit_code}' already exists.")

        config = LiquidityLimitConfiguration(
            limit_code=payload.limit_code,
            limit_name=payload.limit_name,
            description=payload.description,
            portfolio_id=payload.portfolio_id,
            instrument_id=payload.instrument_id,
            profile_id=payload.profile_id,
            limit_type=payload.limit_type,
            metric_name=payload.metric_name,
            minimum_threshold=payload.minimum_threshold,
            maximum_threshold=payload.maximum_threshold,
            warning_threshold=payload.warning_threshold,
            threshold_unit=payload.threshold_unit,
            threshold_currency=payload.threshold_currency,
            participation_rate=payload.participation_rate,
            lookback_sessions=payload.lookback_sessions,
            horizon_unit=payload.horizon_unit,
            cost_methodology=payload.cost_methodology,
            is_stress_limit=payload.is_stress_limit,
            stress_scenario_id=payload.stress_scenario_id,
            precedence=payload.precedence,
            status="ACTIVE",
            approval_status="APPROVED",
            created_by=payload.created_by,
        )
        created = await self.repo.create_configuration(config)
        await self.repo.log_audit(
            entity_type="CONFIGURATION",
            entity_id=created.id,
            action="CREATE",
            actor=payload.created_by,
            details={"code": created.limit_code, "type": created.limit_type}
        )
        return created

    async def list_configurations(self, portfolio_id: Optional[str] = None) -> List[LiquidityLimitConfiguration]:
        return await self.repo.list_configurations(portfolio_id)

    # Profile Management
    async def create_profile(self, payload: LiquidityProfileCreate) -> LiquidityLimitProfile:
        existing = await self.repo.get_profile_by_code(payload.profile_code)
        if existing:
            raise ValueError(f"Liquidity limit profile '{payload.profile_code}' already exists.")

        profile = LiquidityLimitProfile(
            profile_code=payload.profile_code,
            profile_name=payload.profile_name,
            description=payload.description,
            profile_tier=payload.profile_tier,
            base_currency=payload.base_currency,
            status="ACTIVE",
            is_active=True,
            created_by=payload.created_by,
        )

        if payload.initial_limits:
            for l_in in payload.initial_limits:
                cfg = LiquidityLimitConfiguration(
                    limit_code=l_in.limit_code,
                    limit_name=l_in.limit_name,
                    description=l_in.description,
                    portfolio_id=l_in.portfolio_id,
                    instrument_id=l_in.instrument_id,
                    limit_type=l_in.limit_type,
                    metric_name=l_in.metric_name,
                    minimum_threshold=l_in.minimum_threshold,
                    maximum_threshold=l_in.maximum_threshold,
                    warning_threshold=l_in.warning_threshold,
                    threshold_unit=l_in.threshold_unit,
                    threshold_currency=l_in.threshold_currency,
                    participation_rate=l_in.participation_rate,
                    lookback_sessions=l_in.lookback_sessions,
                    horizon_unit=l_in.horizon_unit,
                    cost_methodology=l_in.cost_methodology,
                    is_stress_limit=l_in.is_stress_limit,
                    stress_scenario_id=l_in.stress_scenario_id,
                    precedence=l_in.precedence,
                    status="ACTIVE",
                    approval_status="APPROVED",
                    created_by=payload.created_by,
                )
                profile.configurations.append(cfg)

        created = await self.repo.create_profile(profile)
        await self.repo.log_audit(
            entity_type="PROFILE",
            entity_id=created.id,
            action="CREATE",
            actor=payload.created_by,
            details={"code": created.profile_code, "tier": created.profile_tier}
        )
        return created

    async def list_profiles(self) -> List[LiquidityLimitProfile]:
        return await self.repo.list_profiles()

    async def get_profile(self, code_or_id: str) -> Optional[LiquidityLimitProfile]:
        p = await self.repo.get_profile_by_code(code_or_id)
        if not p:
            p = await self.repo.get_profile_by_id(code_or_id)
        return p

    # Assignment Management
    async def assign_profile(self, payload: LiquidityAssignmentCreate) -> LiquidityLimitAssignment:
        profile = await self.get_profile(payload.profile_id)
        if not profile:
            raise ValueError(f"Profile '{payload.profile_id}' not found.")

        assignment = LiquidityLimitAssignment(
            profile_id=profile.id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            precedence=payload.precedence,
            status="ACTIVE",
            assigned_by=payload.assigned_by,
            effective_from=payload.effective_from or datetime.utcnow(),
            effective_to=payload.effective_to
        )
        created = await self.repo.create_assignment(assignment)
        await self.repo.log_audit(
            entity_type="ASSIGNMENT",
            entity_id=created.id,
            action="ASSIGN",
            actor=payload.assigned_by,
            details={"target_type": payload.target_type, "target_id": payload.target_id}
        )
        return created

    # Evaluation Engine
    async def evaluate_portfolio_liquidity(self, request: LiquidityEvaluationRequest) -> LiquidityLimitEvaluation:
        """
        Evaluates portfolio positions across liquidity limits:
        - Score, Depth (side-aware), ADV/Turnover, Cost, Horizon.
        - Applies stress shocks when stress_parameters is provided.
        """
        start_time = time.perf_counter()

        if request.portfolio_nav <= Decimal("0"):
            raise ValueError("Portfolio NAV must be strictly positive for liquidity limit evaluations.")

        # Retrieve active limits
        active_configs: List[LiquidityLimitConfiguration] = []
        assignment = await self.repo.get_active_assignment_for_portfolio(request.portfolio_id)
        if assignment:
            profile = await self.repo.get_profile_by_id(assignment.profile_id)
            if profile and profile.configurations:
                active_configs.extend([c for c in profile.configurations if c.status == "ACTIVE"])

        port_cfgs = await self.repo.list_configurations(request.portfolio_id)
        for c in port_cfgs:
            if c.status == "ACTIVE" and c.id not in [x.id for x in active_configs]:
                active_configs.append(c)

        total_cost = sum([pos.estimated_liquidation_cost or Decimal("0.0") for pos in request.positions])

        eval_header = LiquidityLimitEvaluation(
            id=str(uuid.uuid4()),
            portfolio_id=request.portfolio_id,
            evaluation_type=request.evaluation_type,
            evaluation_timestamp=datetime.utcnow(),
            portfolio_nav=request.portfolio_nav,
            base_currency=request.base_currency,
            total_positions_evaluated=len(request.positions),
            total_liquidation_cost=total_cost,
            max_liquidation_horizon_days=Decimal("0.0000"),
            overall_status="WITHIN_LIMIT",
            warning_breaches_count=0,
            hard_breaches_count=0,
            unavailable_count=0,
        )

        results: List[PositionLiquidityEvaluationResult] = []
        breaches: List[LiquidityLimitBreachEvent] = []
        exceptions: List[LiquidityDataExceptionRecord] = []
        worst_status = "WITHIN_LIMIT"
        max_horizon = Decimal("0.0000")

        # Map active configs by instrument_id (or None for portfolio-wide)
        configs_by_inst: Dict[Optional[str], List[LiquidityLimitConfiguration]] = {}
        for c in active_configs:
            configs_by_inst.setdefault(c.instrument_id, []).append(c)

        for pos in request.positions:
            pos_side = pos.position_side.upper()
            abs_qty = abs(pos.quantity)
            pos_notional = abs(pos.market_value)
            est_cost = pos.estimated_liquidation_cost

            # Determine side-aware executable depth:
            # Long liquidation -> Sell side -> Bid depth
            # Short covering -> Buy side -> Ask depth
            side_depth = pos.bid_depth if pos_side == "LONG" else pos.ask_depth

            # Calculate or use ADV
            computed_adv = pos.adv
            if computed_adv is None and pos.daily_volumes:
                computed_adv = calculate_adv(pos.daily_volumes)

            # Check if stress is active
            eval_adv = computed_adv
            eval_depth = side_depth
            eval_spread = pos.spread_bps
            eval_part = Decimal("0.1000")  # default

            # Get applicable configs for this instrument + portfolio-wide configs
            inst_cfgs = configs_by_inst.get(pos.instrument_id, []) + configs_by_inst.get(None, [])

            if not inst_cfgs:
                continue

            for cfg in inst_cfgs:
                eval_part = cfg.participation_rate

                if request.stress_parameters:
                    stress_res = apply_stressed_liquidity_shocks(
                        baseline_adv=computed_adv,
                        baseline_depth=side_depth,
                        baseline_spread_bps=pos.spread_bps,
                        baseline_participation_rate=eval_part,
                        volume_contraction_pct=request.stress_parameters.volume_contraction_pct,
                        depth_reduction_pct=request.stress_parameters.depth_reduction_pct,
                        spread_widening_pct=request.stress_parameters.spread_widening_pct,
                        participation_reduction_pct=request.stress_parameters.participation_reduction_pct,
                    )
                    eval_adv = stress_res["stressed_adv"]
                    eval_depth = stress_res["stressed_depth"]
                    eval_spread = stress_res["stressed_spread_bps"]
                    eval_part = stress_res["stressed_participation_rate"]

                # Calculate estimated horizon
                horizon_res = calculate_liquidation_horizon(
                    position_quantity=pos.quantity,
                    adv=eval_adv,
                    participation_rate=eval_part,
                )
                est_horizon_days = horizon_res.get("liquidation_horizon_days")
                if est_horizon_days is not None and est_horizon_days > max_horizon:
                    max_horizon = est_horizon_days

                # Evaluate by Limit Type
                st = "WITHIN_LIMIT"
                u_pct = None
                breach_val = Decimal("0.0000")
                headroom_val = None
                actual_val = None
                thresh_val = Decimal("0.0000")
                warn_thresh = cfg.warning_threshold
                q_status = "VALID"

                if cfg.limit_type == "MIN_LIQUIDITY_SCORE":
                    actual_val = pos.liquidity_score
                    thresh_val = cfg.minimum_threshold or Decimal("0.0")
                    eval_min = evaluate_minimum_limit(actual_val, thresh_val, warn_thresh, unit=cfg.threshold_unit)
                    st = eval_min["status"]
                    u_pct = eval_min["utilization_pct"]
                    breach_val = eval_min["breach_amount"] or Decimal("0.0")
                    headroom_val = eval_min["headroom"]

                elif cfg.limit_type == "MIN_DISPLAYED_DEPTH":
                    actual_val = eval_depth
                    thresh_val = cfg.minimum_threshold or Decimal("0.0")
                    eval_min = evaluate_minimum_limit(actual_val, thresh_val, warn_thresh, unit=cfg.threshold_unit)
                    st = eval_min["status"]
                    u_pct = eval_min["utilization_pct"]
                    breach_val = eval_min["breach_amount"] or Decimal("0.0")
                    headroom_val = eval_min["headroom"]

                elif cfg.limit_type in ("MIN_DAILY_VOLUME", "MIN_ADV"):
                    actual_val = eval_adv
                    thresh_val = cfg.minimum_threshold or Decimal("0.0")
                    eval_min = evaluate_minimum_limit(actual_val, thresh_val, warn_thresh, unit=cfg.threshold_unit)
                    st = eval_min["status"]
                    u_pct = eval_min["utilization_pct"]
                    breach_val = eval_min["breach_amount"] or Decimal("0.0")
                    headroom_val = eval_min["headroom"]

                elif cfg.limit_type in ("MIN_DAILY_TURNOVER", "MIN_ADTV"):
                    actual_val = pos.adtv
                    thresh_val = cfg.minimum_threshold or Decimal("0.0")
                    eval_min = evaluate_minimum_limit(actual_val, thresh_val, warn_thresh, unit=cfg.threshold_unit)
                    st = eval_min["status"]
                    u_pct = eval_min["utilization_pct"]
                    breach_val = eval_min["breach_amount"] or Decimal("0.0")
                    headroom_val = eval_min["headroom"]

                elif cfg.limit_type == "MAX_LIQUIDATION_HORIZON":
                    actual_val = est_horizon_days
                    thresh_val = cfg.maximum_threshold or Decimal("5.0")
                    if actual_val is None:
                        st = horizon_res.get("status", "UNAVAILABLE")
                        q_status = "UNAVAILABLE"
                        exceptions.append(LiquidityDataExceptionRecord(
                            portfolio_id=request.portfolio_id,
                            instrument_id=pos.instrument_id,
                            exception_type="MISSING_OR_ZERO_ADV",
                            quality_state="UNAVAILABLE",
                            reason=horizon_res.get("reason", "ADV missing or invalid"),
                        ))
                    else:
                        eval_max = evaluate_maximum_limit(actual_val, thresh_val, warn_thresh, unit=cfg.threshold_unit)
                        st = eval_max["status"]
                        u_pct = eval_max["utilization_pct"]
                        breach_val = eval_max["breach_amount"] or Decimal("0.0")
                        headroom_val = eval_max["remaining_capacity"]

                elif cfg.limit_type in ("MAX_LIQUIDATION_COST", "MAX_LIQUIDATION_COST_AMOUNT"):
                    actual_val = est_cost
                    thresh_val = cfg.maximum_threshold or Decimal("100000.0")
                    if actual_val is None:
                        st = "UNAVAILABLE"
                        q_status = "UNAVAILABLE"
                        exceptions.append(LiquidityDataExceptionRecord(
                            portfolio_id=request.portfolio_id,
                            instrument_id=pos.instrument_id,
                            exception_type="MISSING_COST_MODEL",
                            quality_state="UNAVAILABLE",
                            reason="Liquidation cost estimate unavailable",
                        ))
                    else:
                        eval_max = evaluate_maximum_limit(actual_val, thresh_val, warn_thresh, unit=cfg.threshold_unit)
                        st = eval_max["status"]
                        u_pct = eval_max["utilization_pct"]
                        breach_val = eval_max["breach_amount"] or Decimal("0.0")
                        headroom_val = eval_max["remaining_capacity"]

                elif cfg.limit_type == "MAX_LIQUIDATION_COST_BPS":
                    cost_metrics = calculate_liquidation_cost_metrics(est_cost or Decimal("0.0"), pos_notional)
                    actual_val = cost_metrics["cost_bps"]
                    thresh_val = cfg.maximum_threshold or Decimal("50.0")
                    eval_max = evaluate_maximum_limit(actual_val, thresh_val, warn_thresh, unit=cfg.threshold_unit)
                    st = eval_max["status"]
                    u_pct = eval_max["utilization_pct"]
                    breach_val = eval_max["breach_amount"] or Decimal("0.0")
                    headroom_val = eval_max["remaining_capacity"]

                # Record status
                if st == "HARD_LIMIT_EXCEEDED":
                    worst_status = "HARD_LIMIT_EXCEEDED"
                    eval_header.hard_breaches_count += 1
                    breaches.append(LiquidityLimitBreachEvent(
                        evaluation_id=eval_header.id,
                        portfolio_id=request.portfolio_id,
                        instrument_id=pos.instrument_id,
                        limit_code=cfg.limit_code,
                        breach_type=f"{cfg.limit_type}_BREACH",
                        severity="HIGH" if breach_val > Decimal("0") else "WARNING",
                        actual_value=actual_val,
                        threshold_value=thresh_val,
                        breach_amount=breach_val,
                        utilization_pct=u_pct,
                        unit=cfg.threshold_unit,
                        cause="LIQUIDITY_DETERIORATION" if not request.stress_parameters else "STRESSED_LIQUIDITY_SHOCK",
                    ))
                elif st == "WARNING" and worst_status != "HARD_LIMIT_EXCEEDED":
                    worst_status = "WARNING"
                    eval_header.warning_breaches_count += 1
                elif st in ("UNAVAILABLE", "INVALID"):
                    eval_header.unavailable_count += 1
                    if worst_status != "HARD_LIMIT_EXCEEDED":
                        worst_status = "UNAVAILABLE"

                res_item = PositionLiquidityEvaluationResult(
                    evaluation_id=eval_header.id,
                    limit_id=cfg.id,
                    limit_code=cfg.limit_code,
                    limit_type=cfg.limit_type,
                    instrument_id=pos.instrument_id,
                    position_side=pos_side,
                    position_quantity=pos.quantity,
                    position_notional=pos_notional,
                    actual_value=actual_val,
                    liquidity_score=pos.liquidity_score,
                    available_depth=eval_depth,
                    adv=eval_adv,
                    spread_bps=eval_spread,
                    estimated_liquidation_cost=est_cost,
                    estimated_horizon_days=est_horizon_days,
                    participation_rate=eval_part,
                    threshold_value=thresh_val,
                    warning_threshold=warn_thresh,
                    threshold_unit=cfg.threshold_unit,
                    utilization_pct=u_pct,
                    headroom_or_capacity=headroom_val,
                    breach_amount=breach_val,
                    evaluation_status=st,
                    quality_status=q_status,
                    details={
                        "side_evaluated": "BID_SIDE" if pos_side == "LONG" else "ASK_SIDE",
                        "stressed": bool(request.stress_parameters)
                    }
                )
                results.append(res_item)

        eval_header.overall_status = worst_status
        eval_header.max_liquidation_horizon_days = max_horizon
        eval_header.execution_duration_ms = int((time.perf_counter() - start_time) * 1000)

        saved = await self.repo.save_evaluation(eval_header, results, breaches, exceptions)
        # Fetch loaded evaluation with eager-loaded results
        loaded = await self.repo.get_latest_evaluation(request.portfolio_id)
        return loaded or saved

    # Pre-trade Proposed Order Evaluation
    async def evaluate_proposed_order(self, request: ProposedOrderLiquidityRequest) -> ProposedOrderLiquidityResponse:
        """
        Simulates post-trade position and prospective liquidity constraints for M11.07.
        """
        sim = simulate_proposed_order(
            current_quantity=request.current_quantity,
            proposed_quantity=request.proposed_quantity,
            order_side=request.order_side,
            adv=request.adv,
            participation_rate=request.participation_rate,
            estimated_cost_per_share=request.estimated_cost_per_share,
        )

        proj_horizon = sim["projected_horizon_days"]
        proj_cost = sim["projected_cost"]
        eval_status = "WITHIN_LIMIT"
        reason = None

        if sim["status"] in ("UNAVAILABLE", "INVALID"):
            eval_status = sim["status"]
            reason = f"Liquidity horizon unavailable: {sim['status']}"
        else:
            if request.max_horizon_days_limit is not None and proj_horizon is not None:
                if proj_horizon > request.max_horizon_days_limit:
                    eval_status = "HARD_LIMIT_EXCEEDED"
                    reason = f"Projected horizon ({proj_horizon} days) exceeds limit ({request.max_horizon_days_limit} days)"

            if request.max_cost_limit is not None and proj_cost > request.max_cost_limit:
                eval_status = "HARD_LIMIT_EXCEEDED"
                reason = f"Projected cost ({proj_cost}) exceeds limit ({request.max_cost_limit})"

        return ProposedOrderLiquidityResponse(
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id,
            order_side=request.order_side,
            proposed_quantity=request.proposed_quantity,
            current_quantity=request.current_quantity,
            projected_quantity=sim["projected_quantity"],
            projected_side=sim["projected_side"],
            projected_horizon_days=proj_horizon,
            projected_cost=proj_cost,
            evaluation_status=eval_status,
            reason=reason,
        )
