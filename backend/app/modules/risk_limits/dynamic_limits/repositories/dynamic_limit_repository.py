"""
Async Repository implementation for M11.05 — Dynamic Limits.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, and_, or_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.dynamic_limits.models.dynamic_limit_models import (
    DynamicLimitPolicy,
    DynamicLimitPolicyVersion,
    DynamicLimitCondition,
    DynamicLimitSchedule,
    DynamicLimitOverride,
    EffectiveLimitSnapshot,
    DynamicLimitAuditEvent,
)


class DynamicLimitRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------
    # Policy CRUD
    # ---------------------------------------------------------

    async def create_policy(self, policy: DynamicLimitPolicy) -> DynamicLimitPolicy:
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        return await self.get_policy_by_id(policy.id)

    async def get_policy_by_id(self, policy_id: str) -> Optional[DynamicLimitPolicy]:
        stmt = (
            select(DynamicLimitPolicy)
            .where(DynamicLimitPolicy.id == policy_id)
            .options(
                selectinload(DynamicLimitPolicy.versions)
                .selectinload(DynamicLimitPolicyVersion.conditions),
                selectinload(DynamicLimitPolicy.versions)
                .selectinload(DynamicLimitPolicyVersion.schedules),
                selectinload(DynamicLimitPolicy.overrides),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_policy_by_code(self, policy_code: str) -> Optional[DynamicLimitPolicy]:
        stmt = (
            select(DynamicLimitPolicy)
            .where(DynamicLimitPolicy.policy_code == policy_code)
            .options(
                selectinload(DynamicLimitPolicy.versions)
                .selectinload(DynamicLimitPolicyVersion.conditions),
                selectinload(DynamicLimitPolicy.versions)
                .selectinload(DynamicLimitPolicyVersion.schedules),
                selectinload(DynamicLimitPolicy.overrides),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_policies(
        self,
        portfolio_id: Optional[str] = None,
        market: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[DynamicLimitPolicy]:
        query = select(DynamicLimitPolicy).options(
            selectinload(DynamicLimitPolicy.versions)
            .selectinload(DynamicLimitPolicyVersion.conditions),
            selectinload(DynamicLimitPolicy.versions)
            .selectinload(DynamicLimitPolicyVersion.schedules),
            selectinload(DynamicLimitPolicy.overrides),
        )
        
        conditions = []
        if portfolio_id:
            conditions.append(or_(DynamicLimitPolicy.portfolio_id == portfolio_id, DynamicLimitPolicy.portfolio_id.is_(None)))
        if market:
            conditions.append(or_(DynamicLimitPolicy.market == market, DynamicLimitPolicy.market.is_(None)))
        if status:
            conditions.append(DynamicLimitPolicy.status == status)

        if conditions:
            query = query.where(and_(*conditions))

        res = await self.db.execute(query)
        return list(res.scalars().all())

    async def update_policy(self, policy: DynamicLimitPolicy) -> DynamicLimitPolicy:
        await self.db.commit()
        await self.db.refresh(policy)
        return await self.get_policy_by_id(policy.id)

    # ---------------------------------------------------------
    # Policy Version CRUD
    # ---------------------------------------------------------

    async def create_version(self, version: DynamicLimitPolicyVersion) -> DynamicLimitPolicyVersion:
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def get_version_by_id(self, version_id: str) -> Optional[DynamicLimitPolicyVersion]:
        stmt = (
            select(DynamicLimitPolicyVersion)
            .where(DynamicLimitPolicyVersion.id == version_id)
            .options(
                selectinload(DynamicLimitPolicyVersion.conditions),
                selectinload(DynamicLimitPolicyVersion.schedules),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------------------------------------------------
    # Manual Overrides (Maker-Checker)
    # ---------------------------------------------------------

    async def create_override(self, override: DynamicLimitOverride) -> DynamicLimitOverride:
        self.db.add(override)
        await self.db.commit()
        await self.db.refresh(override)
        return override

    async def get_override_by_id(self, override_id: str) -> Optional[DynamicLimitOverride]:
        stmt = select(DynamicLimitOverride).where(DynamicLimitOverride.id == override_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_active_overrides(
        self,
        policy_id: str,
        target_limit_code: str,
        as_of_time: datetime
    ) -> List[DynamicLimitOverride]:
        stmt = (
            select(DynamicLimitOverride)
            .where(
                and_(
                    DynamicLimitOverride.policy_id == policy_id,
                    DynamicLimitOverride.target_limit_code == target_limit_code,
                    DynamicLimitOverride.status == "APPROVED",
                    DynamicLimitOverride.effective_from <= as_of_time,
                    DynamicLimitOverride.effective_to >= as_of_time,
                )
            )
            .order_by(desc(DynamicLimitOverride.approved_at))
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Effective Limit Snapshots
    # ---------------------------------------------------------

    async def create_snapshot(self, snapshot: EffectiveLimitSnapshot) -> EffectiveLimitSnapshot:
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def get_latest_snapshot(
        self,
        policy_id: str,
        target_limit_code: str,
        portfolio_id: Optional[str] = None
    ) -> Optional[EffectiveLimitSnapshot]:
        conditions = [
            EffectiveLimitSnapshot.policy_id == policy_id,
            EffectiveLimitSnapshot.target_limit_code == target_limit_code,
        ]
        if portfolio_id:
            conditions.append(EffectiveLimitSnapshot.portfolio_id == portfolio_id)
            
        stmt = (
            select(EffectiveLimitSnapshot)
            .where(and_(*conditions))
            .order_by(desc(EffectiveLimitSnapshot.as_of_time))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_snapshots(
        self,
        portfolio_id: Optional[str] = None,
        target_limit_code: Optional[str] = None,
        limit: int = 50
    ) -> List[EffectiveLimitSnapshot]:
        conditions = []
        if portfolio_id:
            conditions.append(EffectiveLimitSnapshot.portfolio_id == portfolio_id)
        if target_limit_code:
            conditions.append(EffectiveLimitSnapshot.target_limit_code == target_limit_code)
            
        query = select(EffectiveLimitSnapshot)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(desc(EffectiveLimitSnapshot.as_of_time)).limit(limit)
        res = await self.db.execute(query)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Audit Trail
    # ---------------------------------------------------------

    async def create_audit_event(self, event: DynamicLimitAuditEvent) -> DynamicLimitAuditEvent:
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def list_audit_events(self, entity_id: Optional[str] = None, limit: int = 50) -> List[DynamicLimitAuditEvent]:
        query = select(DynamicLimitAuditEvent)
        if entity_id:
            query = query.where(DynamicLimitAuditEvent.entity_id == entity_id)
        query = query.order_by(desc(DynamicLimitAuditEvent.timestamp)).limit(limit)
        res = await self.db.execute(query)
        return list(res.scalars().all())

