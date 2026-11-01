"""
Repositories for M03.08 Exception Management entities.
Provides atomic transactions, indexed lookups, and audit event logging.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.exception_management.models import (
    ExceptionRecord,
    ExceptionObservation,
    ExceptionFinding,
    QuarantineRecord,
    RejectionRecord,
    CorrectionProposal,
    CorrectionFieldChange,
    CorrectionApproval,
    ReplayRequest,
    ReplayRecordResult,
    ExceptionNote,
    ExceptionAuditEvent,
    ExceptionReasonCode,
    ExceptionPolicy,
    compute_payload_hash,
)
from backend.app.modules.market_data_quality.exception_management.state_machine.transitions import (
    WorkflowStatus,
    RecordDisposition,
    ApprovalStatus,
    ReplayStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExceptionRepository:
    """Repository handling database operations for Exception Management."""

    @staticmethod
    async def create_audit_event(
        session: AsyncSession,
        exception_id: str,
        action_type: str,
        new_state: str,
        actor_id: str,
        reason: str,
        previous_state: Optional[str] = None,
        observation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExceptionAuditEvent:
        """Appends an immutable audit event."""
        event = ExceptionAuditEvent(
            exception_id=exception_id,
            observation_id=observation_id,
            action_type=action_type,
            previous_state=previous_state,
            new_state=new_state,
            actor_id=actor_id,
            reason=reason,
            correlation_id=correlation_id,
            metadata_snapshot=metadata,
        )
        session.add(event)
        return event

    @staticmethod
    async def get_or_create_reason_codes(session: AsyncSession, codes: List[Dict[str, Any]]):
        """Ensures default reason codes are present in database."""
        for c in codes:
            stmt = select(ExceptionReasonCode).where(ExceptionReasonCode.code == c["code"])
            existing = (await session.execute(stmt)).scalars().first()
            if not existing:
                new_code = ExceptionReasonCode(**c)
                session.add(new_code)
        await session.flush()

    @staticmethod
    async def get_by_correlation_key(
        session: AsyncSession, correlation_key: str
    ) -> Optional[ExceptionRecord]:
        stmt = select(ExceptionRecord).where(ExceptionRecord.correlation_key == correlation_key)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_by_id(
        session: AsyncSession, exception_id: str
    ) -> Optional[ExceptionRecord]:
        stmt = select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_exceptions(
        session: AsyncSession,
        workflow_status: Optional[str] = None,
        severity: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ExceptionRecord]:
        stmt = select(ExceptionRecord).order_by(desc(ExceptionRecord.created_at))
        if workflow_status:
            stmt = stmt.where(ExceptionRecord.workflow_status == workflow_status)
        if severity:
            stmt = stmt.where(ExceptionRecord.severity == severity)
        if priority:
            stmt = stmt.where(ExceptionRecord.priority == priority)
        if assigned_user_id:
            stmt = stmt.where(ExceptionRecord.assigned_user_id == assigned_user_id)
        stmt = stmt.limit(limit).offset(offset)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_observations_for_exception(
        session: AsyncSession, exception_id: str
    ) -> List[ExceptionObservation]:
        stmt = select(ExceptionObservation).where(ExceptionObservation.exception_id == exception_id)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_findings_for_exception(
        session: AsyncSession, exception_id: str
    ) -> List[ExceptionFinding]:
        stmt = select(ExceptionFinding).where(ExceptionFinding.exception_id == exception_id)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_audit_trail(
        session: AsyncSession, exception_id: str
    ) -> List[ExceptionAuditEvent]:
        stmt = select(ExceptionAuditEvent).where(
            ExceptionAuditEvent.exception_id == exception_id
        ).order_by(ExceptionAuditEvent.created_at.asc())
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_notes(
        session: AsyncSession, exception_id: str
    ) -> List[ExceptionNote]:
        stmt = select(ExceptionNote).where(
            ExceptionNote.exception_id == exception_id
        ).order_by(ExceptionNote.created_at.asc())
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_quarantine_by_id(
        session: AsyncSession, quarantine_id: str
    ) -> Optional[QuarantineRecord]:
        stmt = select(QuarantineRecord).where(QuarantineRecord.quarantine_id == quarantine_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_quarantines(
        session: AsyncSession, release_status: Optional[str] = None, limit: int = 50
    ) -> List[QuarantineRecord]:
        stmt = select(QuarantineRecord).order_by(desc(QuarantineRecord.quarantined_at))
        if release_status:
            stmt = stmt.where(QuarantineRecord.release_status == release_status)
        stmt = stmt.limit(limit)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_rejection_by_id(
        session: AsyncSession, rejection_id: str
    ) -> Optional[RejectionRecord]:
        stmt = select(RejectionRecord).where(RejectionRecord.rejection_id == rejection_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_rejections(
        session: AsyncSession, limit: int = 50
    ) -> List[RejectionRecord]:
        stmt = select(RejectionRecord).order_by(desc(RejectionRecord.rejected_at)).limit(limit)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_correction_by_id(
        session: AsyncSession, correction_id: str
    ) -> Optional[CorrectionProposal]:
        stmt = select(CorrectionProposal).where(CorrectionProposal.correction_id == correction_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_corrections(
        session: AsyncSession, exception_id: str
    ) -> List[CorrectionProposal]:
        stmt = select(CorrectionProposal).where(
            CorrectionProposal.exception_id == exception_id
        ).order_by(CorrectionProposal.correction_version.asc())
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_replay_by_id(
        session: AsyncSession, replay_id: str
    ) -> Optional[ReplayRequest]:
        stmt = select(ReplayRequest).where(ReplayRequest.replay_id == replay_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_replay_by_idempotency_key(
        session: AsyncSession, idempotency_key: str
    ) -> Optional[ReplayRequest]:
        stmt = select(ReplayRequest).where(ReplayRequest.idempotency_key == idempotency_key)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_replays(
        session: AsyncSession, exception_id: Optional[str] = None, limit: int = 50
    ) -> List[ReplayRequest]:
        stmt = select(ReplayRequest).order_by(desc(ReplayRequest.requested_at))
        if exception_id:
            stmt = stmt.where(ReplayRequest.exception_id == exception_id)
        stmt = stmt.limit(limit)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_replay_results(
        session: AsyncSession, replay_id: str
    ) -> List[ReplayRecordResult]:
        stmt = select(ReplayRecordResult).where(ReplayRecordResult.replay_id == replay_id)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_metrics_summary(session: AsyncSession) -> Dict[str, int]:
        total_exc = (await session.execute(select(func.count(ExceptionRecord.id)))).scalar() or 0
        open_exc = (await session.execute(select(func.count(ExceptionRecord.id)).where(ExceptionRecord.workflow_status == WorkflowStatus.OPEN.value))).scalar() or 0
        in_review = (await session.execute(select(func.count(ExceptionRecord.id)).where(ExceptionRecord.workflow_status == WorkflowStatus.IN_REVIEW.value))).scalar() or 0
        awaiting_app = (await session.execute(select(func.count(ExceptionRecord.id)).where(ExceptionRecord.workflow_status == WorkflowStatus.AWAITING_APPROVAL.value))).scalar() or 0
        resolved = (await session.execute(select(func.count(ExceptionRecord.id)).where(ExceptionRecord.workflow_status == WorkflowStatus.RESOLVED.value))).scalar() or 0
        
        quarantined = (await session.execute(select(func.count(QuarantineRecord.id)).where(QuarantineRecord.release_status == "QUARANTINED"))).scalar() or 0
        rejected = (await session.execute(select(func.count(RejectionRecord.id)))).scalar() or 0
        
        total_rpl = (await session.execute(select(func.count(ReplayRequest.id)))).scalar() or 0
        succeeded_rpl = (await session.execute(select(func.count(ReplayRequest.id)).where(ReplayRequest.replay_status == ReplayStatus.SUCCEEDED.value))).scalar() or 0
        failed_rpl = (await session.execute(select(func.count(ReplayRequest.id)).where(ReplayRequest.replay_status == ReplayStatus.FAILED.value))).scalar() or 0

        return {
            "total_exceptions": total_exc,
            "open_exceptions": open_exc,
            "in_review_exceptions": in_review,
            "awaiting_approval_exceptions": awaiting_app,
            "resolved_exceptions": resolved,
            "quarantined_records": quarantined,
            "rejected_records": rejected,
            "total_replays": total_rpl,
            "successful_replays": succeeded_rpl,
            "failed_replays": failed_rpl,
        }
