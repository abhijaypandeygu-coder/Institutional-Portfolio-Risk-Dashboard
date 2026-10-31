"""
Module 01: Feed Registry & Configuration - Data Repository Layer.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.feed_registry.models import (
    CommandStatus,
    FeedAuditLog,
    FeedConfigVersion,
    FeedFailoverGroup,
    FeedHealthEvent,
    FeedLifecycleCommand,
    FeedPriorityMember,
    FeedRecordStatus,
    FeedRegistry,
    FeedSchedule,
)


class FeedRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Feed Registry Operations
    # =========================================================================

    async def get_by_id(self, feed_id: UUID) -> Optional[FeedRegistry]:
        stmt = (
            select(FeedRegistry)
            .where(FeedRegistry.id == feed_id)
            .options(
                selectinload(FeedRegistry.schedule),
                selectinload(FeedRegistry.config_versions),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, feed_code: str) -> Optional[FeedRegistry]:
        stmt = (
            select(FeedRegistry)
            .where(FeedRegistry.feed_code == feed_code.strip().upper())
            .options(
                selectinload(FeedRegistry.schedule),
                selectinload(FeedRegistry.config_versions),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_feeds(
        self,
        category: Optional[str] = None,
        desired_state: Optional[str] = None,
        record_status: Optional[FeedRecordStatus] = FeedRecordStatus.ACTIVE,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FeedRegistry]:
        stmt = select(FeedRegistry)
        if record_status:
            stmt = stmt.where(FeedRegistry.record_status == record_status)
        if category:
            stmt = stmt.where(FeedRegistry.category == category)
        if desired_state:
            stmt = stmt.where(FeedRegistry.desired_state == desired_state)
        stmt = stmt.order_by(FeedRegistry.feed_code.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_feed(self, feed: FeedRegistry) -> FeedRegistry:
        self.session.add(feed)
        await self.session.flush()
        return feed

    async def update_feed(self, feed: FeedRegistry) -> FeedRegistry:
        feed.updated_at = datetime.now(timezone.utc)
        self.session.add(feed)
        await self.session.flush()
        return feed

    # =========================================================================
    # Configuration Version Operations
    # =========================================================================

    async def get_latest_config(self, feed_id: UUID) -> Optional[FeedConfigVersion]:
        stmt = (
            select(FeedConfigVersion)
            .where(FeedConfigVersion.feed_id == feed_id)
            .order_by(desc(FeedConfigVersion.version_number))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_config_by_version(self, feed_id: UUID, version: int) -> Optional[FeedConfigVersion]:
        stmt = (
            select(FeedConfigVersion)
            .where(
                FeedConfigVersion.feed_id == feed_id,
                FeedConfigVersion.version_number == version,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_config_versions(self, feed_id: UUID) -> List[FeedConfigVersion]:
        stmt = (
            select(FeedConfigVersion)
            .where(FeedConfigVersion.feed_id == feed_id)
            .order_by(desc(FeedConfigVersion.version_number))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_config_version(self, config_version: FeedConfigVersion) -> FeedConfigVersion:
        self.session.add(config_version)
        await self.session.flush()
        return config_version

    # =========================================================================
    # Feed Schedule Operations
    # =========================================================================

    async def get_schedule(self, feed_id: UUID) -> Optional[FeedSchedule]:
        stmt = select(FeedSchedule).where(FeedSchedule.feed_id == feed_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_schedule(self, schedule: FeedSchedule) -> FeedSchedule:
        existing = await self.get_schedule(schedule.feed_id)
        if existing:
            existing.timezone = schedule.timezone
            existing.auto_start_stop_enabled = schedule.auto_start_stop_enabled
            existing.sessions = schedule.sessions
            existing.polling_interval_ms = schedule.polling_interval_ms
            existing.active_days = schedule.active_days
            existing.updated_at = datetime.now(timezone.utc)
            self.session.add(existing)
            await self.session.flush()
            return existing
        else:
            self.session.add(schedule)
            await self.session.flush()
            return schedule

    # =========================================================================
    # Failover & Priority Groups Operations
    # =========================================================================

    async def get_failover_group(self, group_id: UUID) -> Optional[FeedFailoverGroup]:
        stmt = (
            select(FeedFailoverGroup)
            .where(FeedFailoverGroup.id == group_id)
            .options(selectinload(FeedFailoverGroup.priority_members))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_failover_group_by_name(self, group_name: str) -> Optional[FeedFailoverGroup]:
        stmt = (
            select(FeedFailoverGroup)
            .where(FeedFailoverGroup.group_name == group_name.strip())
            .options(selectinload(FeedFailoverGroup.priority_members))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_failover_groups(self) -> List[FeedFailoverGroup]:
        stmt = (
            select(FeedFailoverGroup)
            .options(selectinload(FeedFailoverGroup.priority_members))
            .order_by(FeedFailoverGroup.group_name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_failover_group(self, group: FeedFailoverGroup) -> FeedFailoverGroup:
        self.session.add(group)
        await self.session.flush()
        return group

    async def add_priority_member(self, member: FeedPriorityMember) -> FeedPriorityMember:
        self.session.add(member)
        await self.session.flush()
        return member

    # =========================================================================
    # Lifecycle & Outbox Command Operations
    # =========================================================================

    async def create_lifecycle_command(self, cmd: FeedLifecycleCommand) -> FeedLifecycleCommand:
        self.session.add(cmd)
        await self.session.flush()
        return cmd

    async def get_pending_commands(self, limit: int = 50) -> List[FeedLifecycleCommand]:
        stmt = (
            select(FeedLifecycleCommand)
            .where(FeedLifecycleCommand.status == CommandStatus.PENDING)
            .order_by(FeedLifecycleCommand.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_command_status(
        self,
        command_id: UUID,
        status: CommandStatus,
        error_message: Optional[str] = None,
    ) -> None:
        stmt = (
            update(FeedLifecycleCommand)
            .where(FeedLifecycleCommand.id == command_id)
            .values(
                status=status,
                executed_at=datetime.now(timezone.utc) if status == CommandStatus.PROCESSED else None,
                error_message=error_message,
                attempts=FeedLifecycleCommand.attempts + 1,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    # =========================================================================
    # Health & Monitoring Operations
    # =========================================================================

    async def record_health_event(self, event: FeedHealthEvent) -> FeedHealthEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_recent_health_events(self, feed_id: UUID, limit: int = 50) -> List[FeedHealthEvent]:
        stmt = (
            select(FeedHealthEvent)
            .where(FeedHealthEvent.feed_id == feed_id)
            .order_by(desc(FeedHealthEvent.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_health_event(self, feed_id: UUID) -> Optional[FeedHealthEvent]:
        stmt = (
            select(FeedHealthEvent)
            .where(FeedHealthEvent.feed_id == feed_id)
            .order_by(desc(FeedHealthEvent.timestamp))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # Audit Logging Operations
    # =========================================================================

    async def record_audit_log(self, log_entry: FeedAuditLog) -> FeedAuditLog:
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def list_audit_logs(
        self,
        feed_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List[FeedAuditLog]:
        stmt = select(FeedAuditLog)
        if feed_id:
            stmt = stmt.where(FeedAuditLog.resource_id == str(feed_id))
        stmt = stmt.order_by(desc(FeedAuditLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

