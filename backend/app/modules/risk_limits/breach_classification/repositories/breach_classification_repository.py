"""
Async Repository implementation for M11.07 — Breach Classification.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.breach_classification.models.breach_classification_models import (
    ClassificationPolicy,
    ClassificationPolicyVersion,
    ClassificationRule,
    BreachClassification,
    ClassificationEvidence,
    ClassificationHistory,
    ClassificationEvent,
    ClassificationAuditEvent,
)


class BreachClassificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------
    # Policy CRUD
    # ---------------------------------------------------------

    async def create_policy(self, policy: ClassificationPolicy) -> ClassificationPolicy:
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        return await self.get_policy_by_id(policy.id)

    async def get_policy_by_id(self, policy_id: str) -> Optional[ClassificationPolicy]:
        # Expire session cache to ensure newly added versions are fresh
        self.db.expire_all()
        stmt = (
            select(ClassificationPolicy)
            .where(ClassificationPolicy.id == policy_id)
            .options(
                selectinload(ClassificationPolicy.versions)
                .selectinload(ClassificationPolicyVersion.rules)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_policy_by_code(self, code: str) -> Optional[ClassificationPolicy]:
        stmt = (
            select(ClassificationPolicy)
            .where(ClassificationPolicy.policy_code == code)
            .options(
                selectinload(ClassificationPolicy.versions)
                .selectinload(ClassificationPolicyVersion.rules)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_policy(
        self,
        portfolio_id: Optional[str] = None,
        risk_category: Optional[str] = None
    ) -> Optional[ClassificationPolicy]:
        """
        Finds the highest-priority ACTIVE classification policy matching scope.
        """
        stmt = select(ClassificationPolicy).where(ClassificationPolicy.lifecycle_status == "ACTIVE")
        if portfolio_id:
            stmt = stmt.where(or_(ClassificationPolicy.scope_id == portfolio_id, ClassificationPolicy.scope_type == "ALL"))
        if risk_category:
            stmt = stmt.where(or_(ClassificationPolicy.risk_category == risk_category, ClassificationPolicy.risk_category == "ALL"))

        stmt = (
            stmt.options(
                selectinload(ClassificationPolicy.versions)
                .selectinload(ClassificationPolicyVersion.rules)
            )
            .order_by(ClassificationPolicy.priority)
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_policies(self, status: Optional[str] = None) -> List[ClassificationPolicy]:
        query = select(ClassificationPolicy).options(
            selectinload(ClassificationPolicy.versions)
            .selectinload(ClassificationPolicyVersion.rules)
        )
        if status:
            query = query.where(ClassificationPolicy.lifecycle_status == status)
        query = query.order_by(ClassificationPolicy.priority)
        res = await self.db.execute(query)
        return list(res.scalars().all())

    async def update_policy(self, policy: ClassificationPolicy) -> ClassificationPolicy:
        await self.db.commit()
        await self.db.refresh(policy)
        return await self.get_policy_by_id(policy.id)

    # ---------------------------------------------------------
    # Policy Version CRUD
    # ---------------------------------------------------------

    async def create_version(self, version: ClassificationPolicyVersion) -> ClassificationPolicyVersion:
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def get_version_by_id(self, version_id: str) -> Optional[ClassificationPolicyVersion]:
        stmt = (
            select(ClassificationPolicyVersion)
            .where(ClassificationPolicyVersion.id == version_id)
            .options(selectinload(ClassificationPolicyVersion.rules))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------------------------------------------------
    # Classification CRUD & Deduplication
    # ---------------------------------------------------------

    async def create_classification(self, classification: BreachClassification) -> BreachClassification:
        self.db.add(classification)
        await self.db.commit()
        await self.db.refresh(classification)
        return await self.get_classification_by_id(classification.id)

    async def get_classification_by_id(self, classification_id: str) -> Optional[BreachClassification]:
        self.db.expire_all()
        stmt = (
            select(BreachClassification)
            .where(BreachClassification.id == classification_id)
            .options(
                selectinload(BreachClassification.evidence),
                selectinload(BreachClassification.history),
                selectinload(BreachClassification.events),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_classification_by_event_id(self, breach_event_id: str) -> Optional[BreachClassification]:
        stmt = (
            select(BreachClassification)
            .where(BreachClassification.breach_event_id == breach_event_id)
            .options(
                selectinload(BreachClassification.evidence),
                selectinload(BreachClassification.history),
                selectinload(BreachClassification.events),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_classifications(
        self,
        portfolio_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[BreachClassification]:
        conditions = []
        if portfolio_id:
            conditions.append(BreachClassification.portfolio_id == portfolio_id)
        if severity:
            conditions.append(BreachClassification.severity == severity)

        query = select(BreachClassification).options(
            selectinload(BreachClassification.evidence),
            selectinload(BreachClassification.history),
        )
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(desc(BreachClassification.classified_at)).limit(limit)

        res = await self.db.execute(query)
        return list(res.scalars().all())

    async def update_classification(self, classification: BreachClassification) -> BreachClassification:
        await self.db.commit()
        await self.db.refresh(classification)
        return await self.get_classification_by_id(classification.id)

    # ---------------------------------------------------------
    # Evidence & History
    # ---------------------------------------------------------

    async def create_evidence(self, evidence: ClassificationEvidence) -> ClassificationEvidence:
        self.db.add(evidence)
        await self.db.commit()
        await self.db.refresh(evidence)
        return evidence

    async def create_history_record(self, record: ClassificationHistory) -> ClassificationHistory:
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def create_classification_event(self, event: ClassificationEvent) -> ClassificationEvent:
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def list_history(self, classification_id: Optional[str] = None, limit: int = 50) -> List[ClassificationHistory]:
        query = select(ClassificationHistory)
        if classification_id:
            query = query.where(ClassificationHistory.classification_id == classification_id)
        query = query.order_by(desc(ClassificationHistory.changed_at)).limit(limit)
        res = await self.db.execute(query)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Audit Events
    # ---------------------------------------------------------

    async def create_audit_event(self, audit: ClassificationAuditEvent) -> ClassificationAuditEvent:
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(audit)
        return audit

    async def list_audit_events(self, entity_id: Optional[str] = None, limit: int = 50) -> List[ClassificationAuditEvent]:
        query = select(ClassificationAuditEvent)
        if entity_id:
            query = query.where(ClassificationAuditEvent.entity_id == entity_id)
        query = query.order_by(desc(ClassificationAuditEvent.timestamp)).limit(limit)
        res = await self.db.execute(query)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Monitoring Overview
    # ---------------------------------------------------------

    async def get_overview_statistics(self) -> Dict[str, int]:
        total_warning = await self.db.scalar(
            select(func.count(BreachClassification.id)).where(BreachClassification.severity == "WARNING")
        ) or 0
        total_critical = await self.db.scalar(
            select(func.count(BreachClassification.id)).where(BreachClassification.severity == "CRITICAL")
        ) or 0
        total_emergency = await self.db.scalar(
            select(func.count(BreachClassification.id)).where(BreachClassification.severity == "EMERGENCY")
        ) or 0
        total_active = await self.db.scalar(select(func.count(BreachClassification.id))) or 0
        
        upgrades = await self.db.scalar(
            select(func.count(ClassificationHistory.id)).where(ClassificationHistory.change_type == "UPGRADE")
        ) or 0
        downgrades = await self.db.scalar(
            select(func.count(ClassificationHistory.id)).where(ClassificationHistory.change_type == "DOWNGRADE")
        ) or 0

        return {
            "total_warning_events": total_warning,
            "total_critical_events": total_critical,
            "total_emergency_events": total_emergency,
            "total_active_classifications": total_active,
            "total_upgraded_events": upgrades,
            "total_downgraded_events": downgrades,
        }
