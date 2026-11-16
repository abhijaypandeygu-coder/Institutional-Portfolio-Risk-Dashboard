"""
Async SQLAlchemy repository for M12.06 — Alert Management.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_alerts.models.risk_alerts_models import AlertEvent
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


class AlertManagementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------ Master Alert Lookup ------------------
    async def get_master_alert(self, alert_id: str) -> Optional[AlertEvent]:
        res = await self.session.execute(
            select(AlertEvent).where(AlertEvent.id == alert_id)
        )
        return res.scalar_one_or_none()

    # ------------------ Workflow State Projection ------------------
    async def get_workflow_state(self, alert_id: str) -> Optional[AlertWorkflowState]:
        res = await self.session.execute(
            select(AlertWorkflowState).where(AlertWorkflowState.alert_id == alert_id)
        )
        return res.scalar_one_or_none()

    async def create_or_init_workflow_state(
        self,
        alert_id: str,
        initial_state: str = "OPEN",
    ) -> AlertWorkflowState:
        state = await self.get_workflow_state(alert_id)
        if not state:
            state = AlertWorkflowState(
                id=f"WFS-{alert_id}",
                alert_id=alert_id,
                workflow_cycle=1,
                current_state=initial_state,
                acknowledgement_state="UNACKNOWLEDGED",
                resolution_state="NOT_ASSESSED",
                version=1,
                opened_at=datetime.utcnow(),
            )
            self.session.add(state)
            await self.session.flush()
        return state

    async def update_workflow_state(self, state: AlertWorkflowState) -> AlertWorkflowState:
        state.version += 1
        state.updated_at = datetime.utcnow()
        await self.session.flush()
        return state

    # ------------------ Workflow Events (Audit Timeline) ------------------
    async def get_next_sequence_number(self, alert_id: str, cycle: int) -> int:
        res = await self.session.execute(
            select(func.coalesce(func.max(AlertWorkflowEvent.sequence_number), 0))
            .where(
                and_(
                    AlertWorkflowEvent.alert_id == alert_id,
                    AlertWorkflowEvent.workflow_cycle == cycle,
                )
            )
        )
        return int(res.scalar() or 0) + 1

    async def append_workflow_event(self, event: AlertWorkflowEvent) -> AlertWorkflowEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_workflow_events(self, alert_id: str) -> List[AlertWorkflowEvent]:
        stmt = (
            select(AlertWorkflowEvent)
            .where(AlertWorkflowEvent.alert_id == alert_id)
            .order_by(AlertWorkflowEvent.workflow_cycle.asc(), AlertWorkflowEvent.sequence_number.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ Acknowledgements ------------------
    async def save_acknowledgement(self, ack: AlertAcknowledgement) -> AlertAcknowledgement:
        self.session.add(ack)
        await self.session.flush()
        return ack

    async def get_latest_acknowledgement(self, alert_id: str, cycle: int) -> Optional[AlertAcknowledgement]:
        stmt = (
            select(AlertAcknowledgement)
            .where(
                and_(
                    AlertAcknowledgement.alert_id == alert_id,
                    AlertAcknowledgement.workflow_cycle == cycle,
                )
            )
            .order_by(desc(AlertAcknowledgement.acknowledged_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_acknowledgements(self, alert_id: str) -> List[AlertAcknowledgement]:
        stmt = (
            select(AlertAcknowledgement)
            .where(AlertAcknowledgement.alert_id == alert_id)
            .order_by(desc(AlertAcknowledgement.acknowledged_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ Assignments ------------------
    async def save_assignment(self, assignment: AlertAssignment) -> AlertAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_active_assignment(self, alert_id: str) -> Optional[AlertAssignment]:
        stmt = (
            select(AlertAssignment)
            .where(
                and_(
                    AlertAssignment.alert_id == alert_id,
                    AlertAssignment.assignment_status == "ACTIVE",
                )
            )
            .order_by(desc(AlertAssignment.created_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_assignments(self, alert_id: str) -> List[AlertAssignment]:
        stmt = (
            select(AlertAssignment)
            .where(AlertAssignment.alert_id == alert_id)
            .order_by(desc(AlertAssignment.created_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ Comments & Revisions ------------------
    async def save_comment(self, comment: AlertInvestigationComment) -> AlertInvestigationComment:
        self.session.add(comment)
        await self.session.flush()
        return comment

    async def get_comment_by_id(self, comment_id: str) -> Optional[AlertInvestigationComment]:
        res = await self.session.execute(
            select(AlertInvestigationComment)
            .options(selectinload(AlertInvestigationComment.revisions))
            .where(AlertInvestigationComment.id == comment_id)
        )
        return res.scalar_one_or_none()

    async def list_comments(self, alert_id: str) -> List[AlertInvestigationComment]:
        stmt = (
            select(AlertInvestigationComment)
            .options(selectinload(AlertInvestigationComment.revisions))
            .where(AlertInvestigationComment.alert_id == alert_id)
            .order_by(AlertInvestigationComment.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_comment_revision(self, rev: AlertCommentRevision) -> AlertCommentRevision:
        self.session.add(rev)
        await self.session.flush()
        return rev

    # ------------------ Evidence ------------------
    async def save_evidence(self, ev: AlertManagementEvidence) -> AlertManagementEvidence:
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def list_evidence(self, alert_id: str) -> List[AlertManagementEvidence]:
        stmt = (
            select(AlertManagementEvidence)
            .where(AlertManagementEvidence.alert_id == alert_id)
            .order_by(desc(AlertManagementEvidence.uploaded_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ Disposition & Resolution ------------------
    async def save_disposition(self, disp: AlertDisposition) -> AlertDisposition:
        self.session.add(disp)
        await self.session.flush()
        return disp

    async def get_latest_disposition(self, alert_id: str, cycle: int) -> Optional[AlertDisposition]:
        stmt = (
            select(AlertDisposition)
            .where(
                and_(
                    AlertDisposition.alert_id == alert_id,
                    AlertDisposition.workflow_cycle == cycle,
                )
            )
            .order_by(desc(AlertDisposition.created_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_resolution_assessment(self, res_rec: AlertResolutionAssessment) -> AlertResolutionAssessment:
        self.session.add(res_rec)
        await self.session.flush()
        return res_rec

    async def get_latest_resolution_assessment(self, alert_id: str, cycle: int) -> Optional[AlertResolutionAssessment]:
        stmt = (
            select(AlertResolutionAssessment)
            .where(
                and_(
                    AlertResolutionAssessment.alert_id == alert_id,
                    AlertResolutionAssessment.workflow_cycle == cycle,
                )
            )
            .order_by(desc(AlertResolutionAssessment.assessed_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ------------------ Closure & Reopening ------------------
    async def save_closure(self, closure: AlertClosure) -> AlertClosure:
        self.session.add(closure)
        await self.session.flush()
        return closure

    async def list_closures(self, alert_id: str) -> List[AlertClosure]:
        stmt = (
            select(AlertClosure)
            .where(AlertClosure.alert_id == alert_id)
            .order_by(desc(AlertClosure.closed_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_reopening(self, reopening: AlertReopening) -> AlertReopening:
        self.session.add(reopening)
        await self.session.flush()
        return reopening

    async def list_reopenings(self, alert_id: str) -> List[AlertReopening]:
        stmt = (
            select(AlertReopening)
            .where(AlertReopening.alert_id == alert_id)
            .order_by(desc(AlertReopening.reopened_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ Work Queue & Analytics ------------------
    async def list_work_queue(
        self,
        current_state: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        assigned_role_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Tuple[AlertWorkflowState, AlertEvent]]:
        stmt = (
            select(AlertWorkflowState, AlertEvent)
            .join(AlertEvent, AlertWorkflowState.alert_id == AlertEvent.id)
            .order_by(desc(AlertWorkflowState.updated_at))
            .limit(limit)
            .offset(offset)
        )
        if current_state:
            stmt = stmt.where(AlertWorkflowState.current_state == current_state)
        if assigned_user_id:
            stmt = stmt.where(AlertWorkflowState.current_owner_user_id == assigned_user_id)
        if assigned_role_id:
            stmt = stmt.where(AlertWorkflowState.current_owner_role_id == assigned_role_id)
        if portfolio_id:
            stmt = stmt.where(AlertEvent.portfolio_id == portfolio_id)

        res = await self.session.execute(stmt)
        return list(res.all())

    async def get_management_summary_stats(self) -> Dict[str, Any]:
        tot = (await self.session.execute(select(func.count(AlertWorkflowState.id)))).scalar() or 0
        unack = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.acknowledgement_state == "UNACKNOWLEDGED"))).scalar() or 0
        ack = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.acknowledgement_state == "ACKNOWLEDGED"))).scalar() or 0
        unassigned = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.current_owner_user_id.is_(None)))).scalar() or 0
        assigned = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.current_owner_user_id.is_not(None)))).scalar() or 0
        investigating = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.current_state == "INVESTIGATING"))).scalar() or 0
        pending_info_act = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.current_state.in_(["PENDING_INFORMATION", "PENDING_ACTION"])))).scalar() or 0
        resolved_pend_close = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.current_state == "RESOLVED"))).scalar() or 0
        closed = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.current_state == "CLOSED"))).scalar() or 0
        reopened = (await self.session.execute(select(func.count(AlertWorkflowState.id)).where(AlertWorkflowState.current_state == "REOPENED"))).scalar() or 0

        # Status distribution
        st_res = await self.session.execute(
            select(AlertWorkflowState.current_state, func.count(AlertWorkflowState.id))
            .group_by(AlertWorkflowState.current_state)
        )
        dist = {row[0]: row[1] for row in st_res.all()}

        return {
            "total_alerts": tot,
            "unacknowledged_count": unack,
            "acknowledged_count": ack,
            "unassigned_count": unassigned,
            "assigned_count": assigned,
            "investigating_count": investigating,
            "pending_info_or_action_count": pending_info_act,
            "resolved_pending_closure_count": resolved_pend_close,
            "closed_count": closed,
            "reopened_count": reopened,
            "status_distribution": dist,
            "avg_acknowledgement_seconds": None,
            "avg_resolution_seconds": None,
        }

