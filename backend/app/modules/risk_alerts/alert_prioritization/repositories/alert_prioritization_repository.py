"""
Async SQLAlchemy repository for M12.05 — Alert Prioritization.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_alerts.alert_prioritization.models.alert_prioritization_models import (
    AlertPriorityPolicy,
    AlertGroup,
    AlertGroupMember,
    AlertPriorityEvaluation,
    AlertPriorityHistory,
    AlertDeduplicationRecord,
    AlertOccurrence,
    AlertEscalationEvent,
)


class AlertPrioritizationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------ Policy Operations ------------------
    async def create_policy(self, policy: AlertPriorityPolicy) -> AlertPriorityPolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_policy_by_id(self, policy_id: str) -> Optional[AlertPriorityPolicy]:
        res = await self.session.execute(
            select(AlertPriorityPolicy).where(AlertPriorityPolicy.id == policy_id)
        )
        return res.scalar_one_or_none()

    async def get_applicable_policy(
        self,
        category: Optional[str] = None,
        event_type: Optional[str] = None,
        source_module: Optional[str] = None,
    ) -> Optional[AlertPriorityPolicy]:
        """
        Finds the most specific enabled policy (matching category & event_type),
        falling back to default.
        """
        stmt = (
            select(AlertPriorityPolicy)
            .where(AlertPriorityPolicy.enabled.is_(True))
            .order_by(
                desc(AlertPriorityPolicy.alert_category == category),
                desc(AlertPriorityPolicy.event_type == event_type),
                desc(AlertPriorityPolicy.policy_version),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_policies(self, enabled_only: bool = False) -> List[AlertPriorityPolicy]:
        stmt = select(AlertPriorityPolicy).order_by(desc(AlertPriorityPolicy.created_at))
        if enabled_only:
            stmt = stmt.where(AlertPriorityPolicy.enabled.is_(True))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ Group Operations ------------------
    async def get_group_by_key(self, group_key: str) -> Optional[AlertGroup]:
        res = await self.session.execute(
            select(AlertGroup)
            .options(selectinload(AlertGroup.members), selectinload(AlertGroup.occurrences))
            .where(AlertGroup.group_key == group_key)
        )
        return res.scalar_one_or_none()

    async def get_group_by_id(self, group_id: str) -> Optional[AlertGroup]:
        res = await self.session.execute(
            select(AlertGroup)
            .options(
                selectinload(AlertGroup.members),
                selectinload(AlertGroup.occurrences),
                selectinload(AlertGroup.escalations),
            )
            .where(AlertGroup.id == group_id)
        )
        return res.scalar_one_or_none()

    async def create_group(self, group: AlertGroup) -> AlertGroup:
        self.session.add(group)
        await self.session.flush()
        return group

    async def list_groups(self, status: Optional[str] = None, limit: int = 50) -> List[AlertGroup]:
        stmt = select(AlertGroup).order_by(desc(AlertGroup.current_priority_score)).limit(limit)
        if status:
            stmt = stmt.where(AlertGroup.group_status == status)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_group_member(self, member: AlertGroupMember) -> AlertGroupMember:
        self.session.add(member)
        await self.session.flush()
        return member

    # ------------------ Evaluation Operations ------------------
    async def save_evaluation(self, eval_record: AlertPriorityEvaluation) -> AlertPriorityEvaluation:
        self.session.add(eval_record)
        await self.session.flush()
        return eval_record

    async def get_evaluation_by_id(self, eval_id: str) -> Optional[AlertPriorityEvaluation]:
        res = await self.session.execute(
            select(AlertPriorityEvaluation).where(AlertPriorityEvaluation.id == eval_id)
        )
        return res.scalar_one_or_none()

    async def get_latest_evaluation_by_alert_id(self, alert_id: str) -> Optional[AlertPriorityEvaluation]:
        stmt = (
            select(AlertPriorityEvaluation)
            .where(AlertPriorityEvaluation.alert_id == alert_id)
            .order_by(desc(AlertPriorityEvaluation.evaluated_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_evaluations(
        self,
        priority_band: Optional[str] = None,
        severity: Optional[str] = None,
        urgency: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AlertPriorityEvaluation]:
        stmt = select(AlertPriorityEvaluation).order_by(desc(AlertPriorityEvaluation.priority_score)).limit(limit).offset(offset)
        if priority_band:
            stmt = stmt.where(AlertPriorityEvaluation.priority_band == priority_band)
        if severity:
            stmt = stmt.where(AlertPriorityEvaluation.severity == severity)
        if urgency:
            stmt = stmt.where(AlertPriorityEvaluation.urgency == urgency)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ History & Deduplication & Occurrence ------------------
    async def add_priority_history(self, history: AlertPriorityHistory) -> AlertPriorityHistory:
        self.session.add(history)
        await self.session.flush()
        return history

    async def list_priority_history(self, alert_id: str) -> List[AlertPriorityHistory]:
        stmt = (
            select(AlertPriorityHistory)
            .where(AlertPriorityHistory.alert_id == alert_id)
            .order_by(desc(AlertPriorityHistory.created_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_deduplication_record(self, dedupe_rec: AlertDeduplicationRecord) -> AlertDeduplicationRecord:
        self.session.add(dedupe_rec)
        await self.session.flush()
        return dedupe_rec

    async def get_dedupe_record_by_key(self, dedupe_key: str) -> Optional[AlertDeduplicationRecord]:
        stmt = (
            select(AlertDeduplicationRecord)
            .where(AlertDeduplicationRecord.deduplication_key == dedupe_key)
            .order_by(desc(AlertDeduplicationRecord.evaluated_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_occurrence(self, occurrence: AlertOccurrence) -> AlertOccurrence:
        self.session.add(occurrence)
        await self.session.flush()
        return occurrence

    async def get_occurrence_by_idempotency_key(self, key: str) -> Optional[AlertOccurrence]:
        res = await self.session.execute(
            select(AlertOccurrence).where(AlertOccurrence.idempotency_key == key)
        )
        return res.scalar_one_or_none()

    async def count_occurrences(self, alert_id: str) -> int:
        res = await self.session.execute(
            select(func.count(AlertOccurrence.id)).where(AlertOccurrence.alert_id == alert_id)
        )
        return res.scalar() or 0

    async def list_occurrences_for_alert(self, alert_id: str, limit: int = 50) -> List[AlertOccurrence]:
        stmt = (
            select(AlertOccurrence)
            .where(AlertOccurrence.alert_id == alert_id)
            .order_by(desc(AlertOccurrence.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_escalation(self, escalation: AlertEscalationEvent) -> AlertEscalationEvent:
        self.session.add(escalation)
        await self.session.flush()
        return escalation

    async def list_escalations_for_group(self, group_id: str) -> List[AlertEscalationEvent]:
        stmt = (
            select(AlertEscalationEvent)
            .where(AlertEscalationEvent.group_id == group_id)
            .order_by(desc(AlertEscalationEvent.created_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ------------------ Analytics ------------------
    async def get_prioritization_summary_stats(self) -> Dict[str, Any]:
        tot_evals = (await self.session.execute(select(func.count(AlertPriorityEvaluation.id)))).scalar() or 0
        tot_groups = (await self.session.execute(select(func.count(AlertGroup.id)))).scalar() or 0
        tot_occs = (await self.session.execute(select(func.count(AlertOccurrence.id)))).scalar() or 0
        tot_escs = (await self.session.execute(select(func.count(AlertEscalationEvent.id)))).scalar() or 0

        # Band counts
        band_res = await self.session.execute(
            select(AlertPriorityEvaluation.priority_band, func.count(AlertPriorityEvaluation.id))
            .group_by(AlertPriorityEvaluation.priority_band)
        )
        band_dist = {row[0]: row[1] for row in band_res.all()}

        # Severity counts
        sev_res = await self.session.execute(
            select(AlertPriorityEvaluation.severity, func.count(AlertPriorityEvaluation.id))
            .group_by(AlertPriorityEvaluation.severity)
        )
        sev_dist = {row[0]: row[1] for row in sev_res.all()}

        # Urgency counts
        urg_res = await self.session.execute(
            select(AlertPriorityEvaluation.urgency, func.count(AlertPriorityEvaluation.id))
            .group_by(AlertPriorityEvaluation.urgency)
        )
        urg_dist = {row[0]: row[1] for row in urg_res.all()}

        dedupe_rate = 0.0
        if tot_occs > 0:
            duplicate_occs = max(0, tot_occs - tot_evals)
            dedupe_rate = round((duplicate_occs / tot_occs) * 100.0, 2)

        return {
            "total_evaluations": tot_evals,
            "active_groups_count": tot_groups,
            "total_occurrences_recorded": tot_occs,
            "total_escalations_recorded": tot_escs,
            "priority_band_distribution": band_dist,
            "severity_distribution": sev_dist,
            "urgency_distribution": urg_dist,
            "deduplication_rate_pct": dedupe_rate,
            "emergency_unacknowledged_count": sev_dist.get("EMERGENCY", 0),
        }

