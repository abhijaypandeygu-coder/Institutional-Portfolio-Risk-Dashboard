"""
Repository data access layer for M11.02 Position Limits.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.position_limits.models.position_limit_models import (
    PositionLimitConfiguration,
    PositionLimitProfile,
    PositionLimitAssignment,
    PositionLimitEvaluation,
    PositionLimitEvaluationResult,
    PositionLimitBreachEvent,
    PositionLimitAuditLog,
)


class PositionLimitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Configurations
    async def create_configuration(self, config: PositionLimitConfiguration) -> PositionLimitConfiguration:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_configuration_by_code(self, code: str) -> Optional[PositionLimitConfiguration]:
        stmt = select(PositionLimitConfiguration).where(PositionLimitConfiguration.limit_code == code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_configuration_by_id(self, config_id: str) -> Optional[PositionLimitConfiguration]:
        stmt = select(PositionLimitConfiguration).where(PositionLimitConfiguration.id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configurations(self, portfolio_id: Optional[str] = None) -> List[PositionLimitConfiguration]:
        stmt = select(PositionLimitConfiguration)
        if portfolio_id:
            stmt = stmt.where(
                or_(
                    PositionLimitConfiguration.portfolio_id == portfolio_id,
                    PositionLimitConfiguration.portfolio_id.is_(None)
                )
            )
        stmt = stmt.order_by(PositionLimitConfiguration.precedence.asc(), PositionLimitConfiguration.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Profiles
    async def create_profile(self, profile: PositionLimitProfile) -> PositionLimitProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile_by_code(self, profile_code: str) -> Optional[PositionLimitProfile]:
        stmt = (
            select(PositionLimitProfile)
            .where(PositionLimitProfile.profile_code == profile_code)
            .options(selectinload(PositionLimitProfile.configurations))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_profile_by_id(self, profile_id: str) -> Optional[PositionLimitProfile]:
        stmt = (
            select(PositionLimitProfile)
            .where(PositionLimitProfile.id == profile_id)
            .options(selectinload(PositionLimitProfile.configurations))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_profiles(self) -> List[PositionLimitProfile]:
        stmt = select(PositionLimitProfile).options(selectinload(PositionLimitProfile.configurations)).order_by(PositionLimitProfile.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Assignments
    async def create_assignment(self, assignment: PositionLimitAssignment) -> PositionLimitAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_active_assignment_for_portfolio(self, portfolio_id: str) -> Optional[PositionLimitAssignment]:
        stmt = (
            select(PositionLimitAssignment)
            .where(
                and_(
                    PositionLimitAssignment.target_type == "PORTFOLIO",
                    PositionLimitAssignment.target_id == portfolio_id,
                    PositionLimitAssignment.status == "ACTIVE"
                )
            )
            .order_by(PositionLimitAssignment.precedence.asc(), PositionLimitAssignment.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # Evaluations
    async def save_evaluation(self, eval_header: PositionLimitEvaluation) -> PositionLimitEvaluation:
        self.session.add(eval_header)
        await self.session.flush()
        return eval_header

    async def get_latest_evaluation(self, portfolio_id: str) -> Optional[PositionLimitEvaluation]:
        stmt = (
            select(PositionLimitEvaluation)
            .where(PositionLimitEvaluation.portfolio_id == portfolio_id)
            .options(selectinload(PositionLimitEvaluation.results))
            .order_by(desc(PositionLimitEvaluation.evaluation_timestamp))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_evaluations(self, portfolio_id: str, limit: int = 50) -> List[PositionLimitEvaluation]:
        stmt = (
            select(PositionLimitEvaluation)
            .where(PositionLimitEvaluation.portfolio_id == portfolio_id)
            .options(selectinload(PositionLimitEvaluation.results))
            .order_by(desc(PositionLimitEvaluation.evaluation_timestamp))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Breaches
    async def record_breaches(self, breaches: List[PositionLimitBreachEvent]) -> None:
        self.session.add_all(breaches)
        await self.session.flush()

    async def list_breaches(self, portfolio_id: Optional[str] = None, limit: int = 100) -> List[PositionLimitBreachEvent]:
        stmt = select(PositionLimitBreachEvent)
        if portfolio_id:
            stmt = stmt.where(PositionLimitBreachEvent.portfolio_id == portfolio_id)
        stmt = stmt.order_by(desc(PositionLimitBreachEvent.detection_timestamp)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Audit Logs
    async def log_audit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str = "system",
        details: Optional[dict] = None
    ) -> PositionLimitAuditLog:
        audit = PositionLimitAuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=details,
            timestamp=datetime.utcnow()
        )
        self.session.add(audit)
        await self.session.flush()
        return audit
