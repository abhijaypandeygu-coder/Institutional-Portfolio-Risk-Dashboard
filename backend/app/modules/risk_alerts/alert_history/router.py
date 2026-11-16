"""
FastAPI router for M12.08 — Alert History.
"""

from datetime import datetime
import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.alert_history.services.alert_history_service import (
    AlertHistoryService,
)
from backend.app.modules.risk_alerts.alert_history.schemas.alert_history_schemas import (
    HistoricalAlertItemResponse,
    HistoricalAlertSearchResponse,
    HistoricalAlertCountsResponse,
    AlertTimelineResponse,
    AlertRecurrenceGroupResponse,
    RuleAnalyticsResponse,
    AlertExportCreateRequest,
    AlertExportJobResponse,
    IntegrityIssueResponse,
    IntegrityOverviewResponse,
)

router = APIRouter(prefix="/alert-history", tags=["M12.08 Alert History"])


def get_service(session: AsyncSession = Depends(get_db)) -> AlertHistoryService:
    return AlertHistoryService(session)


# -------------------------------------------------------------
# Search & Retrieval Endpoints
# -------------------------------------------------------------
@router.get("", response_model=HistoricalAlertSearchResponse)
async def search_alerts(
    portfolio_id: Optional[str] = Query(None),
    instrument_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source_rule_id: Optional[str] = Query(None),
    source_module: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    sort_by: str = Query("newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service: AlertHistoryService = Depends(get_service),
):
    offset = (page - 1) * page_size
    items, total = await service.repo.search_historical_alerts(
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        severity=severity,
        category=category,
        status=status,
        source_rule_id=source_rule_id,
        source_module=source_module,
        start_time=start_time,
        end_time=end_time,
        sort_by=sort_by,
        limit=page_size,
        offset=offset,
    )
    return {
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/counts", response_model=HistoricalAlertCountsResponse)
async def get_historical_counts(
    service: AlertHistoryService = Depends(get_service),
):
    return await service.repo.get_historical_counts()


@router.get("/{alert_id}", response_model=HistoricalAlertItemResponse)
async def get_historical_alert(
    alert_id: str,
    service: AlertHistoryService = Depends(get_service),
):
    alert = await service.repo.get_indexed_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found in historical repository")
    return alert


# -------------------------------------------------------------
# Lifecycle Timeline & Durations
# -------------------------------------------------------------
@router.get("/{alert_id}/timeline", response_model=AlertTimelineResponse)
async def get_alert_timeline(
    alert_id: str,
    service: AlertHistoryService = Depends(get_service),
):
    try:
        return await service.get_alert_lifecycle_timeline(alert_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -------------------------------------------------------------
# Recurrence Analysis Endpoints
# -------------------------------------------------------------
@router.get("/recurrence/groups", response_model=List[AlertRecurrenceGroupResponse])
async def list_recurrence_groups(
    min_occurrences: int = Query(2, ge=1),
    limit: int = Query(50, ge=1, le=200),
    service: AlertHistoryService = Depends(get_service),
):
    groups = await service.repo.list_recurrence_groups(min_occurrences=min_occurrences, limit=limit)
    return groups


# -------------------------------------------------------------
# Rule Analytics & Noise Scores
# -------------------------------------------------------------
@router.get("/rule-analytics/list", response_model=List[RuleAnalyticsResponse])
async def list_rule_analytics(
    limit: int = Query(50, ge=1, le=200),
    service: AlertHistoryService = Depends(get_service),
):
    return await service.repo.list_rule_analytics(limit=limit)


# -------------------------------------------------------------
# Backfill Endpoint
# -------------------------------------------------------------
@router.post("/backfill")
async def trigger_backfill(
    service: AlertHistoryService = Depends(get_service),
):
    return await service.run_historical_backfill()


# -------------------------------------------------------------
# Export Management Endpoints
# -------------------------------------------------------------
@router.post("/exports", response_model=AlertExportJobResponse, status_code=status.HTTP_201_CREATED)
async def create_export_job(
    req: AlertExportCreateRequest,
    service: AlertHistoryService = Depends(get_service),
):
    filters = {
        "portfolio_id": req.portfolio_id,
        "instrument_id": req.instrument_id,
        "severity": req.severity,
        "alert_category": req.alert_category,
        "source_rule_id": req.source_rule_id,
    }
    job = await service.repo.create_export_job(
        requested_by=req.requested_by,
        export_type=req.export_type,
        export_format=req.export_format,
        requested_filters_json=filters,
    )
    # Process job synchronously for immediate download readiness
    completed_job = await service.process_export_job(job.id)
    return completed_job


@router.get("/exports", response_model=List[AlertExportJobResponse])
async def list_export_jobs(
    limit: int = Query(50, ge=1, le=200),
    service: AlertHistoryService = Depends(get_service),
):
    return await service.repo.list_export_jobs(limit=limit)


@router.get("/exports/{export_id}/download")
async def download_export_file(
    export_id: str,
    user_id: str = Query("admin"),
    service: AlertHistoryService = Depends(get_service),
):
    job = await service.repo.get_export_job(export_id)
    if not job or not job.file_reference or not os.path.exists(job.file_reference):
        raise HTTPException(status_code=404, detail="Export file not found or expired")

    await service.repo.record_export_download(
        export_job_id=job.id,
        downloaded_by=user_id,
        download_result="SUCCESS",
    )

    return FileResponse(
        path=job.file_reference,
        media_type="text/csv",
        filename=f"alert_history_{job.id}.csv",
    )


# -------------------------------------------------------------
# Integrity Monitoring Endpoints
# -------------------------------------------------------------
@router.get("/integrity/overview", response_model=IntegrityOverviewResponse)
async def get_integrity_overview(
    service: AlertHistoryService = Depends(get_service),
):
    return await service.repo.get_integrity_overview()


@router.get("/integrity/issues", response_model=List[IntegrityIssueResponse])
async def list_integrity_issues(
    limit: int = Query(50, ge=1, le=200),
    service: AlertHistoryService = Depends(get_service),
):
    return await service.repo.list_integrity_issues(limit=limit)

