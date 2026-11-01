"""
Module 03.02: Price Validation - Repository Layer.
Manages database operations for:
- Validation rules (versioned updates, listing, fetching)
- Validation results and detailed evidence items
- Price anomaly incidents with idempotent incident key upserts
- Reference snapshots
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.market_data_quality.price_validation.models import (
    AnomalyIncidentStatus,
    PriceAnomalyIncident,
    PriceReferenceSnapshot,
    PriceValidationEvidence,
    PriceValidationResult,
    PriceValidationRule,
    ValidationSeverity,
    ValidationStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PriceValidationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Rule Management
    # =========================================================================

    async def create_rule(self, rule: PriceValidationRule) -> PriceValidationRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_rule_by_code(self, rule_code: str) -> Optional[PriceValidationRule]:
        stmt = select(PriceValidationRule).where(PriceValidationRule.rule_code == rule_code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_rule_by_id(self, rule_id: UUID) -> Optional[PriceValidationRule]:
        stmt = select(PriceValidationRule).where(PriceValidationRule.id == rule_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_rules(self, enabled_only: bool = False) -> List[PriceValidationRule]:
        stmt = select(PriceValidationRule).order_by(
            PriceValidationRule.priority.asc(), PriceValidationRule.rule_code.asc()
        )
        if enabled_only:
            stmt = stmt.where(PriceValidationRule.enabled == True)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_rule(
        self, rule_id: UUID, updates: Dict[str, Any]
    ) -> Optional[PriceValidationRule]:
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
        self, result: PriceValidationResult, evidence_items: List[PriceValidationEvidence]
    ) -> PriceValidationResult:
        self.session.add(result)
        await self.session.flush()
        for ev in evidence_items:
            ev.validation_result_id = result.id
            self.session.add(ev)
        await self.session.flush()
        return result

    async def get_result_by_id(self, result_id: UUID) -> Optional[PriceValidationResult]:
        stmt = (
            select(PriceValidationResult)
            .where(PriceValidationResult.id == result_id)
            .options(selectinload(PriceValidationResult.evidence_items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_results(
        self,
        instrument_id: Optional[str] = None,
        feed_id: Optional[str] = None,
        status: Optional[ValidationStatus] = None,
        limit: int = 100,
    ) -> List[PriceValidationResult]:
        stmt = (
            select(PriceValidationResult)
            .order_by(desc(PriceValidationResult.validation_timestamp))
            .limit(limit)
            .options(selectinload(PriceValidationResult.evidence_items))
        )
        if instrument_id:
            stmt = stmt.where(PriceValidationResult.instrument_id == instrument_id)
        if feed_id:
            stmt = stmt.where(PriceValidationResult.feed_id == feed_id)
        if status:
            stmt = stmt.where(PriceValidationResult.validation_status == status)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Anomaly Incidents
    # =========================================================================

    async def upsert_anomaly_incident(
        self, incident: PriceAnomalyIncident
    ) -> PriceAnomalyIncident:
        stmt = select(PriceAnomalyIncident).where(
            PriceAnomalyIncident.incident_key == incident.incident_key
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.last_detected_at = utc_now()
            existing.observed_price = incident.observed_price
            existing.reference_price = incident.reference_price
            existing.absolute_difference = incident.absolute_difference
            existing.percentage_difference = incident.percentage_difference
            existing.evidence = incident.evidence
            existing.severity = incident.severity
            return existing
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def get_incident_by_id(self, incident_id: UUID) -> Optional[PriceAnomalyIncident]:
        stmt = select(PriceAnomalyIncident).where(PriceAnomalyIncident.id == incident_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_incidents(
        self,
        status: Optional[AnomalyIncidentStatus] = None,
        instrument_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PriceAnomalyIncident]:
        stmt = (
            select(PriceAnomalyIncident)
            .order_by(desc(PriceAnomalyIncident.last_detected_at))
            .limit(limit)
        )
        if status:
            stmt = stmt.where(PriceAnomalyIncident.incident_status == status)
        if instrument_id:
            stmt = stmt.where(PriceAnomalyIncident.instrument_id == instrument_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Reference Snapshots
    # =========================================================================

    async def save_reference_snapshot(
        self, snapshot: PriceReferenceSnapshot
    ) -> PriceReferenceSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_latest_reference_snapshot(
        self, instrument_id: str, reference_type: str
    ) -> Optional[PriceReferenceSnapshot]:
        stmt = (
            select(PriceReferenceSnapshot)
            .where(
                PriceReferenceSnapshot.instrument_id == instrument_id,
                PriceReferenceSnapshot.reference_type == reference_type,
            )
            .order_by(desc(PriceReferenceSnapshot.source_timestamp))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
