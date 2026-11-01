"""
FastAPI Router for M03.05 - Duplicate Detection.
Exposes endpoints for:
- Event detection & batch processing
- Duplicate trade & market event queries
- Idempotency checks
- Duplicate audit records & summary metrics
- Identity conflict resolution
- Detection rules configuration
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import require_role, UserRole
from backend.app.modules.market_data_quality.duplicate_detection.schemas import (
    EventDetectionInput,
    DuplicateDetectionResult,
    DuplicateDetectionRuleCreate,
    DuplicateDetectionRuleResponse,
    DuplicateReceiptResponse,
    IdentityConflictResponse,
    ConflictResolutionRequest,
    DuplicateAuditSummary,
)
from backend.app.modules.market_data_quality.duplicate_detection.service import (
    DuplicateDetectionService,
)
from backend.app.modules.market_data_quality.duplicate_detection.audit.repository import (
    DuplicateRepository,
)

router = APIRouter(prefix="/quality/duplicates", tags=["M03.05 - Duplicate Detection"])


@router.post("/detect", response_model=DuplicateDetectionResult)
async def detect_duplicate_event(
    payload: EventDetectionInput,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.OPERATOR)),
):
    """
    Evaluates an incoming market data event (trade, quote, snapshot, delta, OHLCV)
    for duplicates, replays, or identity conflicts.
    """
    try:
        return await DuplicateDetectionService.process_market_event(session, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Duplicate detection error: {str(e)}")


@router.post("/detect/batch", response_model=List[DuplicateDetectionResult])
async def detect_duplicate_batch(
    payloads: List[EventDetectionInput],
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.OPERATOR)),
):
    """
    Batch evaluation of incoming market data events.
    """
    results = []
    for item in payloads:
        res = await DuplicateDetectionService.process_market_event(session, item)
        results.append(res)
    return results


@router.get("/receipts", response_model=List[DuplicateReceiptResponse])
async def list_duplicate_receipts(
    instrument_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Lists audit receipts of intercepted duplicate deliveries.
    """
    return await DuplicateRepository.list_receipts(session, instrument_id, event_type, limit)


@router.get("/audit/summary", response_model=DuplicateAuditSummary)
async def get_duplicate_audit_summary(
    provider_id: Optional[str] = Query(None),
    instrument_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Retrieves aggregate counts, duplicate rate, and prevented volume / turnover.
    """
    summary = await DuplicateRepository.get_audit_summary(session, provider_id, instrument_id)
    return DuplicateAuditSummary(**summary)


@router.get("/conflicts", response_model=List[IdentityConflictResponse])
async def list_identity_conflicts(
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Lists recorded identity conflicts.
    """
    return await DuplicateRepository.list_conflicts(session, status)


@router.post("/conflicts/{conflict_id}/resolve", response_model=IdentityConflictResponse)
async def resolve_identity_conflict(
    conflict_id: str,
    resolution: ConflictResolutionRequest,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.OPERATOR)),
):
    """
    Resolves an identity conflict with an explicit operator decision.
    """
    cnf = await DuplicateRepository.resolve_conflict(session, conflict_id, resolution)
    if not cnf:
        raise HTTPException(status_code=404, detail=f"Conflict '{conflict_id}' not found.")
    return cnf


@router.post("/rules", response_model=DuplicateDetectionRuleResponse)
async def create_detection_rule(
    rule_in: DuplicateDetectionRuleCreate,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.ADMIN)),
):
    """
    Configures a versioned duplicate detection policy.
    """
    existing = await DuplicateRepository.get_rule_by_code(session, rule_in.rule_code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Rule '{rule_in.rule_code}' already exists.")
    return await DuplicateRepository.create_rule(session, rule_in)


@router.get("/rules", response_model=List[DuplicateDetectionRuleResponse])
async def list_detection_rules(
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Lists all configured duplicate detection rules.
    """
    return await DuplicateRepository.list_rules(session)
