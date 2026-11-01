"""
Core Business Services for M04.01 Instrument Master.
Handles:
- Canonical identity generation and instrument creation.
- Venue-specific listing management and primary listing enforcement.
- Attribute updates with effective-dated history retention.
- Venue-aware identity resolution (for M02 ingestion & M03 validation).
- Staged batch imports with preview, validation, and review gating.
"""
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.app.modules.instrument_reference_data.instrument_master.models import (
    Instrument,
    InstrumentListing,
    InstrumentIdentifier,
    InstrumentSource,
    InstrumentAttributeHistory,
    InstrumentImportBatch,
    InstrumentImportRecord,
    InstrumentIdentityReview,
    InstrumentAuditEvent,
    utc_now,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentCreateRequest,
    InstrumentUpdateRequest,
    ListingCreateRequest,
    ListingStatusUpdateRequest,
    IdentifierCreateRequest,
    ImportBatchCreateRequest,
    IdentityReviewResolveRequest,
    InstrumentResolutionResponse,
)
from backend.app.modules.instrument_reference_data.instrument_master.repositories.repository import (
    InstrumentRepository,
)
from backend.app.modules.instrument_reference_data.instrument_master.policies.identity_rules import (
    LifecycleStatus,
    ListingStatus,
    VerificationStatus,
    ImportStatus,
    MatchClassification,
    validate_isin_checksum,
)


class InstrumentMasterService:
    """Orchestrates authoritative canonical instrument lifecycle, listings, and resolution."""

    # ---------------------------------------------------------
    # 1. CANONICAL INSTRUMENTS
    # ---------------------------------------------------------
    @classmethod
    async def create_instrument(
        cls,
        session: AsyncSession,
        req: InstrumentCreateRequest,
        actor_id: str = "system",
    ) -> Instrument:
        """Creates a canonical instrument with a stable internal UUID."""
        # 1. Duplicate check by verified ISIN
        if req.isin:
            existing = await InstrumentRepository.get_by_isin(session, req.isin)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An instrument with verified ISIN '{req.isin}' already exists ({existing.instrument_id}: {existing.canonical_name}).",
                )

        inst_id = f"INST_{uuid.uuid4().hex[:12].upper()}"
        instrument = Instrument(
            instrument_id=inst_id,
            canonical_name=req.canonical_name,
            short_name=req.short_name,
            instrument_type=req.instrument_type,
            asset_class=req.asset_class,
            security_type=req.security_type,
            issuer_name=req.issuer_name,
            isin=req.isin,
            country_of_issue=req.country_of_issue,
            issue_currency=req.issue_currency,
            primary_market_id=req.primary_market_id,
            lifecycle_status=LifecycleStatus.ACTIVE.value,
            verification_status=VerificationStatus.VERIFIED.value if req.isin else VerificationStatus.UNVERIFIED.value,
            current_version=1,
            effective_from=utc_now(),
        )
        session.add(instrument)
        await session.flush()

        # Add initial source provenance
        source = InstrumentSource(
            instrument_id=inst_id,
            source_name=req.source_name,
            source_type="MANUAL_ADMIN" if actor_id != "system" else "SYSTEM",
            retrieved_at=utc_now(),
            verification_status=VerificationStatus.VERIFIED.value if req.isin else VerificationStatus.UNVERIFIED.value,
        )
        session.add(source)

        # Audit event
        await InstrumentRepository.create_audit_event(
            session=session,
            instrument_id=inst_id,
            action_type="INSTRUMENT_CREATED",
            new_state=LifecycleStatus.ACTIVE.value,
            actor_id=actor_id,
            reason=f"Initial registration of {req.canonical_name}",
            metadata={"isin": req.isin, "type": req.instrument_type},
        )

        await session.commit()
        return instrument

    @classmethod
    async def update_instrument(
        cls,
        session: AsyncSession,
        instrument_id: str,
        req: InstrumentUpdateRequest,
        actor_id: str,
    ) -> Instrument:
        """Updates permitted instrument attributes with full effective-dated version history."""
        inst = await InstrumentRepository.get_by_instrument_id(session, instrument_id)
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

        history_entries = []
        now = utc_now()

        if req.canonical_name and req.canonical_name != inst.canonical_name:
            history_entries.append(
                InstrumentAttributeHistory(
                    instrument_id=instrument_id,
                    field_name="canonical_name",
                    old_value=inst.canonical_name,
                    new_value=req.canonical_name,
                    effective_from=inst.effective_from,
                    effective_to=now,
                    recorded_at=now,
                    changed_by=actor_id,
                    change_reason=req.change_reason,
                    record_version=inst.current_version,
                )
            )
            inst.canonical_name = req.canonical_name

        if req.short_name and req.short_name != inst.short_name:
            history_entries.append(
                InstrumentAttributeHistory(
                    instrument_id=instrument_id,
                    field_name="short_name",
                    old_value=inst.short_name,
                    new_value=req.short_name,
                    effective_from=inst.effective_from,
                    effective_to=now,
                    recorded_at=now,
                    changed_by=actor_id,
                    change_reason=req.change_reason,
                    record_version=inst.current_version,
                )
            )
            inst.short_name = req.short_name

        if req.lifecycle_status and req.lifecycle_status != inst.lifecycle_status:
            history_entries.append(
                InstrumentAttributeHistory(
                    instrument_id=instrument_id,
                    field_name="lifecycle_status",
                    old_value=inst.lifecycle_status,
                    new_value=req.lifecycle_status,
                    effective_from=inst.effective_from,
                    effective_to=now,
                    recorded_at=now,
                    changed_by=actor_id,
                    change_reason=req.change_reason,
                    record_version=inst.current_version,
                )
            )
            inst.lifecycle_status = req.lifecycle_status

        for h in history_entries:
            session.add(h)

        if history_entries:
            inst.current_version += 1
            inst.updated_at = now

            await InstrumentRepository.create_audit_event(
                session=session,
                instrument_id=instrument_id,
                action_type="INSTRUMENT_UPDATED",
                new_state=f"Version {inst.current_version}",
                actor_id=actor_id,
                reason=req.change_reason,
                metadata={"changes_count": len(history_entries)},
            )

        await session.commit()
        return inst

    # ---------------------------------------------------------
    # 2. EXCHANGE-SPECIFIC LISTINGS
    # ---------------------------------------------------------
    @classmethod
    async def create_listing(
        cls,
        session: AsyncSession,
        instrument_id: str,
        req: ListingCreateRequest,
        actor_id: str,
    ) -> InstrumentListing:
        """Creates a venue listing for an instrument."""
        inst = await InstrumentRepository.get_by_instrument_id(session, instrument_id)
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

        # Check existing active listing on the same exchange & symbol
        existing = await InstrumentRepository.find_listing_by_symbol(
            session, req.exchange_id, req.exchange_symbol
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An active listing already exists for {req.exchange_id}:{req.exchange_symbol} (listing_id={existing.listing_id}).",
            )

        # Primary listing constraint: Only one active primary listing permitted per instrument
        if req.is_primary_listing:
            curr_listings = await InstrumentRepository.get_listings_for_instrument(session, instrument_id)
            for lst in curr_listings:
                if lst.is_primary_listing:
                    lst.is_primary_listing = False

        lst_id = f"LST_{uuid.uuid4().hex[:12].upper()}"
        listing = InstrumentListing(
            listing_id=lst_id,
            instrument_id=instrument_id,
            market_id=req.market_id,
            exchange_id=req.exchange_id,
            exchange_symbol=req.exchange_symbol.upper(),
            exchange_security_code=req.exchange_security_code,
            trading_currency=req.trading_currency,
            listing_type=req.listing_type,
            listing_status=ListingStatus.ACTIVE.value,
            is_primary_listing=req.is_primary_listing,
            source_reference=req.source_reference,
            effective_from=utc_now(),
        )
        session.add(listing)

        await InstrumentRepository.create_audit_event(
            session=session,
            instrument_id=instrument_id,
            listing_id=lst_id,
            action_type="LISTING_CREATED",
            new_state=ListingStatus.ACTIVE.value,
            actor_id=actor_id,
            reason=f"Created listing for {req.exchange_id}:{req.exchange_symbol}",
        )

        await session.commit()
        return listing

    @classmethod
    async def update_listing_status(
        cls,
        session: AsyncSession,
        listing_id: str,
        req: ListingStatusUpdateRequest,
        actor_id: str,
    ) -> InstrumentListing:
        """Updates listing status (SUSPENDED, DELISTED, etc.) without deleting historical record."""
        listing = await InstrumentRepository.get_listing_by_id(session, listing_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found.")

        old_status = listing.listing_status
        listing.listing_status = req.listing_status
        listing.updated_at = utc_now()

        await InstrumentRepository.create_audit_event(
            session=session,
            instrument_id=listing.instrument_id,
            listing_id=listing_id,
            action_type="LISTING_STATUS_CHANGED",
            previous_state=old_status,
            new_state=req.listing_status,
            actor_id=actor_id,
            reason=req.change_reason,
        )

        await session.commit()
        return listing

    # ---------------------------------------------------------
    # 3. IDENTITY RESOLUTION (FOR M02 & M03)
    # ---------------------------------------------------------
    @classmethod
    async def resolve_identifier(
        cls,
        session: AsyncSession,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        isin: Optional[str] = None,
    ) -> InstrumentResolutionResponse:
        """
        Authoritative identity resolution for M02 ingestion & M03 validation.
        Resolves exchange + symbol or ISIN to canonical instrument_id and listing_id.
        """
        # 1. Resolve by ISIN (unambiguous)
        if isin:
            cleaned_isin = isin.strip().upper()
            inst = await InstrumentRepository.get_by_isin(session, cleaned_isin)
            if inst:
                listings = await InstrumentRepository.get_listings_for_instrument(session, inst.instrument_id)
                prim = next((l for l in listings if l.is_primary_listing), (listings[0] if listings else None))
                return InstrumentResolutionResponse(
                    match_status="EXACT_MATCH",
                    instrument_id=inst.instrument_id,
                    canonical_name=inst.canonical_name,
                    listing_id=prim.listing_id if prim else None,
                    exchange_id=prim.exchange_id if prim else None,
                    exchange_symbol=prim.exchange_symbol if prim else None,
                    isin=inst.isin,
                    lifecycle_status=inst.lifecycle_status,
                    listing_status=prim.listing_status if prim else None,
                    verification_status=inst.verification_status,
                    confidence_score=1.0,
                )

        # 2. Resolve by Exchange + Symbol
        if exchange and symbol:
            cleaned_sym = symbol.strip().upper()
            cleaned_exch = exchange.strip().upper()
            listing = await InstrumentRepository.find_listing_by_symbol(session, cleaned_exch, cleaned_sym)
            if listing:
                inst = await InstrumentRepository.get_by_instrument_id(session, listing.instrument_id)
                return InstrumentResolutionResponse(
                    match_status="EXACT_MATCH",
                    instrument_id=inst.instrument_id,
                    canonical_name=inst.canonical_name,
                    listing_id=listing.listing_id,
                    exchange_id=listing.exchange_id,
                    exchange_symbol=listing.exchange_symbol,
                    isin=inst.isin,
                    lifecycle_status=inst.lifecycle_status,
                    listing_status=listing.listing_status,
                    verification_status=listing.verification_status,
                    confidence_score=1.0,
                )

        # 3. Resolve by Symbol alone (Ambiguity check across venues)
        if symbol and not exchange:
            cleaned_sym = symbol.strip().upper()
            listings = await InstrumentRepository.find_listings_by_symbol_only(session, cleaned_sym)
            if len(listings) == 1:
                lst = listings[0]
                inst = await InstrumentRepository.get_by_instrument_id(session, lst.instrument_id)
                return InstrumentResolutionResponse(
                    match_status="EXACT_MATCH",
                    instrument_id=inst.instrument_id,
                    canonical_name=inst.canonical_name,
                    listing_id=lst.listing_id,
                    exchange_id=lst.exchange_id,
                    exchange_symbol=lst.exchange_symbol,
                    isin=inst.isin,
                    confidence_score=0.9,
                )
            elif len(listings) > 1:
                # Ambiguous! Must return candidate listings without making arbitrary choice
                candidates = [
                    {
                        "instrument_id": l.instrument_id,
                        "listing_id": l.listing_id,
                        "exchange_id": l.exchange_id,
                        "exchange_symbol": l.exchange_symbol,
                    }
                    for l in listings
                ]
                return InstrumentResolutionResponse(
                    match_status="AMBIGUOUS_MATCH",
                    confidence_score=0.5,
                    candidates=candidates,
                )

        return InstrumentResolutionResponse(match_status="NO_MATCH", confidence_score=0.0)

    # ---------------------------------------------------------
    # 4. STAGED IMPORT BATCHES
    # ---------------------------------------------------------
    @classmethod
    async def create_import_batch(
        cls,
        session: AsyncSession,
        req: ImportBatchCreateRequest,
        actor_id: str,
    ) -> InstrumentImportBatch:
        """Creates a staged import batch, validates rows, and checks duplicate candidates."""
        serialized_records = str(req.records)
        f_hash = hashlib.sha256(serialized_records.encode("utf-8")).hexdigest()

        batch_ref = f"IMP_{uuid.uuid4().hex[:12].upper()}"
        batch = InstrumentImportBatch(
            batch_reference=batch_ref,
            source_name=req.source_name,
            source_type=req.source_type,
            file_hash=f_hash,
            import_status=ImportStatus.VALIDATING.value,
            total_rows=len(req.records),
            created_by=actor_id,
        )
        session.add(batch)
        await session.flush()

        valid_count = 0
        invalid_count = 0
        dup_count = 0

        for idx, row in enumerate(req.records, 1):
            val_status = "VALID"
            err_details = None
            match_status = "NO_MATCH"
            resolved_inst_id = None

            # Basic field presence check
            canon_name = row.get("canonical_name")
            isin = row.get("isin")
            exch = row.get("exchange_id")
            sym = row.get("exchange_symbol")

            if not canon_name:
                val_status = "INVALID"
                err_details = "Missing required 'canonical_name'"
                invalid_count += 1
            elif isin and not validate_isin_checksum(isin.strip().upper()):
                val_status = "INVALID"
                err_details = f"Invalid ISIN format/checksum '{isin}'"
                invalid_count += 1
            else:
                valid_count += 1
                # Check duplicate candidate
                if isin:
                    existing_inst = await InstrumentRepository.get_by_isin(session, isin.strip().upper())
                    if existing_inst:
                        match_status = "EXACT_MATCH"
                        resolved_inst_id = existing_inst.instrument_id
                        dup_count += 1

            record = InstrumentImportRecord(
                batch_reference=batch_ref,
                source_row_number=idx,
                parsed_payload=row,
                validation_status=val_status,
                match_status=match_status,
                resolved_instrument_id=resolved_inst_id,
                error_details=err_details,
            )
            session.add(record)

        batch.valid_rows = valid_count
        batch.invalid_rows = invalid_count
        batch.duplicate_candidates = dup_count
        batch.import_status = ImportStatus.REVIEW_REQUIRED.value if (invalid_count > 0 or dup_count > 0) else ImportStatus.APPROVED.value

        await session.commit()
        return batch

    @classmethod
    async def process_import_batch(
        cls,
        session: AsyncSession,
        batch_reference: str,
        actor_id: str,
    ) -> InstrumentImportBatch:
        """Processes approved records from an import batch into canonical instruments & listings."""
        batch = await InstrumentRepository.get_import_batch(session, batch_reference)
        if not batch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found.")

        # Query records
        stmt = select(InstrumentImportRecord).where(
            InstrumentImportRecord.batch_reference == batch_reference,
            InstrumentImportRecord.validation_status == "VALID",
        )
        records = list((await session.execute(stmt)).scalars().all())

        created = 0
        updated = 0
        failed = 0

        for rec in records:
            p = rec.parsed_payload
            try:
                # If matched existing instrument, add listing
                if rec.resolved_instrument_id:
                    inst_id = rec.resolved_instrument_id
                    updated += 1
                else:
                    # Create new instrument
                    inst_req = InstrumentCreateRequest(
                        canonical_name=p["canonical_name"],
                        short_name=p.get("short_name", p["canonical_name"][:16]),
                        instrument_type=p.get("instrument_type", "COMMON_STOCK"),
                        asset_class=p.get("asset_class", "EQUITY"),
                        issuer_name=p.get("issuer_name"),
                        isin=p.get("isin"),
                        country_of_issue=p.get("country_of_issue"),
                        issue_currency=p.get("issue_currency"),
                        source_name=batch.source_name,
                    )
                    new_inst = await cls.create_instrument(session, inst_req, actor_id=actor_id)
                    inst_id = new_inst.instrument_id
                    rec.resolved_instrument_id = inst_id
                    created += 1

                # If exchange + symbol specified, create listing
                if p.get("exchange_id") and p.get("exchange_symbol"):
                    lst_req = ListingCreateRequest(
                        market_id=p.get("market_id", "IN"),
                        exchange_id=p["exchange_id"],
                        exchange_symbol=p["exchange_symbol"],
                        trading_currency=p.get("trading_currency", "INR"),
                        is_primary_listing=p.get("is_primary_listing", True),
                        source_reference=batch_reference,
                    )
                    lst = await cls.create_listing(session, inst_id, lst_req, actor_id=actor_id)
                    rec.resolved_listing_id = lst.listing_id

            except Exception as e:
                failed += 1
                rec.error_details = str(e)

        batch.created_count = created
        batch.updated_count = updated
        batch.failed_count = failed
        batch.completed_at = utc_now()
        if failed > 0 or batch.invalid_rows > 0:
            batch.import_status = ImportStatus.PARTIALLY_COMPLETED.value
        else:
            batch.import_status = ImportStatus.COMPLETED.value

        await session.commit()
        return batch
