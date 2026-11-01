"""
FastAPI Router for M03.08 Exception Management.
Mounts endpoints under /api/v1/exceptions with RBAC and full audit trails.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role, UserRole, AuthenticatedUser
from backend.app.modules.market_data_quality.exception_management.schemas import (
    ExceptionCreateRequest,
    ExceptionRecordResponse,
    ExceptionObservationResponse,
    ExceptionAssignmentUpdate,
    ExceptionPriorityUpdate,
    ExceptionNoteCreate,
    ExceptionResolveRequest,
    ExceptionDismissRequest,
    ExceptionReopenRequest,
    QuarantineCreateRequest,
    QuarantineReleaseRequest,
    QuarantineRecordResponse,
    RejectionCreateRequest,
    RejectionRecordResponse,
    CorrectionProposalCreate,
    CorrectionApprovalRequest,
    CorrectionRejectRequest,
    CorrectionProposalResponse,
    ReplaySubmitRequest,
    ReplayRequestResponse,
    ExceptionSummaryMetrics,
)
from backend.app.modules.market_data_quality.exception_management.services.service import ExceptionManagementService
from backend.app.modules.market_data_quality.exception_management.repositories.repository import ExceptionRepository

router = APIRouter(prefix="/exceptions", tags=["M03.08 - Exception Management"])


# 1. Exception Core Endpoints
@router.post("/", response_model=ExceptionRecordResponse, status_code=status.HTTP_201_CREATED)
async def register_exception(
    req: ExceptionCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Registers an upstream validation finding as a controlled exception."""
    return await ExceptionManagementService.register_exception(session, req, actor_id=user.username)


@router.get("/", response_model=List[ExceptionRecordResponse])
async def list_exceptions(
    workflow_status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists exceptions with filtering and pagination."""
    return await ExceptionRepository.list_exceptions(
        session, workflow_status, severity, priority, assigned_user_id, limit, offset
    )


@router.get("/summary", response_model=ExceptionSummaryMetrics)
async def get_summary_metrics(
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves operational metrics and summary statistics for exception management."""
    return await ExceptionRepository.get_metrics_summary(session)


@router.get("/{exception_id}", response_model=ExceptionRecordResponse)
async def get_exception_details(
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves full details of a single exception."""
    exc = await ExceptionRepository.get_by_id(session, exception_id)
    if not exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Exception not found.")
    return exc


@router.get("/{exception_id}/observations", response_model=List[ExceptionObservationResponse])
async def get_exception_observations(
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves all observations linked to an exception."""
    return await ExceptionRepository.get_observations_for_exception(session, exception_id)


@router.patch("/{exception_id}/assignment", response_model=ExceptionRecordResponse)
async def assign_exception(
    req: ExceptionAssignmentUpdate,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Assigns or reassigns an exception to an owner."""
    return await ExceptionManagementService.update_assignment(
        session, exception_id, req.assigned_user_id, req.assigned_group, actor_id=user.username
    )


@router.post("/{exception_id}/notes")
async def add_investigation_note(
    req: ExceptionNoteCreate,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Appends an investigation note to an exception."""
    note = await ExceptionManagementService.add_note(
        session, exception_id, req.note_content, req.note_type, user.username, req.evidence_reference
    )
    return {"status": "NOTE_ADDED", "note_id": note.note_id}


@router.get("/{exception_id}/history")
async def get_exception_history(
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves immutable append-only audit trail and notes for an exception."""
    audits = await ExceptionRepository.get_audit_trail(session, exception_id)
    notes = await ExceptionRepository.get_notes(session, exception_id)
    return {"audit_trail": audits, "notes": notes}


@router.post("/{exception_id}/resolve", response_model=ExceptionRecordResponse)
async def resolve_exception(
    req: ExceptionResolveRequest,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Resolves an exception with documented outcome and justification."""
    return await ExceptionManagementService.resolve_exception(
        session, exception_id, req.resolution_outcome, req.justification, actor_id=user.username
    )


@router.post("/{exception_id}/reopen", response_model=ExceptionRecordResponse)
async def reopen_exception(
    req: ExceptionReopenRequest,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Reopens a previously resolved exception."""
    return await ExceptionManagementService.reopen_exception(
        session, exception_id, req.reason, actor_id=user.username
    )


# 2. Quarantine Endpoints
@router.post("/{exception_id}/quarantine", response_model=QuarantineRecordResponse)
async def quarantine_observation(
    req: QuarantineCreateRequest,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Isolates suspect observation outside trusted data path."""
    return await ExceptionManagementService.quarantine_observation(
        session, exception_id, req, actor_id=user.username
    )


@router.get("/quarantine/records", response_model=List[QuarantineRecordResponse])
async def list_quarantine_records(
    release_status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists quarantined records."""
    return await ExceptionRepository.list_quarantines(session, release_status, limit)


@router.post("/quarantine/{quarantine_id}/release", response_model=QuarantineRecordResponse)
async def release_quarantined_record(
    req: QuarantineReleaseRequest,
    quarantine_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Releases quarantined record back to processing pipeline upon verified authorization."""
    return await ExceptionManagementService.release_quarantine(
        session, quarantine_id, req, actor_id=user.username
    )


# 3. Rejection Endpoints
@router.post("/{exception_id}/reject", response_model=RejectionRecordResponse)
async def reject_observation(
    req: RejectionCreateRequest,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Explicitly rejects an observation that violates hard schemas or rules."""
    return await ExceptionManagementService.reject_observation(
        session, exception_id, req, actor_id=user.username
    )


@router.get("/rejections/records", response_model=List[RejectionRecordResponse])
async def list_rejection_records(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists rejected records."""
    return await ExceptionRepository.list_rejections(session, limit)


# 4. Correction Endpoints
@router.post("/{exception_id}/corrections", response_model=CorrectionProposalResponse)
async def propose_correction(
    req: CorrectionProposalCreate,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Proposes an auditable correction with before/after values and provenance."""
    return await ExceptionManagementService.create_correction_proposal(
        session, exception_id, req, actor_id=user.username
    )


@router.get("/{exception_id}/corrections", response_model=List[CorrectionProposalResponse])
async def list_corrections(
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists correction proposals for an exception."""
    return await ExceptionRepository.list_corrections(session, exception_id)


@router.post("/corrections/{correction_id}/approve", response_model=CorrectionProposalResponse)
async def approve_correction(
    req: CorrectionApprovalRequest,
    correction_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    """Approves a correction proposal. Enforces separation of duties (cannot self-approve)."""
    return await ExceptionManagementService.approve_correction(
        session, correction_id, req, approver_id=user.username
    )


@router.post("/corrections/{correction_id}/reject", response_model=CorrectionProposalResponse)
async def reject_correction(
    req: CorrectionRejectRequest,
    correction_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    """Rejects a correction proposal."""
    return await ExceptionManagementService.reject_correction(
        session, correction_id, req, actor_id=user.username
    )


# 5. Replay Endpoints
@router.post("/{exception_id}/replay", response_model=ReplayRequestResponse)
async def submit_replay(
    req: ReplaySubmitRequest,
    exception_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Submits an idempotent replay request through M02."""
    return await ExceptionManagementService.submit_replay(
        session, exception_id, req, actor_id=user.username
    )


@router.get("/replays/requests", response_model=List[ReplayRequestResponse])
async def list_replay_requests(
    exception_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists replay requests."""
    return await ExceptionRepository.list_replays(session, exception_id, limit)


@router.get("/replays/{replay_id}/results")
async def get_replay_results(
    replay_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves per-record execution results of a replay operation."""
    return await ExceptionRepository.get_replay_results(session, replay_id)

