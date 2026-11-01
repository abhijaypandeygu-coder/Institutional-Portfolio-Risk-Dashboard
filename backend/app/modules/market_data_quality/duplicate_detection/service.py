"""
M03.05 - Duplicate Detection and Idempotent Ingestion Service.
Orchestrates:
1. Event Identity Resolution (provider IDs, exchange IDs, sequence tracking, fingerprints).
2. Atomic Database-Level Idempotency (preventing second business inserts).
3. Conflict Detection vs Replay Audits.
4. Protection of Downstream Aggregates (volume, turnover, trade count).
"""

import uuid
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.duplicate_detection.schemas import (
    EventDetectionInput,
    DuplicateDetectionResult,
)
from backend.app.modules.market_data_quality.duplicate_detection.identity.resolver import (
    EventIdentityResolver,
)
from backend.app.modules.market_data_quality.duplicate_detection.audit.repository import (
    DuplicateRepository,
)

logger = logging.getLogger(__name__)


class DuplicateDetectionService:
    """
    Main orchestration service for M03.05.
    """

    @classmethod
    async def process_market_event(
        cls,
        session: AsyncSession,
        input_data: EventDetectionInput,
        commit_on_accept: bool = True
    ) -> DuplicateDetectionResult:
        """
        Evaluates an incoming market event against the canonical identity registry.
        If new: registers identity and authorizes canonical creation.
        If existing + identical content: records duplicate receipt and suppresses duplicate insert.
        If existing + conflicting content: records identity conflict.
        """
        # 1. Resolve stable identity key and fingerprint
        idempotency_key, identity_strategy, identity_scope, canonical_table = (
            EventIdentityResolver.resolve_identity(input_data)
        )
        incoming_fingerprint = EventIdentityResolver.compute_payload_fingerprint(input_data)

        # 2. Check existing identity registration
        existing_identity = await DuplicateRepository.get_identity_by_key(
            session=session, idempotency_key=idempotency_key
        )

        evidence: Dict[str, Any] = {
            "feed_id": input_data.feed_id,
            "instrument_id": input_data.instrument_id,
            "exchange": input_data.exchange,
            "event_type": input_data.event_type,
            "event_timestamp": input_data.event_timestamp.isoformat(),
            "price": str(input_data.price) if input_data.price is not None else None,
            "quantity": str(input_data.quantity) if input_data.quantity is not None else None,
            "provider_event_id": input_data.provider_event_id,
            "sequence_number": input_data.sequence_number,
        }

        # 3. Path A: New Event (with atomic concurrency conflict safety)
        if not existing_identity:
            canonical_event_id = f"EVT_{uuid.uuid4().hex[:12].upper()}"
            try:
                new_record = await DuplicateRepository.register_new_identity(
                    session=session,
                    provider_id=input_data.provider_id,
                    feed_id=input_data.feed_id,
                    instrument_id=input_data.instrument_id,
                    exchange=input_data.exchange,
                    event_type=input_data.event_type,
                    identity_strategy=identity_strategy,
                    identity_scope=identity_scope,
                    idempotency_key=idempotency_key,
                    payload_fingerprint=incoming_fingerprint,
                    canonical_event_id=canonical_event_id,
                    canonical_record_table=canonical_table,
                )
                if commit_on_accept:
                    await session.commit()
                    await session.refresh(new_record)

                return DuplicateDetectionResult(
                    classification="NEW_EVENT",
                    is_duplicate=False,
                    is_new=True,
                    is_conflict=False,
                    identity_strategy=identity_strategy,
                    idempotency_key=idempotency_key,
                    payload_fingerprint=incoming_fingerprint,
                    canonical_event_id=canonical_event_id,
                    canonical_record_table=canonical_table,
                    duplicate_reason=None,
                    existing_delivery_count=1,
                    evidence=evidence,
                )
            except Exception:
                # Concurrent race condition: another worker inserted this exact idempotency_key first!
                await session.rollback()
                existing_identity = await DuplicateRepository.get_identity_by_key(
                    session=session, idempotency_key=idempotency_key
                )
                if not existing_identity:
                    raise  # Re-raise if not an identity race

        # 4. Path B: Existing Identity - Compare Fingerprints
        if existing_identity.payload_fingerprint == incoming_fingerprint:
            # Exact Replay / Confirmed Duplicate
            reason = f"{identity_strategy}_REPLAY"
            receipt = await DuplicateRepository.record_duplicate_receipt(
                session=session,
                identity_record=existing_identity,
                duplicate_reason=reason,
                incoming_provider_event_id=input_data.provider_event_id,
                incoming_sequence=input_data.sequence_number,
                incoming_fingerprint=incoming_fingerprint,
                evidence=evidence,
            )
            if commit_on_accept:
                await session.commit()

            return DuplicateDetectionResult(
                classification="DUPLICATE_EVENT",
                is_duplicate=True,
                is_new=False,
                is_conflict=False,
                identity_strategy=identity_strategy,
                idempotency_key=idempotency_key,
                payload_fingerprint=incoming_fingerprint,
                canonical_event_id=existing_identity.canonical_event_id,
                canonical_record_table=existing_identity.canonical_record_table,
                duplicate_reason=reason,
                existing_delivery_count=existing_identity.delivery_count,
                evidence=evidence,
            )

        # 5. Path C: Identity Conflict (Same key, different payload content)
        conflict_type = "TRADE_VALUE_MISMATCH" if input_data.event_type == "TRADE" else "PAYLOAD_MISMATCH"
        await DuplicateRepository.record_identity_conflict(
            session=session,
            identity_record=existing_identity,
            incoming_reference=input_data.provider_event_id or str(input_data.sequence_number) or idempotency_key,
            incoming_fingerprint=incoming_fingerprint,
            conflict_type=conflict_type,
            evidence=evidence,
        )
        if commit_on_accept:
            await session.commit()

        return DuplicateDetectionResult(
            classification="IDENTITY_CONFLICT",
            is_duplicate=False,
            is_new=False,
            is_conflict=True,
            identity_strategy=identity_strategy,
            idempotency_key=idempotency_key,
            payload_fingerprint=incoming_fingerprint,
            canonical_event_id=existing_identity.canonical_event_id,
            canonical_record_table=existing_identity.canonical_record_table,
            duplicate_reason="IDENTITY_CONFLICT",
            existing_delivery_count=existing_identity.delivery_count,
            evidence=evidence,
        )
