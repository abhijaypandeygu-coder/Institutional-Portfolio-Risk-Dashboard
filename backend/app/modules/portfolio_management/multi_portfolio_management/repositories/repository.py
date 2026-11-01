"""
M05.08 Multi-Portfolio Management Repository.
Data access layer for groups, memberships, policies, overrides, consolidation runs, holdings, and snapshots.
"""

from datetime import datetime
from typing import Optional, List, Sequence
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.modules.portfolio_management.multi_portfolio_management.models import (
    PortfolioGroup,
    PortfolioGroupMembership,
    PortfolioGroupMembershipEvent,
    PortfolioGroupPolicy,
    PortfolioGroupSettingOverride,
    PortfolioGroupConsolidationRun,
    PortfolioGroupConsolidatedHolding,
    PortfolioGroupHoldingContributor,
    PortfolioGroupCashSummary,
    PortfolioGroupSnapshot,
    PortfolioGroupAuditEvent,
    MembershipStatus,
)


class MultiPortfolioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ==========================================
    # Group Management
    # ==========================================

    async def create_group(self, group: PortfolioGroup) -> PortfolioGroup:
        self.session.add(group)
        await self.session.flush()
        return group

    async def get_group_by_id(self, group_id: str) -> Optional[PortfolioGroup]:
        stmt = select(PortfolioGroup).where(PortfolioGroup.id == group_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_group_by_code(self, group_code: str) -> Optional[PortfolioGroup]:
        stmt = select(PortfolioGroup).where(PortfolioGroup.group_code == group_code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_groups(
        self,
        group_type: Optional[str] = None,
        status: Optional[str] = None,
        owner_reference: Optional[str] = None,
        parent_group_id: Optional[str] = None,
        limit: int = 100,
    ) -> Sequence[PortfolioGroup]:
        conditions = []
        if group_type:
            conditions.append(PortfolioGroup.group_type == group_type)
        if status:
            conditions.append(PortfolioGroup.status == status)
        if owner_reference:
            conditions.append(PortfolioGroup.owner_reference == owner_reference)
        if parent_group_id:
            conditions.append(PortfolioGroup.parent_group_id == parent_group_id)

        stmt = select(PortfolioGroup)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(asc(PortfolioGroup.group_code)).limit(limit)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_child_groups(self, parent_group_id: str) -> Sequence[PortfolioGroup]:
        stmt = select(PortfolioGroup).where(PortfolioGroup.parent_group_id == parent_group_id)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    # ==========================================
    # Membership Management
    # ==========================================

    async def add_membership(self, membership: PortfolioGroupMembership) -> PortfolioGroupMembership:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_membership(self, group_id: str, portfolio_id: str) -> Optional[PortfolioGroupMembership]:
        stmt = (
            select(PortfolioGroupMembership)
            .where(
                and_(
                    PortfolioGroupMembership.group_id == group_id,
                    PortfolioGroupMembership.portfolio_id == portfolio_id,
                )
            )
            .order_by(desc(PortfolioGroupMembership.membership_version))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_memberships_as_of(
        self,
        group_id: str,
        as_of: datetime,
    ) -> Sequence[PortfolioGroupMembership]:
        stmt = (
            select(PortfolioGroupMembership)
            .where(
                and_(
                    PortfolioGroupMembership.group_id == group_id,
                    PortfolioGroupMembership.membership_status == MembershipStatus.ACTIVE.value,
                    PortfolioGroupMembership.effective_from <= as_of,
                    or_(
                        PortfolioGroupMembership.effective_to.is_(None),
                        PortfolioGroupMembership.effective_to > as_of,
                    ),
                )
            )
            .order_by(asc(PortfolioGroupMembership.portfolio_id))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def list_group_memberships(
        self,
        group_id: str,
        include_historical: bool = False,
    ) -> Sequence[PortfolioGroupMembership]:
        stmt = select(PortfolioGroupMembership).where(PortfolioGroupMembership.group_id == group_id)
        if not include_historical:
            stmt = stmt.where(PortfolioGroupMembership.membership_status == MembershipStatus.ACTIVE.value)
        stmt = stmt.order_by(asc(PortfolioGroupMembership.portfolio_id))
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def add_membership_event(self, event: PortfolioGroupMembershipEvent) -> PortfolioGroupMembershipEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_membership_history(self, group_id: str) -> Sequence[PortfolioGroupMembershipEvent]:
        stmt = (
            select(PortfolioGroupMembershipEvent)
            .where(PortfolioGroupMembershipEvent.group_id == group_id)
            .order_by(asc(PortfolioGroupMembershipEvent.recorded_at))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    # ==========================================
    # Shared Policies & Overrides
    # ==========================================

    async def create_policy(self, policy: PortfolioGroupPolicy) -> PortfolioGroupPolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_latest_group_policy(self, group_id: str) -> Optional[PortfolioGroupPolicy]:
        stmt = (
            select(PortfolioGroupPolicy)
            .where(PortfolioGroupPolicy.group_id == group_id)
            .order_by(desc(PortfolioGroupPolicy.policy_version))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_override(self, override: PortfolioGroupSettingOverride) -> PortfolioGroupSettingOverride:
        self.session.add(override)
        await self.session.flush()
        return override

    async def get_portfolio_override(
        self,
        group_id: str,
        portfolio_id: str,
        setting_type: str,
        as_of: datetime,
    ) -> Optional[PortfolioGroupSettingOverride]:
        stmt = (
            select(PortfolioGroupSettingOverride)
            .where(
                and_(
                    PortfolioGroupSettingOverride.group_id == group_id,
                    PortfolioGroupSettingOverride.portfolio_id == portfolio_id,
                    PortfolioGroupSettingOverride.setting_type == setting_type,
                    PortfolioGroupSettingOverride.effective_from <= as_of,
                    or_(
                        PortfolioGroupSettingOverride.effective_to.is_(None),
                        PortfolioGroupSettingOverride.effective_to > as_of,
                    ),
                )
            )
            .order_by(desc(PortfolioGroupSettingOverride.override_version))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ==========================================
    # Consolidation Runs & Holdings
    # ==========================================

    async def create_consolidation_run(self, run: PortfolioGroupConsolidationRun) -> PortfolioGroupConsolidationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_consolidation_run(self, run_id: str) -> Optional[PortfolioGroupConsolidationRun]:
        stmt = select(PortfolioGroupConsolidationRun).where(PortfolioGroupConsolidationRun.id == run_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_consolidation_runs(self, group_id: str, limit: int = 50) -> Sequence[PortfolioGroupConsolidationRun]:
        stmt = (
            select(PortfolioGroupConsolidationRun)
            .where(PortfolioGroupConsolidationRun.group_id == group_id)
            .order_by(desc(PortfolioGroupConsolidationRun.started_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_run_holdings(self, run_id: str) -> Sequence[PortfolioGroupConsolidatedHolding]:
        stmt = (
            select(PortfolioGroupConsolidatedHolding)
            .where(PortfolioGroupConsolidatedHolding.consolidation_run_id == run_id)
            .order_by(asc(PortfolioGroupConsolidatedHolding.instrument_id))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_holding_contributors(self, consolidated_holding_id: str) -> Sequence[PortfolioGroupHoldingContributor]:
        stmt = (
            select(PortfolioGroupHoldingContributor)
            .where(PortfolioGroupHoldingContributor.consolidated_holding_id == consolidated_holding_id)
            .order_by(asc(PortfolioGroupHoldingContributor.portfolio_id), asc(PortfolioGroupHoldingContributor.account_id))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_run_cash_summaries(self, run_id: str) -> Sequence[PortfolioGroupCashSummary]:
        stmt = (
            select(PortfolioGroupCashSummary)
            .where(PortfolioGroupCashSummary.consolidation_run_id == run_id)
            .order_by(asc(PortfolioGroupCashSummary.currency))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    # ==========================================
    # Group Snapshots & Audit
    # ==========================================

    async def create_snapshot(self, snapshot: PortfolioGroupSnapshot) -> PortfolioGroupSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_snapshot(self, snapshot_id: str) -> Optional[PortfolioGroupSnapshot]:
        stmt = select(PortfolioGroupSnapshot).where(PortfolioGroupSnapshot.id == snapshot_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_snapshots(self, group_id: str, limit: int = 50) -> Sequence[PortfolioGroupSnapshot]:
        stmt = (
            select(PortfolioGroupSnapshot)
            .where(PortfolioGroupSnapshot.group_id == group_id)
            .order_by(desc(PortfolioGroupSnapshot.effective_as_of), desc(PortfolioGroupSnapshot.knowledge_as_of))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def add_audit_event(self, event: PortfolioGroupAuditEvent) -> PortfolioGroupAuditEvent:
        self.session.add(event)
        await self.session.flush()
        return event
