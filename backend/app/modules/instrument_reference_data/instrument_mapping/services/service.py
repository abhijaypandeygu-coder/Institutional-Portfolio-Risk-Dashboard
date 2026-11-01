import uuid
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.instrument_reference_data.instrument_mapping.models import (
    IdentifierNamespace,
    ExternalIdentifierMapping,
    MappingConflictRecord,
    MappingStatus,
    VerificationStatus,
    ResolutionMatchingLevel
)
from backend.app.modules.instrument_reference_data.instrument_mapping.schemas import (
    IdentifierNamespaceCreate,
    ExternalIdentifierMappingCreate,
    ResolveIdentifierRequest,
    ResolvedIdentifierResponse,
    BulkResolveRequest,
    BulkResolveResponse
)
from backend.app.modules.instrument_reference_data.instrument_mapping.repositories.repository import InstrumentMappingRepository
from backend.app.modules.instrument_reference_data.instrument_mapping.normalization.normalizer import normalize_identifier
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument


class InstrumentMappingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InstrumentMappingRepository(session)

    async def create_namespace(self, payload: IdentifierNamespaceCreate) -> IdentifierNamespace:
        existing = await self.repo.get_namespace(payload.namespace_code)
        if existing:
            raise ValueError(f"Namespace '{payload.namespace_code}' already exists.")

        ns = IdentifierNamespace(
            namespace_code=payload.namespace_code.upper(),
            namespace_name=payload.namespace_name,
            namespace_type=payload.namespace_type,
            provider_name=payload.provider_name,
            exchange_code=payload.exchange_code.upper() if payload.exchange_code else None,
            case_sensitive=payload.case_sensitive,
            strip_suffix=payload.strip_suffix
        )
        await self.repo.add_namespace(ns)
        await self.session.commit()
        await self.session.refresh(ns)
        return ns

    async def create_mapping(self, payload: ExternalIdentifierMappingCreate) -> ExternalIdentifierMapping:
        # Validate instrument exists
        inst_res = await self.session.execute(
            select(Instrument).where(Instrument.instrument_id == payload.instrument_id)
        )
        if not inst_res.scalar_one_or_none():
            raise ValueError(f"Instrument '{payload.instrument_id}' does not exist in Instrument Master.")

        # Validate namespace exists
        ns = await self.repo.get_namespace(payload.namespace_code.upper())
        if not ns:
            raise ValueError(f"Namespace '{payload.namespace_code}' does not exist.")

        existing = await self.repo.get_mapping_by_id(payload.mapping_id)
        if existing:
            raise ValueError(f"Mapping '{payload.mapping_id}' already exists.")

        # Normalize identifier
        normalized = normalize_identifier(
            raw_identifier=payload.external_identifier_raw,
            case_sensitive=ns.case_sensitive,
            strip_exchange_suffix=ns.strip_suffix
        )

        mapping = ExternalIdentifierMapping(
            mapping_id=payload.mapping_id,
            namespace_code=payload.namespace_code.upper(),
            external_identifier_raw=payload.external_identifier_raw,
            external_identifier_normalized=normalized,
            target_type=payload.target_type,
            instrument_id=payload.instrument_id,
            listing_id=payload.listing_id,
            exchange_code=payload.exchange_code.upper() if payload.exchange_code else ns.exchange_code,
            mapping_status=payload.mapping_status,
            verification_status=VerificationStatus.VERIFIED,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            source_reference=payload.source_reference
        )
        await self.repo.add_mapping(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def resolve_identifier(self, req: ResolveIdentifierRequest) -> ResolvedIdentifierResponse:
        ns = await self.repo.get_namespace(req.namespace_code.upper())
        if not ns:
            return ResolvedIdentifierResponse(
                matching_level=ResolutionMatchingLevel.INSUFFICIENT_CONTEXT,
                raw_identifier=req.raw_identifier,
                normalized_identifier=req.raw_identifier,
                namespace_code=req.namespace_code,
                is_eligible_for_ingestion=False,
                reason=f"Unknown namespace '{req.namespace_code}'."
            )

        target_date = req.as_of_date or date.today()
        normalized = normalize_identifier(
            raw_identifier=req.raw_identifier,
            case_sensitive=ns.case_sensitive,
            strip_exchange_suffix=ns.strip_suffix
        )

        candidates = await self.repo.find_candidates(
            namespace_code=req.namespace_code.upper(),
            normalized_identifier=normalized,
            as_of_date=target_date,
            exchange_code=req.exchange_code
        )

        if len(candidates) == 0:
            return ResolvedIdentifierResponse(
                matching_level=ResolutionMatchingLevel.NO_MATCH,
                raw_identifier=req.raw_identifier,
                normalized_identifier=normalized,
                namespace_code=req.namespace_code,
                is_eligible_for_ingestion=False,
                reason=f"No active mapping found for identifier '{normalized}' on {target_date}."
            )

        if len(candidates) > 1:
            # Ambiguity / Conflict detection
            inst_ids = list(set(c.instrument_id for c in candidates))
            conflict = MappingConflictRecord(
                conflict_id=f"CONF_{uuid.uuid4().hex[:12].upper()}",
                namespace_code=req.namespace_code.upper(),
                identifier_normalized=normalized,
                conflict_type="MULTIPLE_TARGETS",
                candidate_instrument_ids=",".join(inst_ids),
                reason=f"Identifier '{normalized}' resolved to multiple canonical instruments."
            )
            await self.repo.add_conflict(conflict)
            await self.session.commit()

            return ResolvedIdentifierResponse(
                matching_level=ResolutionMatchingLevel.AMBIGUOUS_MATCH,
                raw_identifier=req.raw_identifier,
                normalized_identifier=normalized,
                namespace_code=req.namespace_code,
                is_eligible_for_ingestion=False,
                candidate_instrument_ids=inst_ids,
                reason=f"Ambiguous mapping: resolves to {len(inst_ids)} distinct canonical instruments."
            )

        # Single unambiguous match
        m = candidates[0]
        eligible = (m.mapping_status == MappingStatus.APPROVED_FOR_INGESTION and m.verification_status == VerificationStatus.VERIFIED)

        return ResolvedIdentifierResponse(
            matching_level=ResolutionMatchingLevel.EXACT_VERIFIED_MATCH,
            raw_identifier=req.raw_identifier,
            normalized_identifier=normalized,
            namespace_code=req.namespace_code,
            instrument_id=m.instrument_id,
            listing_id=m.listing_id,
            exchange_code=m.exchange_code,
            mapping_id=m.mapping_id,
            mapping_version=m.mapping_version,
            is_eligible_for_ingestion=eligible,
            candidate_instrument_ids=[m.instrument_id]
        )

    async def bulk_resolve(self, req: BulkResolveRequest) -> BulkResolveResponse:
        results: List[ResolvedIdentifierResponse] = []
        resolved_cnt = 0
        unresolved_cnt = 0

        for r in req.requests:
            res = await self.resolve_identifier(r)
            results.append(res)
            if res.is_eligible_for_ingestion and res.instrument_id:
                resolved_cnt += 1
            else:
                unresolved_cnt += 1

        return BulkResolveResponse(
            total_requested=len(req.requests),
            resolved_count=resolved_cnt,
            unresolved_count=unresolved_cnt,
            results=results
        )

