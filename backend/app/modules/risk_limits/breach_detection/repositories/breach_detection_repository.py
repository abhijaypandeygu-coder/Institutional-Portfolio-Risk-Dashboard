"""
Async Repository implementation for M11.06 — Breach Detection.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.breach_detection.models.breach_detection_models import (
    BreachEvaluation,
    BreachEpisode,
    BreachObservation,
    BreachEvent,
    BreachDetectionRule,
    BreachDetectionRuleVersion,
    BreachEventLink,
    BreachAuditEvent,
)


class BreachDetectionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------
    # Evaluation Persistence
    # ---------------------------------------------------------

    async def create_evaluation(self, evaluation: BreachEvaluation) -> BreachEvaluation:
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        return evaluation

    async def get_evaluation_by_id(self, evaluation_id: str) -> Optional[BreachEvaluation]:
        stmt = (
            select(BreachEvaluation)
            .where(BreachEvaluation.id == evaluation_id)
            .options(
                selectinload(BreachEvaluation.observations),
                selectinload(BreachEvaluation.events),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_evaluations(
        self,
        portfolio_id: Optional[str] = None,
        metric_code: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[BreachEvaluation]:
        conditions = []
        if portfolio_id:
            conditions.append(BreachEvaluation.portfolio_id == portfolio_id)
        if metric_code:
            conditions.append(BreachEvaluation.metric_code == metric_code)
        if status:
            conditions.append(BreachEvaluation.evaluation_status == status)

        query = select(BreachEvaluation)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(desc(BreachEvaluation.created_at)).limit(limit)

        res = await self.db.execute(query)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Episode Management & Deduplication
    # ---------------------------------------------------------

    async def get_active_episode(
        self,
        portfolio_id: str,
        target_entity_id: str,
        metric_code: str
    ) -> Optional[BreachEpisode]:
        """
        Finds currently open/active breach episode for this entity & metric.
        Used to prevent duplicate episode creation.
        """
        stmt = (
            select(BreachEpisode)
            .where(
                and_(
                    BreachEpisode.portfolio_id == portfolio_id,
                    BreachEpisode.target_entity_id == target_entity_id,
                    BreachEpisode.metric_code == metric_code,
                    BreachEpisode.episode_status.in_(["ACTIVE_WARNING", "ACTIVE_HARD_BREACH", "PERSISTENT_BREACH", "RECOVERING"]),
                )
            )
            .options(
                selectinload(BreachEpisode.observations),
                selectinload(BreachEpisode.events),
            )
            .order_by(desc(BreachEpisode.created_at))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_episode(self, episode: BreachEpisode) -> BreachEpisode:
        self.db.add(episode)
        await self.db.commit()
        await self.db.refresh(episode)
        return episode

    async def update_episode(self, episode: BreachEpisode) -> BreachEpisode:
        await self.db.commit()
        await self.db.refresh(episode)
        return episode

    async def get_episode_by_id(self, episode_id: str) -> Optional[BreachEpisode]:
        stmt = (
            select(BreachEpisode)
            .where(BreachEpisode.id == episode_id)
            .options(
                selectinload(BreachEpisode.observations),
                selectinload(BreachEpisode.events),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_episodes(
        self,
        portfolio_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[BreachEpisode]:
        conditions = []
        if portfolio_id:
            conditions.append(BreachEpisode.portfolio_id == portfolio_id)
        if status:
            conditions.append(BreachEpisode.episode_status == status)

        query = select(BreachEpisode)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(desc(BreachEpisode.created_at)).limit(limit)

        res = await self.db.execute(query)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Observation Records
    # ---------------------------------------------------------

    async def create_observation(self, observation: BreachObservation) -> BreachObservation:
        self.db.add(observation)
        await self.db.commit()
        await self.db.refresh(observation)
        return observation

    async def list_observations_for_episode(self, episode_id: str) -> List[BreachObservation]:
        stmt = (
            select(BreachObservation)
            .where(BreachObservation.episode_id == episode_id)
            .order_by(BreachObservation.observation_sequence)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Breach Events (Immutable)
    # ---------------------------------------------------------

    async def create_event(self, event: BreachEvent) -> BreachEvent:
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_event_by_id(self, event_id: str) -> Optional[BreachEvent]:
        stmt = select(BreachEvent).where(BreachEvent.id == event_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_event_by_reference(self, ref: str) -> Optional[BreachEvent]:
        stmt = select(BreachEvent).where(BreachEvent.event_reference == ref)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_events(
        self,
        portfolio_id: Optional[str] = None,
        severity: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[BreachEvent]:
        conditions = []
        if portfolio_id:
            conditions.append(BreachEvent.portfolio_id == portfolio_id)
        if severity:
            conditions.append(BreachEvent.severity == severity)
        if event_type:
            conditions.append(BreachEvent.event_type == event_type)

        query = select(BreachEvent)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(desc(BreachEvent.detected_at)).limit(limit)

        res = await self.db.execute(query)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Detection Rules
    # ---------------------------------------------------------

    async def create_rule(self, rule: BreachDetectionRule) -> BreachDetectionRule:
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def get_rule_by_code(self, code: str) -> Optional[BreachDetectionRule]:
        stmt = (
            select(BreachDetectionRule)
            .where(BreachDetectionRule.rule_code == code)
            .options(selectinload(BreachDetectionRule.versions))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_rule_by_id(self, rule_id: str) -> Optional[BreachDetectionRule]:
        stmt = (
            select(BreachDetectionRule)
            .where(BreachDetectionRule.id == rule_id)
            .options(selectinload(BreachDetectionRule.versions))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_rule_for_metric(self, metric_code: str) -> Optional[BreachDetectionRule]:
        stmt = (
            select(BreachDetectionRule)
            .where(
                and_(
                    BreachDetectionRule.metric_code == metric_code,
                    BreachDetectionRule.status == "ACTIVE"
                )
            )
            .order_by(desc(BreachDetectionRule.rule_version))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_rules(self, status: Optional[str] = None) -> List[BreachDetectionRule]:
        query = select(BreachDetectionRule).options(selectinload(BreachDetectionRule.versions))
        if status:
            query = query.where(BreachDetectionRule.status == status)
        res = await self.db.execute(query)
        return list(res.scalars().all())

    async def update_rule(self, rule: BreachDetectionRule) -> BreachDetectionRule:
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    # ---------------------------------------------------------
    # Audit Events
    # ---------------------------------------------------------

    async def create_audit_event(self, audit: BreachAuditEvent) -> BreachAuditEvent:
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(audit)
        return audit

    async def list_audit_events(self, entity_id: Optional[str] = None, limit: int = 50) -> List[BreachAuditEvent]:
        query = select(BreachAuditEvent)
        if entity_id:
            query = query.where(BreachAuditEvent.entity_id == entity_id)
        query = query.order_by(desc(BreachAuditEvent.timestamp)).limit(limit)
        res = await self.db.execute(query)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Monitoring Statistics
    # ---------------------------------------------------------

    async def get_monitoring_overview(self) -> Dict[str, int]:
        # Count active episodes by status
        active_warnings = await self.db.scalar(
            select(func.count(BreachEpisode.id)).where(BreachEpisode.episode_status == "ACTIVE_WARNING")
        ) or 0
        active_hard = await self.db.scalar(
            select(func.count(BreachEpisode.id)).where(BreachEpisode.episode_status == "ACTIVE_HARD_BREACH")
        ) or 0
        persistent = await self.db.scalar(
            select(func.count(BreachEpisode.id)).where(BreachEpisode.episode_status == "PERSISTENT_BREACH")
        ) or 0
        recovering = await self.db.scalar(
            select(func.count(BreachEpisode.id)).where(BreachEpisode.episode_status == "RECOVERING")
        ) or 0
        
        # Recent stale/invalid input evaluations
        stale_count = await self.db.scalar(
            select(func.count(BreachEvaluation.id)).where(BreachEvaluation.evaluation_status == "STALE_INPUT")
        ) or 0
        invalid_count = await self.db.scalar(
            select(func.count(BreachEvaluation.id)).where(BreachEvaluation.evaluation_status == "INVALID_INPUT")
        ) or 0

        total_active = active_warnings + active_hard + persistent + recovering

        return {
            "total_active_warnings": active_warnings,
            "total_active_hard_breaches": active_hard,
            "total_persistent_breaches": persistent,
            "total_transient_breaches": active_hard,
            "total_recovering_breaches": recovering,
            "total_stale_inputs": stale_count,
            "total_invalid_inputs": invalid_count,
            "total_episodes_active": total_active,
        }
