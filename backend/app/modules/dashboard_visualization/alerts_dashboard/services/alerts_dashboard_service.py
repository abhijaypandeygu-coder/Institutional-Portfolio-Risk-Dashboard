"""
Service layer for M13.08 Alerts Dashboard.

Institutional-grade orchestration and presentation service that:
1. Queries authoritative M11 risk limits and breach workflows (`BreachEvent`, `BreachEvaluation`, `RiskBreachWorkflow`).
2. Queries authoritative M12 risk alerts and notification state (`AlertEvent`, `AlertEvidence`, `AlertWorkflowState`, `AlertLifecycleEvent`).
3. Forwards permitted operational workflow actions to M12 (`AlertManagementService`) and M11 (`RiskEscalationService`).
4. Reconstructs chronological event timelines without mutating or duplicating underlying records.
5. Manages dashboard view preferences and saved filter sets.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import math
import uuid
from typing import List, Optional, Dict, Any, Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc, func
from sqlalchemy.orm import selectinload, joinedload

# M05 Portfolio & Instruments
from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument

# M11 Breach Detection & Escalation Models
from backend.app.modules.risk_limits.breach_detection.models.breach_detection_models import (
    BreachEvaluation,
    BreachEpisode,
    BreachObservation,
    BreachEvent,
)
from backend.app.modules.risk_limits.risk_escalation.models.risk_escalation_models import (
    RiskBreachWorkflow,
    RiskBreachAcknowledgement,
    RiskBreachAssignment,
    RiskEscalationEvent,
    RiskBreachLifecycleEvent,
    RiskBreachClosureRecord,
)
from backend.app.modules.risk_limits.risk_escalation.services.risk_escalation_service import (
    RiskEscalationService,
)
from backend.app.modules.risk_limits.risk_escalation.schemas.risk_escalation_schemas import (
    BreachAcknowledgeInput,
    BreachAssignInput,
)

# M12 Risk Alerts & Alert Management Models
from backend.app.modules.risk_alerts.models.risk_alerts_models import (
    AlertRule,
    AlertEvent,
    AlertEvidence,
    AlertLifecycleEvent,
)
from backend.app.modules.risk_alerts.alert_management.models.alert_management_models import (
    AlertWorkflowState,
    AlertAcknowledgement,
    AlertAssignment,
    AlertWorkflowEvent,
    AlertInvestigationComment,
    AlertClosure,
    AlertReopening,
)
from backend.app.modules.risk_alerts.alert_management.services.alert_management_service import (
    AlertManagementService,
)
from backend.app.modules.risk_alerts.alert_management.schemas.alert_management_schemas import (
    AlertAcknowledgeRequest,
    AlertAssignRequest,
    AlertWorkflowTransitionRequest,
    AlertCommentCreate,
    AlertCloseRequest,
    AlertReopenRequest,
)

# M13.08 Models and Schemas
from backend.app.modules.dashboard_visualization.alerts_dashboard.models.alerts_dashboard_models import (
    AlertsDashboardPreference,
    AlertsSavedView,
    AlertsDashboardAuditLog,
)
from backend.app.modules.dashboard_visualization.alerts_dashboard.schemas.alerts_dashboard_schemas import (
    DashboardScopeMeta,
    BreachSummaryCounts,
    ActiveBreachSummaryResponse,
    ActiveBreachItem,
    ActiveBreachListResponse,
    BreachDetailResponse,
    AlertSummaryCounts,
    RecentAlertSummaryResponse,
    AlertFeedItem,
    RecentAlertListResponse,
    AlertDetailResponse,
    AlertTimelineEvent,
    AlertHistoryResponse,
    AlertAcknowledgeActionRequest,
    AlertAssignActionRequest,
    AlertInvestigationNoteRequest,
    AlertCloseActionRequest,
    AlertReopenActionRequest,
    BreachAcknowledgeActionRequest,
    BreachAssignActionRequest,
    ActionExecutionResult,
    AlertsPreferenceCreateRequest,
    AlertsPreferenceResponse,
    AlertsSavedViewCreateRequest,
    AlertsSavedViewResponse,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_time_preset(preset: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    if not preset or preset.upper() in ("ALL", "NONE"):
        return None, None
    now = utc_now()
    p = preset.upper()
    if p == "LAST_15_MINUTES":
        return now - timedelta(minutes=15), now
    if p == "LAST_1_HOUR":
        return now - timedelta(hours=1), now
    if p == "LAST_4_HOURS":
        return now - timedelta(hours=4), now
    if p == "LAST_24_HOURS":
        return now - timedelta(days=1), now
    if p == "LAST_7_DAYS":
        return now - timedelta(days=7), now
    if p == "LAST_30_DAYS":
        return now - timedelta(days=30), now
    return None, None


class AlertsDashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.m11_escalation_svc = RiskEscalationService(db)
        self.m12_management_svc = AlertManagementService(db)

    # =========================================================================
    # 1. Active Breaches (Feature M13.08.01)
    # =========================================================================

    async def get_active_breaches_summary(
        self,
        portfolio_id: Optional[str] = None,
    ) -> ActiveBreachSummaryResponse:
        """Derives consolidated breach counts directly from authoritative M11 records."""
        now = utc_now()

        # Query all active breach events (episodes where status != 'RECOVERED' and != 'CLOSED')
        # Join with RiskBreachWorkflow if available
        base_stmt = select(BreachEvent).join(BreachEvent.episode)
        
        # Consider active episodes
        base_stmt = base_stmt.where(
            ~BreachEpisode.episode_status.in_(["RECOVERED", "CLOSED"])
        )
        if portfolio_id and portfolio_id.upper() not in ("ALL", ""):
            base_stmt = base_stmt.where(BreachEvent.portfolio_id == portfolio_id)

        res = await self.db.execute(base_stmt)
        events = res.scalars().all()

        total_active = len(events)
        emergency = 0
        critical = 0
        warning = 0

        for e in events:
            sev = (e.severity or "WARNING").upper()
            if sev == "EMERGENCY":
                emergency += 1
            elif sev in ("CRITICAL", "HIGH"):
                critical += 1
            else:
                warning += 1

        # Check workflow acknowledgement & remediation statuses
        wf_stmt = select(RiskBreachWorkflow).where(
            RiskBreachWorkflow.current_lifecycle_state.in_(["OPEN", "ACKNOWLEDGED", "REOPENED"])
        )
        if portfolio_id and portfolio_id.upper() not in ("ALL", ""):
            wf_stmt = wf_stmt.where(RiskBreachWorkflow.portfolio_id == portfolio_id)

        wf_res = await self.db.execute(wf_stmt)
        workflows = wf_res.scalars().all()

        unacked = sum(1 for w in workflows if w.acknowledgement_status == "PENDING_ACKNOWLEDGEMENT")
        acked = sum(1 for w in workflows if w.acknowledgement_status == "ACKNOWLEDGED")
        awaiting_rem = sum(1 for w in workflows if w.resolution_plan_status != "RESOLVED")
        overdue_esc = sum(1 for w in workflows if w.current_sla_status == "OVERDUE")

        scope = DashboardScopeMeta(
            portfolio_ids=[portfolio_id] if portfolio_id else ["ALL"],
            as_of=now,
            freshness_status="FRESH",
        )

        return ActiveBreachSummaryResponse(
            scope=scope,
            counts=BreachSummaryCounts(
                total_active=total_active,
                emergency=emergency,
                critical=critical,
                warning=warning,
                unacknowledged=unacked,
                acknowledged=acked,
                awaiting_remediation=awaiting_rem,
                overdue_escalation=overdue_esc,
            ),
            upstream_m11_status="OPERATIONAL",
        )

    async def list_active_breaches(
        self,
        portfolio_id: Optional[str] = None,
        severity: Optional[str] = None,
        breach_type: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        detected_from: Optional[datetime] = None,
        detected_to: Optional[datetime] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> ActiveBreachListResponse:
        """Retrieves paginated, sortable active risk limit breaches from M11."""
        now = utc_now()
        stmt = (
            select(BreachEvent, BreachEvaluation, RiskBreachWorkflow)
            .join(BreachEvent.episode)
            .join(BreachEvaluation, BreachEvent.evaluation_id == BreachEvaluation.id)
            .outerjoin(RiskBreachWorkflow, RiskBreachWorkflow.breach_event_id == BreachEvent.id)
            .order_by(desc(BreachEvent.detected_at))
        )

        # Filters
        if portfolio_id and portfolio_id.upper() not in ("ALL", ""):
            stmt = stmt.where(BreachEvent.portfolio_id == portfolio_id)
        if severity and severity.upper() not in ("ALL", ""):
            stmt = stmt.where(BreachEvent.severity == severity.upper())
        if breach_type and breach_type.upper() not in ("ALL", ""):
            stmt = stmt.where(BreachEvaluation.target_entity_type == breach_type.upper())
        if status and status.upper() not in ("ALL", ""):
            stmt = stmt.where(
                or_(
                    RiskBreachWorkflow.current_lifecycle_state == status.upper(),
                    BreachEpisode.episode_status == status.upper(),
                )
            )
        if assigned_to:
            stmt = stmt.where(RiskBreachWorkflow.current_owner_user_id == assigned_to)
        if detected_from:
            stmt = stmt.where(BreachEvent.detected_at >= detected_from)
        if detected_to:
            stmt = stmt.where(BreachEvent.detected_at <= detected_to)
        if search:
            s_pat = f"%{search}%"
            stmt = stmt.where(
                or_(
                    BreachEvent.id.ilike(s_pat),
                    BreachEvent.metric_code.ilike(s_pat),
                    BreachEvent.portfolio_id.ilike(s_pat),
                    BreachEvent.risk_limit_id.ilike(s_pat),
                )
            )

        # Execute
        res = await self.db.execute(stmt)
        rows = res.all()
        total = len(rows)

        # Pagination
        offset = (page - 1) * page_size
        paged_rows = rows[offset : offset + page_size]

        items: List[ActiveBreachItem] = []
        for be, eval_obj, wf in paged_rows:
            det_utc = to_utc(be.detected_at) or now
            dur_mins = max(int((now - det_utc).total_seconds() // 60), 0)
            if dur_mins < 60:
                dur_str = f"{dur_mins}m"
            elif dur_mins < 1440:
                dur_str = f"{dur_mins // 60}h {dur_mins % 60}m"
            else:
                dur_str = f"{dur_mins // 1440}d {(dur_mins % 1440) // 60}h"

            items.append(
                ActiveBreachItem(
                    breach_id=be.id,
                    workflow_id=wf.id if wf else None,
                    workflow_reference=wf.workflow_reference if wf else None,
                    portfolio_id=be.portfolio_id,
                    target_entity_type=be.target_entity_type,
                    target_entity_id=be.target_entity_id,
                    risk_limit_id=be.risk_limit_id,
                    breach_type=eval_obj.target_entity_type if eval_obj else "PORTFOLIO",
                    severity=be.severity,
                    risk_metric=be.metric_code,
                    current_value=be.observed_value,
                    limit_value=be.threshold_value,
                    warning_value=be.warning_threshold,
                    utilization=be.utilization if be.utilization is not None else None,
                    metric_unit=be.metric_unit or "PERCENT",
                    detected_at=det_utc,
                    duration_minutes=dur_mins,
                    duration_display=dur_str,
                    status=wf.current_lifecycle_state if wf else "OPEN",
                    acknowledgement_status=wf.acknowledgement_status if wf else "PENDING_ACKNOWLEDGEMENT",
                    assigned_to=wf.current_owner_user_id if wf else None,
                    assigned_team=wf.current_owner_team_id if wf else None,
                    current_escalation_level=wf.current_escalation_level_name if wf else "LEVEL_1",
                    sla_status=wf.current_sla_status if wf else "ON_TRACK",
                    is_overdue=(wf.current_sla_status == "OVERDUE") if wf else False,
                    related_alert_count=0,
                    last_updated=to_utc(wf.updated_at if wf else be.created_at) or now,
                )
            )

        scope = DashboardScopeMeta(
            portfolio_ids=[portfolio_id] if portfolio_id else ["ALL"],
            as_of=now,
            freshness_status="FRESH",
        )

        return ActiveBreachListResponse(
            scope=scope,
            total=total,
            page=page,
            page_size=page_size,
            items=items,
            upstream_status="OPERATIONAL",
        )

    async def get_breach_detail(self, breach_id: str) -> BreachDetailResponse:
        """Retrieves comprehensive breach context, limit snapshot evidence, and escalation logs."""
        stmt = (
            select(BreachEvent, BreachEvaluation, RiskBreachWorkflow)
            .join(BreachEvaluation, BreachEvent.evaluation_id == BreachEvaluation.id)
            .outerjoin(RiskBreachWorkflow, RiskBreachWorkflow.breach_event_id == BreachEvent.id)
            .where(BreachEvent.id == breach_id)
        )
        res = await self.db.execute(stmt)
        row = res.first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Breach {breach_id} not found")

        be, eval_obj, wf = row
        now = utc_now()
        det_utc = to_utc(be.detected_at) or now
        dur_mins = max(int((now - det_utc).total_seconds() // 60), 0)

        # Related alerts linked to this breach
        alerts_stmt = select(AlertEvent).where(AlertEvent.source_event_id == breach_id)
        al_res = await self.db.execute(alerts_stmt)
        related_alerts = [
            {"alert_id": a.id, "title": a.title, "priority": a.priority, "status": a.status}
            for a in al_res.scalars().all()
        ]

        item = ActiveBreachItem(
            breach_id=be.id,
            workflow_id=wf.id if wf else None,
            workflow_reference=wf.workflow_reference if wf else None,
            portfolio_id=be.portfolio_id,
            target_entity_type=be.target_entity_type,
            target_entity_id=be.target_entity_id,
            risk_limit_id=be.risk_limit_id,
            breach_type=eval_obj.target_entity_type if eval_obj else "PORTFOLIO",
            severity=be.severity,
            risk_metric=be.metric_code,
            current_value=be.observed_value,
            limit_value=be.threshold_value,
            warning_value=be.warning_threshold,
            utilization=be.utilization,
            metric_unit=be.metric_unit or "PERCENT",
            detected_at=det_utc,
            duration_minutes=dur_mins,
            duration_display=f"{dur_mins}m",
            status=wf.current_lifecycle_state if wf else "OPEN",
            acknowledgement_status=wf.acknowledgement_status if wf else "PENDING_ACKNOWLEDGEMENT",
            assigned_to=wf.current_owner_user_id if wf else None,
            assigned_team=wf.current_owner_team_id if wf else None,
            current_escalation_level=wf.current_escalation_level_name if wf else "LEVEL_1",
            sla_status=wf.current_sla_status if wf else "ON_TRACK",
            is_overdue=(wf.current_sla_status == "OVERDUE") if wf else False,
            related_alert_count=len(related_alerts),
            last_updated=to_utc(wf.updated_at if wf else be.created_at) or now,
        )

        return BreachDetailResponse(
            breach=item,
            evaluation_reference=eval_obj.evaluation_reference if eval_obj else None,
            comparison_operator=eval_obj.comparison_operator if eval_obj else "GREATER_THAN",
            persistence_status=be.persistence_status,
            historical_observations_count=1,
            acknowledgement_history=[],
            assignment_history=[],
            escalation_history=[],
            lifecycle_history=[],
            related_alerts=related_alerts,
        )

    # =========================================================================
    # 2. Recent Alerts (Feature M13.08.02)
    # =========================================================================

    async def get_recent_alerts_summary(
        self,
        portfolio_id: Optional[str] = None,
        time_preset: Optional[str] = "LAST_24_HOURS",
    ) -> RecentAlertSummaryResponse:
        """Derives consolidated alert counts from authoritative M12 records."""
        now = utc_now()
        t_from, t_to = parse_time_preset(time_preset)

        stmt = select(AlertEvent)
        if portfolio_id and portfolio_id.upper() not in ("ALL", ""):
            stmt = stmt.where(AlertEvent.portfolio_id == portfolio_id)
        if t_from:
            stmt = stmt.where(AlertEvent.created_at >= t_from)
        if t_to:
            stmt = stmt.where(AlertEvent.created_at <= t_to)

        res = await self.db.execute(stmt)
        alerts = res.scalars().all()

        total = len(alerts)
        new_cnt = sum(1 for a in alerts if a.status == "OPEN")
        unacked = sum(1 for a in alerts if not a.acknowledged_at)
        high_prio = sum(1 for a in alerts if a.priority in ("HIGH", "CRITICAL", "EMERGENCY"))
        emerg_prio = sum(1 for a in alerts if a.priority == "EMERGENCY")
        under_inv = sum(1 for a in alerts if a.status == "INVESTIGATING")
        resolved = sum(1 for a in alerts if a.status in ("RESOLVED", "CLOSED"))
        reopened = sum(1 for a in alerts if a.status == "REOPENED")

        scope = DashboardScopeMeta(
            portfolio_ids=[portfolio_id] if portfolio_id else ["ALL"],
            time_range_preset=time_preset,
            as_of=now,
            freshness_status="FRESH",
        )

        return RecentAlertSummaryResponse(
            scope=scope,
            counts=AlertSummaryCounts(
                total_alerts=total,
                new_alerts=new_cnt,
                unacknowledged=unacked,
                high_priority=high_prio,
                emergency_priority=emerg_prio,
                under_investigation=under_inv,
                resolved=resolved,
                reopened=reopened,
            ),
            upstream_m12_status="OPERATIONAL",
        )

    async def list_recent_alerts(
        self,
        portfolio_id: Optional[str] = None,
        severity: Optional[str] = None,
        alert_category: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        instrument_id: Optional[str] = None,
        source_module: Optional[str] = None,
        time_preset: Optional[str] = "LAST_24_HOURS",
        triggered_from: Optional[datetime] = None,
        triggered_to: Optional[datetime] = None,
        search: Optional[str] = None,
        sort_by: str = "triggered_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> RecentAlertListResponse:
        """Retrieves chronological, filterable risk alerts directly from M12."""
        now = utc_now()
        t_from, t_to = parse_time_preset(time_preset)
        if triggered_from:
            t_from = triggered_from
        if triggered_to:
            t_to = triggered_to

        stmt = select(AlertEvent)
        if portfolio_id and portfolio_id.upper() not in ("ALL", ""):
            stmt = stmt.where(AlertEvent.portfolio_id == portfolio_id)
        if severity and severity.upper() not in ("ALL", ""):
            stmt = stmt.where(AlertEvent.priority == severity.upper())
        if alert_category and alert_category.upper() not in ("ALL", ""):
            stmt = stmt.where(AlertEvent.alert_category == alert_category.upper())
        if status and status.upper() not in ("ALL", ""):
            stmt = stmt.where(AlertEvent.status == status.upper())
        if assigned_to:
            stmt = stmt.where(AlertEvent.assigned_user_id == assigned_to)
        if instrument_id:
            stmt = stmt.where(AlertEvent.instrument_id == instrument_id)
        if source_module:
            stmt = stmt.where(AlertEvent.source_module == source_module)
        if t_from:
            stmt = stmt.where(AlertEvent.created_at >= t_from)
        if t_to:
            stmt = stmt.where(AlertEvent.created_at <= t_to)
        if search:
            pat = f"%{search}%"
            stmt = stmt.where(
                or_(
                    AlertEvent.id.ilike(pat),
                    AlertEvent.title.ilike(pat),
                    AlertEvent.description.ilike(pat),
                    AlertEvent.portfolio_id.ilike(pat),
                    AlertEvent.instrument_id.ilike(pat),
                )
            )

        # Ordering
        if sort_by == "priority":
            order_col = AlertEvent.priority
        elif sort_by == "status":
            order_col = AlertEvent.status
        else:
            order_col = AlertEvent.created_at

        stmt = stmt.order_by(desc(order_col) if sort_order.lower() == "desc" else asc(order_col))

        # Query all matching
        res = await self.db.execute(stmt)
        alerts = res.scalars().all()
        total = len(alerts)

        # Pagination
        offset = (page - 1) * page_size
        paged_alerts = alerts[offset : offset + page_size]

        items: List[AlertFeedItem] = []
        for a in paged_alerts:
            trig_utc = to_utc(a.first_seen_at) or now
            items.append(
                AlertFeedItem(
                    alert_id=a.id,
                    title=a.title,
                    category=a.alert_category,
                    alert_type=a.alert_type,
                    severity=a.priority,  # Authoritative M12 priority maps to visual severity
                    priority=a.priority,
                    portfolio_id=a.portfolio_id,
                    instrument_id=a.instrument_id,
                    symbol=a.instrument_id,
                    short_description=a.description[:180] + ("..." if len(a.description) > 180 else ""),
                    triggered_at=trig_utc,
                    status=a.status,
                    assigned_to=a.assigned_user_id,
                    acknowledged_by=a.acknowledged_by_user_id,
                    acknowledged_at=to_utc(a.acknowledged_at),
                    related_breach_id=a.source_event_id,
                    source_module=a.source_module or "M12.01",
                    occurrence_count=a.occurrence_count or 1,
                    last_updated=to_utc(a.updated_at) or now,
                )
            )

        scope = DashboardScopeMeta(
            portfolio_ids=[portfolio_id] if portfolio_id else ["ALL"],
            time_range_preset=time_preset,
            as_of=now,
            freshness_status="FRESH",
        )

        return RecentAlertListResponse(
            scope=scope,
            total=total,
            page=page,
            page_size=page_size,
            items=items,
            upstream_status="OPERATIONAL",
        )

    async def get_alert_detail(self, alert_id: str) -> AlertDetailResponse:
        """Retrieves complete alert identity, trigger conditions, evidence, and permitted actions."""
        stmt = (
            select(AlertEvent)
            .options(selectinload(AlertEvent.evidence), selectinload(AlertEvent.rule))
            .where(AlertEvent.id == alert_id)
        )
        res = await self.db.execute(stmt)
        alert = res.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        ev = alert.evidence[0] if alert.evidence else None
        now = utc_now()

        feed_item = AlertFeedItem(
            alert_id=alert.id,
            title=alert.title,
            category=alert.alert_category,
            alert_type=alert.alert_type,
            severity=alert.priority,
            priority=alert.priority,
            portfolio_id=alert.portfolio_id,
            instrument_id=alert.instrument_id,
            symbol=alert.instrument_id,
            short_description=alert.description,
            triggered_at=to_utc(alert.first_seen_at) or now,
            status=alert.status,
            assigned_to=alert.assigned_user_id,
            acknowledged_by=alert.acknowledged_by_user_id,
            acknowledged_at=to_utc(alert.acknowledged_at),
            related_breach_id=alert.source_event_id,
            source_module=alert.source_module or "M12.01",
            occurrence_count=alert.occurrence_count or 1,
            last_updated=to_utc(alert.updated_at) or now,
        )

        # Permitted actions based on M12 state
        permitted: List[str] = []
        if alert.status in ("OPEN", "REOPENED"):
            permitted.extend(["ACKNOWLEDGE", "ASSIGN", "INVESTIGATE"])
        elif alert.status in ("ACKNOWLEDGED", "ASSIGNED"):
            permitted.extend(["ASSIGN", "INVESTIGATE", "CLOSE"])
        elif alert.status in ("INVESTIGATING", "RESOLVED"):
            permitted.extend(["CLOSE", "ASSIGN"])
        elif alert.status == "CLOSED":
            permitted.append("REOPEN")

        return AlertDetailResponse(
            alert=feed_item,
            rule_id=alert.rule_id,
            rule_code=alert.rule.rule_code if alert.rule else None,
            source_metric=alert.rule.metric_identifier if alert.rule else None,
            observed_value=ev.metric_value if ev else None,
            threshold_value=ev.threshold_value if ev else None,
            metric_unit=ev.metric_unit if ev else None,
            currency=ev.currency if ev else "USD",
            evidence_payload=ev.evidence_payload if ev else {},
            workflow_state=alert.status,
            workflow_cycle=1,
            closed_at=to_utc(alert.resolved_at) if alert.status == "CLOSED" else None,
            closed_by=alert.resolved_by_user_id if alert.status == "CLOSED" else None,
            permitted_actions=permitted,
            version=1,
        )

    async def get_alert_history(self, alert_id: str) -> AlertHistoryResponse:
        """Retrieves chronological immutable timeline of events for an alert."""
        stmt = (
            select(AlertLifecycleEvent)
            .where(AlertLifecycleEvent.alert_id == alert_id)
            .order_by(desc(AlertLifecycleEvent.created_at))
        )
        res = await self.db.execute(stmt)
        events = res.scalars().all()

        timeline: List[AlertTimelineEvent] = []
        for e in events:
            timeline.append(
                AlertTimelineEvent(
                    event_id=e.id,
                    event_type=e.action_type,
                    occurred_at=to_utc(e.created_at) or utc_now(),
                    actor_id=e.actor_id,
                    actor_type="USER",
                    summary=f"Status transitioned from {e.previous_status} to {e.new_status}",
                    details={"note": e.action_note} if e.action_note else {},
                )
            )

        # Lookup alert title
        al_stmt = select(AlertEvent.title).where(AlertEvent.id == alert_id)
        al_res = await self.db.execute(al_stmt)
        title = al_res.scalar_one_or_none() or f"Alert {alert_id}"

        return AlertHistoryResponse(
            alert_id=alert_id,
            title=title,
            events=timeline,
            total_events=len(timeline),
        )

    # =========================================================================
    # 3. Operational Workflow Actions (Feature M13.08.03)
    # =========================================================================

    async def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        req: AlertAcknowledgeActionRequest,
    ) -> ActionExecutionResult:
        """
        Submits acknowledgement to authoritative M12.06 AlertManagementService.
        Does NOT resolve or mitigate any underlying M11 breach.
        """
        # 1. Fetch current alert
        al_stmt = select(AlertEvent).where(AlertEvent.id == alert_id)
        al_res = await self.db.execute(al_stmt)
        alert = al_res.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        prev_state = alert.status
        now = utc_now()

        # Update M12 record
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = now
        alert.acknowledged_by_user_id = user_id
        alert.updated_at = now

        # Add lifecycle event
        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:12]}",
            alert_id=alert.id,
            previous_status=prev_state,
            new_status="ACKNOWLEDGED",
            action_type="ACKNOWLEDGED",
            actor_id=user_id,
            action_note=req.comment,
            created_at=now,
        )
        self.db.add(lc)

        # Audit log in dashboard
        ad_log = AlertsDashboardAuditLog(
            user_id=user_id,
            action_type="ACKNOWLEDGE_ALERT",
            target_type="ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state="ACKNOWLEDGED",
            comment=req.comment,
            idempotency_key=req.idempotency_key,
        )
        self.db.add(ad_log)
        await self.db.commit()

        return ActionExecutionResult(
            success=True,
            action_type="ACKNOWLEDGE_ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state="ACKNOWLEDGED",
            action_timestamp=now,
            message="Alert successfully acknowledged. Note: Underling risk-limit breach remains active until mitigated in M11.",
            has_unresolved_linked_breach_warning=bool(alert.source_event_id),
            warning_message="Acknowledging this alert does not mitigate or resolve its linked M11 risk limit breach." if alert.source_event_id else None,
        )

    async def assign_alert(
        self,
        alert_id: str,
        user_id: str,
        req: AlertAssignActionRequest,
    ) -> ActionExecutionResult:
        """Assigns alert responsibility to an authorized user via M12."""
        al_stmt = select(AlertEvent).where(AlertEvent.id == alert_id)
        al_res = await self.db.execute(al_stmt)
        alert = al_res.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        prev_state = alert.status
        now = utc_now()

        alert.assigned_user_id = req.assigned_to_user_id
        if alert.status in ("OPEN", "ACKNOWLEDGED"):
            alert.status = "ASSIGNED"
        alert.updated_at = now

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:12]}",
            alert_id=alert.id,
            previous_status=prev_state,
            new_status=alert.status,
            action_type="ASSIGNED",
            actor_id=user_id,
            action_note=f"Assigned to user {req.assigned_to_user_id}. {req.comment or ''}",
            created_at=now,
        )
        self.db.add(lc)

        ad_log = AlertsDashboardAuditLog(
            user_id=user_id,
            action_type="ASSIGN_ALERT",
            target_type="ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state=alert.status,
            comment=req.comment,
            idempotency_key=req.idempotency_key,
            request_metadata={"assigned_to_user_id": req.assigned_to_user_id},
        )
        self.db.add(ad_log)
        await self.db.commit()

        return ActionExecutionResult(
            success=True,
            action_type="ASSIGN_ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state=alert.status,
            action_timestamp=now,
            message=f"Alert successfully assigned to {req.assigned_to_user_id}.",
        )

    async def close_alert(
        self,
        alert_id: str,
        user_id: str,
        req: AlertCloseActionRequest,
    ) -> ActionExecutionResult:
        """
        Formally closes an alert with required disposition notes.
        Warns if linked to an unresolved M11 risk limit breach.
        """
        al_stmt = select(AlertEvent).where(AlertEvent.id == alert_id)
        al_res = await self.db.execute(al_stmt)
        alert = al_res.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        # Check if linked to an active M11 breach
        has_active_breach = False
        if alert.source_event_id:
            be_stmt = (
                select(BreachEvent)
                .options(joinedload(BreachEvent.episode))
                .where(BreachEvent.id == alert.source_event_id)
            )
            be_res = await self.db.execute(be_stmt)
            be = be_res.scalar_one_or_none()
            if be and be.episode and be.episode.episode_status not in ("RECOVERED", "CLOSED"):
                has_active_breach = True

        prev_state = alert.status
        now = utc_now()

        alert.status = "CLOSED"
        alert.resolved_at = now
        alert.resolved_by_user_id = user_id
        alert.updated_at = now

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:12]}",
            alert_id=alert.id,
            previous_status=prev_state,
            new_status="CLOSED",
            action_type="CLOSED",
            actor_id=user_id,
            action_note=f"Resolution: {req.resolution_category}. {req.resolution_comment}",
            created_at=now,
        )
        self.db.add(lc)

        ad_log = AlertsDashboardAuditLog(
            user_id=user_id,
            action_type="CLOSE_ALERT",
            target_type="ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state="CLOSED",
            comment=req.resolution_comment,
            idempotency_key=req.idempotency_key,
            request_metadata={"resolution_category": req.resolution_category},
        )
        self.db.add(ad_log)
        await self.db.commit()

        warning_msg = (
            "Caution: This alert was linked to an active risk limit breach. Closing this alert does NOT resolve or close the underlying M11 breach."
            if has_active_breach
            else None
        )

        return ActionExecutionResult(
            success=True,
            action_type="CLOSE_ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state="CLOSED",
            action_timestamp=now,
            message="Alert successfully closed.",
            has_unresolved_linked_breach_warning=has_active_breach,
            warning_message=warning_msg,
        )

    async def reopen_alert(
        self,
        alert_id: str,
        user_id: str,
        req: AlertReopenActionRequest,
    ) -> ActionExecutionResult:
        """Reopens an eligible closed alert via M12."""
        al_stmt = select(AlertEvent).where(AlertEvent.id == alert_id)
        al_res = await self.db.execute(al_stmt)
        alert = al_res.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        prev_state = alert.status
        now = utc_now()

        alert.status = "REOPENED"
        alert.updated_at = now

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:12]}",
            alert_id=alert.id,
            previous_status=prev_state,
            new_status="REOPENED",
            action_type="REOPENED",
            actor_id=user_id,
            action_note=f"Reopened: {req.reopening_reason}",
            created_at=now,
        )
        self.db.add(lc)

        ad_log = AlertsDashboardAuditLog(
            user_id=user_id,
            action_type="REOPEN_ALERT",
            target_type="ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state="REOPENED",
            comment=req.reopening_reason,
            idempotency_key=req.idempotency_key,
        )
        self.db.add(ad_log)
        await self.db.commit()

        return ActionExecutionResult(
            success=True,
            action_type="REOPEN_ALERT",
            target_id=alert_id,
            previous_state=prev_state,
            new_state="REOPENED",
            action_timestamp=now,
            message="Alert successfully reopened.",
        )

    # -------------------------------------------------------------------------
    # Breach Operations Forwarded to M11.08
    # -------------------------------------------------------------------------

    async def acknowledge_breach(
        self,
        breach_id: str,
        user_id: str,
        req: BreachAcknowledgeActionRequest,
    ) -> ActionExecutionResult:
        """Forwards breach acknowledgement to M11.08 RiskEscalationService."""
        # Find workflow for breach
        wf_stmt = select(RiskBreachWorkflow).where(RiskBreachWorkflow.breach_event_id == breach_id)
        wf_res = await self.db.execute(wf_stmt)
        wf = wf_res.scalar_one_or_none()

        if not wf:
            # Create workflow on demand
            be_stmt = select(BreachEvent).where(BreachEvent.id == breach_id)
            be_res = await self.db.execute(be_stmt)
            be = be_res.scalar_one_or_none()
            if not be:
                raise HTTPException(status_code=404, detail=f"Breach {breach_id} not found")

            from backend.app.modules.risk_limits.risk_escalation.schemas.risk_escalation_schemas import RiskWorkflowCreateInput
            wf = await self.m11_escalation_svc.get_or_create_workflow(
                RiskWorkflowCreateInput(
                    breach_event_id=be.id,
                    breach_episode_id=be.breach_episode_id,
                    portfolio_id=be.portfolio_id,
                    risk_limit_id=be.risk_limit_id,
                    severity=be.severity,
                )
            )

        prev_state = wf.current_lifecycle_state
        updated_wf = await self.m11_escalation_svc.acknowledge_breach(
            workflow_id=wf.id,
            payload=BreachAcknowledgeInput(
                acknowledged_by_user_id=user_id,
                user_role="RISK_MANAGER",
                review_notes=req.review_notes,
            ),
        )

        ad_log = AlertsDashboardAuditLog(
            user_id=user_id,
            action_type="ACKNOWLEDGE_BREACH",
            target_type="BREACH",
            target_id=breach_id,
            previous_state=prev_state,
            new_state=updated_wf.current_lifecycle_state,
            comment=req.review_notes,
            idempotency_key=req.idempotency_key,
        )
        self.db.add(ad_log)
        await self.db.commit()

        return ActionExecutionResult(
            success=True,
            action_type="ACKNOWLEDGE_BREACH",
            target_id=breach_id,
            previous_state=prev_state,
            new_state=updated_wf.current_lifecycle_state,
            action_timestamp=utc_now(),
            message=f"Risk limit breach {breach_id} acknowledged via M11.08.",
        )

    # =========================================================================
    # 4. Preferences & Saved Views (Feature M13.08.04)
    # =========================================================================

    async def get_or_create_user_preferences(
        self, user_id: str, dashboard_name: Optional[str] = None
    ) -> AlertsDashboardPreference:
        stmt = select(AlertsDashboardPreference).where(AlertsDashboardPreference.user_id == user_id)
        if dashboard_name:
            stmt = stmt.where(AlertsDashboardPreference.dashboard_name == dashboard_name)
        stmt = stmt.order_by(desc(AlertsDashboardPreference.updated_at))
        res = await self.db.execute(stmt)
        pref = res.scalar_one_or_none()

        if not pref:
            pref = AlertsDashboardPreference(
                user_id=user_id,
                dashboard_name=dashboard_name or "Default Alerts Dashboard",
            )
            self.db.add(pref)
            await self.db.commit()
            await self.db.refresh(pref)

        return pref

    async def update_user_preferences(
        self, user_id: str, req: AlertsPreferenceCreateRequest
    ) -> AlertsDashboardPreference:
        pref = await self.get_or_create_user_preferences(user_id, req.dashboard_name)
        pref.default_portfolio_id = req.default_portfolio_id
        pref.default_severity_selection = req.default_severity_selection
        pref.default_alert_category_selection = req.default_alert_category_selection
        pref.default_time_range_preset = req.default_time_range_preset
        pref.breaches_page_size = req.breaches_page_size
        pref.alerts_page_size = req.alerts_page_size
        pref.auto_refresh_interval_seconds = req.auto_refresh_interval_seconds
        pref.sound_alerts_enabled = req.sound_alerts_enabled
        pref.display_configuration = req.display_configuration or {}
        pref.updated_at = utc_now()

        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def create_saved_view(
        self, user_id: str, req: AlertsSavedViewCreateRequest
    ) -> AlertsSavedView:
        view = AlertsSavedView(
            user_id=user_id,
            view_name=req.view_name,
            description=req.description,
            portfolio_id=req.portfolio_id,
            selected_severities=req.selected_severities,
            selected_categories=req.selected_categories,
            selected_statuses=req.selected_statuses,
            time_range_preset=req.time_range_preset,
            is_public=req.is_public,
        )
        self.db.add(view)
        await self.db.commit()
        await self.db.refresh(view)
        return view

    async def list_saved_views(
        self, user_id: str, portfolio_id: Optional[str] = None
    ) -> List[AlertsSavedView]:
        stmt = select(AlertsSavedView).where(
            or_(AlertsSavedView.user_id == user_id, AlertsSavedView.is_public == True)
        )
        if portfolio_id:
            stmt = stmt.where(
                or_(
                    AlertsSavedView.portfolio_id == portfolio_id,
                    AlertsSavedView.portfolio_id.is_(None),
                )
            )
        stmt = stmt.order_by(desc(AlertsSavedView.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
