"""
Core Business Services for M04.02 Security Classification.
Handles:
- Classification scheme registration and taxonomy node hierarchy
- Sector and industry assignment with parent-child relationship validation
- Asset category assignment with M04.01 instrument type compatibility checks
- Bitemporal point-in-time classification resolution
- High-performance bulk lookup for portfolio concentration and risk analytics
- Conflict and review management
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.app.modules.instrument_reference_data.security_classification.models import (
    ClassificationScheme,
    ClassificationSchemeVersion,
    ClassificationNode,
    AssetCategory,
    InstrumentClassificationAssignment,
    InstrumentAssetCategoryAssignment,
    ClassificationReviewCase,
    ClassificationAuditEvent,
    utc_now,
)
from backend.app.modules.instrument_reference_data.security_classification.schemas import (
    ClassificationSchemeCreate,
    ClassificationSchemeVersionCreate,
    ClassificationNodeCreate,
    AssetCategoryCreate,
    ClassificationAssignRequest,
    AssetCategoryAssignRequest,
    BulkClassificationLookupRequest,
    BulkClassificationLookupResponse,
    InstrumentClassificationDetail,
)
from backend.app.modules.instrument_reference_data.security_classification.repositories.repository import (
    ClassificationRepository,
)
from backend.app.modules.instrument_reference_data.security_classification.policies.classification_rules import (
    validate_asset_category_compatibility,
    AssignmentStatus,
    VerificationStatus,
    AssetCategoryCode,
)
from backend.app.modules.instrument_reference_data.instrument_master.repositories.repository import (
    InstrumentRepository,
)


class SecurityClassificationService:
    """Orchestrates taxonomy management, instrument classification, and bitemporal resolution."""

    # ---------------------------------------------------------
    # 1. SCHEMES & TAXONOMY
    # ---------------------------------------------------------
    @classmethod
    async def create_scheme(
        cls,
        session: AsyncSession,
        req: ClassificationSchemeCreate,
        actor_id: str,
    ) -> ClassificationScheme:
        existing = await ClassificationRepository.get_scheme_by_code(session, req.scheme_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Classification scheme '{req.scheme_code}' already exists.",
            )

        scheme = ClassificationScheme(
            scheme_code=req.scheme_code,
            scheme_name=req.scheme_name,
            description=req.description,
            provider=req.provider,
            scheme_type=req.scheme_type,
            applicable_market_scope=req.applicable_market_scope,
            is_primary_default=req.is_primary_default,
        )
        session.add(scheme)
        await session.flush()

        # Create default initial version (V1.0)
        v1 = ClassificationSchemeVersion(
            scheme_id=scheme.id,
            version_code="1.0.0",
            version_description="Initial scheme taxonomy baseline",
            effective_from=utc_now(),
        )
        session.add(v1)

        await ClassificationRepository.create_audit_event(
            session=session,
            action_type="SCHEME_CREATED",
            new_state=req.scheme_code,
            actor_id=actor_id,
            reason=f"Registered classification scheme {req.scheme_name}",
        )
        await session.commit()
        return scheme

    @classmethod
    async def create_node(
        cls,
        session: AsyncSession,
        scheme_code: str,
        version_code: str,
        req: ClassificationNodeCreate,
        actor_id: str,
    ) -> ClassificationNode:
        """Creates a Sector or Industry node, verifying parent hierarchy."""
        scheme = await ClassificationRepository.get_scheme_by_code(session, scheme_code)
        if not scheme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme not found.")

        version = await ClassificationRepository.get_version_by_code(session, scheme.id, version_code)
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme version not found.")

        # Check existing code
        existing = await ClassificationRepository.get_node_by_code(session, scheme.id, version.id, req.node_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Node '{req.node_code}' already exists in {scheme_code} version {version_code}.",
            )

        # Hierarchy validation: If INDUSTRY, must have valid parent SECTOR node
        if req.node_type == "INDUSTRY":
            if not req.parent_node_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Industry node must reference a valid parent sector node_id.",
                )
            parent = await ClassificationRepository.get_node_by_id(session, req.parent_node_id)
            if not parent or parent.node_type != "SECTOR":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Parent node '{req.parent_node_id}' is invalid or is not of type SECTOR.",
                )

        node_id = f"NOD_{uuid.uuid4().hex[:12].upper()}"
        node = ClassificationNode(
            node_id=node_id,
            scheme_id=scheme.id,
            scheme_version_id=version.id,
            node_code=req.node_code,
            node_name=req.node_name,
            node_description=req.node_description,
            node_type=req.node_type,
            parent_node_id=req.parent_node_id,
            hierarchy_level=req.hierarchy_level,
            effective_from=utc_now(),
        )
        session.add(node)

        await ClassificationRepository.create_audit_event(
            session=session,
            action_type="TAXONOMY_NODE_CREATED",
            new_state=f"{req.node_type}:{req.node_code}",
            actor_id=actor_id,
            reason=f"Created {req.node_name} under {scheme_code}",
        )
        await session.commit()
        return node

    # ---------------------------------------------------------
    # 2. INSTRUMENT CLASSIFICATION ASSIGNMENT
    # ---------------------------------------------------------
    @classmethod
    async def assign_classification(
        cls,
        session: AsyncSession,
        instrument_id: str,
        req: ClassificationAssignRequest,
        actor_id: str,
    ) -> InstrumentClassificationAssignment:
        """
        Assigns sector and industry classification with bitemporal valid time and versioning.
        Enforces parent-sector consistency between sector and industry nodes.
        """
        inst = await InstrumentRepository.get_by_instrument_id(session, instrument_id)
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

        scheme = await ClassificationRepository.get_scheme_by_code(session, req.scheme_code)
        if not scheme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme not found.")

        version = (
            await ClassificationRepository.get_version_by_code(session, scheme.id, req.version_code)
            if req.version_code
            else await ClassificationRepository.get_latest_version_for_scheme(session, scheme.id)
        )
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active scheme version not found.")

        # Resolve sector node
        sector_node = await ClassificationRepository.get_node_by_code(session, scheme.id, version.id, req.sector_code)
        if not sector_node or sector_node.node_type != "SECTOR":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sector code '{req.sector_code}' is invalid in {req.scheme_code}.",
            )

        # Resolve industry node if provided
        industry_node = None
        if req.industry_code:
            industry_node = await ClassificationRepository.get_node_by_code(
                session, scheme.id, version.id, req.industry_code
            )
            if not industry_node or industry_node.node_type != "INDUSTRY":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Industry code '{req.industry_code}' is invalid in {req.scheme_code}.",
                )

            # Industry-to-Sector Consistency Check
            if industry_node.parent_node_id != sector_node.node_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sector-Industry inconsistency: Industry '{industry_node.node_name}' does not belong to Sector '{sector_node.node_name}'.",
                )

        now = utc_now()
        valid_from = req.valid_from or now

        # Close existing active assignment for this scheme
        curr_assignment = await ClassificationRepository.get_active_classification(
            session, instrument_id, scheme.id, as_of_valid_time=valid_from
        )
        next_ver = 1
        if curr_assignment:
            curr_assignment.valid_to = valid_from
            next_ver = curr_assignment.assignment_version + 1

        assign_id = f"ASN_{uuid.uuid4().hex[:12].upper()}"
        assignment = InstrumentClassificationAssignment(
            assignment_id=assign_id,
            instrument_id=instrument_id,
            scheme_id=scheme.id,
            scheme_version_id=version.id,
            sector_node_id=sector_node.node_id,
            industry_node_id=industry_node.node_id if industry_node else None,
            assignment_status=AssignmentStatus.CLASSIFIED.value,
            verification_status=VerificationStatus.APPROVED.value,
            assignment_source=req.assignment_source,
            assignment_reason=req.assignment_reason,
            assignment_version=next_ver,
            valid_from=valid_from,
            recorded_at=now,
            recorded_by=actor_id,
        )
        session.add(assignment)

        await ClassificationRepository.create_audit_event(
            session=session,
            instrument_id=instrument_id,
            action_type="CLASSIFICATION_ASSIGNED",
            new_state=f"{sector_node.node_code}:{industry_node.node_code if industry_node else 'NONE'}",
            actor_id=actor_id,
            reason=req.assignment_reason,
            metadata={"scheme": req.scheme_code, "version": version.version_code},
        )
        await session.commit()
        return assignment

    # ---------------------------------------------------------
    # 3. ASSET CATEGORY ASSIGNMENT
    # ---------------------------------------------------------
    @classmethod
    async def assign_asset_category(
        cls,
        session: AsyncSession,
        instrument_id: str,
        req: AssetCategoryAssignRequest,
        actor_id: str,
    ) -> InstrumentAssetCategoryAssignment:
        """Assigns an analytical asset category, verifying compatibility with M04.01 instrument_type."""
        inst = await InstrumentRepository.get_by_instrument_id(session, instrument_id)
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

        # Check compatibility with M04.01 instrument_type
        if not validate_asset_category_compatibility(inst.instrument_type, req.category_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Compatibility Error: Asset category '{req.category_code}' is incompatible with canonical instrument type '{inst.instrument_type}'.",
            )

        now = utc_now()
        curr_cat = await ClassificationRepository.get_active_asset_category(session, instrument_id)
        if curr_cat:
            curr_cat.valid_to = now

        assign_id = f"ACA_{uuid.uuid4().hex[:12].upper()}"
        assignment = InstrumentAssetCategoryAssignment(
            assignment_id=assign_id,
            instrument_id=instrument_id,
            category_code=req.category_code,
            assignment_status=AssignmentStatus.CLASSIFIED.value,
            verification_status=VerificationStatus.APPROVED.value,
            assignment_source=req.assignment_source,
            assignment_reason=req.assignment_reason,
            valid_from=now,
            recorded_at=now,
            recorded_by=actor_id,
        )
        session.add(assignment)

        await ClassificationRepository.create_audit_event(
            session=session,
            instrument_id=instrument_id,
            action_type="ASSET_CATEGORY_ASSIGNED",
            new_state=req.category_code,
            actor_id=actor_id,
            reason=req.assignment_reason,
        )
        await session.commit()
        return assignment

    # ---------------------------------------------------------
    # 4. POINT-IN-TIME & BULK LOOKUP (PORTFOLIO & RISK ENTRYPOINT)
    # ---------------------------------------------------------
    @classmethod
    async def lookup_instrument_classification(
        cls,
        session: AsyncSession,
        instrument_id: str,
        scheme_code: Optional[str] = None,
        as_of_valid_time: Optional[datetime] = None,
        as_of_transaction_time: Optional[datetime] = None,
    ) -> Optional[InstrumentClassificationDetail]:
        """Resolves classification for a single instrument with bitemporal point-in-time support."""
        scheme = (
            await ClassificationRepository.get_scheme_by_code(session, scheme_code)
            if scheme_code
            else await ClassificationRepository.get_default_primary_scheme(session)
        )
        if not scheme:
            return None

        assignment = await ClassificationRepository.get_active_classification(
            session,
            instrument_id=instrument_id,
            scheme_id=scheme.id,
            as_of_valid_time=as_of_valid_time,
            as_of_transaction_time=as_of_transaction_time,
        )
        if not assignment:
            return None

        # Resolve nodes
        sector = await ClassificationRepository.get_node_by_id(session, assignment.sector_node_id)
        industry = (
            await ClassificationRepository.get_node_by_id(session, assignment.industry_node_id)
            if assignment.industry_node_id
            else None
        )
        version = await session.get(ClassificationSchemeVersion, assignment.scheme_version_id)
        cat_assignment = await ClassificationRepository.get_active_asset_category(session, instrument_id)

        return InstrumentClassificationDetail(
            instrument_id=instrument_id,
            scheme_code=scheme.scheme_code,
            scheme_name=scheme.scheme_name,
            version_code=version.version_code if version else "1.0.0",
            sector_code=sector.node_code if sector else "UNKNOWN",
            sector_name=sector.node_name if sector else "UNKNOWN",
            industry_code=industry.node_code if industry else None,
            industry_name=industry.node_name if industry else None,
            asset_category_code=cat_assignment.category_code if cat_assignment else None,
            asset_category_name=cat_assignment.category_code if cat_assignment else None,
            assignment_status=assignment.assignment_status,
            verification_status=assignment.verification_status,
            assignment_source=assignment.assignment_source,
            valid_from=assignment.valid_from,
            valid_to=assignment.valid_to,
            recorded_at=assignment.recorded_at,
            assignment_version=assignment.assignment_version,
        )

    @classmethod
    async def bulk_lookup(
        cls,
        session: AsyncSession,
        req: BulkClassificationLookupRequest,
    ) -> BulkClassificationLookupResponse:
        """High-performance bulk classification retrieval for portfolio concentration and risk models."""
        results: Dict[str, Optional[InstrumentClassificationDetail]] = {}
        classified_count = 0

        for inst_id in req.instrument_ids:
            detail = await cls.lookup_instrument_classification(
                session,
                instrument_id=inst_id,
                scheme_code=req.scheme_code,
                as_of_valid_time=req.as_of_valid_time,
                as_of_transaction_time=req.as_of_transaction_time,
            )
            results[inst_id] = detail
            if detail is not None:
                classified_count += 1

        return BulkClassificationLookupResponse(
            results=results,
            as_of_valid_time=req.as_of_valid_time,
            as_of_transaction_time=req.as_of_transaction_time,
            total_requested=len(req.instrument_ids),
            total_classified=classified_count,
        )

