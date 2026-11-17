from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.report_archive.models.archive_models import (
    ReportArchiveType,
    ArchiveStatus,
)
from backend.app.modules.reporting_attribution_audit.report_archive.schemas.archive_schemas import (
    ArchiveSubmissionRequest,
    ReportArchiveSummaryResponse,
    ReportArchiveDetailResponse,
    ArchiveSearchResponse,
    VersionComparisonResponse,
    RetentionEvaluationResponse,
    ReportSupersedeRequest,
    ReportRestateRequest,
    ReportWithdrawRequest,
    LegalHoldCreateRequest,
    LegalHoldReleaseRequest,
)
from backend.app.modules.reporting_attribution_audit.report_archive.services.report_archive_service import (
    ReportArchiveService,
)

router = APIRouter(prefix="/api/v1/report-archive", tags=["M14.08 Historical Report Archive"])


@router.post("", response_model=ReportArchiveDetailResponse, status_code=status.HTTP_201_CREATED)
async def submit_report_for_archive(
    req: ArchiveSubmissionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submits a newly generated report artifact for immutable historical archiving."""
    service = ReportArchiveService(db)
    try:
        archive_detail = await service.submit_report_for_archive(req)
        return archive_detail
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Archival failed: {str(e)}")


@router.get("", response_model=ArchiveSearchResponse)
async def search_archives(
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    report_type: Optional[ReportArchiveType] = Query(None, description="Filter by report category"),
    report_run_id: Optional[str] = Query(None, description="Exact report run ID lookup"),
    status_filter: Optional[ArchiveStatus] = Query(None, alias="status", description="Archive status"),
    period_start_from: Optional[datetime] = Query(None, description="Filter period start from"),
    period_end_to: Optional[datetime] = Query(None, description="Filter period end to"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """Search and filter historical report archives with pagination."""
    service = ReportArchiveService(db)
    return await service.search_archives(
        portfolio_id=portfolio_id,
        report_type=report_type,
        report_run_id=report_run_id,
        status=status_filter,
        period_start_from=period_start_from,
        period_end_to=period_end_to,
        page=page,
        page_size=page_size,
    )


@router.get("/retention/dry-run", response_model=RetentionEvaluationResponse)
async def evaluate_retention_dry_run(
    db: AsyncSession = Depends(get_db),
):
    """Evaluates archive records against retention policies and legal holds without mutating state."""
    service = ReportArchiveService(db)
    return await service.evaluate_retention_dry_run()


@router.get("/{archive_id}", response_model=ReportArchiveDetailResponse)
async def get_archive_metadata(
    archive_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full archive metadata, artifact summary, and provenance manifest for an exact archive ID."""
    service = ReportArchiveService(db)
    detail = await service.get_archive_by_id(archive_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Archive {archive_id} not found.")
    return detail


@router.get("/{archive_id}/download")
async def download_artifact(
    archive_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Downloads the exact binary report artifact, validating quarantine, retention, and policy states."""
    service = ReportArchiveService(db)
    try:
        content_bytes, filename, mime_type = await service.get_artifact_download(archive_id)
        return Response(
            content=content_bytes,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{archive_id}/versions", response_model=List[ReportArchiveSummaryResponse])
async def get_report_version_history(
    archive_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves complete version history for the logical report of the specified archive."""
    service = ReportArchiveService(db)
    return await service.get_version_history(archive_id)


@router.get("/{archive_id}/compare/{other_archive_id}", response_model=VersionComparisonResponse)
async def compare_archive_versions(
    archive_id: str,
    other_archive_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Compares metrics, models, datasets, and configurations between two archive versions."""
    service = ReportArchiveService(db)
    try:
        return await service.compare_archive_versions(archive_id, other_archive_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{archive_id}/integrity")
async def verify_artifact_integrity(
    archive_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Verifies stored artifact integrity against its registered SHA-256 hash."""
    service = ReportArchiveService(db)
    status_result, calculated_hash = await service.verify_artifact_integrity(archive_id)
    return {
        "archive_id": archive_id,
        "integrity_status": status_result.value,
        "calculated_hash": calculated_hash,
    }


@router.post("/{archive_id}/supersede")
async def supersede_report(
    archive_id: str,
    req: ReportSupersedeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Marks an archive version as superseded by a newer version."""
    service = ReportArchiveService(db)
    try:
        await service.supersede_report(archive_id, req.new_archive_id, req.reason)
        return {"status": "SUCCESS", "archive_id": archive_id, "superseded_by": req.new_archive_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{archive_id}/withdraw")
async def withdraw_report(
    archive_id: str,
    req: ReportWithdrawRequest,
    db: AsyncSession = Depends(get_db),
):
    """Formally withdraws a report from active distribution with documented reason."""
    service = ReportArchiveService(db)
    try:
        await service.withdraw_report(archive_id, req.reason, req.actor_id)
        return {"status": "SUCCESS", "archive_id": archive_id, "status": "WITHDRAWN"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/legal-holds")
async def apply_legal_hold(
    req: LegalHoldCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Places a compliance legal hold on a report archive to prevent automated disposal."""
    service = ReportArchiveService(db)
    try:
        hold = await service.apply_legal_hold(req.archive_id, req.reason, req.initiated_by)
        return {
            "status": "SUCCESS",
            "hold_id": hold.hold_id,
            "archive_id": req.archive_id,
            "hold_status": hold.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/legal-holds/{hold_id}/release")
async def release_legal_hold(
    hold_id: str,
    req: LegalHoldReleaseRequest,
    db: AsyncSession = Depends(get_db),
):
    """Releases an active compliance legal hold."""
    service = ReportArchiveService(db)
    try:
        await service.release_legal_hold(hold_id, req.release_reason, req.released_by)
        return {"status": "SUCCESS", "hold_id": hold_id, "hold_status": "RELEASED"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
