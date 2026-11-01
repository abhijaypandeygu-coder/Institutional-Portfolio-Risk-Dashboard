"""
Module 03.03: Timestamp Validation - Repository Layer.
Handles database queries and persistence for:
- Timestamp validation rules (versioned updates, active policies)
- Timestamp validation results and subfeature evidence records
- Timestamp anomaly incidents with idempotent incident key upserts
- Clock offset samples
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.market_data_quality.timestamp_validation.models import (
    ClockOffsetSample,
    FinalTimestampStatus,
    TimestampAnomalyIncident,
    TimestampAnomalyStatus,
    TimestampValidationEvidence,
    TimestampValidationResult,
    TimestampValidationRule,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampValidationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Rule Management
    # =========================================================================

    async def create_rule(self, rule: TimestampValidationRule) -> TimestampValidationRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_rule_by_code(self, rule_code: str) -> Optional[TimestampValidationRule]:
        stmt = select(TimestampValidationRule).where(TimestampValidationRule.rule_code == rule_code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_rule_by_id(self, rule_id: UUID) -> Optional[TimestampValidationRule]:
        stmt = select(TimestampValidationRule).where(TimestampValidationRule.id == rule_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_rules(self, enabled_only: bool = False) -> List[TimestampValidationRule]:
        stmt = select(TimestampValidationRule).order_by(
            TimestampValidationRule.priority.asc(), TimestampValidationRule.rule_code.asc()
        )
        if enabled_only:
            stmt = stmt.where(TimestampValidationRule.enabled == True)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_rule(
        self, rule_id: UUID, updates: Dict[str, Any]
    ) -> Optional[TimestampValidationRule]:
        rule = await self.get_rule_by_id(rule_id)
        if not rule:
            return None
        rule.version += 1
        rule.updated_at = utc_now()
        for k, v in updates.items():
            if hasattr(rule, k) and v is not None:
                setattr(rule, k, v)
        await self.session.flush()
        return rule

    # =========================================================================
    # Results & Evidence
    # =========================================================================

    async def save_validation_result(
        self, result: TimestampValidationResult, evidence_items: List[TimestampValidationEvidence]
    ) -> TimestampValidationResult:
        self.session.add(result)
        await self.session.flush()
        for ev in evidence_items:
            ev.validation_result_id = result.id
            self.session.add(ev)
        await self.session.flush()
        return result

    async def get_result_by_id(self, result_id: UUID) -> Optional[TimestampValidationResult]:
        stmt = (
            select(TimestampValidationResult)
            .where(TimestampValidationResult.id == result_id)
            .options(selectinload(TimestampValidationResult.evidence_items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_results(
        self,
        instrument_id: Optional[str] = None,
        feed_id: Optional[str] = None,
        final_status: Optional[FinalTimestampStatus] = None,
        limit: int = 100,
    ) -> List[TimestampValidationResult]:
        stmt = (
            select(TimestampValidationResult)
            .order_by(desc(TimestampValidationResult.validation_timestamp))
            .limit(limit)
            .options(selectinload(TimestampValidationResult.evidence_items))
        )
        if instrument_id:
            stmt = stmt.where(TimestampValidationResult.instrument_id == instrument_id)
        if feed_id:
            stmt = stmt.where(TimestampValidationResult.feed_id == feed_id)
        if final_status:
            stmt = stmt.where(TimestampValidationResult.final_status == final_status)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Anomaly Incidents
    # =========================================================================

    async def upsert_anomaly_incident(
        self, incident: TimestampAnomalyIncident
    ) -> TimestampAnomalyIncident:
        stmt = select(TimestampAnomalyIncident).where(
            TimestampAnomalyIncident.incident_key == incident.incident_key
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.last_detected_at = utc_now()
            existing.calculated_difference_ms = incident.calculated_difference_ms
            existing.threshold_ms = incident.threshold_ms
            existing.evidence = incident.evidence
            existing.severity = incident.severity
            return existing
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def get_incident_by_id(self, incident_id: UUID) -> Optional[TimestampAnomalyIncident]:
        stmt = select(TimestampAnomalyIncident).where(TimestampAnomalyIncident.id == incident_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_incidents(
        self,
        status: Optional[TimestampAnomalyStatus] = None,
        instrument_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[TimestampAnomalyIncident]:
        stmt = (
            select(TimestampAnomalyIncident)
            .order_by(desc(TimestampAnomalyIncident.last_detected_at))
            .limit(limit)
        )
        if status:
            stmt = stmt.where(TimestampAnomalyIncident.incident_status == status)
        if instrument_id:
            stmt = stmt.where(TimestampAnomalyIncident.instrument_id == instrument_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Clock Offset Telemetry
    # =========================================================================

    async def save_clock_sample(self, sample: ClockOffsetSample) -> ClockOffsetSample:
        self.session.add(sample)
        await self.session.flush()
        return sample
