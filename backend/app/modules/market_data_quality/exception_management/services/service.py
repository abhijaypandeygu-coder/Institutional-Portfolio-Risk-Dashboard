"""
Core Business Services for M03.08 Exception Management.
Implements Feature Groups 1 to 8:
- Intake & Registration with Deduplication & Grouping
- Quarantine Management & Preservation
- Rejection Management & Reason Codes
- Controlled Correction Workflows & Separation of Duties
- Replay Management & Idempotency
- State Machine Workflow & Dispositions
"""
import uuid
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

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
    compute_payload_hash,
)
from backend.app.modules.market_data_quality.exception_management.schemas import (
    FindingIntakeSchema,
    ExceptionCreateRequest,
    QuarantineCreateRequest,
    QuarantineReleaseRequest,
    RejectionCreateRequest,
    CorrectionProposalCreate,
    CorrectionApprovalRequest,
    CorrectionRejectRequest,
    ReplaySubmitRequest,
)
from backend.app.modules.market_data_quality.exception_management.repositories.repository import (
    ExceptionRepository,
    utc_now,
)
from backend.app.modules.market_data_quality.exception_management.state_machine.transitions import (
    WorkflowStatus,
    RecordDisposition,
    ApprovalStatus,
    ReplayStatus,
    validate_workflow_transition,
    validate_disposition_transition,
)
from backend.app.modules.market_data_quality.exception_management.integrations.clients import (
    IngestionQuarantineClient,
    IngestionReplayClient,
    QualityResultClient,
)


class ExceptionManagementService:
    """Orchestrates exception lifecycle, quarantine, correction, and replay."""

    # ---------------------------------------------------------
    # FEATURE GROUP 1: INTAKE & REGISTRATION
    # ---------------------------------------------------------
    @classmethod
    async def register_exception(
        cls,
        session: AsyncSession,
        req: ExceptionCreateRequest,
        actor_id: str = "system",
    ) -> ExceptionRecord:
        """
        Idempotently registers an exception with upstream findings and affected observations.
        Uses deterministic correlation key based on findings to prevent duplication.
        """
        if not req.findings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exception creation requires at least one upstream validation finding.",
            )

        # Build deterministic correlation key across findings
        sorted_finding_ids = sorted([f.finding_id for f in req.findings])
        feed_ids = sorted(list(set([f.feed_id for f in req.findings])))
        corr_seed = f"{feed_ids[0]}:{req.exception_type}:{':'.join(sorted_finding_ids)}"
        correlation_key = hashlib.sha256(corr_seed.encode("utf-8")).hexdigest()[:32]

        # Check existing exception with this correlation key
        existing = await ExceptionRepository.get_by_correlation_key(session, correlation_key)
        if existing:
            # Idempotent response - update timestamp and return
            existing.updated_at = utc_now()
            return existing

        exc_ref = f"EXC-REF-{uuid.uuid4().hex[:8].upper()}"
        exc_id = f"EXC_{uuid.uuid4().hex[:12].upper()}"

        record = ExceptionRecord(
            exception_id=exc_id,
            exception_reference=exc_ref,
            category=req.category,
            exception_type=req.exception_type,
            severity=req.severity,
            priority=req.priority,
            workflow_status=WorkflowStatus.OPEN.value,
            summary=req.summary,
            description=req.description,
            creation_source=req.creation_source,
            correlation_key=correlation_key,
            policy_version="1.0.0",
        )
        session.add(record)
        await session.flush()

        # Link findings and observations
        seen_observations = set()
        for finding in req.findings:
            f_link = ExceptionFinding(
                exception_id=exc_id,
                source_module=finding.source_module,
                source_feature=finding.source_feature,
                finding_id=finding.finding_id,
                finding_code=finding.finding_code,
                source_severity=finding.source_severity,
                finding_reference=finding.rule_reference,
                evidence=finding.evidence,
            )
            session.add(f_link)

            if finding.observation_id not in seen_observations:
                seen_observations.add(finding.observation_id)
                p_hash = compute_payload_hash(finding.raw_payload or {})
                obs_link = ExceptionObservation(
                    exception_id=exc_id,
                    observation_id=finding.observation_id,
                    feed_id=finding.feed_id,
                    instrument_id=finding.instrument_id,
                    listing_id=finding.listing_id,
                    exchange=finding.exchange or "NSE",
                    data_origin=finding.data_origin,
                    payload_snapshot=finding.raw_payload,
                    payload_hash=p_hash,
                    record_disposition=RecordDisposition.QUARANTINED.value,
                    source_event_timestamp=finding.source_event_timestamp,
                    ingestion_timestamp=finding.ingestion_timestamp or utc_now(),
                )
                session.add(obs_link)

                # Automatically isolate into quarantine records
                qrn = QuarantineRecord(
                    exception_id=exc_id,
                    observation_id=finding.observation_id,
                    quarantine_reason_code=finding.finding_code,
                    quarantine_reason=f"Quarantined by automated validation finding: {finding.finding_code}",
                    quarantined_by=actor_id,
                    payload_snapshot=finding.raw_payload,
                    payload_hash=p_hash,
                    release_status="QUARANTINED",
                )
                session.add(qrn)

                # Request M02 isolation
                await IngestionQuarantineClient.request_observation_quarantine(
                    finding.observation_id, finding.feed_id, finding.finding_code
                )

        # Audit event
        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exc_id,
            action_type="EXCEPTION_CREATED",
            new_state=WorkflowStatus.OPEN.value,
            actor_id=actor_id,
            reason="Automated validation finding intake",
            correlation_id=correlation_key,
            metadata={"findings_count": len(req.findings), "observations_count": len(seen_observations)},
        )

        await session.commit()
        return record

    # ---------------------------------------------------------
    # FEATURE GROUP 2: QUARANTINE MANAGEMENT
    # ---------------------------------------------------------
    @classmethod
    async def quarantine_observation(
        cls,
        session: AsyncSession,
        exception_id: str,
        req: QuarantineCreateRequest,
        actor_id: str,
    ) -> QuarantineRecord:
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Exception {exception_id} not found.")

        p_hash = compute_payload_hash(req.payload_snapshot or {})
        qrn = QuarantineRecord(
            exception_id=exception_id,
            observation_id=req.observation_id,
            quarantine_reason_code=req.quarantine_reason_code,
            quarantine_reason=req.quarantine_reason,
            quarantined_by=actor_id,
            original_payload_reference=req.original_payload_reference,
            payload_snapshot=req.payload_snapshot,
            payload_hash=p_hash,
            release_status="QUARANTINED",
        )
        session.add(qrn)

        # Update observation disposition
        stmt = (
            update(ExceptionObservation)
            .where(
                ExceptionObservation.exception_id == exception_id,
                ExceptionObservation.observation_id == req.observation_id,
            )
            .values(record_disposition=RecordDisposition.QUARANTINED.value)
        )
        await session.execute(stmt)

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exception_id,
            observation_id=req.observation_id,
            action_type="OBSERVATION_QUARANTINED",
            new_state=RecordDisposition.QUARANTINED.value,
            actor_id=actor_id,
            reason=req.quarantine_reason,
        )
        await session.commit()
        return qrn

    @classmethod
    async def release_quarantine(
        cls,
        session: AsyncSession,
        quarantine_id: str,
        req: QuarantineReleaseRequest,
        actor_id: str,
    ) -> QuarantineRecord:
        qrn = await ExceptionRepository.get_quarantine_by_id(session, quarantine_id)
        if not qrn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quarantine record not found.")

        if qrn.release_status == "RELEASED":
            return qrn

        qrn.release_status = "RELEASED"
        qrn.released_at = utc_now()
        qrn.released_by = actor_id
        qrn.release_authorization_reference = req.release_authorization_reference

        # Notify M02
        await IngestionQuarantineClient.request_observation_release(
            qrn.observation_id, req.release_authorization_reference
        )

        # Update observation disposition
        stmt = (
            update(ExceptionObservation)
            .where(
                ExceptionObservation.exception_id == qrn.exception_id,
                ExceptionObservation.observation_id == qrn.observation_id,
            )
            .values(record_disposition=RecordDisposition.RELEASED.value)
        )
        await session.execute(stmt)

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=qrn.exception_id,
            observation_id=qrn.observation_id,
            action_type="QUARANTINE_RELEASED",
            previous_state="QUARANTINED",
            new_state="RELEASED",
            actor_id=actor_id,
            reason=req.justification,
        )
        await session.commit()
        return qrn

    # ---------------------------------------------------------
    # FEATURE GROUP 3: REJECTION MANAGEMENT
    # ---------------------------------------------------------
    @classmethod
    async def reject_observation(
        cls,
        session: AsyncSession,
        exception_id: str,
        req: RejectionCreateRequest,
        actor_id: str,
    ) -> RejectionRecord:
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Exception {exception_id} not found.")

        # Find observation
        obs_stmt = select(ExceptionObservation).where(
            ExceptionObservation.exception_id == exception_id,
            ExceptionObservation.observation_id == req.observation_id,
        )
        obs = (await session.execute(obs_stmt)).scalars().first()
        p_hash = obs.payload_hash if obs else "UNKNOWN_HASH"

        rej = RejectionRecord(
            exception_id=exception_id,
            observation_id=req.observation_id,
            reason_code=req.reason_code,
            reason_details=req.reason_details,
            recoverability=req.recoverability,
            rejected_by=actor_id,
            policy_reference=req.policy_reference,
            original_payload_hash=p_hash,
        )
        session.add(rej)

        if obs:
            obs.record_disposition = RecordDisposition.REJECTED.value

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exception_id,
            observation_id=req.observation_id,
            action_type="OBSERVATION_REJECTED",
            new_state=RecordDisposition.REJECTED.value,
            actor_id=actor_id,
            reason=f"Code: {req.reason_code} - {req.reason_details}",
        )
        await session.commit()
        return rej

    # ---------------------------------------------------------
    # FEATURE GROUP 4: CONTROLLED CORRECTION WORKFLOWS
    # ---------------------------------------------------------
    @classmethod
    async def create_correction_proposal(
        cls,
        session: AsyncSession,
        exception_id: str,
        req: CorrectionProposalCreate,
        actor_id: str,
    ) -> CorrectionProposal:
        """Proposes a controlled, auditable correction. Enforces provenance integrity."""
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Exception {exception_id} not found.")

        # Check observation provenance: Synthetic test simulator observations CANNOT correct real observations
        obs_stmt = select(ExceptionObservation).where(
            ExceptionObservation.exception_id == exception_id,
            ExceptionObservation.observation_id == req.observation_id,
        )
        obs = (await session.execute(obs_stmt)).scalars().first()
        if obs and obs.data_origin == "REAL" and req.provenance_source == "SYNTHETIC_SIM":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Synthetic simulator data cannot be used as authoritative evidence to repair real market observations.",
            )

        # Get existing versions
        existing_corrections = await ExceptionRepository.list_corrections(session, exception_id)
        next_version = len([c for c in existing_corrections if c.observation_id == req.observation_id]) + 1

        cor_id = f"COR_{uuid.uuid4().hex[:12].upper()}"
        proposal = CorrectionProposal(
            correction_id=cor_id,
            exception_id=exception_id,
            observation_id=req.observation_id,
            correction_version=next_version,
            correction_category=req.correction_category,
            correction_reason=req.correction_reason,
            proposed_by=actor_id,
            approval_status=ApprovalStatus.PENDING.value,
            correction_status="PROPOSED",
            resulting_payload_snapshot=req.resulting_payload_snapshot,
            provenance_reference=req.provenance_reference,
            provenance_source=req.provenance_source,
        )
        session.add(proposal)
        await session.flush()

        # Add field changes (preserves financial precision as strings)
        for fc in req.field_changes:
            change = CorrectionFieldChange(
                correction_id=cor_id,
                field_name=fc.field_name,
                before_value=str(fc.before_value),
                after_value=str(fc.after_value),
                field_data_type=fc.field_data_type,
                change_reason=fc.change_reason,
                provenance_reference=fc.provenance_reference or req.provenance_reference,
            )
            session.add(change)

        # Transition exception workflow status if valid
        if validate_workflow_transition(WorkflowStatus(exc.workflow_status), WorkflowStatus.AWAITING_APPROVAL):
            exc.workflow_status = WorkflowStatus.AWAITING_APPROVAL.value

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exception_id,
            observation_id=req.observation_id,
            action_type="CORRECTION_PROPOSED",
            new_state=ApprovalStatus.PENDING.value,
            actor_id=actor_id,
            reason=f"Version {next_version} proposed: {req.correction_reason}",
        )
        await session.commit()
        return proposal

    @classmethod
    async def approve_correction(
        cls,
        session: AsyncSession,
        correction_id: str,
        req: CorrectionApprovalRequest,
        approver_id: str,
    ) -> CorrectionProposal:
        """Approves a proposed correction. Enforces separation of duties."""
        prop = await ExceptionRepository.get_correction_by_id(session, correction_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction proposal not found.")

        # SEPARATION OF DUTIES: Proposer cannot approve their own correction
        if prop.proposed_by == approver_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Separation of duties violation: Proposer '{prop.proposed_by}' cannot approve their own correction.",
            )

        if prop.approval_status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Correction proposal is not pending approval (current: {prop.approval_status}).",
            )

        prop.approval_status = ApprovalStatus.APPROVED.value
        prop.correction_status = "APPROVED"

        # Record approval decision
        approval = CorrectionApproval(
            correction_id=correction_id,
            approval_status=ApprovalStatus.APPROVED.value,
            approver_id=approver_id,
            approval_reason=req.approval_reason,
            policy_reference=req.policy_reference,
        )
        session.add(approval)

        # Update exception workflow
        exc = await ExceptionRepository.get_by_id(session, prop.exception_id)
        if exc and validate_workflow_transition(WorkflowStatus(exc.workflow_status), WorkflowStatus.APPROVED):
            exc.workflow_status = WorkflowStatus.APPROVED.value

        # Update observation disposition to READY_FOR_REPLAY
        stmt = (
            update(ExceptionObservation)
            .where(
                ExceptionObservation.exception_id == prop.exception_id,
                ExceptionObservation.observation_id == prop.observation_id,
            )
            .values(record_disposition=RecordDisposition.READY_FOR_REPLAY.value)
        )
        await session.execute(stmt)

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=prop.exception_id,
            observation_id=prop.observation_id,
            action_type="CORRECTION_APPROVED",
            previous_state=ApprovalStatus.PENDING.value,
            new_state=ApprovalStatus.APPROVED.value,
            actor_id=approver_id,
            reason=req.approval_reason,
        )
        await session.commit()
        return prop

    @classmethod
    async def reject_correction(
        cls,
        session: AsyncSession,
        correction_id: str,
        req: CorrectionRejectRequest,
        actor_id: str,
    ) -> CorrectionProposal:
        prop = await ExceptionRepository.get_correction_by_id(session, correction_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction proposal not found.")

        prop.approval_status = ApprovalStatus.REJECTED.value
        prop.correction_status = "REJECTED"

        approval = CorrectionApproval(
            correction_id=correction_id,
            approval_status=ApprovalStatus.REJECTED.value,
            approver_id=actor_id,
            approval_reason=req.rejection_reason,
        )
        session.add(approval)

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=prop.exception_id,
            observation_id=prop.observation_id,
            action_type="CORRECTION_REJECTED",
            previous_state=ApprovalStatus.PENDING.value,
            new_state=ApprovalStatus.REJECTED.value,
            actor_id=actor_id,
            reason=req.rejection_reason,
        )
        await session.commit()
        return prop

    # ---------------------------------------------------------
    # FEATURE GROUP 5: REPLAY MANAGEMENT
    # ---------------------------------------------------------
    @classmethod
    async def submit_replay(
        cls,
        session: AsyncSession,
        exception_id: str,
        req: ReplaySubmitRequest,
        actor_id: str,
    ) -> ReplayRequest:
        """
        Submits an idempotent replay request to M02.
        Enforces approved correction prerequisite if replaying corrected data.
        """
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Exception {exception_id} not found.")

        cor_version = None
        resulting_payload = None
        if req.correction_id:
            cor = await ExceptionRepository.get_correction_by_id(session, req.correction_id)
            if not cor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced correction not found.")
            if cor.approval_status != ApprovalStatus.APPROVED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot replay unapproved correction proposal. Must be APPROVED first.",
                )
            cor_version = cor.correction_version
            resulting_payload = cor.resulting_payload_snapshot

        # Deterministic Idempotency Key
        idempotency_key = req.idempotency_key or hashlib.sha256(
            f"{exception_id}:{req.replay_mode}:{req.correction_id}:{cor_version}".encode("utf-8")
        ).hexdigest()[:32]

        # Check existing replay
        existing = await ExceptionRepository.get_replay_by_idempotency_key(session, idempotency_key)
        if existing:
            return existing

        rpl_id = f"RPL_{uuid.uuid4().hex[:12].upper()}"
        replay_req = ReplayRequest(
            replay_id=rpl_id,
            exception_id=exception_id,
            replay_mode=req.replay_mode,
            replay_status=ReplayStatus.REPLAYING.value,
            idempotency_key=idempotency_key,
            requested_by=actor_id,
            correction_id=req.correction_id,
            correction_version=cor_version,
            replay_reason=req.replay_reason,
            last_attempt_at=utc_now(),
        )
        session.add(replay_req)
        await session.flush()

        # Execute M02 replay through integration interface
        observations = await ExceptionRepository.get_observations_for_exception(session, exception_id)
        all_succeeded = True
        for obs in observations:
            obs.record_disposition = RecordDisposition.REPLAYING.value
            exec_res = await IngestionReplayClient.submit_replay_request(
                replay_id=rpl_id,
                observation_id=obs.observation_id,
                replay_mode=req.replay_mode,
                correction_payload=resulting_payload,
                idempotency_key=idempotency_key,
            )

            res_status = exec_res.get("execution_status", "SUCCEEDED")
            rec_result = ReplayRecordResult(
                replay_id=rpl_id,
                observation_id=obs.observation_id,
                execution_status=res_status,
                downstream_reference=exec_res.get("integration_reference"),
                result_details=exec_res.get("details", ""),
            )
            session.add(rec_result)

            if res_status == "SUCCEEDED":
                obs.record_disposition = RecordDisposition.REPLAYED.value
            else:
                obs.record_disposition = RecordDisposition.REPLAY_FAILED.value
                all_succeeded = False

        replay_req.replay_status = ReplayStatus.SUCCEEDED.value if all_succeeded else ReplayStatus.PARTIALLY_SUCCEEDED.value
        replay_req.completed_at = utc_now()
        replay_req.integration_reference = f"M02_BATCH_{uuid.uuid4().hex[:8]}"

        # Workflow status update
        if validate_workflow_transition(WorkflowStatus(exc.workflow_status), WorkflowStatus.RESOLVED):
            exc.workflow_status = WorkflowStatus.RESOLVED.value
            exc.resolved_at = utc_now()
            exc.resolved_by = actor_id
            exc.resolution_outcome = "REPLAYED_AND_RESOLVED"

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exception_id,
            action_type="REPLAY_EXECUTED",
            new_state=replay_req.replay_status,
            actor_id=actor_id,
            reason=req.replay_reason,
            correlation_id=idempotency_key,
            metadata={"records_replayed": len(observations), "status": replay_req.replay_status},
        )

        await session.commit()
        return replay_req

    # ---------------------------------------------------------
    # FEATURE GROUP 6: LIFECYCLE MANAGEMENT & NOTES
    # ---------------------------------------------------------
    @classmethod
    async def update_assignment(
        cls,
        session: AsyncSession,
        exception_id: str,
        assigned_user_id: str,
        assigned_group: Optional[str],
        actor_id: str,
    ) -> ExceptionRecord:
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        exc.assigned_user_id = assigned_user_id
        exc.assigned_group = assigned_group
        if exc.workflow_status == WorkflowStatus.OPEN.value:
            exc.workflow_status = WorkflowStatus.IN_REVIEW.value

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exception_id,
            action_type="ASSIGNMENT_UPDATED",
            new_state=f"User: {assigned_user_id}",
            actor_id=actor_id,
            reason="Triage assignment",
        )
        await session.commit()
        return exc

    @classmethod
    async def add_note(
        cls,
        session: AsyncSession,
        exception_id: str,
        content: str,
        note_type: str,
        actor_id: str,
        evidence_reference: Optional[str] = None,
    ) -> ExceptionNote:
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        note = ExceptionNote(
            exception_id=exception_id,
            author_id=actor_id,
            note_type=note_type,
            note_content=content,
            evidence_reference=evidence_reference,
        )
        session.add(note)
        await session.commit()
        return note

    @classmethod
    async def resolve_exception(
        cls,
        session: AsyncSession,
        exception_id: str,
        outcome: str,
        justification: str,
        actor_id: str,
    ) -> ExceptionRecord:
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        current = WorkflowStatus(exc.workflow_status)
        if not validate_workflow_transition(current, WorkflowStatus.RESOLVED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition exception directly from {current.value} to RESOLVED.",
            )

        exc.workflow_status = WorkflowStatus.RESOLVED.value
        exc.resolved_at = utc_now()
        exc.resolved_by = actor_id
        exc.resolution_outcome = outcome
        exc.resolution_justification = justification

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exception_id,
            action_type="EXCEPTION_RESOLVED",
            previous_state=current.value,
            new_state=WorkflowStatus.RESOLVED.value,
            actor_id=actor_id,
            reason=justification,
        )
        await session.commit()
        return exc

    @classmethod
    async def reopen_exception(
        cls,
        session: AsyncSession,
        exception_id: str,
        reason: str,
        actor_id: str,
    ) -> ExceptionRecord:
        exc = await ExceptionRepository.get_by_id(session, exception_id)
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        current = WorkflowStatus(exc.workflow_status)
        if not validate_workflow_transition(current, WorkflowStatus.REOPENED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only resolved or dismissed exceptions can be reopened (current: {current.value}).",
            )

        exc.workflow_status = WorkflowStatus.REOPENED.value
        exc.resolved_at = None
        exc.resolved_by = None

        await ExceptionRepository.create_audit_event(
            session=session,
            exception_id=exception_id,
            action_type="EXCEPTION_REOPENED",
            previous_state=current.value,
            new_state=WorkflowStatus.REOPENED.value,
            actor_id=actor_id,
            reason=reason,
        )
        await session.commit()
        return exc

