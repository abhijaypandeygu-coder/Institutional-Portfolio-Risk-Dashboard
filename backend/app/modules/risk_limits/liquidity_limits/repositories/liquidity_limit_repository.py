"""
Repository layer for M11.04 Liquidity Limits.
Provides async database CRUD operations and audit logging.
"""

from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.liquidity_limits.models.liquidity_limit_models import (
    LiquidityLimitConfiguration,
    LiquidityLimitProfile,
    LiquidityLimitAssignment,
    LiquidityLimitEvaluation,
    PositionLiquidityEvaluationResult,
    LiquidityLimitBreachEvent,
    LiquidityDataExceptionRecord,
    LiquidityLimitAuditLog,
)


class LiquidityLimitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Configurations
    async def create_configuration(self, config: LiquidityLimitConfiguration) -> LiquidityLimitConfiguration:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_configuration_by_code(self, code: str) -> Optional[LiquidityLimitConfiguration]:
        stmt = select(LiquidityLimitConfiguration).where(LiquidityLimitConfiguration.limit_code == code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configurations(self, portfolio_id: Optional[str] = None) -> List[LiquidityLimitConfiguration]:
        stmt = select(LiquidityLimitConfiguration)
        if portfolio_id:
            stmt = stmt.where(LiquidityLimitConfiguration.portfolio_id == portfolio_id)
        stmt = stmt.order_by(LiquidityLimitConfiguration.precedence.asc(), LiquidityLimitConfiguration.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Profiles
    async def create_profile(self, profile: LiquidityLimitProfile) -> LiquidityLimitProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile_by_code(self, profile_code: str) -> Optional[LiquidityLimitProfile]:
        stmt = (
            select(LiquidityLimitProfile)
            .where(LiquidityLimitProfile.profile_code == profile_code)
            .options(selectinload(LiquidityLimitProfile.configurations))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_profile_by_id(self, profile_id: str) -> Optional[LiquidityLimitProfile]:
        stmt = (
            select(LiquidityLimitProfile)
            .where(LiquidityLimitProfile.id == profile_id)
            .options(selectinload(LiquidityLimitProfile.configurations))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_profiles(self) -> List[LiquidityLimitProfile]:
        stmt = (
            select(LiquidityLimitProfile)
            .options(selectinload(LiquidityLimitProfile.configurations))
            .order_by(LiquidityLimitProfile.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Assignments
    async def create_assignment(self, assignment: LiquidityLimitAssignment) -> LiquidityLimitAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_active_assignment_for_portfolio(self, portfolio_id: str) -> Optional[LiquidityLimitAssignment]:
        stmt = (
            select(LiquidityLimitAssignment)
            .where(
                LiquidityLimitAssignment.target_id == portfolio_id,
                LiquidityLimitAssignment.status == "ACTIVE"
            )
            .order_by(LiquidityLimitAssignment.precedence.asc())
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # Evaluations
    async def save_evaluation(
        self,
        evaluation: LiquidityLimitEvaluation,
        results: List[PositionLiquidityEvaluationResult],
        breaches: List[LiquidityLimitBreachEvent],
        exceptions: Optional[List[LiquidityDataExceptionRecord]] = None,
    ) -> LiquidityLimitEvaluation:
        self.session.add(evaluation)
        for r in results:
            self.session.add(r)
        for b in breaches:
            self.session.add(b)
        if exceptions:
            for exc in exceptions:
                self.session.add(exc)
        await self.session.flush()
        return evaluation

    async def get_latest_evaluation(self, portfolio_id: str) -> Optional[LiquidityLimitEvaluation]:
        stmt = (
            select(LiquidityLimitEvaluation)
            .where(LiquidityLimitEvaluation.portfolio_id == portfolio_id)
            .options(selectinload(LiquidityLimitEvaluation.results))
            .order_by(LiquidityLimitEvaluation.evaluation_timestamp.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # Breaches & Exceptions
    async def list_breaches(self, portfolio_id: Optional[str] = None) -> List[LiquidityLimitBreachEvent]:
        stmt = select(LiquidityLimitBreachEvent)
        if portfolio_id:
            stmt = stmt.where(LiquidityLimitBreachEvent.portfolio_id == portfolio_id)
        stmt = stmt.order_by(LiquidityLimitBreachEvent.detection_timestamp.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_exceptions(self, portfolio_id: Optional[str] = None) -> List[LiquidityDataExceptionRecord]:
        stmt = select(LiquidityDataExceptionRecord)
        if portfolio_id:
            stmt = stmt.where(LiquidityDataExceptionRecord.portfolio_id == portfolio_id)
        stmt = stmt.order_by(LiquidityDataExceptionRecord.detected_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Audit
    async def log_audit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str = "system",
        details: Optional[dict] = None
    ) -> LiquidityLimitAuditLog:
        audit = LiquidityLimitAuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=details,
        )
        self.session.add(audit)
        await self.session.flush()
        return audit

