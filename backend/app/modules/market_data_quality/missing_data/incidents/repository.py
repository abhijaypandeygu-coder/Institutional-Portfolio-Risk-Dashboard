"""
Module 03.01: Missing Data Detection - Repository Layer.
Handles database queries and upserts for policies, incidents, evidence, and coverage windows.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.missing_data.models import (
    CoverageWindow,
    ExpectedObservationPolicy,
    IncidentStatus,
    MissingDataEvidence,
    MissingDataIncident,
)


class MissingDataRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Policies
    # -------------------------------------------------------------------------
    async def create_policy(self, policy: ExpectedObservationPolicy) -> ExpectedObservationPolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def list_policies(self) -> List[ExpectedObservationPolicy]:
        stmt = select(ExpectedObservationPolicy).order_by(desc(ExpectedObservationPolicy.priority))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Incidents (Idempotent by incident_key)
    # -------------------------------------------------------------------------
    async def get_incident_by_key(self, incident_key: str) -> Optional[MissingDataIncident]:
        stmt = select(MissingDataIncident).where(MissingDataIncident.incident_key == incident_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_incident_by_id(self, incident_id: UUID) -> Optional[MissingDataIncident]:
        stmt = select(MissingDataIncident).where(MissingDataIncident.id == incident_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_incident(self, incident: MissingDataIncident) -> MissingDataIncident:
        existing = await self.get_incident_by_key(incident.incident_key)
        if existing:
            # Update last detected timestamp and counts
            existing.last_detected_at = datetime.now(timezone.utc)
            existing.missing_count = incident.missing_count
            existing.evidence = incident.evidence
            self.session.add(existing)
            await self.session.flush()
            return existing
        else:
            self.session.add(incident)
            await self.session.flush()
            return incident

    async def list_incidents(
        self,
        instrument_id: Optional[str] = None,
        issue_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[MissingDataIncident]:
        stmt = select(MissingDataIncident)
        if instrument_id:
            stmt = stmt.where(MissingDataIncident.instrument_id == instrument_id)
        if issue_status:
            stmt = stmt.where(MissingDataIncident.issue_status == issue_status)
        stmt = stmt.order_by(desc(MissingDataIncident.last_detected_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_incident(self, incident_id: UUID, reason: str) -> Optional[MissingDataIncident]:
        incident = await self.get_incident_by_id(incident_id)
        if incident:
            incident.issue_status = IncidentStatus.RESOLVED.value
            incident.resolved_at = datetime.now(timezone.utc)
            incident.resolution_reason = reason
            self.session.add(incident)
            await self.session.flush()
        return incident

    # -------------------------------------------------------------------------
    # Coverage Windows
    # -------------------------------------------------------------------------
    async def save_coverage_window(self, window: CoverageWindow) -> CoverageWindow:
        self.session.add(window)
        await self.session.flush()
        return window

    async def list_coverage_windows(
        self,
        instrument_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[CoverageWindow]:
        stmt = select(CoverageWindow)
        if instrument_id:
            stmt = stmt.where(CoverageWindow.instrument_id == instrument_id)
        stmt = stmt.order_by(desc(CoverageWindow.window_end)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
