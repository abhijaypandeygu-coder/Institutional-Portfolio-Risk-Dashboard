"""
Service orchestration layer for M11.02 Position Limits.
Coordinates:
1. Position limit configuration and profile management.
2. Portfolio limit assignments and deterministic precedence.
3. Multi-dimensional position evaluation:
   - Weight limits (% of NAV)
   - Notional limits (Absolute / Long / Short)
   - Long / Short separation
   - Multi-instrument/multi-listing issuer concentration
4. Proposed-order simulation and pre-trade evaluation for M11.07.
5. Breach event detection and recording for M11.08.
"""

from datetime import datetime
from decimal import Decimal
import time
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.position_limits.models.position_limit_models import (
    PositionLimitConfiguration,
    PositionLimitProfile,
    PositionLimitAssignment,
    PositionLimitEvaluation,
    PositionLimitEvaluationResult,
    PositionLimitBreachEvent,
)
from backend.app.modules.risk_limits.position_limits.schemas.position_limit_schemas import (
    ConfigurationCreate,
    ProfileCreate,
    AssignmentCreate,
    PortfolioEvaluationRequest,
    ProposedOrderRequest,
    ProposedOrderEvaluationResponse,
    EvaluationResultItem,
)
from backend.app.modules.risk_limits.position_limits.repositories.position_limit_repository import (
    PositionLimitRepository,
)
from backend.app.modules.risk_limits.position_limits.calculations.position_limit_math import (
    calculate_position_weight,
    calculate_directional_exposure,
    calculate_limit_utilization,
    aggregate_issuer_exposures,
    simulate_proposed_order,
)


class PositionLimitService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PositionLimitRepository(session)

    # Configuration Management
    async def create_configuration(self, payload: ConfigurationCreate) -> PositionLimitConfiguration:
        existing = await self.repo.get_configuration_by_code(payload.limit_code)
        if existing:
            raise ValueError(f"Position limit configuration '{payload.limit_code}' already exists.")

        config = PositionLimitConfiguration(
            limit_code=payload.limit_code,
            limit_name=payload.limit_name,
            description=payload.description,
            portfolio_id=payload.portfolio_id,
            instrument_id=payload.instrument_id,
            listing_id=payload.listing_id,
            issuer_id=payload.issuer_id,
            limit_type=payload.limit_type,
            direction=payload.direction,
            aggregation_level=payload.aggregation_level,
            threshold_value=payload.threshold_value,
            warning_threshold=payload.warning_threshold,
            threshold_unit=payload.threshold_unit,
            limit_currency=payload.limit_currency or "USD",
            comparison_operator=payload.comparison_operator,
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

    async def list_configurations(self, portfolio_id: Optional[str] = None) -> List[PositionLimitConfiguration]:
        return await self.repo.list_configurations(portfolio_id)

    # Profile Management
    async def create_profile(self, payload: ProfileCreate) -> PositionLimitProfile:
        existing = await self.repo.get_profile_by_code(payload.profile_code)
        if existing:
            raise ValueError(f"Position limit profile '{payload.profile_code}' already exists.")

        profile = PositionLimitProfile(
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
                cfg = PositionLimitConfiguration(
                    limit_code=l_in.limit_code,
                    limit_name=l_in.limit_name,
                    description=l_in.description,
                    portfolio_id=l_in.portfolio_id,
                    instrument_id=l_in.instrument_id,
                    listing_id=l_in.listing_id,
                    issuer_id=l_in.issuer_id,
                    limit_type=l_in.limit_type,
                    direction=l_in.direction,
                    aggregation_level=l_in.aggregation_level,
                    threshold_value=l_in.threshold_value,
                    warning_threshold=l_in.warning_threshold,
                    threshold_unit=l_in.threshold_unit,
                    limit_currency=l_in.limit_currency or "USD",
                    comparison_operator=l_in.comparison_operator,
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

    async def list_profiles(self) -> List[PositionLimitProfile]:
        return await self.repo.list_profiles()

    async def get_profile(self, code_or_id: str) -> Optional[PositionLimitProfile]:
        p = await self.repo.get_profile_by_code(code_or_id)
        if not p:
            p = await self.repo.get_profile_by_id(code_or_id)
        return p

    # Assignment Management
    async def assign_profile(self, payload: AssignmentCreate) -> PositionLimitAssignment:
        profile = await self.get_profile(payload.profile_id)
        if not profile:
            raise ValueError(f"Profile '{payload.profile_id}' not found.")

        assignment = PositionLimitAssignment(
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
    async def evaluate_portfolio_positions(self, request: PortfolioEvaluationRequest) -> PositionLimitEvaluation:
        """
        Full portfolio evaluation against active position limits:
        1. Validates NAV (strictly positive fail-safe).
        2. Resolves applicable limit configurations for portfolio.
        3. Evaluates per-position weight and notional limits.
        4. Evaluates aggregated issuer concentration limits.
        5. Computes worst overall status, generates breach events, and persists run.
        """
        start_time = time.perf_counter()

        # Fail-safe NAV check
        if request.portfolio_nav <= Decimal("0"):
            raise ValueError("Portfolio NAV must be strictly positive for position limit evaluations.")

        # Resolve active configurations: check portfolio assignment, then portfolio-specific overrides, then global
        active_configs: List[PositionLimitConfiguration] = []
        assignment = await self.repo.get_active_assignment_for_portfolio(request.portfolio_id)
        if assignment:
            profile = await self.repo.get_profile_by_id(assignment.profile_id)
            if profile and profile.configurations:
                active_configs.extend([c for c in profile.configurations if c.status == "ACTIVE"])

        # Also retrieve explicit portfolio-specific configurations
        portfolio_configs = await self.repo.list_configurations(request.portfolio_id)
        for c in portfolio_configs:
            if c.status == "ACTIVE" and c.id not in [x.id for x in active_configs]:
                active_configs.append(c)

        # Fallback to standard defaults if no configs assigned
        if not active_configs:
            all_cfgs = await self.repo.list_configurations()
            active_configs = [c for c in all_cfgs if c.status == "ACTIVE"]

        eval_header = PositionLimitEvaluation(
            id=str(uuid.uuid4()),
            portfolio_id=request.portfolio_id,
            evaluation_type=request.evaluation_type,
            evaluation_timestamp=datetime.utcnow(),
            portfolio_nav=request.portfolio_nav,
            base_currency=request.base_currency,
            overall_status="WITHIN_LIMIT",
            total_positions_evaluated=len(request.positions),
            warning_breaches_count=0,
            hard_breaches_count=0,
        )

        results: List[PositionLimitEvaluationResult] = []
        breaches: List[PositionLimitBreachEvent] = []
        worst_status = "WITHIN_LIMIT"

        # Group positions by issuer for issuer aggregation
        issuer_groups: Dict[str, List[Dict[str, Any]]] = {}

        # 1. Position-level evaluations
        for pos in request.positions:
            signed_mv = pos.market_value
            direction = "LONG" if pos.quantity > 0 else ("SHORT" if pos.quantity < 0 else "FLAT")

            if pos.issuer_id:
                issuer_groups.setdefault(pos.issuer_id, []).append({
                    "instrument_id": pos.instrument_id,
                    "symbol": pos.symbol,
                    "market_value": signed_mv,
                    "quantity": pos.quantity
                })

            for cfg in active_configs:
                if cfg.aggregation_level == "ISSUER":
                    continue  # Evaluated in issuer pass below

                # Check scope match: portfolio or instrument override
                if cfg.instrument_id and cfg.instrument_id != pos.instrument_id:
                    continue

                # Determine exposure for this limit type
                actual_exp = Decimal("0.0000")
                unit = cfg.threshold_unit
                is_applicable = True

                if cfg.limit_type in ("MAX_POSITION_WEIGHT", "MAX_ABSOLUTE_NOTIONAL"):
                    if cfg.direction == "LONG" and direction != "LONG":
                        is_applicable = False
                    elif cfg.direction == "SHORT" and direction != "SHORT":
                        is_applicable = False

                if not is_applicable:
                    continue

                if "WEIGHT" in cfg.limit_type:
                    if "LONG" in cfg.limit_type:
                        exp_val = max(signed_mv, Decimal("0.0"))
                    elif "SHORT" in cfg.limit_type:
                        exp_val = max(-signed_mv, Decimal("0.0"))
                    else:
                        exp_val = abs(signed_mv)

                    w, _ = calculate_position_weight(exp_val, request.portfolio_nav, use_absolute=False)
                    actual_exp = w
                    unit = "PERCENT_NAV"
                else:
                    # NOTIONAL limits
                    if "LONG" in cfg.limit_type:
                        actual_exp = max(signed_mv, Decimal("0.0"))
                    elif "SHORT" in cfg.limit_type:
                        actual_exp = max(-signed_mv, Decimal("0.0"))
                    else:
                        actual_exp = abs(signed_mv)
                    unit = cfg.limit_currency or request.base_currency

                util_res = calculate_limit_utilization(
                    actual_exposure=actual_exp,
                    warning_threshold=cfg.warning_threshold,
                    hard_threshold=cfg.threshold_value,
                    comparison_operator=cfg.comparison_operator
                )

                st = util_res["evaluation_status"]
                if st == "HARD_LIMIT_EXCEEDED":
                    worst_status = "HARD_LIMIT_EXCEEDED"
                    eval_header.hard_breaches_count += 1
                    breaches.append(PositionLimitBreachEvent(
                        evaluation_id=eval_header.id,
                        portfolio_id=request.portfolio_id,
                        instrument_id=pos.instrument_id,
                        symbol=pos.symbol,
                        issuer_id=pos.issuer_id,
                        limit_code=cfg.limit_code,
                        breach_type=f"{cfg.limit_type}_BREACH",
                        severity="CRITICAL" if util_res["hard_utilization_pct"] > Decimal("120.0") else "HIGH",
                        actual_exposure=actual_exp,
                        hard_threshold=cfg.threshold_value,
                        breach_amount=util_res["breach_amount"],
                        utilization_pct=util_res["hard_utilization_pct"],
                        unit=unit,
                        cause="POSITION_CONCENTRATION"
                    ))
                elif st == "WARNING" and worst_status != "HARD_LIMIT_EXCEEDED":
                    worst_status = "WARNING"
                    eval_header.warning_breaches_count += 1

                res_item = PositionLimitEvaluationResult(
                    evaluation_id=eval_header.id,
                    limit_id=cfg.id,
                    limit_code=cfg.limit_code,
                    limit_type=cfg.limit_type,
                    instrument_id=pos.instrument_id,
                    symbol=pos.symbol,
                    issuer_id=pos.issuer_id,
                    position_direction=direction,
                    actual_exposure=actual_exp,
                    exposure_currency=pos.currency,
                    warning_threshold=cfg.warning_threshold,
                    hard_threshold=cfg.threshold_value,
                    threshold_unit=unit,
                    warning_utilization_pct=util_res["warning_utilization_pct"],
                    hard_utilization_pct=util_res["hard_utilization_pct"],
                    remaining_capacity=util_res["remaining_capacity"],
                    breach_amount=util_res["breach_amount"],
                    evaluation_status=st,
                    details={"pos_qty": str(pos.quantity), "market_value": str(pos.market_value)}
                )
                results.append(res_item)

        # 2. Issuer-level aggregations
        issuer_configs = [c for c in active_configs if c.aggregation_level == "ISSUER" or "ISSUER" in c.limit_type]
        for issuer_id, issuer_positions in issuer_groups.items():
            agg = aggregate_issuer_exposures(issuer_positions, request.portfolio_nav)
            for cfg in issuer_configs:
                if cfg.issuer_id and cfg.issuer_id != issuer_id:
                    continue

                if "WEIGHT" in cfg.limit_type:
                    actual_exp = agg["gross_weight_pct"] if cfg.direction in ("ANY", "GROSS") else agg["net_weight_pct"]
                    unit = "PERCENT_NAV"
                else:
                    actual_exp = agg["gross_exposure"] if cfg.direction in ("ANY", "GROSS") else agg["net_exposure"]
                    unit = cfg.limit_currency or request.base_currency

                util_res = calculate_limit_utilization(
                    actual_exposure=actual_exp,
                    warning_threshold=cfg.warning_threshold,
                    hard_threshold=cfg.threshold_value,
                    comparison_operator=cfg.comparison_operator
                )

                st = util_res["evaluation_status"]
                if st == "HARD_LIMIT_EXCEEDED":
                    worst_status = "HARD_LIMIT_EXCEEDED"
                    eval_header.hard_breaches_count += 1
                    breaches.append(PositionLimitBreachEvent(
                        evaluation_id=eval_header.id,
                        portfolio_id=request.portfolio_id,
                        issuer_id=issuer_id,
                        limit_code=cfg.limit_code,
                        breach_type="ISSUER_CONCENTRATION_BREACH",
                        severity="CRITICAL",
                        actual_exposure=actual_exp,
                        hard_threshold=cfg.threshold_value,
                        breach_amount=util_res["breach_amount"],
                        utilization_pct=util_res["hard_utilization_pct"],
                        unit=unit,
                        cause="ISSUER_CONCENTRATION"
                    ))
                elif st == "WARNING" and worst_status != "HARD_LIMIT_EXCEEDED":
                    worst_status = "WARNING"
                    eval_header.warning_breaches_count += 1

                res_item = PositionLimitEvaluationResult(
                    evaluation_id=eval_header.id,
                    limit_id=cfg.id,
                    limit_code=cfg.limit_code,
                    limit_type=cfg.limit_type,
                    issuer_id=issuer_id,
                    position_direction=cfg.direction,
                    actual_exposure=actual_exp,
                    exposure_currency=request.base_currency,
                    warning_threshold=cfg.warning_threshold,
                    hard_threshold=cfg.threshold_value,
                    threshold_unit=unit,
                    warning_utilization_pct=util_res["warning_utilization_pct"],
                    hard_utilization_pct=util_res["hard_utilization_pct"],
                    remaining_capacity=util_res["remaining_capacity"],
                    breach_amount=util_res["breach_amount"],
                    evaluation_status=st,
                    details={
                        "gross_exposure": str(agg["gross_exposure"]),
                        "net_exposure": str(agg["net_exposure"]),
                        "long_exposure": str(agg["long_exposure"]),
                        "short_exposure": str(agg["short_exposure"]),
                        "gross_weight_pct": str(agg["gross_weight_pct"]),
                        "net_weight_pct": str(agg["net_weight_pct"]),
                        "constituent_count": agg["constituent_count"],
                    }
                )
                results.append(res_item)

        eval_header.overall_status = worst_status
        eval_header.results = results
        eval_header.execution_duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Save evaluation and breaches
        saved = await self.repo.save_evaluation(eval_header)
        if breaches:
            await self.repo.record_breaches(breaches)

        await self.repo.log_audit(
            entity_type="EVALUATION",
            entity_id=saved.id,
            action="EVALUATE",
            actor=request.evaluator,
            details={"overall_status": worst_status, "positions": len(request.positions), "breaches": len(breaches)}
        )
        return saved

    async def evaluate_proposed_order(self, request: ProposedOrderRequest) -> ProposedOrderEvaluationResponse:
        """
        Simulates post-trade position and evaluates against limits for pre-trade check (M11.07 consumption).
        """
        sim = simulate_proposed_order(
            current_quantity=request.current_quantity,
            current_market_value=request.current_market_value,
            order_side=request.order_side,
            order_quantity=request.order_quantity,
            reference_price=request.reference_price,
            fx_rate=request.fx_rate,
            portfolio_nav=request.portfolio_nav
        )

        current_w, _ = calculate_position_weight(request.current_market_value, request.portfolio_nav)

        # Retrieve applicable limits
        configs = await self.repo.list_configurations(request.portfolio_id)
        eval_items: List[EvaluationResultItem] = []
        is_approved = True
        worst_status = "WITHIN_LIMIT"

        for cfg in configs:
            if cfg.instrument_id and cfg.instrument_id != request.instrument_id:
                continue

            if cfg.aggregation_level == "ISSUER":
                continue

            actual_exp = sim["post_weight_pct"] if "WEIGHT" in cfg.limit_type else sim["post_notional"]
            unit = "PERCENT_NAV" if "WEIGHT" in cfg.limit_type else (cfg.limit_currency or request.base_currency)

            util_res = calculate_limit_utilization(
                actual_exposure=actual_exp,
                warning_threshold=cfg.warning_threshold,
                hard_threshold=cfg.threshold_value,
                comparison_operator=cfg.comparison_operator
            )

            st = util_res["evaluation_status"]
            if st == "HARD_LIMIT_EXCEEDED":
                is_approved = False
                worst_status = "HARD_LIMIT_EXCEEDED"
            elif st == "WARNING" and worst_status != "HARD_LIMIT_EXCEEDED":
                worst_status = "WARNING"

            eval_items.append(EvaluationResultItem(
                limit_id=cfg.id,
                limit_code=cfg.limit_code,
                limit_type=cfg.limit_type,
                instrument_id=request.instrument_id,
                symbol=request.symbol,
                issuer_id=request.issuer_id,
                position_direction="LONG" if sim["post_quantity"] > 0 else "SHORT",
                actual_exposure=actual_exp,
                exposure_currency=request.base_currency,
                warning_threshold=cfg.warning_threshold,
                hard_threshold=cfg.threshold_value,
                threshold_unit=unit,
                warning_utilization_pct=util_res["warning_utilization_pct"],
                hard_utilization_pct=util_res["hard_utilization_pct"],
                remaining_capacity=util_res["remaining_capacity"],
                breach_amount=util_res["breach_amount"],
                evaluation_status=st,
                details=sim
            ))

        return ProposedOrderEvaluationResponse(
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id,
            symbol=request.symbol,
            order_side=request.order_side,
            order_quantity=request.order_quantity,
            reference_price=request.reference_price,
            current_market_value=request.current_market_value,
            projected_market_value=sim["post_market_value"],
            current_weight_pct=current_w,
            projected_weight_pct=sim["post_weight_pct"],
            projected_notional=sim["post_notional"],
            overall_status=worst_status,
            evaluations=eval_items,
            is_pretrade_approved=is_approved
        )
