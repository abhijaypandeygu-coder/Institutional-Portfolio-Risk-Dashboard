"""
Service orchestration layer for M11.03 Sector Limits.
Coordinates:
1. Sector & Industry limit configuration and reusable profiles.
2. Classification-aware exposure aggregation (Gross, Net, Long, Short).
3. Benchmark-relative active overweight & underweight monitoring.
4. Classification coverage & unclassified exposure tracking.
5. Breach detection and audit event emission for M11.08.
"""

from datetime import datetime
from decimal import Decimal
import time
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.sector_limits.models.sector_limit_models import (
    SectorLimitConfiguration,
    SectorLimitProfile,
    SectorLimitAssignment,
    SectorLimitEvaluation,
    SectorLimitEvaluationResult,
    SectorLimitBreachEvent,
)
from backend.app.modules.risk_limits.sector_limits.schemas.sector_limit_schemas import (
    SectorLimitConfigCreate,
    SectorProfileCreate,
    SectorAssignmentCreate,
    SectorEvaluationRequest,
    SectorEvaluationResultItem,
)
from backend.app.modules.risk_limits.sector_limits.repositories.sector_limit_repository import (
    SectorLimitRepository,
)
from backend.app.modules.risk_limits.sector_limits.calculations.sector_limit_math import (
    calculate_sector_utilization,
    evaluate_active_weight_limit,
    aggregate_sector_and_industry_exposures,
)


class SectorLimitService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SectorLimitRepository(session)

    # Configuration Management
    async def create_configuration(self, payload: SectorLimitConfigCreate) -> SectorLimitConfiguration:
        existing = await self.repo.get_configuration_by_code(payload.limit_code)
        if existing:
            raise ValueError(f"Sector limit configuration '{payload.limit_code}' already exists.")

        config = SectorLimitConfiguration(
            limit_code=payload.limit_code,
            limit_name=payload.limit_name,
            description=payload.description,
            portfolio_id=payload.portfolio_id,
            classification_system=payload.classification_system,
            classification_version=payload.classification_version,
            sector_id=payload.sector_id,
            sector_name=payload.sector_name,
            industry_id=payload.industry_id,
            industry_name=payload.industry_name,
            limit_type=payload.limit_type,
            direction=payload.direction,
            threshold_value=payload.threshold_value,
            warning_threshold=payload.warning_threshold,
            lower_threshold=payload.lower_threshold,
            threshold_unit=payload.threshold_unit,
            benchmark_id=payload.benchmark_id,
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

    async def list_configurations(self, portfolio_id: Optional[str] = None) -> List[SectorLimitConfiguration]:
        return await self.repo.list_configurations(portfolio_id)

    # Profile Management
    async def create_profile(self, payload: SectorProfileCreate) -> SectorLimitProfile:
        existing = await self.repo.get_profile_by_code(payload.profile_code)
        if existing:
            raise ValueError(f"Sector limit profile '{payload.profile_code}' already exists.")

        profile = SectorLimitProfile(
            profile_code=payload.profile_code,
            profile_name=payload.profile_name,
            description=payload.description,
            profile_tier=payload.profile_tier,
            classification_system=payload.classification_system,
            base_currency=payload.base_currency,
            status="ACTIVE",
            is_active=True,
            created_by=payload.created_by,
        )

        if payload.initial_limits:
            for l_in in payload.initial_limits:
                cfg = SectorLimitConfiguration(
                    limit_code=l_in.limit_code,
                    limit_name=l_in.limit_name,
                    description=l_in.description,
                    portfolio_id=l_in.portfolio_id,
                    classification_system=l_in.classification_system,
                    classification_version=l_in.classification_version,
                    sector_id=l_in.sector_id,
                    sector_name=l_in.sector_name,
                    industry_id=l_in.industry_id,
                    industry_name=l_in.industry_name,
                    limit_type=l_in.limit_type,
                    direction=l_in.direction,
                    threshold_value=l_in.threshold_value,
                    warning_threshold=l_in.warning_threshold,
                    lower_threshold=l_in.lower_threshold,
                    threshold_unit=l_in.threshold_unit,
                    benchmark_id=l_in.benchmark_id,
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

    async def list_profiles(self) -> List[SectorLimitProfile]:
        return await self.repo.list_profiles()

    async def get_profile(self, code_or_id: str) -> Optional[SectorLimitProfile]:
        p = await self.repo.get_profile_by_code(code_or_id)
        if not p:
            p = await self.repo.get_profile_by_id(code_or_id)
        return p

    # Assignment Management
    async def assign_profile(self, payload: SectorAssignmentCreate) -> SectorLimitAssignment:
        profile = await self.get_profile(payload.profile_id)
        if not profile:
            raise ValueError(f"Profile '{payload.profile_id}' not found.")

        assignment = SectorLimitAssignment(
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
    async def evaluate_portfolio_sectors(self, request: SectorEvaluationRequest) -> SectorLimitEvaluation:
        """
        Evaluates portfolio positions across sector, industry, and benchmark-relative limits.
        """
        start_time = time.perf_counter()

        if request.portfolio_nav <= Decimal("0"):
            raise ValueError("Portfolio NAV must be strictly positive for sector limit evaluations.")

        # Aggregate positions
        positions_data = [p.model_dump() for p in request.positions]
        agg = aggregate_sector_and_industry_exposures(positions_data, request.portfolio_nav)

        # Retrieve active limits
        active_configs: List[SectorLimitConfiguration] = []
        assignment = await self.repo.get_active_assignment_for_portfolio(request.portfolio_id)
        if assignment:
            profile = await self.repo.get_profile_by_id(assignment.profile_id)
            if profile and profile.configurations:
                active_configs.extend([c for c in profile.configurations if c.status == "ACTIVE"])

        # Also get portfolio-specific configs (assigned explicitly to this portfolio_id)
        port_cfgs = await self.repo.list_configurations(request.portfolio_id)
        for c in port_cfgs:
            if c.status == "ACTIVE" and c.id not in [x.id for x in active_configs]:
                active_configs.append(c)

        eval_header = SectorLimitEvaluation(
            id=str(uuid.uuid4()),
            portfolio_id=request.portfolio_id,
            evaluation_type=request.evaluation_type,
            evaluation_timestamp=datetime.utcnow(),
            portfolio_nav=request.portfolio_nav,
            base_currency=request.base_currency,
            total_eligible_exposure=agg["total_gross_exposure"],
            classified_exposure=agg["classified_gross_exposure"],
            unclassified_exposure=agg["unclassified_gross_exposure"],
            classification_coverage_pct=agg["classification_coverage_pct"],
            overall_status="WITHIN_LIMIT",
            total_sectors_evaluated=len(agg["sectors"]),
            total_industries_evaluated=len(agg["industries"]),
            warning_breaches_count=0,
            hard_breaches_count=0,
        )

        results: List[SectorLimitEvaluationResult] = []
        breaches: List[SectorLimitBreachEvent] = []
        worst_status = "WITHIN_LIMIT"

        sectors_by_id = {s["sector_id"]: s for s in agg["sectors"]}
        industries_by_id = {ind["industry_id"]: ind for ind in agg["industries"]}
        bm_weights = request.benchmark_weights or {}

        # Evaluate configs
        for cfg in active_configs:
            if cfg.sector_id and not cfg.industry_id:
                # Sector-level limit
                s_data = sectors_by_id.get(cfg.sector_id)
                actual_exp = s_data["gross_weight_pct"] if s_data else Decimal("0.0000")
                bm_weight = bm_weights.get(cfg.sector_id, Decimal("0.0000"))

                if "ACTIVE" in cfg.limit_type:
                    # Benchmark relative limit
                    act_res = evaluate_active_weight_limit(
                        portfolio_weight_pct=actual_exp,
                        benchmark_weight_pct=bm_weight,
                        upper_overweight_limit_pct=cfg.threshold_value if "OVERWEIGHT" in cfg.limit_type else None,
                        lower_underweight_limit_pct=cfg.lower_threshold or cfg.threshold_value if "UNDERWEIGHT" in cfg.limit_type else None,
                        warning_buffer_pct=Decimal("1.0")
                    )
                    st = act_res["evaluation_status"]
                    rem_cap = (cfg.threshold_value - act_res["active_weight_pct"]).quantize(Decimal("0.0001"))
                    res_item = SectorLimitEvaluationResult(
                        evaluation_id=eval_header.id,
                        limit_id=cfg.id,
                        limit_code=cfg.limit_code,
                        limit_type=cfg.limit_type,
                        classification_level="SECTOR",
                        sector_id=cfg.sector_id,
                        actual_exposure=actual_exp,
                        benchmark_exposure=bm_weight,
                        active_weight_pct=act_res["active_weight_pct"],
                        warning_threshold=cfg.warning_threshold,
                        hard_threshold=cfg.threshold_value,
                        threshold_unit="ACTIVE_PERCENT",
                        warning_utilization_pct=Decimal("0.0"),
                        hard_utilization_pct=Decimal("0.0"),
                        remaining_capacity=rem_cap,
                        breach_amount=act_res["breach_amount"],
                        evaluation_status=st,
                        details=act_res
                    )
                else:
                    # Absolute Sector Cap
                    util = calculate_sector_utilization(
                        actual_exposure=actual_exp,
                        warning_threshold=cfg.warning_threshold,
                        hard_threshold=cfg.threshold_value,
                    )
                    st = util["evaluation_status"]
                    res_item = SectorLimitEvaluationResult(
                        evaluation_id=eval_header.id,
                        limit_id=cfg.id,
                        limit_code=cfg.limit_code,
                        limit_type=cfg.limit_type,
                        classification_level="SECTOR",
                        sector_id=cfg.sector_id,
                        actual_exposure=actual_exp,
                        warning_threshold=cfg.warning_threshold,
                        hard_threshold=cfg.threshold_value,
                        threshold_unit="PERCENT_NAV",
                        warning_utilization_pct=util["warning_utilization_pct"],
                        hard_utilization_pct=util["hard_utilization_pct"],
                        remaining_capacity=util["remaining_capacity"],
                        breach_amount=util["breach_amount"],
                        evaluation_status=st,
                        details={"gross_exp": str(s_data["gross_exposure"] if s_data else 0)}
                    )

                if st == "HARD_LIMIT_EXCEEDED":
                    worst_status = "HARD_LIMIT_EXCEEDED"
                    eval_header.hard_breaches_count += 1
                    breaches.append(SectorLimitBreachEvent(
                        evaluation_id=eval_header.id,
                        portfolio_id=request.portfolio_id,
                        sector_id=cfg.sector_id,
                        limit_code=cfg.limit_code,
                        breach_type=f"{cfg.limit_type}_BREACH",
                        severity="CRITICAL" if res_item.breach_amount > Decimal("5.0") else "HIGH",
                        actual_exposure=actual_exp,
                        hard_threshold=cfg.threshold_value,
                        breach_amount=res_item.breach_amount,
                        utilization_pct=res_item.hard_utilization_pct,
                        unit=res_item.threshold_unit,
                        cause="SECTOR_CONCENTRATION"
                    ))
                elif st == "WARNING" and worst_status != "HARD_LIMIT_EXCEEDED":
                    worst_status = "WARNING"
                    eval_header.warning_breaches_count += 1

                results.append(res_item)

            elif cfg.industry_id:
                # Industry-level limit
                ind_data = industries_by_id.get(cfg.industry_id)
                actual_exp = ind_data["gross_weight_pct"] if ind_data else Decimal("0.0000")
                util = calculate_sector_utilization(
                    actual_exposure=actual_exp,
                    warning_threshold=cfg.warning_threshold,
                    hard_threshold=cfg.threshold_value,
                )
                st = util["evaluation_status"]
                res_item = SectorLimitEvaluationResult(
                    evaluation_id=eval_header.id,
                    limit_id=cfg.id,
                    limit_code=cfg.limit_code,
                    limit_type=cfg.limit_type,
                    classification_level="INDUSTRY",
                    sector_id=cfg.sector_id or (ind_data.get("sector_id") if ind_data else None),
                    industry_id=cfg.industry_id,
                    actual_exposure=actual_exp,
                    warning_threshold=cfg.warning_threshold,
                    hard_threshold=cfg.threshold_value,
                    threshold_unit="PERCENT_NAV",
                    warning_utilization_pct=util["warning_utilization_pct"],
                    hard_utilization_pct=util["hard_utilization_pct"],
                    remaining_capacity=util["remaining_capacity"],
                    breach_amount=util["breach_amount"],
                    evaluation_status=st,
                    details={"gross_exp": str(ind_data["gross_exposure"] if ind_data else 0)}
                )

                if st == "HARD_LIMIT_EXCEEDED":
                    worst_status = "HARD_LIMIT_EXCEEDED"
                    eval_header.hard_breaches_count += 1
                    breaches.append(SectorLimitBreachEvent(
                        evaluation_id=eval_header.id,
                        portfolio_id=request.portfolio_id,
                        sector_id=res_item.sector_id,
                        industry_id=cfg.industry_id,
                        limit_code=cfg.limit_code,
                        breach_type=f"{cfg.limit_type}_BREACH",
                        severity="HIGH",
                        actual_exposure=actual_exp,
                        hard_threshold=cfg.threshold_value,
                        breach_amount=util["breach_amount"],
                        utilization_pct=util["hard_utilization_pct"],
                        unit="PERCENT_NAV",
                        cause="INDUSTRY_CONCENTRATION"
                    ))
                elif st == "WARNING" and worst_status != "HARD_LIMIT_EXCEEDED":
                    worst_status = "WARNING"
                    eval_header.warning_breaches_count += 1

                results.append(res_item)

        eval_header.overall_status = worst_status
        eval_header.results = results
        eval_header.execution_duration_ms = int((time.perf_counter() - start_time) * 1000)

        saved = await self.repo.save_evaluation(eval_header)
        if breaches:
            await self.repo.record_breaches(breaches)

        await self.repo.log_audit(
            entity_type="EVALUATION",
            entity_id=saved.id,
            action="EVALUATE",
            actor=request.evaluator,
            details={
                "overall_status": worst_status,
                "sectors": len(agg["sectors"]),
                "industries": len(agg["industries"]),
                "coverage": str(agg["classification_coverage_pct"])
            }
        )
        return saved

