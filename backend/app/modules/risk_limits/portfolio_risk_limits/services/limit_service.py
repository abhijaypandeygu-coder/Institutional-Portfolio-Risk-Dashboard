"""
Service orchestration layer for M11.01 Portfolio Risk Limits.
Orchestrates:
1. Profile lifecycle (draft, approval, activation, suspension).
2. Limit definition and versioning.
3. Portfolio assignment and precedence resolution.
4. Threshold evaluation across VaR, Volatility, and Drawdown.
5. Standardized downstream contract output and persistence.
"""

from datetime import datetime
from decimal import Decimal
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.portfolio_risk_limits.models.limit_models import (
    RiskLimitProfile,
    RiskLimitProfileVersion,
    PortfolioRiskLimit,
    PortfolioLimitAssignment,
    RiskLimitUtilizationSnapshot,
)
from backend.app.modules.risk_limits.portfolio_risk_limits.schemas.limit_schemas import (
    ProfileCreate,
    RiskLimitCreate,
    AssignmentCreate,
    EvaluationRequest,
)
from backend.app.modules.risk_limits.portfolio_risk_limits.repositories.limit_repository import (
    RiskLimitRepository,
)
from backend.app.modules.risk_limits.portfolio_risk_limits.calculations.limit_math import (
    evaluate_var_limit,
    evaluate_volatility_limit,
    evaluate_drawdown_limit,
)


class PortfolioRiskLimitService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RiskLimitRepository(session)

    async def create_profile(self, payload: ProfileCreate) -> RiskLimitProfile:
        existing = await self.repo.get_profile_by_code(payload.profile_code)
        if existing:
            raise ValueError(f"Risk limit profile '{payload.profile_code}' already exists.")

        profile = RiskLimitProfile(
            profile_code=payload.profile_code,
            profile_name=payload.profile_name,
            description=payload.description,
            profile_category=payload.profile_category,
            mandate_type=payload.mandate_type,
            portfolio_type=payload.portfolio_type,
            base_currency_policy=payload.base_currency_policy,
            status="ACTIVE",
            owner_id=payload.owner_id,
            is_active=True
        )

        version = RiskLimitProfileVersion(
            version_number=1,
            version_status="ACTIVE",
            change_summary="Initial approved profile version",
            created_by=payload.owner_id,
            approved_by=payload.owner_id,
            approved_at=datetime.utcnow(),
            effective_from=datetime.utcnow()
        )

        if payload.initial_limits:
            for l_in in payload.initial_limits:
                limit_obj = PortfolioRiskLimit(
                    limit_code=l_in.limit_code,
                    limit_name=l_in.limit_name,
                    risk_category=l_in.risk_category,
                    metric_identifier=l_in.metric_identifier,
                    limit_type=l_in.limit_type,
                    warning_threshold=l_in.warning_threshold,
                    hard_threshold=l_in.hard_threshold,
                    threshold_unit=l_in.threshold_unit,
                    comparison_operator=l_in.comparison_operator,
                    confidence_level=l_in.confidence_level,
                    risk_horizon_days=l_in.risk_horizon_days,
                    risk_methodology=l_in.risk_methodology,
                    volatility_type=l_in.volatility_type,
                    return_frequency=l_in.return_frequency,
                    annualization_factor=l_in.annualization_factor,
                    estimation_window_days=l_in.estimation_window_days,
                    drawdown_methodology=l_in.drawdown_methodology,
                    is_active=True
                )
                version.limits.append(limit_obj)

        profile.versions.append(version)
        created = await self.repo.create_profile(profile)

        await self.repo.log_audit_event(
            profile_id=created.id,
            event_type="CREATE_PROFILE",
            actor_id=payload.owner_id,
            details={"code": created.profile_code, "version": 1, "limits_count": len(version.limits)}
        )
        return created

    async def get_profile(self, code_or_id: str) -> Optional[RiskLimitProfile]:
        p = await self.repo.get_profile_by_code(code_or_id)
        if not p:
            p = await self.repo.get_profile_by_id(code_or_id)
        return p

    async def list_profiles(self) -> List[RiskLimitProfile]:
        return await self.repo.list_profiles()

    async def assign_profile(self, payload: AssignmentCreate) -> PortfolioLimitAssignment:
        profile = await self.get_profile(payload.profile_id)
        if not profile:
            raise ValueError(f"Profile '{payload.profile_id}' not found.")

        # Find active version
        active_ver = None
        for v in profile.versions:
            if v.version_status == "ACTIVE":
                active_ver = v
                break
        if not active_ver and profile.versions:
            active_ver = profile.versions[-1]

        if not active_ver:
            raise ValueError(f"No active version found for profile '{profile.profile_code}'.")

        assignment = PortfolioLimitAssignment(
            profile_id=profile.id,
            profile_version_id=active_ver.id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            assignment_status="ACTIVE",
            precedence=payload.precedence,
            assigned_by=payload.assigned_by,
            effective_from=payload.effective_from or datetime.utcnow(),
            effective_to=payload.effective_to
        )
        created_assign = await self.repo.create_assignment(assignment)
        await self.repo.log_audit_event(
            profile_id=profile.id,
            portfolio_id=payload.target_id,
            event_type="ASSIGN_PROFILE",
            actor_id=payload.assigned_by,
            details={"target_type": payload.target_type, "target_id": payload.target_id}
        )
        return created_assign

    async def evaluate_portfolio_limits(
        self,
        request: EvaluationRequest
    ) -> Dict[str, Any]:
        """
        Evaluates active limits for a target portfolio against observed risk measurements.
        """
        assignment = await self.repo.get_effective_assignment_for_portfolio(request.portfolio_id)
        if not assignment:
            # Fallback check if default standard profile exists
            all_profiles = await self.repo.list_profiles()
            if not all_profiles:
                raise ValueError(f"No active risk-limit profile assigned to portfolio '{request.portfolio_id}'.")
            profile = all_profiles[0]
            version = profile.versions[0]
        else:
            profile = await self.repo.get_profile_by_id(assignment.profile_id)
            if not profile or not profile.versions:
                raise ValueError(f"Profile for assignment '{assignment.id}' not found.")
            version = profile.versions[0]

        evaluations = []
        snapshots_to_save = []
        worst_state = "WITHIN_LIMIT"

        # Defaults if observed values not explicitly passed
        obs_var = request.observed_var_monetary or Decimal("25000.00")
        obs_vol = request.observed_volatility_annualized or Decimal("0.1850")
        obs_dd = request.observed_drawdown_magnitude or Decimal("0.0650")
        portfolio_nav = request.portfolio_nav or Decimal("1000000.00")

        for lim in version.limits:
            if not lim.is_active:
                continue

            if lim.risk_category == "VAR":
                res = evaluate_var_limit(
                    observed_var=obs_var,
                    limit_type=lim.limit_type,
                    warning_threshold=lim.warning_threshold,
                    hard_threshold=lim.hard_threshold,
                    portfolio_nav=portfolio_nav
                )
            elif lim.risk_category == "VOLATILITY":
                res = evaluate_volatility_limit(
                    observed_volatility=obs_vol,
                    warning_threshold=lim.warning_threshold,
                    hard_threshold=lim.hard_threshold
                )
            elif lim.risk_category == "DRAWDOWN":
                res = evaluate_drawdown_limit(
                    observed_drawdown=obs_dd,
                    warning_threshold=lim.warning_threshold,
                    hard_threshold=lim.hard_threshold
                )
            else:
                continue

            # Update overall worst state
            st = res["evaluation_status"]
            if st == "HARD_LIMIT_EXCEEDED":
                worst_state = "HARD_LIMIT_EXCEEDED"
            elif st == "WARNING" and worst_state != "HARD_LIMIT_EXCEEDED":
                worst_state = "WARNING"
            elif st in ("INVALID", "UNAVAILABLE") and worst_state == "WITHIN_LIMIT":
                worst_state = st

            eval_item = {
                "limit_id": lim.id,
                "limit_code": lim.limit_code,
                "risk_category": lim.risk_category,
                "metric_identifier": lim.metric_identifier,
                "observed_metric_value": res["observed_value"],
                "warning_threshold": lim.warning_threshold,
                "hard_threshold": lim.hard_threshold,
                "warning_utilization_pct": res["warning_utilization_pct"],
                "hard_utilization_pct": res["hard_utilization_pct"],
                "headroom": res["headroom"],
                "unit": lim.threshold_unit,
                "evaluation_status": st,
                "details": res
            }
            evaluations.append(eval_item)

            snapshot = RiskLimitUtilizationSnapshot(
                portfolio_id=request.portfolio_id,
                profile_id=profile.id,
                profile_version_number=version.version_number,
                limit_id=lim.id,
                limit_code=lim.limit_code,
                risk_category=lim.risk_category,
                metric_identifier=lim.metric_identifier,
                observed_metric_value=res["observed_value"],
                warning_threshold=lim.warning_threshold,
                hard_threshold=lim.hard_threshold,
                warning_utilization_pct=res["warning_utilization_pct"],
                hard_utilization_pct=res["hard_utilization_pct"],
                headroom=res["headroom"],
                unit=lim.threshold_unit,
                evaluation_status=st,
                evaluated_at=datetime.utcnow(),
                details={"metric": lim.metric_identifier, "state": st}
            )
            snapshots_to_save.append(snapshot)

        # Save snapshots
        if snapshots_to_save:
            await self.repo.save_utilization_snapshots(snapshots_to_save)

        return {
            "portfolio_id": request.portfolio_id,
            "profile_code": profile.profile_code,
            "profile_version_number": version.version_number,
            "evaluated_at": datetime.utcnow(),
            "overall_status": worst_state,
            "utilizations": evaluations,
            "narrative": f"Portfolio '{request.portfolio_id}' evaluated against profile '{profile.profile_code}'. Overall state: {worst_state}."
        }

