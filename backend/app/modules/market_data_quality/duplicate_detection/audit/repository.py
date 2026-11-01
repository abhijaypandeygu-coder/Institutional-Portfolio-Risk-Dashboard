"""
M03.05 - Duplicate Detection Data Access & Incident Repository.
Provides atomic transactions, unique constraint handling, duplicate receipt logging,
conflict recording, and audit aggregations.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.duplicate_detection.models import (
    EventIdentityRegistry,
    DuplicateEventReceipt,
    EventIdentityConflict,
    DuplicateDetectionRule,
    DuplicateDetectionMetrics,
)
from backend.app.modules.market_data_quality.duplicate_detection.schemas import (
    DuplicateDetectionRuleCreate,
    ConflictResolutionRequest,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DuplicateRepository:
    """
    Persistence operations for M03.05 Duplicate Detection.
    """

    @staticmethod
    async def get_identity_by_key(
        session: AsyncSession, idempotency_key: str
    ) -> Optional[EventIdentityRegistry]:
        stmt = select(EventIdentityRegistry).where(
            EventIdentityRegistry.idempotency_key == idempotency_key
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def register_new_identity(
        session: AsyncSession,
        provider_id: str,
        feed_id: str,
        instrument_id: str,
        exchange: str,
        event_type: str,
        identity_strategy: str,
        identity_scope: str,
        idempotency_key: str,
        payload_fingerprint: str,
        canonical_event_id: str,
        canonical_record_table: str,
    ) -> EventIdentityRegistry:
        record = EventIdentityRegistry(
            provider_id=provider_id,
            feed_id=feed_id,
            instrument_id=instrument_id,
            exchange=exchange,
            event_type=event_type,
            identity_strategy=identity_strategy,
            identity_scope=identity_scope,
            idempotency_key=idempotency_key,
            payload_fingerprint=payload_fingerprint,
            canonical_event_id=canonical_event_id,
            canonical_record_table=canonical_record_table,
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
            delivery_count=1,
            record_status="NEW_EVENT_ACCEPTED",
        )
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def record_duplicate_receipt(
        session: AsyncSession,
        identity_record: EventIdentityRegistry,
        duplicate_reason: str,
        incoming_provider_event_id: Optional[str],
        incoming_sequence: Optional[int],
        incoming_fingerprint: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> DuplicateEventReceipt:
        # Increment delivery count on identity
        identity_record.delivery_count += 1
        identity_record.last_seen_at = utc_now()

        receipt_id = f"RCP_{uuid.uuid4().hex[:12].upper()}"
        receipt = DuplicateEventReceipt(
            receipt_id=receipt_id,
            identity_registry_id=identity_record.id,
            canonical_event_id=identity_record.canonical_event_id,
            provider_id=identity_record.provider_id,
            feed_id=identity_record.feed_id,
            instrument_id=identity_record.instrument_id,
            exchange=identity_record.exchange,
            event_type=identity_record.event_type,
            duplicate_reason=duplicate_reason,
            identity_strategy=identity_record.identity_strategy,
            incoming_provider_event_id=incoming_provider_event_id,
            incoming_sequence=incoming_sequence,
            incoming_payload_fingerprint=incoming_fingerprint,
            original_receive_timestamp=identity_record.first_seen_at,
            duplicate_receive_timestamp=utc_now(),
            processing_outcome="IGNORED_REPLAY",
            evidence=evidence or {},
        )
        session.add(receipt)
        await session.flush()
        return receipt

    @staticmethod
    async def record_identity_conflict(
        session: AsyncSession,
        identity_record: EventIdentityRegistry,
        incoming_reference: str,
        incoming_fingerprint: str,
        conflict_type: str = "PAYLOAD_MISMATCH",
        evidence: Optional[Dict[str, Any]] = None,
    ) -> EventIdentityConflict:
        identity_record.record_status = "IDENTITY_CONFLICT"

        conflict_id = f"CNF_{uuid.uuid4().hex[:12].upper()}"
        conflict = EventIdentityConflict(
            conflict_id=conflict_id,
            identity_registry_id=identity_record.id,
            canonical_event_id=identity_record.canonical_event_id,
            incoming_event_reference=incoming_reference,
            original_fingerprint=identity_record.payload_fingerprint,
            incoming_fingerprint=incoming_fingerprint,
            conflict_type=conflict_type,
            conflict_status="OPEN",
            evidence=evidence or {},
            first_detected_at=utc_now(),
            last_detected_at=utc_now(),
        )
        session.add(conflict)
        await session.flush()
        return conflict

    @staticmethod
    async def list_conflicts(
        session: AsyncSession,
        status: Optional[str] = None
    ) -> List[EventIdentityConflict]:
        stmt = select(EventIdentityConflict)
        if status:
            stmt = stmt.where(EventIdentityConflict.conflict_status == status)
        stmt = stmt.order_by(EventIdentityConflict.id.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def resolve_conflict(
        session: AsyncSession,
        conflict_id: str,
        resolution_in: ConflictResolutionRequest
    ) -> Optional[EventIdentityConflict]:
        stmt = select(EventIdentityConflict).where(
            EventIdentityConflict.conflict_id == conflict_id
        )
        res = await session.execute(stmt)
        cnf = res.scalar_one_or_none()
        if cnf:
            cnf.conflict_status = "RESOLVED"
            cnf.resolved_at = utc_now()
            cnf.resolution_reason = f"[{resolution_in.resolution_action}] {resolution_in.resolution_reason}"
            await session.commit()
            await session.refresh(cnf)
        return cnf

    @staticmethod
    async def create_rule(
        session: AsyncSession, rule_in: DuplicateDetectionRuleCreate
    ) -> DuplicateDetectionRule:
        rule = DuplicateDetectionRule(**rule_in.model_dump())
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    @staticmethod
    async def list_rules(session: AsyncSession) -> List[DuplicateDetectionRule]:
        stmt = select(DuplicateDetectionRule).order_by(DuplicateDetectionRule.id.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_rule_by_code(
        session: AsyncSession, rule_code: str
    ) -> Optional[DuplicateDetectionRule]:
        stmt = select(DuplicateDetectionRule).where(
            DuplicateDetectionRule.rule_code == rule_code
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_receipts(
        session: AsyncSession,
        instrument_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[DuplicateEventReceipt]:
        stmt = select(DuplicateEventReceipt)
        conditions = []
        if instrument_id:
            conditions.append(DuplicateEventReceipt.instrument_id == instrument_id)
        if event_type:
            conditions.append(DuplicateEventReceipt.event_type == event_type)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(DuplicateEventReceipt.id.desc()).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_audit_summary(
        session: AsyncSession,
        provider_id: Optional[str] = None,
        instrument_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates aggregate deduplication counts, duplicate rate, and volume protections.
        """
        # Count canonical identities
        stmt_ident = select(func.count(EventIdentityRegistry.id))
        conditions_id = []
        if provider_id:
            conditions_id.append(EventIdentityRegistry.provider_id == provider_id)
        if instrument_id:
            conditions_id.append(EventIdentityRegistry.instrument_id == instrument_id)
        if conditions_id:
            stmt_ident = stmt_ident.where(and_(*conditions_id))
        res_ident = await session.execute(stmt_ident)
        unique_canonical = res_ident.scalar() or 0

        # Count duplicate receipts
        stmt_rcp = select(func.count(DuplicateEventReceipt.id))
        conditions_rcp = []
        if provider_id:
            conditions_rcp.append(DuplicateEventReceipt.provider_id == provider_id)
        if instrument_id:
            conditions_rcp.append(DuplicateEventReceipt.instrument_id == instrument_id)
        if conditions_rcp:
            stmt_rcp = stmt_rcp.where(and_(*conditions_rcp))
        res_rcp = await session.execute(stmt_rcp)
        confirmed_dups = res_rcp.scalar() or 0

        # Count open conflicts
        stmt_cnf = select(func.count(EventIdentityConflict.id))
        res_cnf = await session.execute(stmt_cnf)
        conflicts = res_cnf.scalar() or 0

        total_deliveries = unique_canonical + confirmed_dups
        dup_rate = round((confirmed_dups / total_deliveries * 100), 2) if total_deliveries > 0 else 0.0

        # Calculate prevented volume from duplicate trade receipts
        stmt_trade_rcp = select(DuplicateEventReceipt).where(
            and_(
                DuplicateEventReceipt.event_type == "TRADE",
                DuplicateEventReceipt.processing_outcome == "IGNORED_REPLAY"
            )
        )
        if provider_id:
            stmt_trade_rcp = stmt_trade_rcp.where(DuplicateEventReceipt.provider_id == provider_id)
        if instrument_id:
            stmt_trade_rcp = stmt_trade_rcp.where(DuplicateEventReceipt.instrument_id == instrument_id)

        res_tr = await session.execute(stmt_trade_rcp)
        trade_receipts = res_tr.scalars().all()

        prevented_vol = Decimal("0.0")
        prevented_turn = Decimal("0.0")
        for r in trade_receipts:
            if r.evidence:
                q = Decimal(str(r.evidence.get("quantity", 0)))
                p = Decimal(str(r.evidence.get("price", 0)))
                prevented_vol += q
                prevented_turn += (p * q)

        return {
            "total_deliveries": total_deliveries,
            "unique_canonical_events": unique_canonical,
            "confirmed_duplicates": confirmed_dups,
            "suspected_duplicates": 0,
            "identity_conflicts": conflicts,
            "prevented_business_inserts": confirmed_dups,
            "prevented_volume": prevented_vol,
            "prevented_turnover": prevented_turn,
            "duplicate_rate_percentage": dup_rate,
        }
