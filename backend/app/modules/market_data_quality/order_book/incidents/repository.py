"""
Incident, Rule, and Resync Repository for Order Book Validation.
Handles database persistence, deduplication, and lifecycle tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.order_book.models import (
    BookValidationRule,
    BookValidationResult,
    BookIntegrityIncident,
    BookResynchronizationRequest,
    BookValidationEvidence
)
from backend.app.modules.market_data_quality.order_book.schemas import (
    BookValidationRuleCreate,
    ResyncRequestCreate
)


class BookIncidentRepository:
    """
    Data access repository for M03.04.
    """

    @staticmethod
    async def get_rule_by_code(session: AsyncSession, rule_code: str) -> Optional[BookValidationRule]:
        stmt = select(BookValidationRule).where(BookValidationRule.rule_code == rule_code)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_effective_rule(
        session: AsyncSession,
        feed_id: Optional[str] = None,
        symbol: Optional[str] = None,
        venue: Optional[str] = None
    ) -> Optional[BookValidationRule]:
        """
        Retrieves most specific enabled rule: symbol -> feed_id -> venue -> default.
        """
        stmt = select(BookValidationRule).where(BookValidationRule.is_enabled == True)
        res = await session.execute(stmt)
        rules = res.scalars().all()
        if not rules:
            return None

        for r in rules:
            if symbol and r.symbol == symbol:
                return r
        for r in rules:
            if feed_id and r.feed_id == feed_id:
                return r
        for r in rules:
            if venue and r.venue == venue:
                return r
        for r in rules:
            if not r.symbol and not r.feed_id and not r.venue:
                return r
        return rules[0]

    @staticmethod
    async def create_rule(session: AsyncSession, rule_in: BookValidationRuleCreate) -> BookValidationRule:
        rule = BookValidationRule(**rule_in.model_dump())
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    @staticmethod
    async def list_rules(session: AsyncSession) -> List[BookValidationRule]:
        stmt = select(BookValidationRule).order_by(BookValidationRule.id.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def record_result(session: AsyncSession, result_data: Dict[str, Any]) -> BookValidationResult:
        result = BookValidationResult(**result_data)
        session.add(result)
        await session.commit()
        await session.refresh(result)
        return result

    @staticmethod
    async def record_evidence(
        session: AsyncSession,
        validation_id: str,
        raw_payload: Optional[str],
        parsed_levels: Optional[Dict[str, Any]],
        rule_evals: Optional[Dict[str, Any]]
    ) -> BookValidationEvidence:
        ev = BookValidationEvidence(
            validation_id=validation_id,
            captured_at=datetime.now(timezone.utc),
            raw_payload_snippet=raw_payload,
            parsed_levels=parsed_levels,
            rule_evaluations=rule_evals
        )
        session.add(ev)
        await session.commit()
        return ev

    @staticmethod
    async def create_or_update_incident(
        session: AsyncSession,
        incident_key: str,
        incident_type: str,
        feed_id: str,
        symbol: str,
        venue: Optional[str],
        session_phase: str,
        severity: str,
        details: Dict[str, Any],
        duration_ms: Optional[int] = None
    ) -> BookIntegrityIncident:
        stmt = select(BookIntegrityIncident).where(BookIntegrityIncident.incident_key == incident_key)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.severity = severity
            existing.details = details
            existing.status = "OPEN"
            if duration_ms is not None:
                existing.duration_ms = duration_ms
            await session.commit()
            await session.refresh(existing)
            return existing

        incident = BookIntegrityIncident(
            incident_key=incident_key,
            incident_type=incident_type,
            feed_id=feed_id,
            symbol=symbol,
            venue=venue,
            session_phase=session_phase,
            severity=severity,
            status="OPEN",
            details=details,
            duration_ms=duration_ms,
            started_at=datetime.now(timezone.utc)
        )
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident

    @staticmethod
    async def resolve_incident(session: AsyncSession, incident_key: str) -> Optional[BookIntegrityIncident]:
        stmt = select(BookIntegrityIncident).where(
            and_(BookIntegrityIncident.incident_key == incident_key, BookIntegrityIncident.status == "OPEN")
        )
        res = await session.execute(stmt)
        inc = res.scalar_one_or_none()
        if inc:
            inc.status = "RESOLVED"
            inc.resolved_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(inc)
        return inc

    @staticmethod
    async def list_incidents(
        session: AsyncSession,
        feed_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[BookIntegrityIncident]:
        stmt = select(BookIntegrityIncident)
        conditions = []
        if feed_id:
            conditions.append(BookIntegrityIncident.feed_id == feed_id)
        if symbol:
            conditions.append(BookIntegrityIncident.symbol == symbol)
        if status:
            conditions.append(BookIntegrityIncident.status == status)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(BookIntegrityIncident.id.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_resync_request(
        session: AsyncSession,
        resync_in: ResyncRequestCreate
    ) -> BookResynchronizationRequest:
        req = BookResynchronizationRequest(
            request_id=f"RESYNC_{uuid.uuid4().hex[:12].upper()}",
            feed_id=resync_in.feed_id,
            symbol=resync_in.symbol,
            venue=resync_in.venue,
            reason=resync_in.reason,
            from_sequence=resync_in.from_sequence,
            to_sequence=resync_in.to_sequence,
            status="INITIATED",
            requested_at=datetime.now(timezone.utc),
            m02_acknowledgment={"acknowledged": True, "source": "M03.04_INTEGRITY_ENGINE"}
        )
        session.add(req)
        await session.commit()
        await session.refresh(req)
        return req

    @staticmethod
    async def get_quality_summary(session: AsyncSession, feed_id: str, symbol: str) -> Dict[str, Any]:
        """
        Aggregates historical evaluations and open incidents.
        """
        stmt = select(BookValidationResult).where(
            and_(BookValidationResult.feed_id == feed_id, BookValidationResult.symbol == symbol)
        )
        res = await session.execute(stmt)
        records = res.scalars().all()

        total = len(records)
        if total == 0:
            return {
                "feed_id": feed_id,
                "symbol": symbol,
                "total_evaluations": 0,
                "valid_count": 0,
                "crossed_count": 0,
                "locked_count": 0,
                "quantity_defect_count": 0,
                "continuity_break_count": 0,
                "active_incidents": 0,
                "spread_eligible_ratio": 1.0
            }

        valid_c = sum(1 for r in records if r.is_valid)
        crossed_c = sum(1 for r in records if r.is_crossed)
        locked_c = sum(1 for r in records if r.is_locked)
        qty_c = sum(1 for r in records if r.has_quantity_anomaly)
        cont_c = sum(1 for r in records if r.has_continuity_break)
        spread_el_c = sum(1 for r in records if r.spread_eligible)

        # Count active incidents
        stmt_inc = select(func.count(BookIntegrityIncident.id)).where(
            and_(
                BookIntegrityIncident.feed_id == feed_id,
                BookIntegrityIncident.symbol == symbol,
                BookIntegrityIncident.status == "OPEN"
            )
        )
        inc_res = await session.execute(stmt_inc)
        active_inc = inc_res.scalar() or 0

        return {
            "feed_id": feed_id,
            "symbol": symbol,
            "total_evaluations": total,
            "valid_count": valid_c,
            "crossed_count": crossed_c,
            "locked_count": locked_c,
            "quantity_defect_count": qty_c,
            "continuity_break_count": cont_c,
            "active_incidents": active_inc,
            "spread_eligible_ratio": round(spread_el_c / total, 4)
        }
