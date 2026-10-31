"""
Module 01: Feed Registry & Configuration - Business Logic Service Layer.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import AuthenticatedUser, UserRole
from backend.app.modules.feed_registry.models import (
    CommandStatus,
    FeedAuditLog,
    FeedConfigVersion,
    FeedDesiredState,
    FeedFailoverGroup,
    FeedHealthEvent,
    FeedLifecycleCommand,
    FeedPriorityMember,
    FeedRecordStatus,
    FeedRegistry,
    FeedSchedule,
)
from backend.app.modules.feed_registry.repository import FeedRepository
from backend.app.modules.feed_registry.schemas import (
    ConfigCreate,
    ConfigDiffResponse,
    ConfigRollbackRequest,
    FailoverGroupCreate,
    FeedCreate,
    FeedHealthSummary,
    FeedUpdate,
    HealthEventReport,
    ScheduleCreate,
    StateTransitionRequest,
)
from backend.app.modules.feed_registry.validators import (
    ValidationError,
    validate_configuration_payload,
    validate_session_intervals,
    validate_timezone,
)


class FeedService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FeedRepository(session)

    # -------------------------------------------------------------------------
    # Internal Audit Logger Helper
    # -------------------------------------------------------------------------
    async def _log_audit(
        self,
        actor: AuthenticatedUser,
        operation: str,
        resource_id: Optional[str],
        success: bool,
        details: Dict[str, Any],
    ) -> None:
        log_entry = FeedAuditLog(
            actor=actor.username,
            operation=operation,
            resource_type="feed_registry",
            resource_id=resource_id,
            success=success,
            details=details,
        )
        await self.repo.record_audit_log(log_entry)

    # =========================================================================
    # Feed Registry Management (Milestones 1 & 2)
    # =========================================================================

    async def register_feed(self, payload: FeedCreate, actor: AuthenticatedUser) -> FeedRegistry:
        existing = await self.repo.get_by_code(payload.feed_code)
        if existing:
            await self._log_audit(actor, "REGISTER_FEED_DUPLICATE_FAILED", None, False, {"feed_code": payload.feed_code})
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Feed with code '{payload.feed_code}' already exists.",
            )

        new_feed = FeedRegistry(
            feed_code=payload.feed_code,
            feed_name=payload.feed_name,
            description=payload.description,
            category=payload.category,
            asset_class=payload.asset_class,
            transport_protocol=payload.transport_protocol,
            capabilities=payload.capabilities.model_dump(),
            desired_state=FeedDesiredState.INACTIVE,
            record_status=FeedRecordStatus.ACTIVE,
            current_version=0,
            is_primary_eligible=payload.is_primary_eligible,
            is_backup_eligible=payload.is_backup_eligible,
            metadata_json=payload.metadata_json,
        )
        created = await self.repo.create_feed(new_feed)
        await self._log_audit(actor, "REGISTER_FEED", str(created.id), True, {"feed_code": created.feed_code})
        await self.session.commit()
        return created

    async def update_feed(self, feed_id: UUID, payload: FeedUpdate, actor: AuthenticatedUser) -> FeedRegistry:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")

        if payload.feed_name is not None:
            feed.feed_name = payload.feed_name
        if payload.description is not None:
            feed.description = payload.description
        if payload.capabilities is not None:
            feed.capabilities = payload.capabilities.model_dump()
        if payload.is_primary_eligible is not None:
            feed.is_primary_eligible = payload.is_primary_eligible
        if payload.is_backup_eligible is not None:
            feed.is_backup_eligible = payload.is_backup_eligible
        if payload.metadata_json is not None:
            feed.metadata_json = payload.metadata_json

        updated = await self.repo.update_feed(feed)
        await self._log_audit(actor, "UPDATE_FEED", str(feed.id), True, {"feed_code": feed.feed_code})
        await self.session.commit()
        return updated

    async def get_feed(self, feed_id: UUID) -> FeedRegistry:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")
        return feed

    async def list_feeds(
        self,
        category: Optional[str] = None,
        desired_state: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[FeedRegistry]:
        record_status = None if include_archived else FeedRecordStatus.ACTIVE
        return await self.repo.list_feeds(
            category=category,
            desired_state=desired_state,
            record_status=record_status,
        )

    # =========================================================================
    # Configuration Versioning & Rollback (Milestone 3)
    # =========================================================================

    def _compute_payload_hash(self, payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def create_configuration_version(
        self,
        feed_id: UUID,
        payload: ConfigCreate,
        actor: AuthenticatedUser,
    ) -> FeedConfigVersion:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")

        # Run semantic validation
        try:
            validate_configuration_payload(feed.transport_protocol, payload.config_payload)
        except ValidationError as err:
            await self._log_audit(actor, "CREATE_CONFIG_VALIDATION_FAILED", str(feed_id), False, {"error": str(err)})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))

        payload_dict = payload.config_payload.model_dump()
        payload_hash = self._compute_payload_hash(payload_dict)

        new_version_num = feed.current_version + 1
        new_version = FeedConfigVersion(
            feed_id=feed_id,
            version_number=new_version_num,
            schema_version=payload.schema_version,
            config_payload=payload_dict,
            config_hash=payload_hash,
            change_reason=payload.change_reason,
            author=actor.username,
        )
        created_version = await self.repo.create_config_version(new_version)

        # Update feed current version
        feed.current_version = new_version_num
        await self.repo.update_feed(feed)

        await self._log_audit(
            actor,
            "CREATE_CONFIG_VERSION",
            str(feed_id),
            True,
            {"version": new_version_num, "hash": payload_hash},
        )
        await self.session.commit()
        return created_version

    async def get_configuration(self, feed_id: UUID, version: Optional[int] = None) -> FeedConfigVersion:
        if version is not None:
            cfg = await self.repo.get_config_by_version(feed_id, version)
        else:
            cfg = await self.repo.get_latest_config(feed_id)

        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration not found for feed {feed_id} (version={version}).",
            )
        return cfg

    async def list_configurations(self, feed_id: UUID) -> List[FeedConfigVersion]:
        return await self.repo.list_config_versions(feed_id)

    async def diff_configurations(
        self,
        feed_id: UUID,
        from_version: int,
        to_version: int,
    ) -> ConfigDiffResponse:
        v1 = await self.repo.get_config_by_version(feed_id, from_version)
        v2 = await self.repo.get_config_by_version(feed_id, to_version)

        if not v1 or not v2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both configuration versions specified for diff were not found.",
            )

        p1 = v1.config_payload
        p2 = v2.config_payload

        keys1 = set(p1.keys())
        keys2 = set(p2.keys())

        added = {k: p2[k] for k in keys2 - keys1}
        removed = {k: p1[k] for k in keys1 - keys2}
        modified = {}

        for common in keys1 & keys2:
            if p1[common] != p2[common]:
                modified[common] = {"from": p1[common], "to": p2[common]}

        return ConfigDiffResponse(
            feed_id=feed_id,
            from_version=from_version,
            to_version=to_version,
            added=added,
            removed=removed,
            modified=modified,
        )

    async def rollback_configuration(
        self,
        feed_id: UUID,
        req: ConfigRollbackRequest,
        actor: AuthenticatedUser,
    ) -> FeedConfigVersion:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")

        target = await self.repo.get_config_by_version(feed_id, req.target_version)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target configuration version {req.target_version} does not exist for rollback.",
            )

        # Immutable rollback: creates a NEW version with target's payload
        new_version_num = feed.current_version + 1
        rollback_reason = f"Rollback to v{req.target_version}: {req.change_reason}"
        new_version = FeedConfigVersion(
            feed_id=feed_id,
            version_number=new_version_num,
            schema_version=target.schema_version,
            config_payload=target.config_payload,
            config_hash=target.config_hash,
            change_reason=rollback_reason,
            author=actor.username,
        )
        created_version = await self.repo.create_config_version(new_version)

        feed.current_version = new_version_num
        await self.repo.update_feed(feed)

        await self._log_audit(
            actor,
            "ROLLBACK_CONFIG_VERSION",
            str(feed_id),
            True,
            {"restored_from_version": req.target_version, "new_version": new_version_num},
        )
        await self.session.commit()
        return created_version

    # =========================================================================
    # Lifecycle State Transitions & Transactional Outbox (Milestone 4)
    # =========================================================================

    async def request_state_transition(
        self,
        feed_id: UUID,
        req: StateTransitionRequest,
        actor: AuthenticatedUser,
    ) -> FeedLifecycleCommand:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")

        current = feed.desired_state
        target = req.target_state

        current_val = current.value if hasattr(current, "value") else str(current)
        target_val = target.value if hasattr(target, "value") else str(target)

        if current_val == target_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Feed is already in desired state '{current_val}'.",
            )

        # Update desired state in M01
        feed.desired_state = target_val
        await self.repo.update_feed(feed)

        # Create transactional outbox command for M02
        command_map = {
            FeedDesiredState.ACTIVE: "START",
            FeedDesiredState.INACTIVE: "STOP",
            FeedDesiredState.PAUSED: "PAUSE",
            FeedDesiredState.DRAINING: "DRAIN",
        }
        cmd_type = command_map.get(target, "RESTART")
        idempotency_key = f"{feed_id}-{target_val}-{uuid.uuid4().hex[:8]}"

        cmd = FeedLifecycleCommand(
            feed_id=feed_id,
            command_type=cmd_type,
            parameters={"target_state": target_val, "reason": req.reason, **req.command_parameters},
            idempotency_key=idempotency_key,
            status=CommandStatus.PENDING,
        )
        outbox_cmd = await self.repo.create_lifecycle_command(cmd)

        await self._log_audit(
            actor,
            "STATE_TRANSITION_REQUEST",
            str(feed_id),
            True,
            {"from": current_val, "to": target_val, "command_id": str(outbox_cmd.id)},
        )
        await self.session.commit()
        return outbox_cmd

    # =========================================================================
    # Scheduling & Active Windows (Milestone 5)
    # =========================================================================

    async def configure_schedule(
        self,
        feed_id: UUID,
        payload: ScheduleCreate,
        actor: AuthenticatedUser,
    ) -> FeedSchedule:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")

        try:
            validate_timezone(payload.timezone)
            validate_session_intervals(payload.sessions)
        except ValidationError as err:
            await self._log_audit(actor, "CONFIGURE_SCHEDULE_VALIDATION_FAILED", str(feed_id), False, {"error": str(err)})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))

        sessions_data = [s.model_dump() for s in payload.sessions]
        schedule = FeedSchedule(
            feed_id=feed_id,
            timezone=payload.timezone,
            auto_start_stop_enabled=payload.auto_start_stop_enabled,
            sessions=sessions_data,
            polling_interval_ms=payload.polling_interval_ms,
            active_days=payload.active_days,
        )
        saved = await self.repo.upsert_schedule(schedule)
        await self._log_audit(actor, "CONFIGURE_SCHEDULE", str(feed_id), True, {"timezone": payload.timezone})
        await self.session.commit()
        return saved

    async def get_schedule(self, feed_id: UUID) -> FeedSchedule:
        sched = await self.repo.get_schedule(feed_id)
        if not sched:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not configured for this feed.")
        return sched

    # =========================================================================
    # Failover & Priority Groups (Milestone 6)
    # =========================================================================

    async def create_failover_group(
        self,
        payload: FailoverGroupCreate,
        actor: AuthenticatedUser,
    ) -> FeedFailoverGroup:
        existing = await self.repo.get_failover_group_by_name(payload.group_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Failover group '{payload.group_name}' already exists.",
            )

        group = FeedFailoverGroup(
            group_name=payload.group_name,
            description=payload.description,
            required_capabilities=payload.required_capabilities,
            failover_latency_threshold_ms=payload.failover_latency_threshold_ms,
            consecutive_error_threshold=payload.consecutive_error_threshold,
        )
        created_group = await self.repo.create_failover_group(group)

        # Attach members
        for m in payload.members:
            # Check feed exists
            feed = await self.repo.get_by_id(m.feed_id)
            if not feed:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Feed member {m.feed_id} does not exist.",
                )
            member = FeedPriorityMember(
                group_id=created_group.id,
                feed_id=m.feed_id,
                priority_rank=m.priority_rank,
                is_active_in_group=m.is_active_in_group,
                custom_weight=m.custom_weight,
            )
            await self.repo.add_priority_member(member)

        await self._log_audit(
            actor,
            "CREATE_FAILOVER_GROUP",
            str(created_group.id),
            True,
            {"group_name": payload.group_name, "members_count": len(payload.members)},
        )
        await self.session.commit()
        return await self.repo.get_failover_group(created_group.id)

    async def list_failover_groups(self) -> List[FeedFailoverGroup]:
        return await self.repo.list_failover_groups()

    # =========================================================================
    # Health & Monitoring Sinks (Milestone 7)
    # =========================================================================

    async def ingest_health_report(
        self,
        feed_id: UUID,
        report: HealthEventReport,
        actor: AuthenticatedUser,
    ) -> FeedHealthEvent:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")

        event = FeedHealthEvent(
            feed_id=feed_id,
            runtime_state=report.runtime_state,
            latency_ms=report.latency_ms,
            messages_received_delta=report.messages_received_delta,
            bytes_received_delta=report.bytes_received_delta,
            error_count_delta=report.error_count_delta,
            last_heartbeat_timestamp=report.last_heartbeat_timestamp,
            last_data_timestamp=report.last_data_timestamp,
            error_code=report.error_code,
            error_details=report.error_details,
        )
        recorded = await self.repo.record_health_event(event)
        await self.session.commit()
        return recorded

    async def get_feed_health_summary(self, feed_id: UUID) -> FeedHealthSummary:
        feed = await self.repo.get_by_id(feed_id)
        if not feed or feed.record_status == FeedRecordStatus.DELETED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found.")

        latest = await self.repo.get_latest_health_event(feed_id)
        recent_events = await self.repo.get_recent_health_events(feed_id, limit=20)
        total_errors = sum(e.error_count_delta for e in recent_events)

        is_healthy = False
        if latest:
            rt_state = latest.runtime_state.value if hasattr(latest.runtime_state, "value") else str(latest.runtime_state)
            is_healthy = (
                rt_state == "CONNECTED"
                and (latest.latency_ms is None or latest.latency_ms < 1000.0)
                and total_errors == 0
            )

        latest_rt = latest.runtime_state if latest else None
        if latest_rt and hasattr(latest_rt, "value"):
            latest_rt = latest_rt.value

        return FeedHealthSummary(
            feed_id=feed.id,
            feed_code=feed.feed_code,
            desired_state=feed.desired_state,
            latest_runtime_state=latest_rt,
            last_heartbeat_timestamp=latest.last_heartbeat_timestamp if latest else None,
            last_data_timestamp=latest.last_data_timestamp if latest else None,
            current_latency_ms=latest.latency_ms if latest else None,
            total_errors_recorded=total_errors,
            is_healthy=is_healthy,
        )

    # =========================================================================
    # Audit Logs (Milestone 8)
    # =========================================================================

    async def list_audit_logs(self, feed_id: Optional[UUID] = None, limit: int = 100) -> List[FeedAuditLog]:
        return await self.repo.list_audit_logs(feed_id=feed_id, limit=limit)
