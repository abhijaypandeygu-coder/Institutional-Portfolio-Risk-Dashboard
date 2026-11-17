from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.audit_trail.models.audit_models import (
    AuditEvent,
    AuditChainCheckpoint,
    AuditIntegrityRun,
    AuditRetentionPolicy,
    EventCategory,
    IntegrityVerificationStatus,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.schemas.audit_schemas import (
    AuditEventCreateRequest,
    AuditEventResponse,
    AuditSearchResponse,
    AuditIntegrityRunResponse,
    AuditCheckpointResponse,
    AuditRetentionPolicyResponse,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.services.audit_trail_service import (
    AuditTrailService,
)

router = APIRouter(prefix="/audit", tags=["M14.07 Audit Trail"])


@router.post("/events", response_model=AuditEventResponse, status_code=201)
async def record_audit_event(
    request: AuditEventCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a material user action, system event, or configuration change into the append-only audit trail."""
    service = AuditTrailService(db)
    return await service.record_audit_event(request)


@router.get("/events", response_model=AuditSearchResponse)
async def search_audit_events(
    event_category: Optional[EventCategory] = None,
    source_module: Optional[str] = None,
    target_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Search and filter authorized audit records."""
    service = AuditTrailService(db)
    return await service.search_events(
        event_category=event_category,
        source_module=source_module,
        target_id=target_id,
        actor_id=actor_id,
        correlation_id=correlation_id,
        page=page,
        page_size=page_size,
    )


@router.get("/timeline", response_model=List[AuditEventResponse])
async def get_event_timeline(
    correlation_id: str = Query(..., description="Workflow or incident correlation ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve chronological cross-module timeline of correlated audit events."""
    service = AuditTrailService(db)
    return await service.get_timeline(correlation_id)


@router.post("/integrity/verify", response_model=AuditIntegrityRunResponse)
async def verify_integrity(
    chain_id: str = "GLOBAL_CHAIN",
    db: AsyncSession = Depends(get_db),
):
    """Execute cryptographic SHA-256 hash-chain verification and generate checkpoint."""
    service = AuditTrailService(db)
    return await service.verify_chain_integrity(chain_id)


@router.get("/integrity/checkpoints", response_model=List[AuditCheckpointResponse])
async def list_checkpoints(db: AsyncSession = Depends(get_db)):
    """List historical chain checkpoints with cryptographic hashes."""
    stmt = select(AuditChainCheckpoint).order_by(desc(AuditChainCheckpoint.created_at)).limit(20)
    res = await db.execute(stmt)
    cps = res.scalars().all()
    return [
        AuditCheckpointResponse(
            id=c.id,
            chain_id=c.chain_id,
            highest_sequence=c.highest_sequence,
            checkpoint_hash=c.checkpoint_hash,
            hash_algorithm=c.hash_algorithm,
            event_count=c.event_count,
            created_at=c.created_at,
            verification_status=c.verification_status,
        )
        for c in cps
    ]


@router.get("/retention/policies", response_model=List[AuditRetentionPolicyResponse])
async def list_retention_policies(db: AsyncSession = Depends(get_db)):
    """List active audit retention and archival policies."""
    stmt = select(AuditRetentionPolicy).where(AuditRetentionPolicy.status == "ACTIVE")
    res = await db.execute(stmt)
    policies = res.scalars().all()
    if not policies:
        # Standard default governance policies
        default_policies = [
            AuditRetentionPolicy(policy_code="POL_CONFIG_CHANGES", policy_name="Configuration Changes Policy", event_category=EventCategory.CONFIGURATION_CHANGE, retention_days=2555),
            AuditRetentionPolicy(policy_code="POL_CONTROL_DECISIONS", policy_name="Risk Control & Override Policy", event_category=EventCategory.CONTROL_DECISION, retention_days=2555),
            AuditRetentionPolicy(policy_code="POL_SYSTEM_EVENTS", policy_name="Operational System Events Policy", event_category=EventCategory.SYSTEM_EVENT, retention_days=1095),
        ]
        for p in default_policies:
            db.add(p)
        await db.commit()
        policies = default_policies

    return [
        AuditRetentionPolicyResponse(
            id=p.id,
            policy_code=p.policy_code,
            policy_name=p.policy_name,
            event_category=p.event_category,
            retention_days=p.retention_days,
            archive_before_expiry=p.archive_before_expiry,
            policy_version=p.policy_version,
            status=p.status,
        )
        for p in policies
    ]
