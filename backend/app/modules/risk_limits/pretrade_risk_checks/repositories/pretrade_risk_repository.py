"""
Repository layer for M11.09 Pre-trade Risk Checks.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.pretrade_risk_checks.models.pretrade_risk_models import (
    PretradeOrderRequest,
    PretradeOrderVersion,
    PretradeEvaluationRun,
    PretradeCheckResult,
    PretradeSimulationRun,
    PretradeRiskDecision,
    PretradeAuthorization,
    PretradeRiskReservation,
    PretradeExecutionReference,
    PretradeAuditLog,
)


class PretradeRiskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_order_by_idempotency_key(self, key: str) -> Optional[PretradeOrderRequest]:
        self.db.expire_all()
        stmt = (
            select(PretradeOrderRequest)
            .where(PretradeOrderRequest.idempotency_key == key)
            .options(
                selectinload(PretradeOrderRequest.versions).selectinload(PretradeOrderVersion.evaluations).selectinload(PretradeEvaluationRun.decision)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_by_id(self, order_id: str) -> Optional[PretradeOrderRequest]:
        self.db.expire_all()
        stmt = (
            select(PretradeOrderRequest)
            .where(PretradeOrderRequest.id == order_id)
            .options(
                selectinload(PretradeOrderRequest.versions)
                .selectinload(PretradeOrderVersion.evaluations)
                .selectinload(PretradeEvaluationRun.check_results),
                selectinload(PretradeOrderRequest.versions)
                .selectinload(PretradeOrderVersion.evaluations)
                .selectinload(PretradeEvaluationRun.simulation_runs),
                selectinload(PretradeOrderRequest.versions)
                .selectinload(PretradeOrderVersion.evaluations)
                .selectinload(PretradeEvaluationRun.decision),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_order_request(self, order: PretradeOrderRequest) -> PretradeOrderRequest:
        self.db.add(order)
        await self.db.flush()
        return order

    async def save_order_version(self, version: PretradeOrderVersion) -> PretradeOrderVersion:
        self.db.add(version)
        await self.db.flush()
        return version

    async def save_evaluation_run(self, eval_run: PretradeEvaluationRun) -> PretradeEvaluationRun:
        self.db.add(eval_run)
        await self.db.flush()
        return eval_run

    async def save_check_result(self, check: PretradeCheckResult) -> PretradeCheckResult:
        self.db.add(check)
        await self.db.flush()
        return check

    async def save_simulation_run(self, sim: PretradeSimulationRun) -> PretradeSimulationRun:
        self.db.add(sim)
        await self.db.flush()
        return sim

    async def save_decision(self, decision: PretradeRiskDecision) -> PretradeRiskDecision:
        self.db.add(decision)
        await self.db.flush()
        return decision

    async def save_authorization(self, auth: PretradeAuthorization) -> PretradeAuthorization:
        self.db.add(auth)
        await self.db.flush()
        return auth

    async def save_reservation(self, res: PretradeRiskReservation) -> PretradeRiskReservation:
        self.db.add(res)
        await self.db.flush()
        return res

    async def get_authorization_by_id(self, auth_id: str) -> Optional[PretradeAuthorization]:
        self.db.expire_all()
        stmt = (
            select(PretradeAuthorization)
            .where(PretradeAuthorization.id == auth_id)
            .options(selectinload(PretradeAuthorization.reservations))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_reservations_for_portfolio(self, portfolio_id: str) -> List[PretradeRiskReservation]:
        now = datetime.utcnow()
        stmt = (
            select(PretradeRiskReservation)
            .where(
                and_(
                    PretradeRiskReservation.portfolio_id == portfolio_id,
                    PretradeRiskReservation.reservation_status == "ACTIVE",
                    PretradeRiskReservation.expires_at > now,
                )
            )
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_orders(
        self,
        portfolio_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PretradeOrderRequest]:
        stmt = select(PretradeOrderRequest).order_by(desc(PretradeOrderRequest.created_at))
        if portfolio_id:
            stmt = stmt.where(PretradeOrderRequest.portfolio_id == portfolio_id)
        if status:
            stmt = stmt.where(PretradeOrderRequest.current_status == status)
        stmt = stmt.offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_analytics_summary(self) -> Dict[str, Any]:
        """Aggregate evaluation metrics."""
        stmt = select(PretradeRiskDecision.decision, PretradeRiskDecision.primary_reason_code)
        res = await self.db.execute(stmt)
        rows = res.all()

        total = len(rows)
        pass_c = sum(1 for r in rows if r[0] == "PASS")
        rej_c = sum(1 for r in rows if r[0] == "REJECT")
        rev_c = sum(1 for r in rows if r[0] == "REVIEW_REQUIRED")

        reasons = {}
        for r in rows:
            if r[0] == "REJECT":
                code = r[1]
                reasons[code] = reasons.get(code, 0) + 1

        # Count active reservations
        now = datetime.utcnow()
        res_stmt = select(func.count(PretradeRiskReservation.id)).where(
            and_(PretradeRiskReservation.reservation_status == "ACTIVE", PretradeRiskReservation.expires_at > now)
        )
        res_count = (await self.db.execute(res_stmt)).scalar() or 0

        # Count active authorizations
        auth_stmt = select(func.count(PretradeAuthorization.id)).where(
            and_(PretradeAuthorization.authorization_status == "ACTIVE", PretradeAuthorization.expires_at > now)
        )
        auth_count = (await self.db.execute(auth_stmt)).scalar() or 0

        return {
            "total_orders_evaluated": total,
            "pass_count": pass_c,
            "reject_count": rej_c,
            "review_required_count": rev_c,
            "active_reservations_count": res_count,
            "active_authorizations_count": auth_count,
            "rejection_reasons_breakdown": reasons,
        }
