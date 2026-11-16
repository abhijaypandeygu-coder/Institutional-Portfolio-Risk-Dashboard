"""
Repository layer for M11.01 Portfolio Risk Limits.
Async SQLAlchemy operations for profiles, versions, limits, assignments, utilization snapshots, and audit events.
"""

from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_limits.portfolio_risk_limits.models.limit_models import (
    RiskLimitProfile,
    RiskLimitProfileVersion,
    PortfolioRiskLimit,
    PortfolioLimitAssignment,
    RiskLimitUtilizationSnapshot,
    RiskLimitAuditLog,
)


class RiskLimitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_profile_by_id(self, profile_id: str) -> Optional[RiskLimitProfile]:
        stmt = (
            select(RiskLimitProfile)
            .where(RiskLimitProfile.id == profile_id)
            .options(
                selectinload(RiskLimitProfile.versions).selectinload(RiskLimitProfileVersion.limits),
                selectinload(RiskLimitProfile.assignments),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_profile_by_code(self, profile_code: str) -> Optional[RiskLimitProfile]:
        stmt = (
            select(RiskLimitProfile)
            .where(RiskLimitProfile.profile_code == profile_code)
            .options(
                selectinload(RiskLimitProfile.versions).selectinload(RiskLimitProfileVersion.limits),
                selectinload(RiskLimitProfile.assignments),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_profiles(self) -> List[RiskLimitProfile]:
        stmt = (
            select(RiskLimitProfile)
            .options(
                selectinload(RiskLimitProfile.versions).selectinload(RiskLimitProfileVersion.limits)
            )
            .order_by(RiskLimitProfile.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_profile(self, profile: RiskLimitProfile) -> RiskLimitProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_effective_assignment_for_portfolio(
        self,
        portfolio_id: str
    ) -> Optional[PortfolioLimitAssignment]:
        """
        Resolves effective assignment:
        Precedence:
        1. Specific Portfolio ID (precedence=1)
        2. Mandate (precedence=2)
        3. Default (precedence=3)
        """
        stmt = (
            select(PortfolioLimitAssignment)
            .where(
                and_(
                    PortfolioLimitAssignment.target_id == portfolio_id,
                    PortfolioLimitAssignment.assignment_status == "ACTIVE"
                )
            )
            .order_by(PortfolioLimitAssignment.precedence.asc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def create_assignment(self, assignment: PortfolioLimitAssignment) -> PortfolioLimitAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def list_assignments(self, portfolio_id: Optional[str] = None) -> List[PortfolioLimitAssignment]:
        stmt = select(PortfolioLimitAssignment).order_by(PortfolioLimitAssignment.created_at.desc())
        if portfolio_id:
            stmt = stmt.where(PortfolioLimitAssignment.target_id == portfolio_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_utilization_snapshots(
        self,
        snapshots: List[RiskLimitUtilizationSnapshot]
    ) -> None:
        self.session.add_all(snapshots)
        await self.session.flush()

    async def list_utilizations_for_portfolio(
        self,
        portfolio_id: str,
        limit: int = 50
    ) -> List[RiskLimitUtilizationSnapshot]:
        stmt = (
            select(RiskLimitUtilizationSnapshot)
            .where(RiskLimitUtilizationSnapshot.portfolio_id == portfolio_id)
            .order_by(RiskLimitUtilizationSnapshot.evaluated_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def log_audit_event(
        self,
        event_type: str,
        actor_id: str = "system",
        details: Optional[dict] = None,
        profile_id: Optional[str] = None,
        portfolio_id: Optional[str] = None
    ) -> RiskLimitAuditLog:
        event = RiskLimitAuditLog(
            profile_id=profile_id,
            portfolio_id=portfolio_id,
            event_type=event_type,
            actor_id=actor_id,
            details=details or {}
        )
        self.session.add(event)
        await self.session.flush()
        return event

