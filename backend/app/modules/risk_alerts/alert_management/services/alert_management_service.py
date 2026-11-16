"""
Core Workflow and Lifecycle Services for M12.06 — Alert Management.

Features implemented:
- M12.06.01 & 02: Alert Acknowledgement & Contextual Snapshots (cycle-aware)
- M12.06.03 & 04: Individual and Role-based Ownership Assignment
- M12.06.05: Assignment History and Transition Preservation
- M12.06.06: Investigation Workflow and State Machine Transitions
- M12.06.07: Investigation Comments with Revision History
- M12.06.08: Evidence and Attachments Management
- M12.06.09: Disposition Management and Selected Action Mapping
- M12.06.10: Resolution Assessment
- M12.06.11: Formal Closure with Mandatory Reasons
- M12.06.12: Controlled Alert Reopening (incrementing workflow cycle)
- M12.06.13: Immutable Chronological Workflow Event History
- M12.06.14: Work Queue and Dashboard Presentation
- M12.06.15: Workflow Operations Analytics
- M12.06.16: Permission and Governance Safeguards
"""

from datetime import datetime
from decimal import Decimal
import uuid
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_alerts.alert_management.models.alert_management_models import (
    AlertAcknowledgement,
    AlertAssignment,
    AlertWorkflowState,
    AlertWorkflowEvent,
    AlertInvestigationComment,
    AlertCommentRevision,
    AlertManagementEvidence,
    AlertDisposition,
    AlertResolutionAssessment,
    AlertClosure,
    AlertReopening,
)
from backend.app.modules.risk_alerts.alert_management.repositories.alert_management_repository import (
    AlertManagementRepository,
)
from backend.app.modules.risk_alerts.alert_management.schemas.alert_management_schemas import (
    AlertAcknowledgeRequest,
    AlertAssignRequest,
    AlertWorkflowTransitionRequest,
    AlertCommentCreate,
    AlertCommentUpdate,
    AlertEvidenceCreate,
    AlertDispositionCreate,
    AlertResolutionAssessmentCreate,
    AlertCloseRequest,
    AlertReopenRequest,
    AlertWorkQueueItem,
    AlertManagementSummary,
)


# Allowed State Machine Transitions
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "OPEN": ["ACKNOWLEDGED", "ASSIGNED", "INVESTIGATING"],
    "ACKNOWLEDGED": ["ASSIGNED", "INVESTIGATING"],
    "ASSIGNED": ["INVESTIGATING", "ACKNOWLEDGED"],
    "INVESTIGATING": ["PENDING_INFORMATION", "PENDING_ACTION", "RESOLVED"],
    "PENDING_INFORMATION": ["INVESTIGATING", "RESOLVED"],
    "PENDING_ACTION": ["INVESTIGATING", "RESOLVED"],
    "RESOLVED": ["CLOSED", "REOPENED", "INVESTIGATING"],
    "CLOSED": ["REOPENED"],
    "REOPENED": ["ACKNOWLEDGED", "ASSIGNED", "INVESTIGATING"],
}


class AlertManagementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AlertManagementRepository(session)

    # ------------------ Acknowledgement (M12.06.01 - 02) ------------------
    async def acknowledge_alert(
        self,
        alert_id: str,
        req: AlertAcknowledgeRequest,
    ) -> AlertAcknowledgement:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        # Idempotency: If already acknowledged in current cycle by the same user, return latest
        latest_ack = await self.repo.get_latest_acknowledgement(alert_id, state.workflow_cycle)
        if latest_ack and state.acknowledgement_state == "ACKNOWLEDGED" and latest_ack.reviewer_user_id == req.reviewer_user_id:
            return latest_ack

        ack = AlertAcknowledgement(
            id=f"ACK-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            reviewer_user_id=req.reviewer_user_id,
            reviewer_role_snapshot=req.reviewer_role_snapshot,
            acknowledgement_comment=req.acknowledgement_comment,
            priority_snapshot=req.priority_snapshot or "MEDIUM",
            severity_snapshot=req.severity_snapshot or "WARNING",
            urgency_snapshot=req.urgency_snapshot or "U3_NORMAL",
            acknowledged_at=now,
            request_id=req.request_id,
        )
        await self.repo.save_acknowledgement(ack)

        # Update state projection
        prev_state = state.current_state
        state.acknowledgement_state = "ACKNOWLEDGED"
        state.acknowledged_at = now
        if state.current_state in ("OPEN", "REOPENED"):
            state.current_state = "ACKNOWLEDGED"
        await self.repo.update_workflow_state(state)

        # Append audit timeline event
        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_ACKNOWLEDGED",
            actor_user_id=req.reviewer_user_id,
            actor_role_snapshot=req.reviewer_role_snapshot,
            previous_state=prev_state,
            new_state=state.current_state,
            reason=req.acknowledgement_comment or "Alert acknowledged by reviewer",
            request_id=req.request_id,
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return ack

    # ------------------ Ownership Assignment (M12.06.03 - 05) ------------------
    async def assign_alert(
        self,
        alert_id: str,
        req: AlertAssignRequest,
    ) -> AlertAssignment:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        # Check existing active assignment and transition it
        active_assignment = await self.repo.get_active_assignment(alert_id)
        prev_owner_ref = None
        event_type = "ALERT_ASSIGNED"

        if active_assignment:
            active_assignment.assignment_status = "REASSIGNED"
            active_assignment.effective_to = now
            prev_owner_ref = active_assignment.assigned_user_id or active_assignment.assigned_role_id
            event_type = "ALERT_REASSIGNED"

        new_assignment = AlertAssignment(
            id=f"ASN-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            assignment_type=req.assignment_type.upper(),
            assigned_user_id=req.assigned_user_id,
            assigned_role_id=req.assigned_role_id,
            assigned_team_id=req.assigned_team_id,
            assigned_by_user_id=req.assigned_by_user_id,
            assignment_reason=req.assignment_reason,
            assignment_comment=req.assignment_comment,
            effective_from=now,
            due_at=req.due_at,
            assignment_status="ACTIVE",
            created_at=now,
        )
        await self.repo.save_assignment(new_assignment)

        # Update state projection
        prev_state = state.current_state
        state.current_owner_user_id = req.assigned_user_id
        state.current_owner_role_id = req.assigned_role_id
        state.assigned_at = now
        if state.current_state in ("OPEN", "ACKNOWLEDGED"):
            state.current_state = "ASSIGNED"
        await self.repo.update_workflow_state(state)

        # Record audit event
        new_owner_ref = req.assigned_user_id or req.assigned_role_id
        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type=event_type,
            actor_user_id=req.assigned_by_user_id,
            previous_state=prev_state,
            new_state=state.current_state,
            previous_owner_reference=prev_owner_ref,
            new_owner_reference=new_owner_ref,
            reason=req.assignment_reason,
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return new_assignment

    async def unassign_alert(
        self,
        alert_id: str,
        unassigned_by_user_id: str,
        reason: str,
    ) -> Optional[AlertAssignment]:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)
        active_assignment = await self.repo.get_active_assignment(alert_id)
        if not active_assignment:
            return None

        active_assignment.assignment_status = "UNASSIGNED"
        active_assignment.effective_to = now

        prev_owner = state.current_owner_user_id or state.current_owner_role_id
        state.current_owner_user_id = None
        state.current_owner_role_id = None
        await self.repo.update_workflow_state(state)

        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_UNASSIGNED",
            actor_user_id=unassigned_by_user_id,
            previous_owner_reference=prev_owner,
            new_owner_reference=None,
            reason=reason,
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return active_assignment

    # ------------------ Workflow State Machine (M12.06.06) ------------------
    async def transition_state(
        self,
        alert_id: str,
        req: AlertWorkflowTransitionRequest,
    ) -> AlertWorkflowState:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        # Optimistic concurrency lock
        if req.expected_version is not None and state.version != req.expected_version:
            raise ValueError(f"Concurrency conflict: expected version {req.expected_version}, found {state.version}")

        target = req.target_state.upper()
        if target not in ALLOWED_TRANSITIONS.get(state.current_state, []):
            raise ValueError(f"Invalid state transition from {state.current_state} to {target}")

        prev_state = state.current_state
        state.current_state = target
        if target == "INVESTIGATING" and not state.investigation_started_at:
            state.investigation_started_at = now
        elif target == "RESOLVED":
            state.resolved_at = now
            state.resolution_state = "RESOLVED"
        elif target == "CLOSED":
            state.closed_at = now

        await self.repo.update_workflow_state(state)

        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event_type = "ALERT_INVESTIGATION_STARTED" if target == "INVESTIGATING" else (
            f"ALERT_{target}" if target in ("RESOLVED", "CLOSED", "REOPENED") else "ALERT_STATUS_CHANGED"
        )
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type=event_type,
            actor_user_id=req.actor_user_id,
            actor_role_snapshot=req.actor_role_snapshot,
            previous_state=prev_state,
            new_state=target,
            reason=req.reason or f"Transitioned to {target}",
            event_metadata=req.event_metadata,
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return state

    # ------------------ Investigation Comments (M12.06.07) ------------------
    async def add_comment(
        self,
        alert_id: str,
        req: AlertCommentCreate,
    ) -> AlertInvestigationComment:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        comment = AlertInvestigationComment(
            id=f"CMT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            author_user_id=req.author_user_id,
            comment_category=req.comment_category.upper(),
            comment_content=req.comment_content,
            visibility=req.visibility.upper(),
            created_at=now,
            updated_at=now,
        )
        await self.repo.save_comment(comment)

        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_COMMENT_ADDED",
            actor_user_id=req.author_user_id,
            reason=f"Added comment ({req.comment_category})",
            event_metadata={"comment_id": comment.id},
            created_at=now,
        )
        await self.repo.append_workflow_event(event)

        # Re-fetch with eager loaded revisions for safe Pydantic v2 response serialization
        fetched = await self.repo.get_comment_by_id(comment.id)
        return fetched or comment

    async def update_comment(
        self,
        comment_id: str,
        req: AlertCommentUpdate,
    ) -> AlertInvestigationComment:
        now = datetime.utcnow()
        comment = await self.repo.get_comment_by_id(comment_id)
        if not comment:
            raise ValueError(f"Comment {comment_id} not found")

        rev = AlertCommentRevision(
            id=f"REV-{uuid.uuid4().hex[:12].upper()}",
            comment_id=comment_id,
            previous_content=comment.comment_content,
            revised_content=req.revised_content,
            revised_by_user_id=req.revised_by_user_id,
            revision_reason=req.revision_reason,
            created_at=now,
        )
        await self.repo.save_comment_revision(rev)
        comment.revisions.append(rev)

        comment.comment_content = req.revised_content
        comment.is_edited = True
        comment.updated_at = now
        await self.session.flush()

        seq = await self.repo.get_next_sequence_number(comment.alert_id, comment.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=comment.alert_id,
            workflow_cycle=comment.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_COMMENT_EDITED",
            actor_user_id=req.revised_by_user_id,
            reason=req.revision_reason,
            event_metadata={"comment_id": comment.id, "revision_id": rev.id},
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return comment

    # ------------------ Evidence Management (M12.06.08) ------------------
    async def add_evidence(
        self,
        alert_id: str,
        req: AlertEvidenceCreate,
    ) -> AlertManagementEvidence:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        evidence = AlertManagementEvidence(
            id=f"EVD-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            comment_id=req.comment_id,
            evidence_type=req.evidence_type.upper(),
            source_module=req.source_module,
            source_record_id=req.source_record_id,
            file_reference=req.file_reference,
            file_name=req.file_name,
            content_type=req.content_type,
            file_size_bytes=req.file_size_bytes,
            checksum=req.checksum,
            description=req.description,
            evidence_payload=req.evidence_payload,
            uploaded_by_user_id=req.uploaded_by_user_id,
            uploaded_at=now,
        )
        await self.repo.save_evidence(evidence)

        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_EVIDENCE_ADDED",
            actor_user_id=req.uploaded_by_user_id,
            reason=req.description,
            event_metadata={"evidence_id": evidence.id, "evidence_type": evidence.evidence_type},
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return evidence

    # ------------------ Disposition & Resolution (M12.06.09 - 10) ------------------
    async def record_disposition(
        self,
        alert_id: str,
        req: AlertDispositionCreate,
    ) -> AlertDisposition:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        disp = AlertDisposition(
            id=f"DSP-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            disposition=req.disposition.upper(),
            disposition_reason=req.disposition_reason,
            selected_action=req.selected_action.upper(),
            selected_by_user_id=req.selected_by_user_id,
            related_m11_breach_id=req.related_m11_breach_id,
            created_at=now,
        )
        await self.repo.save_disposition(disp)

        state.current_disposition = req.disposition.upper()
        await self.repo.update_workflow_state(state)

        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_DISPOSITION_SELECTED",
            actor_user_id=req.selected_by_user_id,
            reason=req.disposition_reason,
            event_metadata={"disposition": disp.disposition, "selected_action": disp.selected_action},
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return disp

    async def assess_resolution(
        self,
        alert_id: str,
        req: AlertResolutionAssessmentCreate,
    ) -> AlertResolutionAssessment:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        res_rec = AlertResolutionAssessment(
            id=f"RES-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            resolution_status=req.resolution_status.upper(),
            resolution_reason=req.resolution_reason,
            assessed_by_user_id=req.assessed_by_user_id,
            evidence_reference_id=req.evidence_reference_id,
            related_breach_status_snapshot=req.related_breach_status_snapshot,
            assessed_at=now,
        )
        await self.repo.save_resolution_assessment(res_rec)

        state.resolution_state = req.resolution_status.upper()
        if req.resolution_status.upper() == "RESOLVED":
            state.current_state = "RESOLVED"
            state.resolved_at = now
        await self.repo.update_workflow_state(state)

        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_RESOLVED" if req.resolution_status.upper() == "RESOLVED" else "ALERT_RESOLUTION_ASSESSED",
            actor_user_id=req.assessed_by_user_id,
            reason=req.resolution_reason,
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return res_rec

    # ------------------ Closure & Reopening (M12.06.11 - 12) ------------------
    async def close_alert(
        self,
        alert_id: str,
        req: AlertCloseRequest,
    ) -> AlertClosure:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        # Closure prerequisites: Must be RESOLVED
        if state.current_state != "RESOLVED":
            raise ValueError(f"Cannot close alert in state '{state.current_state}'. Must be in 'RESOLVED' state.")

        # Require a recorded disposition
        latest_disp = await self.repo.get_latest_disposition(alert_id, state.workflow_cycle)
        if not latest_disp:
            raise ValueError("Cannot close alert without a recorded investigation disposition.")

        closure = AlertClosure(
            id=f"CLS-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            closed_by_user_id=req.closed_by_user_id,
            closure_reason=req.closure_reason.upper(),
            closure_notes=req.closure_notes,
            final_disposition=latest_disp.disposition,
            final_priority_snapshot="MEDIUM",
            final_severity_snapshot="WARNING",
            final_owner_snapshot=state.current_owner_user_id or state.current_owner_role_id,
            resolution_reference=state.resolution_state,
            closed_at=now,
        )
        await self.repo.save_closure(closure)

        prev_state = state.current_state
        state.current_state = "CLOSED"
        state.closed_at = now
        await self.repo.update_workflow_state(state)

        seq = await self.repo.get_next_sequence_number(alert_id, state.workflow_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=state.workflow_cycle,
            sequence_number=seq,
            event_type="ALERT_CLOSED",
            actor_user_id=req.closed_by_user_id,
            previous_state=prev_state,
            new_state="CLOSED",
            reason=req.closure_reason,
            event_metadata={"closure_id": closure.id, "disposition": latest_disp.disposition},
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return closure

    async def reopen_alert(
        self,
        alert_id: str,
        req: AlertReopenRequest,
    ) -> AlertReopening:
        now = datetime.utcnow()
        state = await self.repo.create_or_init_workflow_state(alert_id)

        if state.current_state not in ("CLOSED", "RESOLVED"):
            raise ValueError(f"Alert is currently '{state.current_state}'. Only CLOSED or RESOLVED alerts can be reopened.")

        prev_cycle = state.workflow_cycle
        new_cycle = prev_cycle + 1

        reopening = AlertReopening(
            id=f"ROP-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            previous_workflow_cycle=prev_cycle,
            new_workflow_cycle=new_cycle,
            reopened_by_user_id=req.reopened_by_user_id,
            reopening_reason=req.reopening_reason,
            triggering_event_id=req.triggering_event_id,
            reopened_at=now,
        )
        await self.repo.save_reopening(reopening)

        # Update state projection for new cycle
        prev_state = state.current_state
        state.workflow_cycle = new_cycle
        state.current_state = "REOPENED"
        state.acknowledgement_state = "UNACKNOWLEDGED"
        state.resolution_state = "NOT_ASSESSED"
        state.opened_at = now
        state.acknowledged_at = None
        state.resolved_at = None
        state.closed_at = None
        await self.repo.update_workflow_state(state)

        seq = await self.repo.get_next_sequence_number(alert_id, new_cycle)
        event = AlertWorkflowEvent(
            id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            alert_id=alert_id,
            workflow_cycle=new_cycle,
            sequence_number=seq,
            event_type="ALERT_REOPENED",
            actor_user_id=req.reopened_by_user_id,
            previous_state=prev_state,
            new_state="REOPENED",
            reason=req.reopening_reason,
            event_metadata={"reopening_id": reopening.id, "cycle": new_cycle},
            created_at=now,
        )
        await self.repo.append_workflow_event(event)
        return reopening

    # ------------------ Query Services ------------------
    async def get_workflow_state(self, alert_id: str) -> AlertWorkflowState:
        return await self.repo.create_or_init_workflow_state(alert_id)

    async def get_workflow_timeline(self, alert_id: str) -> List[AlertWorkflowEvent]:
        return await self.repo.list_workflow_events(alert_id)

    async def list_comments(self, alert_id: str) -> List[AlertInvestigationComment]:
        return await self.repo.list_comments(alert_id)

    async def list_evidence(self, alert_id: str) -> List[AlertManagementEvidence]:
        return await self.repo.list_evidence(alert_id)

    async def list_work_queue(
        self,
        current_state: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        assigned_role_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AlertWorkQueueItem]:
        pairs = await self.repo.list_work_queue(
            current_state, assigned_user_id, assigned_role_id, portfolio_id, limit, offset
        )
        items = []
        for state, master in pairs:
            items.append(
                AlertWorkQueueItem(
                    alert_id=state.alert_id,
                    title=master.title,
                    category=master.alert_category,
                    portfolio_id=master.portfolio_id,
                    priority=master.priority,
                    severity="WARNING",  # Default baseline
                    urgency="U3_NORMAL",
                    workflow_status=state.current_state,
                    acknowledgement_state=state.acknowledgement_state,
                    assigned_owner=state.current_owner_user_id,
                    assigned_role=state.current_owner_role_id,
                    assigned_at=state.assigned_at,
                    last_activity_at=state.updated_at,
                    due_at=None,
                    workflow_cycle=state.workflow_cycle,
                )
            )
        return items

    async def get_management_summary(self) -> Dict[str, Any]:
        return await self.repo.get_management_summary_stats()

