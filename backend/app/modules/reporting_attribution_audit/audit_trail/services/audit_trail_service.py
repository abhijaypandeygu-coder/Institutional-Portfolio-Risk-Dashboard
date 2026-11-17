"""Centralized Audit Trail Service for M14.07.

Handles durable append-only event ingestion, cryptographic SHA-256 hash chaining,
correlation timelines, configuration before-and-after diffs, and integrity verification.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from fastapi import HTTPException

from backend.app.modules.reporting_attribution_audit.audit_trail.models.audit_models import (
    AuditEvent,
    AuditConfigurationChange,
    AuditApprovalEvent,
    AuditChainCheckpoint,
    AuditIntegrityRun,
    AuditRetentionPolicy,
    ActorType,
    EventCategory,
    EventSeverity,
    EventOutcome,
    IntegrityVerificationStatus,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.schemas.audit_schemas import (
    AuditEventCreateRequest,
    AuditEventResponse,
    AuditConfigurationChangeResponse,
    AuditApprovalResponse,
    AuditSearchResponse,
    AuditIntegrityRunResponse,
    AuditCheckpointResponse,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.integrity.hasher import (
    CanonicalEventSerializer,
)


class AuditTrailService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_audit_event(self, request: AuditEventCreateRequest) -> AuditEventResponse:
        """Durable append-only ingestion with cryptographic hash chaining."""
        now_utc = datetime.now(timezone.utc)
        occurred_time = request.occurred_at or now_utc

        # 1. Fetch latest event in GLOBAL_CHAIN to get previous hash and sequence
        chain_id = "GLOBAL_CHAIN"
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.chain_id == chain_id)
            .order_by(desc(AuditEvent.chain_sequence))
        )
        res = await self.db.execute(stmt)
        latest_event = res.scalars().first()

        next_sequence = (latest_event.chain_sequence + 1) if latest_event else 1
        previous_hash = latest_event.integrity_hash if latest_event else "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000"

        event_id = f"EVT-{request.source_module}-{now_utc.strftime('%Y%m%d%H%M%S')}-{next_sequence:06d}"

        # 2. Build canonical representation for cryptographic hash
        canonical_event_data = {
            "event_id": event_id,
            "event_type": request.event_type,
            "event_category": request.event_category.value,
            "severity": request.severity.value,
            "actor_type": request.actor.type.value,
            "actor_id": request.actor.id,
            "source_module": request.source_module,
            "target_type": request.target_type,
            "target_id": request.target_id,
            "action": request.action,
            "outcome": request.outcome.value,
            "occurred_at": occurred_time,
            "chain_sequence": next_sequence,
            "payload": request.payload or {},
        }
        canonical_str = CanonicalEventSerializer.canonicalize(canonical_event_data)
        integrity_hash = CanonicalEventSerializer.compute_event_hash(canonical_str, previous_hash)

        # 3. Create persistent AuditEvent record
        event = AuditEvent(
            event_id=event_id,
            event_type=request.event_type,
            event_category=request.event_category,
            severity=request.severity,
            actor_type=request.actor.type,
            actor_id=request.actor.id,
            actor_role=request.actor.role,
            source_module=request.source_module,
            source_feature=request.source_feature,
            target_type=request.target_type,
            target_id=request.target_id,
            action=request.action,
            outcome=request.outcome,
            reason=request.reason,
            occurred_at=occurred_time,
            recorded_at=now_utc,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
            parent_event_id=request.parent_event_id,
            payload=request.payload,
            schema_version="v1.0",
            chain_id=chain_id,
            chain_sequence=next_sequence,
            integrity_hash=integrity_hash,
            previous_hash=previous_hash,
            verification_status=IntegrityVerificationStatus.VERIFIED,
        )
        self.db.add(event)
        await self.db.flush()

        # 4. Optional Configuration Change Record
        cfg_resp = None
        if request.configuration_change:
            cc = request.configuration_change
            cfg_db = AuditConfigurationChange(
                event_id=event_id,
                configuration_id=cc.configuration_id,
                configuration_type=cc.configuration_type,
                owning_module=cc.owning_module,
                previous_version=cc.previous_version,
                new_version=cc.new_version,
                effective_at=cc.effective_at,
                recorded_at=now_utc,
                changed_fields=cc.changed_fields,
                old_values_redacted=cc.old_values_redacted,
                new_values_redacted=cc.new_values_redacted,
                reason=cc.reason or request.reason,
                approval_reference=cc.approval_reference,
            )
            self.db.add(cfg_db)
            cfg_resp = AuditConfigurationChangeResponse(
                configuration_id=cfg_db.configuration_id,
                configuration_type=cfg_db.configuration_type,
                owning_module=cfg_db.owning_module,
                previous_version=cfg_db.previous_version,
                new_version=cfg_db.new_version,
                effective_at=cfg_db.effective_at,
                recorded_at=cfg_db.recorded_at,
                changed_fields=cfg_db.changed_fields,
                old_values_redacted=cfg_db.old_values_redacted,
                new_values_redacted=cfg_db.new_values_redacted,
                reason=cfg_db.reason,
                approval_reference=cfg_db.approval_reference,
            )

        # 5. Optional Approval Details Record
        app_resp = None
        if request.approval_details:
            ad = request.approval_details
            app_db = AuditApprovalEvent(
                event_id=event_id,
                approval_id=ad.approval_id,
                target_type=ad.target_type,
                target_id=ad.target_id,
                requesting_actor_id=ad.requesting_actor_id,
                approving_actor_id=ad.approving_actor_id,
                decision=ad.decision,
                reason=ad.reason or request.reason,
                policy_version=ad.policy_version,
                approval_timestamp=now_utc,
            )
            self.db.add(app_db)
            app_resp = AuditApprovalResponse(
                approval_id=app_db.approval_id,
                target_type=app_db.target_type,
                target_id=app_db.target_id,
                requesting_actor_id=app_db.requesting_actor_id,
                approving_actor_id=app_db.approving_actor_id,
                decision=app_db.decision,
                reason=app_db.reason,
                policy_version=app_db.policy_version,
                approval_timestamp=app_db.approval_timestamp,
            )

        await self.db.commit()

        return AuditEventResponse(
            id=event.id,
            event_id=event.event_id,
            event_type=event.event_type,
            event_category=event.event_category,
            severity=event.severity,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            actor_role=event.actor_role,
            source_module=event.source_module,
            source_feature=event.source_feature,
            target_type=event.target_type,
            target_id=event.target_id,
            action=event.action,
            outcome=event.outcome,
            reason=event.reason,
            occurred_at=event.occurred_at,
            recorded_at=event.recorded_at,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            parent_event_id=event.parent_event_id,
            payload=event.payload,
            schema_version=event.schema_version,
            chain_id=event.chain_id,
            chain_sequence=event.chain_sequence,
            integrity_hash=event.integrity_hash,
            previous_hash=event.previous_hash,
            verification_status=event.verification_status,
            configuration_change=cfg_resp,
            approval_details=app_resp,
        )

    async def search_events(
        self,
        event_category: Optional[EventCategory] = None,
        source_module: Optional[str] = None,
        target_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> AuditSearchResponse:
        """Search and filter authorized audit records."""
        stmt = select(AuditEvent)
        if event_category:
            stmt = stmt.where(AuditEvent.event_category == event_category)
        if source_module:
            stmt = stmt.where(AuditEvent.source_module == source_module)
        if target_id:
            stmt = stmt.where(AuditEvent.target_id == target_id)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if correlation_id:
            stmt = stmt.where(AuditEvent.correlation_id == correlation_id)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.db.execute(count_stmt)
        total_count = count_res.scalar() or 0

        # Paginated fetch
        stmt = stmt.order_by(desc(AuditEvent.chain_sequence)).offset((page - 1) * page_size).limit(page_size)
        res = await self.db.execute(stmt)
        events = res.scalars().all()

        items = []
        for e in events:
            # Load config change
            cc_stmt = select(AuditConfigurationChange).where(AuditConfigurationChange.event_id == e.event_id)
            cc_res = await self.db.execute(cc_stmt)
            cc = cc_res.scalars().first()
            cfg_resp = (
                AuditConfigurationChangeResponse(
                    configuration_id=cc.configuration_id,
                    configuration_type=cc.configuration_type,
                    owning_module=cc.owning_module,
                    previous_version=cc.previous_version,
                    new_version=cc.new_version,
                    effective_at=cc.effective_at,
                    recorded_at=cc.recorded_at,
                    changed_fields=cc.changed_fields,
                    old_values_redacted=cc.old_values_redacted,
                    new_values_redacted=cc.new_values_redacted,
                    reason=cc.reason,
                    approval_reference=cc.approval_reference,
                )
                if cc
                else None
            )

            items.append(
                AuditEventResponse(
                    id=e.id,
                    event_id=e.event_id,
                    event_type=e.event_type,
                    event_category=e.event_category,
                    severity=e.severity,
                    actor_type=e.actor_type,
                    actor_id=e.actor_id,
                    actor_role=e.actor_role,
                    source_module=e.source_module,
                    source_feature=e.source_feature,
                    target_type=e.target_type,
                    target_id=e.target_id,
                    action=e.action,
                    outcome=e.outcome,
                    reason=e.reason,
                    occurred_at=e.occurred_at,
                    recorded_at=e.recorded_at,
                    correlation_id=e.correlation_id,
                    causation_id=e.causation_id,
                    parent_event_id=e.parent_event_id,
                    payload=e.payload,
                    schema_version=e.schema_version,
                    chain_id=e.chain_id,
                    chain_sequence=e.chain_sequence,
                    integrity_hash=e.integrity_hash,
                    previous_hash=e.previous_hash,
                    verification_status=e.verification_status,
                    configuration_change=cfg_resp,
                )
            )

        return AuditSearchResponse(
            items=items,
            total=total_count,
            page=page,
            page_size=page_size,
        )

    async def get_timeline(self, correlation_id: str) -> List[AuditEventResponse]:
        """Retrieve chronological cross-module event timeline for an incident or workflow."""
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.correlation_id == correlation_id)
            .order_by(AuditEvent.occurred_at.asc(), AuditEvent.chain_sequence.asc())
        )
        res = await self.db.execute(stmt)
        events = res.scalars().all()
        return [
            AuditEventResponse(
                id=e.id,
                event_id=e.event_id,
                event_type=e.event_type,
                event_category=e.event_category,
                severity=e.severity,
                actor_type=e.actor_type,
                actor_id=e.actor_id,
                actor_role=e.actor_role,
                source_module=e.source_module,
                source_feature=e.source_feature,
                target_type=e.target_type,
                target_id=e.target_id,
                action=e.action,
                outcome=e.outcome,
                reason=e.reason,
                occurred_at=e.occurred_at,
                recorded_at=e.recorded_at,
                correlation_id=e.correlation_id,
                causation_id=e.causation_id,
                parent_event_id=e.parent_event_id,
                payload=e.payload,
                schema_version=e.schema_version,
                chain_id=e.chain_id,
                chain_sequence=e.chain_sequence,
                integrity_hash=e.integrity_hash,
                previous_hash=e.previous_hash,
                verification_status=e.verification_status,
            )
            for e in events
        ]

    async def verify_chain_integrity(self, chain_id: str = "GLOBAL_CHAIN") -> AuditIntegrityRunResponse:
        """Verify entire cryptographic hash chain continuity and payload integrity."""
        now_utc = datetime.now(timezone.utc)
        stmt = select(AuditEvent).where(AuditEvent.chain_id == chain_id).order_by(AuditEvent.chain_sequence.asc())
        res = await self.db.execute(stmt)
        events = res.scalars().all()

        mismatch_count = 0
        missing_count = 0
        expected_seq = 1
        expected_prev_hash = "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000"

        for e in events:
            # Check sequence continuity
            if e.chain_sequence != expected_seq:
                missing_count += 1

            # Check previous hash
            if e.previous_hash != expected_prev_hash:
                mismatch_count += 1

            # Recompute expected hash
            canonical_data = {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "event_category": e.event_category.value,
                "severity": e.severity.value,
                "actor_type": e.actor_type.value,
                "actor_id": e.actor_id,
                "source_module": e.source_module,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "action": e.action,
                "outcome": e.outcome.value,
                "occurred_at": e.occurred_at,
                "chain_sequence": e.chain_sequence,
                "payload": e.payload or {},
            }
            canonical_str = CanonicalEventSerializer.canonicalize(canonical_data)
            recomputed_hash = CanonicalEventSerializer.compute_event_hash(canonical_str, e.previous_hash)

            if recomputed_hash != e.integrity_hash:
                mismatch_count += 1

            expected_seq = e.chain_sequence + 1
            expected_prev_hash = e.integrity_hash

        status = IntegrityVerificationStatus.VERIFIED if (mismatch_count == 0 and missing_count == 0) else IntegrityVerificationStatus.VERIFICATION_FAILED
        summary = f"Chain verification complete: {len(events)} events checked. Mismatches: {mismatch_count}, Missing sequences: {missing_count}."

        run = AuditIntegrityRun(
            chain_id=chain_id,
            verification_scope="FULL_CHAIN",
            start_sequence=1,
            end_sequence=len(events),
            verification_status=status,
            events_checked=len(events),
            mismatch_count=mismatch_count,
            missing_sequence_count=missing_count,
            started_at=now_utc,
            completed_at=datetime.now(timezone.utc),
            result_summary=summary,
        )
        self.db.add(run)

        # Create periodic checkpoint
        if len(events) > 0 and status == IntegrityVerificationStatus.VERIFIED:
            last_event = events[-1]
            cp = AuditChainCheckpoint(
                chain_id=chain_id,
                highest_sequence=last_event.chain_sequence,
                checkpoint_hash=last_event.integrity_hash,
                hash_algorithm="SHA-256",
                checkpoint_version="v1.0",
                event_count=len(events),
                verification_status=IntegrityVerificationStatus.VERIFIED,
            )
            self.db.add(cp)

        await self.db.commit()

        return AuditIntegrityRunResponse(
            run_id=run.id,
            chain_id=chain_id,
            verification_status=status,
            events_checked=len(events),
            mismatch_count=mismatch_count,
            missing_sequence_count=missing_count,
            started_at=run.started_at,
            completed_at=run.completed_at,
            result_summary=summary,
        )
