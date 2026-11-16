"""
Service layer for M11.08 Risk Escalation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.risk_escalation.calculations.risk_escalation_math import (
    calculate_acknowledgement_time,
    calculate_mitigation_time,
    calculate_resolution_time,
    calculate_sla_compliance_rate,
    calculate_reopening_rate,
    calculate_escalation_frequency,
    is_sla_breached,
)
from backend.app.modules.risk_limits.risk_escalation.models.risk_escalation_models import (
    RiskBreachWorkflow,
    RiskBreachAcknowledgement,
    RiskBreachAssignment,
    RiskEscalationPolicy,
    RiskEscalationPolicyVersion,
    RiskEscalationLevel,
    RiskEscalationEvent,
    RiskResolutionPlan,
    RiskResolutionAction,
    RiskMitigationUpdate,
    RiskMitigationEvidence,
    RiskBreachLifecycleEvent,
    RiskBreachClosureRequest,
    RiskBreachClosureRecord,
    RiskBreachReopenEvent,
    RiskWorkflowSLAInstance,
    RiskWorkflowSLAPause,
    RiskEscalationNotification,
    RiskEscalationAuditLog,
)
from backend.app.modules.risk_limits.risk_escalation.repositories.risk_escalation_repository import RiskEscalationRepository
from backend.app.modules.risk_limits.risk_escalation.schemas.risk_escalation_schemas import (
    RiskWorkflowCreateInput,
    BreachAcknowledgeInput,
    BreachAssignInput,
    ManualEscalateInput,
    ResolutionPlanCreateInput,
    ResolutionActionProgressInput,
    MitigationEvidenceInput,
    BreachTransitionInput,
    ClosureRequestInput,
    ClosureApproveInput,
    ClosureRejectInput,
    BreachReopenInput,
    SLAPauseInput,
    SLAResumeInput,
    RiskEscalationPolicyCreateInput,
    EscalationDashboardSummary,
)


def utc_now() -> datetime:
    return datetime.utcnow()


class RiskEscalationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RiskEscalationRepository(db)

    async def get_or_create_workflow(self, payload: RiskWorkflowCreateInput) -> RiskBreachWorkflow:
        existing = await self.repo.get_workflow_by_breach_event_id(payload.breach_event_id)
        if existing:
            return existing

        now = utc_now()
        # Default SLA deadlines based on severity:
        # EMERGENCY: ack 5m, res 60m
        # CRITICAL: ack 15m, res 240m (4h)
        # WARNING: ack 60m, res 1440m (24h)
        ack_mins = 60
        res_mins = 1440
        if payload.severity == "EMERGENCY":
            ack_mins = 5
            res_mins = 60
        elif payload.severity == "CRITICAL":
            ack_mins = 15
            res_mins = 240

        ack_due = now + timedelta(minutes=ack_mins)
        res_due = now + timedelta(minutes=res_mins)

        workflow_id = f"WF_{uuid.uuid4().hex[:12].upper()}"
        wf_ref = f"WRK-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        wf = RiskBreachWorkflow(
            id=workflow_id,
            workflow_reference=wf_ref,
            breach_event_id=payload.breach_event_id,
            breach_episode_id=payload.breach_episode_id,
            portfolio_id=payload.portfolio_id,
            risk_limit_id=payload.risk_limit_id,
            severity=payload.severity,
            classification_id=payload.classification_id,
            classification_version=payload.classification_version,
            current_lifecycle_state="OPEN",
            current_assignment_status="ASSIGNED" if payload.initial_owner_user_id else "UNASSIGNED",
            current_owner_user_id=payload.initial_owner_user_id,
            current_owner_team_id=payload.initial_owner_team_id,
            current_escalation_level_name="LEVEL_3" if payload.severity == "EMERGENCY" else ("LEVEL_2" if payload.severity == "CRITICAL" else "LEVEL_1"),
            escalation_count=0,
            current_sla_status="ON_TRACK",
            acknowledgement_status="PENDING_ACKNOWLEDGEMENT",
            resolution_plan_status="NOT_CREATED",
            closure_status="NOT_REQUESTED",
            sla_start_at=now,
            acknowledgement_due_at=ack_due,
            resolution_due_at=res_due,
            workflow_version=1,
            created_at=now,
            updated_at=now,
        )
        saved = await self.repo.save_workflow(wf)

        # Create SLA instances
        ack_sla = RiskWorkflowSLAInstance(
            id=f"SLA_ACK_{uuid.uuid4().hex[:10]}",
            workflow_id=saved.id,
            sla_type="ACKNOWLEDGEMENT",
            severity=payload.severity,
            start_time=now,
            deadline=ack_due,
            sla_status="ON_TRACK",
            total_paused_seconds=0.0,
            created_at=now,
        )
        res_sla = RiskWorkflowSLAInstance(
            id=f"SLA_RES_{uuid.uuid4().hex[:10]}",
            workflow_id=saved.id,
            sla_type="RESOLUTION",
            severity=payload.severity,
            start_time=now,
            deadline=res_due,
            sla_status="ON_TRACK",
            total_paused_seconds=0.0,
            created_at=now,
        )
        await self.repo.add_sla_instance(ack_sla)
        await self.repo.add_sla_instance(res_sla)

        # Initial assignment log if provided
        if payload.initial_owner_user_id:
            assign = RiskBreachAssignment(
                id=f"ASN_{uuid.uuid4().hex[:10]}",
                workflow_id=saved.id,
                assigned_user_id=payload.initial_owner_user_id,
                assigned_team_id=payload.initial_owner_team_id,
                responsibility_level=saved.current_escalation_level_name,
                assignment_type="INITIAL",
                reassignment_reason="Initial automated workflow routing",
                assigned_by_user_id="SYSTEM",
                created_at=now,
            )
            await self.repo.add_assignment(assign)

        # Initial lifecycle event
        lc = RiskBreachLifecycleEvent(
            id=f"LC_{uuid.uuid4().hex[:10]}",
            workflow_id=saved.id,
            previous_state="NONE",
            new_state="OPEN",
            transition_reason="Workflow created from upstream breach classification event",
            actor_user_id="SYSTEM",
            actor_type="SYSTEM",
            evidence_reference=payload.breach_event_id,
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)

        # Create notification task
        notif = RiskEscalationNotification(
            id=f"NTF_{uuid.uuid4().hex[:10]}",
            workflow_id=saved.id,
            notification_type="NEW_BREACH",
            recipient_user_id=payload.initial_owner_user_id,
            recipient_team_id=payload.initial_owner_team_id,
            channel="IN_APP",
            delivery_status="SENT",
            title=f"New {payload.severity} Breach in Portfolio {payload.portfolio_id}",
            message_body=f"Risk limit {payload.risk_limit_id} violated. Workflow {wf_ref} created.",
            idempotency_key=f"INIT_{saved.id}",
            created_at=now,
        )
        await self.repo.add_notification(notif)
        await self.db.commit()

        # Re-fetch with eager loaded relationships
        return await self.repo.get_workflow_by_id(saved.id)

    async def acknowledge_breach(self, workflow_id: str, payload: BreachAcknowledgeInput) -> RiskBreachWorkflow:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        now = utc_now()
        is_reack = wf.acknowledgement_status == "ACKNOWLEDGED"

        ack = RiskBreachAcknowledgement(
            id=f"ACK_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            acknowledged_by_user_id=payload.acknowledged_by_user_id,
            user_role=payload.user_role,
            review_notes=payload.review_notes,
            severity_at_acknowledgement=wf.severity,
            classification_version=wf.classification_version,
            is_reacknowledgement=is_reack,
            acknowledgement_status="ACKNOWLEDGED",
            created_at=now,
        )
        await self.repo.add_acknowledgement(ack)

        wf.acknowledgement_status = "ACKNOWLEDGED"
        wf.acknowledged_at = now

        # Update ACK SLA instance if active
        for sla in wf.sla_instances:
            if sla.sla_type == "ACKNOWLEDGEMENT" and not sla.completed_time:
                sla.completed_time = now
                sla.sla_status = "COMPLETED_ON_TIME" if now <= sla.deadline else "COMPLETED_LATE"

        # Advance lifecycle to ACKNOWLEDGED if currently OPEN
        if wf.current_lifecycle_state == "OPEN":
            wf.current_lifecycle_state = "ACKNOWLEDGED"
            lc = RiskBreachLifecycleEvent(
                id=f"LC_{uuid.uuid4().hex[:10]}",
                workflow_id=wf.id,
                previous_state="OPEN",
                new_state="ACKNOWLEDGED",
                transition_reason=payload.review_notes or "Formal review acknowledgement completed",
                actor_user_id=payload.acknowledged_by_user_id,
                actor_type="USER",
                created_at=now,
            )
            await self.repo.add_lifecycle_event(lc)

        wf.updated_at = now
        await self.repo.save_workflow(wf)
        await self.db.commit()
        return await self.repo.get_workflow_by_id(wf.id)

    async def assign_breach(self, workflow_id: str, payload: BreachAssignInput) -> RiskBreachWorkflow:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        now = utc_now()
        assign = RiskBreachAssignment(
            id=f"ASN_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            assigned_user_id=payload.assigned_user_id,
            assigned_team_id=payload.assigned_team_id,
            responsibility_level=payload.responsibility_level,
            assignment_type=payload.assignment_type,
            reassignment_reason=payload.reassignment_reason,
            assigned_by_user_id=payload.assigned_by_user_id,
            created_at=now,
        )
        await self.repo.add_assignment(assign)

        wf.current_owner_user_id = payload.assigned_user_id
        wf.current_owner_team_id = payload.assigned_team_id
        wf.current_assignment_status = "ASSIGNED" if payload.assigned_user_id else "UNASSIGNED"
        wf.updated_at = now
        await self.repo.save_workflow(wf)

        # Notify new owner
        notif = RiskEscalationNotification(
            id=f"NTF_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            notification_type="REASSIGNMENT",
            recipient_user_id=payload.assigned_user_id,
            recipient_team_id=payload.assigned_team_id,
            channel="IN_APP",
            delivery_status="SENT",
            title=f"Breach Reassigned: {wf.workflow_reference}",
            message_body=f"You have been assigned responsibility for breach workflow {wf.workflow_reference}.",
            idempotency_key=f"ASN_{assign.id}",
            created_at=now,
        )
        await self.repo.add_notification(notif)
        await self.db.commit()
        return await self.repo.get_workflow_by_id(wf.id)

    async def escalate_breach(
        self,
        workflow_id: str,
        target_level_name: str,
        escalation_reason: str,
        initiated_by_user_id: str,
        trigger_type: str = "MANUAL_ESCALATION",
        idempotency_key: Optional[str] = None,
    ) -> RiskBreachWorkflow:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        now = utc_now()
        idem_key = idempotency_key or f"ESC_{wf.id}_{target_level_name}_{now.timestamp()}"
        acquired = await self.repo.check_and_set_idempotency(idem_key, "ESCALATION", wf.id)
        if not acquired:
            return wf

        prev_level = wf.current_escalation_level_name
        esc_event = RiskEscalationEvent(
            id=f"ESC_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            policy_version_id=None,
            previous_level_name=prev_level,
            new_level_name=target_level_name,
            trigger_type=trigger_type,
            trigger_reference=None,
            escalation_reason=escalation_reason,
            initiated_by_user_id=initiated_by_user_id,
            idempotency_key=idem_key,
            execution_status="EXECUTED",
            created_at=now,
        )
        await self.repo.add_escalation_event(esc_event)

        wf.current_escalation_level_name = target_level_name
        wf.escalation_count += 1
        wf.updated_at = now
        await self.repo.save_workflow(wf)

        # Notify escalation
        notif = RiskEscalationNotification(
            id=f"NTF_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            notification_type="ESCALATION",
            recipient_user_id=wf.current_owner_user_id,
            recipient_team_id=wf.current_owner_team_id,
            channel="IN_APP",
            delivery_status="SENT",
            title=f"Breach Escalated to {target_level_name}: {wf.workflow_reference}",
            message_body=f"Escalation reason: {escalation_reason}",
            idempotency_key=f"NOTIF_{esc_event.id}",
            created_at=now,
        )
        await self.repo.add_notification(notif)
        await self.db.commit()
        return await self.repo.get_workflow_by_id(wf.id)

    async def create_resolution_plan(self, workflow_id: str, payload: ResolutionPlanCreateInput) -> RiskResolutionPlan:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        now = utc_now()
        plan_id = f"PLN_{uuid.uuid4().hex[:10]}"
        plan_code = f"PLAN-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        plan = RiskResolutionPlan(
            id=plan_id,
            workflow_id=wf.id,
            plan_code=plan_code,
            title=payload.title,
            description=payload.description,
            root_cause_hypothesis=payload.root_cause_hypothesis,
            proposed_actions_summary=payload.proposed_actions_summary,
            owner_user_id=payload.owner_user_id,
            owner_team_id=payload.owner_team_id,
            priority=payload.priority,
            plan_status="ACTIVE",
            due_at=payload.due_at,
            original_due_at=payload.due_at,
            approved_by_user_id=payload.created_by,
            approved_at=now,
            created_by=payload.created_by,
            created_at=now,
            updated_at=now,
        )
        await self.repo.add_resolution_plan(plan)

        # Add granular actions
        for idx, act in enumerate(payload.actions, 1):
            action_item = RiskResolutionAction(
                id=f"ACT_{uuid.uuid4().hex[:10]}",
                plan_id=plan.id,
                sequence_order=idx,
                action_title=act.action_title,
                description=act.description,
                assigned_to_user_id=act.assigned_to_user_id,
                action_status="NOT_STARTED",
                progress_percentage=Decimal("0.00"),
                due_at=act.due_at,
                created_at=now,
                updated_at=now,
            )
            await self.repo.add_resolution_action(action_item)

        wf.resolution_plan_status = "ACTIVE"
        wf.updated_at = now
        await self.repo.save_workflow(wf)
        await self.db.commit()
        return await self.repo.get_resolution_plan(plan.id)

    async def update_action_progress(self, action_id: str, payload: ResolutionActionProgressInput) -> RiskResolutionAction:
        action = await self.repo.get_resolution_action(action_id)
        if not action:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

        now = utc_now()
        update_rec = RiskMitigationUpdate(
            id=f"MUPD_{uuid.uuid4().hex[:10]}",
            action_id=action.id,
            previous_status=action.action_status,
            new_status=payload.action_status,
            progress_percentage=payload.progress_percentage,
            notes=payload.notes,
            updated_by_user_id=payload.updated_by_user_id,
            created_at=now,
        )
        await self.repo.add_mitigation_update(update_rec)

        action.action_status = payload.action_status
        action.progress_percentage = payload.progress_percentage
        if payload.action_status == "COMPLETED":
            action.completed_at = now
        action.updated_at = now
        await self.db.commit()
        return await self.repo.get_resolution_action(action.id)

    async def submit_mitigation_evidence(self, workflow_id: str, payload: MitigationEvidenceInput) -> RiskMitigationEvidence:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        now = utc_now()
        ev = RiskMitigationEvidence(
            id=f"EVD_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            evidence_type=payload.evidence_type,
            document_reference=payload.document_reference,
            description=payload.description,
            verified_risk_reduction=payload.verified_risk_reduction,
            submitted_by_user_id=payload.submitted_by_user_id,
            created_at=now,
        )
        await self.repo.add_mitigation_evidence(ev)

        # If verified, mark workflow mitigated
        if payload.verified_risk_reduction and wf.current_lifecycle_state in ["OPEN", "ACKNOWLEDGED"]:
            wf.current_lifecycle_state = "MITIGATED"
            wf.mitigated_at = now
            lc = RiskBreachLifecycleEvent(
                id=f"LC_{uuid.uuid4().hex[:10]}",
                workflow_id=wf.id,
                previous_state="ACKNOWLEDGED",
                new_state="MITIGATED",
                transition_reason="Verified mitigation evidence submitted",
                actor_user_id=payload.submitted_by_user_id,
                actor_type="USER",
                evidence_reference=ev.document_reference,
                created_at=now,
            )
            await self.repo.add_lifecycle_event(lc)
            await self.repo.save_workflow(wf)

        await self.db.commit()
        return ev

    async def request_closure(self, workflow_id: str, payload: ClosureRequestInput) -> RiskBreachClosureRequest:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        now = utc_now()
        req = RiskBreachClosureRequest(
            id=f"CREQ_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            closure_reason=payload.closure_reason,
            closure_description=payload.closure_description,
            closure_evidence_ref=payload.closure_evidence_ref,
            requested_by_user_id=payload.requested_by_user_id,
            request_status="PENDING_APPROVAL",
            created_at=now,
        )
        await self.repo.add_closure_request(req)

        wf.closure_status = "PENDING_APPROVAL"
        wf.updated_at = now
        await self.repo.save_workflow(wf)
        await self.db.commit()
        return req

    async def approve_closure(self, workflow_id: str, payload: ClosureApproveInput) -> RiskBreachWorkflow:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        req = await self.repo.get_latest_closure_request(workflow_id)
        if not req or req.request_status != "PENDING_APPROVAL":
            raise HTTPException(status_code=400, detail="No pending closure request found")

        # Maker-checker validation: approver cannot be the same as requester
        if req.requested_by_user_id == payload.approved_by_user_id:
            raise HTTPException(status_code=403, detail="Segregation of duties: closure approver cannot be the requester")

        now = utc_now()
        req.request_status = "APPROVED"
        req.reviewed_at = now

        closure_rec = RiskBreachClosureRecord(
            id=f"CLO_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            closure_request_id=req.id,
            closure_reason=req.closure_reason,
            closure_description=req.closure_description,
            closed_by_user_id=req.requested_by_user_id,
            approved_by_user_id=payload.approved_by_user_id,
            closed_at=now,
        )
        await self.repo.add_closure_record(closure_rec)

        prev_state = wf.current_lifecycle_state
        wf.current_lifecycle_state = "CLOSED"
        wf.closure_status = "APPROVED"
        wf.closed_at = now
        wf.updated_at = now

        # Update Resolution SLA
        for sla in wf.sla_instances:
            if sla.sla_type == "RESOLUTION" and not sla.completed_time:
                sla.completed_time = now
                sla.sla_status = "COMPLETED_ON_TIME" if now <= sla.deadline else "COMPLETED_LATE"

        lc = RiskBreachLifecycleEvent(
            id=f"LC_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            previous_state=prev_state,
            new_state="CLOSED",
            transition_reason=f"Closure approved by {payload.approved_by_user_id}",
            actor_user_id=payload.approved_by_user_id,
            actor_type="USER",
            evidence_reference=closure_rec.id,
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)
        await self.repo.save_workflow(wf)
        await self.db.commit()
        return await self.repo.get_workflow_by_id(wf.id)

    async def reopen_breach(self, workflow_id: str, payload: BreachReopenInput) -> RiskBreachWorkflow:
        wf = await self.repo.get_workflow_by_id(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        if wf.current_lifecycle_state != "CLOSED":
            raise HTTPException(status_code=400, detail="Only CLOSED breaches can be reopened")

        now = utc_now()
        reopen_ev = RiskBreachReopenEvent(
            id=f"ROP_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            reopen_trigger=payload.reopen_trigger,
            reopen_reason=payload.reopen_reason,
            reopened_by_user_id=payload.reopened_by_user_id,
            previous_closure_id=None,
            created_at=now,
        )
        await self.repo.add_reopen_event(reopen_ev)

        wf.current_lifecycle_state = "REOPENED"
        wf.acknowledgement_status = "PENDING_ACKNOWLEDGEMENT"
        wf.reopened_at = now
        wf.closed_at = None
        wf.updated_at = now

        lc = RiskBreachLifecycleEvent(
            id=f"LC_{uuid.uuid4().hex[:10]}",
            workflow_id=wf.id,
            previous_state="CLOSED",
            new_state="REOPENED",
            transition_reason=payload.reopen_reason,
            actor_user_id=payload.reopened_by_user_id,
            actor_type="USER",
            evidence_reference=payload.reopen_trigger,
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)
        await self.repo.save_workflow(wf)
        await self.db.commit()
        return await self.repo.get_workflow_by_id(wf.id)

    async def get_dashboard_summary(self) -> EscalationDashboardSummary:
        stats = await self.repo.get_counts_summary()
        total_closed = stats["total_closed_count"]
        # Rates
        sla_comp = calculate_sla_compliance_rate(stats["acknowledged_count"], stats["open_count"] + stats["acknowledged_count"])
        reopen_rate = calculate_reopening_rate(stats["reopened_count"], total_closed + stats["reopened_count"])
        esc_freq = calculate_escalation_frequency(stats["total_escalation_events"], stats["total_active_breaches"] + total_closed)

        return EscalationDashboardSummary(
            total_active_breaches=stats["total_active_breaches"],
            open_count=stats["open_count"],
            acknowledged_count=stats["acknowledged_count"],
            mitigated_count=stats["mitigated_count"],
            closed_count=stats["closed_count"],
            reopened_count=stats["reopened_count"],
            escalated_count=stats["escalated_count"],
            overdue_count=stats["overdue_count"],
            unassigned_count=stats["unassigned_count"],
            severity_breakdown=stats["severity_breakdown"],
            sla_compliance_rate=sla_comp,
            reopening_rate=reopen_rate,
            escalation_frequency=esc_freq,
        )
