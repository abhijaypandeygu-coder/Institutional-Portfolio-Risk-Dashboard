"""
Repository layer for M12 Risk Alerts.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_alerts.models.risk_alerts_models import (
    AlertRule,
    AlertRuleVersion,
    AlertThresholdDefinition,
    AlertThresholdState,
    AlertThresholdTransition,
    AlertEvent,
    AlertEvidence,
    AlertLifecycleEvent,
    NotificationPreference,
    NotificationMessage,
    NotificationDeliveryAttempt,
    AlertAuditLog,
)


class RiskAlertsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_rule_by_code(self, rule_code: str) -> Optional[AlertRule]:
        self.db.expire_all()
        stmt = (
            select(AlertRule)
            .where(AlertRule.rule_code == rule_code)
            .options(
                selectinload(AlertRule.versions).selectinload(AlertRuleVersion.thresholds),
                selectinload(AlertRule.states),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_rule_by_id(self, rule_id: str) -> Optional[AlertRule]:
        self.db.expire_all()
        stmt = (
            select(AlertRule)
            .where(AlertRule.id == rule_id)
            .options(
                selectinload(AlertRule.versions).selectinload(AlertRuleVersion.thresholds),
                selectinload(AlertRule.states),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_rules(self, metric_category: Optional[str] = None) -> List[AlertRule]:
        self.db.expire_all()
        stmt = select(AlertRule).order_by(desc(AlertRule.created_at))
        if metric_category:
            stmt = stmt.where(AlertRule.metric_category == metric_category)
        stmt = stmt.options(
            selectinload(AlertRule.versions).selectinload(AlertRuleVersion.thresholds)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_rule(self, rule: AlertRule) -> AlertRule:
        self.db.add(rule)
        await self.db.flush()
        return rule

    async def get_threshold_state(self, rule_id: str, portfolio_id: str) -> Optional[AlertThresholdState]:
        self.db.expire_all()
        stmt = select(AlertThresholdState).where(
            and_(AlertThresholdState.rule_id == rule_id, AlertThresholdState.portfolio_id == portfolio_id)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_threshold_state(self, state: AlertThresholdState) -> AlertThresholdState:
        self.db.add(state)
        await self.db.flush()
        return state

    async def add_threshold_transition(self, trans: AlertThresholdTransition) -> AlertThresholdTransition:
        self.db.add(trans)
        await self.db.flush()
        return trans

    async def get_alert_by_id(self, alert_id: str) -> Optional[AlertEvent]:
        self.db.expire_all()
        stmt = (
            select(AlertEvent)
            .where(AlertEvent.id == alert_id)
            .options(
                selectinload(AlertEvent.evidence),
                selectinload(AlertEvent.lifecycle_events),
                selectinload(AlertEvent.notifications),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_alert_by_dedup_key(self, dedup_key: str) -> Optional[AlertEvent]:
        self.db.expire_all()
        stmt = (
            select(AlertEvent)
            .where(
                and_(
                    AlertEvent.deduplication_key == dedup_key,
                    AlertEvent.status.in_(["OPEN", "ACKNOWLEDGED", "ASSIGNED", "INVESTIGATING"]),
                )
            )
            .options(selectinload(AlertEvent.evidence))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_alert(self, alert: AlertEvent) -> AlertEvent:
        self.db.add(alert)
        await self.db.flush()
        return alert

    async def add_evidence(self, ev: AlertEvidence) -> AlertEvidence:
        self.db.add(ev)
        await self.db.flush()
        return ev

    async def add_lifecycle_event(self, ev: AlertLifecycleEvent) -> AlertLifecycleEvent:
        self.db.add(ev)
        await self.db.flush()
        return ev

    async def add_notification(self, notif: NotificationMessage) -> NotificationMessage:
        self.db.add(notif)
        await self.db.flush()
        return notif

    async def list_alerts(
        self,
        portfolio_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AlertEvent]:
        stmt = (
            select(AlertEvent)
            .order_by(desc(AlertEvent.created_at))
            .options(selectinload(AlertEvent.evidence))
        )
        if portfolio_id:
            stmt = stmt.where(AlertEvent.portfolio_id == portfolio_id)
        if status:
            stmt = stmt.where(AlertEvent.status == status)
        if priority:
            stmt = stmt.where(AlertEvent.priority == priority)
        if category:
            stmt = stmt.where(AlertEvent.alert_category == category)
        stmt = stmt.offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_user_preference(self, user_id: str) -> Optional[NotificationPreference]:
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_user_preference(self, pref: NotificationPreference) -> NotificationPreference:
        self.db.add(pref)
        await self.db.flush()
        return pref

    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """Aggregate stats for alert overview."""
        stmt = select(AlertEvent.status, AlertEvent.priority, AlertEvent.alert_category)
        res = await self.db.execute(stmt)
        rows = res.all()

        total = len(rows)
        open_c = sum(1 for r in rows if r[0] == "OPEN")
        ack_c = sum(1 for r in rows if r[0] == "ACKNOWLEDGED")
        res_c = sum(1 for r in rows if r[0] in ["RESOLVED", "CLOSED"])

        prio_map = {"INFORMATIONAL": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "EMERGENCY": 0}
        cat_map: Dict[str, int] = {}

        unack_crit = 0
        for r in rows:
            st, pr, cat = r[0], r[1], r[2]
            if pr in prio_map:
                prio_map[pr] += 1
            cat_map[cat] = cat_map.get(cat, 0) + 1
            if pr in ["CRITICAL", "EMERGENCY"] and st == "OPEN":
                unack_crit += 1

        return {
            "total_active_alerts": total - res_c,
            "open_alerts": open_c,
            "acknowledged_alerts": ack_c,
            "resolved_alerts": res_c,
            "priority_breakdown": prio_map,
            "category_breakdown": cat_map,
            "unacknowledged_critical_count": unack_crit,
        }
