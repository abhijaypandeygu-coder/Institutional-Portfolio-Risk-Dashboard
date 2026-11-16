"""
Data access repository layer for M11.03 Sector Limits.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.sector_limits.models.sector_limit_models import (
    SectorLimitConfiguration,
    SectorLimitProfile,
    SectorLimitAssignment,
    SectorLimitEvaluation,
    SectorLimitEvaluationResult,
    SectorLimitBreachEvent,
    SectorLimitAuditLog,
)


class SectorLimitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Configurations
    async def create_configuration(self, config: SectorLimitConfiguration) -> SectorLimitConfiguration:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_configuration_by_code(self, code: str) -> Optional[SectorLimitConfiguration]:
        stmt = select(SectorLimitConfiguration).where(SectorLimitConfiguration.limit_code == code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configurations(self, portfolio_id: Optional[str] = None) -> List[SectorLimitConfiguration]:
        stmt = select(SectorLimitConfiguration)
        if portfolio_id:
            stmt = stmt.where(
                or_(
                    SectorLimitConfiguration.portfolio_id == portfolio_id,
                    SectorLimitConfiguration.portfolio_id.is_(None)
                )
            )
        stmt = stmt.order_by(SectorLimitConfiguration.precedence.asc(), SectorLimitConfiguration.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Profiles
    async def create_profile(self, profile: SectorLimitProfile) -> SectorLimitProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile_by_code(self, profile_code: str) -> Optional[SectorLimitProfile]:
        stmt = (
            select(SectorLimitProfile)
            .where(SectorLimitProfile.profile_code == profile_code)
            .options(selectinload(SectorLimitProfile.configurations))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_profile_by_id(self, profile_id: str) -> Optional[SectorLimitProfile]:
        stmt = (
            select(SectorLimitProfile)
            .where(SectorLimitProfile.id == profile_id)
            .options(selectinload(SectorLimitProfile.configurations))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_profiles(self) -> List[SectorLimitProfile]:
        stmt = select(SectorLimitProfile).options(selectinload(SectorLimitProfile.configurations)).order_by(SectorLimitProfile.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Assignments
    async def create_assignment(self, assignment: SectorLimitAssignment) -> SectorLimitAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_active_assignment_for_portfolio(self, portfolio_id: str) -> Optional[SectorLimitAssignment]:
        stmt = (
            select(SectorLimitAssignment)
            .where(
                and_(
                    SectorLimitAssignment.target_type == "PORTFOLIO",
                    SectorLimitAssignment.target_id == portfolio_id,
                    SectorLimitAssignment.status == "ACTIVE"
                )
            )
            .order_by(SectorLimitAssignment.precedence.asc(), SectorLimitAssignment.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # Evaluations
    async def save_evaluation(self, eval_header: SectorLimitEvaluation) -> SectorLimitEvaluation:
        self.session.add(eval_header)
        await self.session.flush()
        return eval_header

    async def get_latest_evaluation(self, portfolio_id: str) -> Optional[SectorLimitEvaluation]:
        stmt = (
            select(SectorLimitEvaluation)
            .where(SectorLimitEvaluation.portfolio_id == portfolio_id)
            .options(selectinload(SectorLimitEvaluation.results))
            .order_by(desc(SectorLimitEvaluation.evaluation_timestamp))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # Breaches
    async def record_breaches(self, breaches: List[SectorLimitBreachEvent]) -> None:
        self.session.add_all(breaches)
        await self.session.flush()

    async def list_breaches(self, portfolio_id: Optional[str] = None, limit: int = 100) -> List[SectorLimitBreachEvent]:
        stmt = select(SectorLimitBreachEvent)
        if portfolio_id:
            stmt = stmt.where(SectorLimitBreachEvent.portfolio_id == portfolio_id)
        stmt = stmt.order_by(desc(SectorLimitBreachEvent.detection_timestamp)).limit(limit)
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
    ) -> SectorLimitAuditLog:
        audit = SectorLimitAuditLog(
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

