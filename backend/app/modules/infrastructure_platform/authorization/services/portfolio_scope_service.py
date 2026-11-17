import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.infrastructure_platform.authorization.models.authz_models import (
    ResourceAccessAssignment,
    AssignmentStatus,
)


class PortfolioScopeService:
    """Manages portfolio access grants and verifies portfolio-level isolation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def grant_portfolio_access(
        self,
        user_id: str,
        portfolio_id: str,
        access_level: str = "READ",
        assigned_by: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> ResourceAccessAssignment:
        assignment = ResourceAccessAssignment(
            assignment_id=f"pacc-{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            resource_type="PORTFOLIO",
            resource_id=portfolio_id,
            access_level=access_level.upper(),
            status=AssignmentStatus.ACTIVE,
            effective_from=datetime.now(timezone.utc),
            expires_at=expires_at,
            assigned_by=assigned_by,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def revoke_portfolio_access(self, assignment_id: str) -> bool:
        res = await self.db.execute(
            select(ResourceAccessAssignment).where(
                ResourceAccessAssignment.assignment_id == assignment_id
            )
        )
        asgn = res.scalar_one_or_none()
        if not asgn:
            return False
        asgn.status = AssignmentStatus.REVOKED
        await self.db.commit()
        return True

    async def get_user_portfolio_scopes(self, user_id: str) -> Set[str]:
        """Returns set of portfolio_ids explicitly assigned to user."""
        now = datetime.now(timezone.utc)
        stmt = select(ResourceAccessAssignment.resource_id).where(
            and_(
                ResourceAccessAssignment.user_id == user_id,
                ResourceAccessAssignment.resource_type == "PORTFOLIO",
                ResourceAccessAssignment.status == AssignmentStatus.ACTIVE,
                ResourceAccessAssignment.effective_from <= now,
            )
        )
        res = await self.db.execute(stmt)
        return set(res.scalars().all())

    async def has_portfolio_access(
        self,
        user_id: str,
        portfolio_id: str,
        required_access: str = "READ",
    ) -> bool:
        """Checks if a user is explicitly granted active access to target portfolio."""
        now = datetime.now(timezone.utc)
        stmt = select(ResourceAccessAssignment).where(
            and_(
                ResourceAccessAssignment.user_id == user_id,
                ResourceAccessAssignment.resource_type == "PORTFOLIO",
                ResourceAccessAssignment.resource_id == portfolio_id,
                ResourceAccessAssignment.status == AssignmentStatus.ACTIVE,
                ResourceAccessAssignment.effective_from <= now,
            )
        )
        res = await self.db.execute(stmt)
        asgn = res.scalar_one_or_none()
        if not asgn:
            return False
        if asgn.expires_at and asgn.expires_at < now:
            return False
        if required_access == "WRITE" and asgn.access_level not in ("WRITE", "ADMIN"):
            return False
        return True
