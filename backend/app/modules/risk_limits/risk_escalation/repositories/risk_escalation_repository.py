"""
Repository layer for M11.08 Risk Escalation.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

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
    RiskWorkflowIdempotencyKey,
)


class RiskEscalationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workflow_by_id(self, workflow_id: str) -> Optional[RiskBreachWorkflow]:
        self.db.expire_all()
        stmt = (
            select(RiskBreachWorkflow)
            .where(RiskBreachWorkflow.id == workflow_id)
            .options(
                selectinload(RiskBreachWorkflow.acknowledgements),
                selectinload(RiskBreachWorkflow.assignments),
                selectinload(RiskBreachWorkflow.escalation_events),
                selectinload(RiskBreachWorkflow.resolution_plans).selectinload(RiskResolutionPlan.actions),
                selectinload(RiskBreachWorkflow.lifecycle_events),
                selectinload(RiskBreachWorkflow.closure_records),
                selectinload(RiskBreachWorkflow.reopen_events),
                selectinload(RiskBreachWorkflow.sla_instances).selectinload(RiskWorkflowSLAInstance.pauses),
                selectinload(RiskBreachWorkflow.notifications),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_workflow_by_breach_event_id(self, breach_event_id: str) -> Optional[RiskBreachWorkflow]:
        self.db.expire_all()
        stmt = select(RiskBreachWorkflow).where(RiskBreachWorkflow.breach_event_id == breach_event_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_workflows(
        self,
        portfolio_id: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        severity: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        is_overdue: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RiskBreachWorkflow]:
        stmt = select(RiskBreachWorkflow).order_by(desc(RiskBreachWorkflow.created_at))
        if portfolio_id:
            stmt = stmt.where(RiskBreachWorkflow.portfolio_id == portfolio_id)
        if lifecycle_state:
            stmt = stmt.where(RiskBreachWorkflow.current_lifecycle_state == lifecycle_state)
        if severity:
            stmt = stmt.where(RiskBreachWorkflow.severity == severity)
        if owner_user_id:
            stmt = stmt.where(RiskBreachWorkflow.current_owner_user_id == owner_user_id)
        if is_overdue is not None:
            if is_overdue:
                stmt = stmt.where(RiskBreachWorkflow.current_sla_status == "OVERDUE")
            else:
                stmt = stmt.where(RiskBreachWorkflow.current_sla_status != "OVERDUE")
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def save_workflow(self, workflow: RiskBreachWorkflow) -> RiskBreachWorkflow:
        self.db.add(workflow)
        await self.db.flush()
        return workflow

    async def check_and_set_idempotency(self, key: str, action_type: str, target_id: str) -> bool:
        """Returns True if key was not present (acquired), False if already present."""
        stmt = select(RiskWorkflowIdempotencyKey).where(RiskWorkflowIdempotencyKey.key == key)
        res = await self.db.execute(stmt)
        if res.scalar_one_or_none():
            return False
        rec = RiskWorkflowIdempotencyKey(key=key, action_type=action_type, target_id=target_id)
        self.db.add(rec)
        await self.db.flush()
        return True

    async def add_acknowledgement(self, ack: RiskBreachAcknowledgement) -> RiskBreachAcknowledgement:
        self.db.add(ack)
        await self.db.flush()
        return ack

    async def add_assignment(self, assignment: RiskBreachAssignment) -> RiskBreachAssignment:
        self.db.add(assignment)
        await self.db.flush()
        return assignment

    async def add_escalation_event(self, event: RiskEscalationEvent) -> RiskEscalationEvent:
        self.db.add(event)
        await self.db.flush()
        return event

    async def add_resolution_plan(self, plan: RiskResolutionPlan) -> RiskResolutionPlan:
        self.db.add(plan)
        await self.db.flush()
        return plan

    async def get_resolution_plan(self, plan_id: str) -> Optional[RiskResolutionPlan]:
        stmt = (
            select(RiskResolutionPlan)
            .where(RiskResolutionPlan.id == plan_id)
            .options(selectinload(RiskResolutionPlan.actions).selectinload(RiskResolutionAction.updates))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def add_resolution_action(self, action: RiskResolutionAction) -> RiskResolutionAction:
        self.db.add(action)
        await self.db.flush()
        return action

    async def get_resolution_action(self, action_id: str) -> Optional[RiskResolutionAction]:
        stmt = select(RiskResolutionAction).where(RiskResolutionAction.id == action_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def add_mitigation_update(self, update_rec: RiskMitigationUpdate) -> RiskMitigationUpdate:
        self.db.add(update_rec)
        await self.db.flush()
        return update_rec

    async def add_mitigation_evidence(self, ev: RiskMitigationEvidence) -> RiskMitigationEvidence:
        self.db.add(ev)
        await self.db.flush()
        return ev

    async def add_lifecycle_event(self, event: RiskBreachLifecycleEvent) -> RiskBreachLifecycleEvent:
        self.db.add(event)
        await self.db.flush()
        return event

    async def add_closure_request(self, req: RiskBreachClosureRequest) -> RiskBreachClosureRequest:
        self.db.add(req)
        await self.db.flush()
        return req

    async def get_latest_closure_request(self, workflow_id: str) -> Optional[RiskBreachClosureRequest]:
        stmt = (
            select(RiskBreachClosureRequest)
            .where(RiskBreachClosureRequest.workflow_id == workflow_id)
            .order_by(desc(RiskBreachClosureRequest.created_at))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def add_closure_record(self, rec: RiskBreachClosureRecord) -> RiskBreachClosureRecord:
        self.db.add(rec)
        await self.db.flush()
        return rec

    async def add_reopen_event(self, ev: RiskBreachReopenEvent) -> RiskBreachReopenEvent:
        self.db.add(ev)
        await self.db.flush()
        return ev

    async def add_sla_instance(self, sla: RiskWorkflowSLAInstance) -> RiskWorkflowSLAInstance:
        self.db.add(sla)
        await self.db.flush()
        return sla

    async def add_sla_pause(self, pause: RiskWorkflowSLAPause) -> RiskWorkflowSLAPause:
        self.db.add(pause)
        await self.db.flush()
        return pause

    async def add_notification(self, notif: RiskEscalationNotification) -> RiskEscalationNotification:
        self.db.add(notif)
        await self.db.flush()
        return notif

    async def add_audit_log(self, audit: RiskEscalationAuditLog) -> RiskEscalationAuditLog:
        self.db.add(audit)
        await self.db.flush()
        return audit

    async def get_policy_by_code(self, policy_code: str) -> Optional[RiskEscalationPolicy]:
        stmt = (
            select(RiskEscalationPolicy)
            .where(RiskEscalationPolicy.policy_code == policy_code)
            .options(
                selectinload(RiskEscalationPolicy.versions).selectinload(RiskEscalationPolicyVersion.levels)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_policy(self, policy: RiskEscalationPolicy) -> RiskEscalationPolicy:
        self.db.add(policy)
        await self.db.flush()
        return policy

    async def list_policies(self) -> List[RiskEscalationPolicy]:
        stmt = (
            select(RiskEscalationPolicy)
            .options(selectinload(RiskEscalationPolicy.versions).selectinload(RiskEscalationPolicyVersion.levels))
            .order_by(desc(RiskEscalationPolicy.created_at))
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_counts_summary(self) -> Dict[str, Any]:
        """Aggregate metrics for dashboard overview."""
        stmt = select(
            RiskBreachWorkflow.current_lifecycle_state,
            RiskBreachWorkflow.severity,
            RiskBreachWorkflow.current_sla_status,
            RiskBreachWorkflow.current_assignment_status,
            RiskBreachWorkflow.escalation_count,
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        total = len(rows)
        open_c = sum(1 for r in rows if r[0] == "OPEN")
        ack_c = sum(1 for r in rows if r[0] == "ACKNOWLEDGED")
        mit_c = sum(1 for r in rows if r[0] == "MITIGATED")
        closed_c = sum(1 for r in rows if r[0] == "CLOSED")
        reopened_c = sum(1 for r in rows if r[0] == "REOPENED")
        escalated_c = sum(1 for r in rows if r[4] > 0)
        overdue_c = sum(1 for r in rows if r[2] == "OVERDUE")
        unassigned_c = sum(1 for r in rows if r[3] == "UNASSIGNED")

        sev_map = {"WARNING": 0, "CRITICAL": 0, "EMERGENCY": 0}
        for r in rows:
            if r[1] in sev_map:
                sev_map[r[1]] += 1

        # Count escalation events
        esc_stmt = select(func.count(RiskEscalationEvent.id))
        esc_res = await self.db.execute(esc_stmt)
        total_esc_events = esc_res.scalar() or 0

        return {
            "total_active_breaches": total - closed_c,
            "open_count": open_c,
            "acknowledged_count": ack_c,
            "mitigated_count": mit_c,
            "closed_count": closed_c,
            "reopened_count": reopened_c,
            "escalated_count": escalated_c,
            "overdue_count": overdue_c,
            "unassigned_count": unassigned_c,
            "severity_breakdown": sev_map,
            "total_escalation_events": total_esc_events,
            "total_closed_count": closed_c,
        }

