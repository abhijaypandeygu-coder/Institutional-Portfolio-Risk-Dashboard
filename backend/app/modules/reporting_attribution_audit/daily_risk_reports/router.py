"""
FastAPI REST router for M14.01 — Daily Risk Reports.
"""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.daily_risk_reports.schemas.daily_risk_report_schemas import (
    DailyReportConfigurationCreate,
    DailyReportConfigurationResponse,
    DailyReportGenerateRequest,
    CanonicalDailyRiskReport,
    DailyReportRunResponse,
    DailyReportIntegrityVerificationResponse,
)
from backend.app.modules.reporting_attribution_audit.daily_risk_reports.services.daily_risk_report_service import (
    DailyRiskReportService,
)

router = APIRouter(prefix="/reports/daily", tags=["M14.01 - Daily Risk Reports"])


# -----------------------------------------------------------------------------
# 1. Configuration Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/configurations",
    response_model=DailyReportConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a daily report configuration profile",
)
async def create_daily_report_configuration(
    req: DailyReportConfigurationCreate,
    user_id: str = Query("CURRENT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    return await service.create_configuration(req=req, user_id=user_id)


@router.get(
    "/configurations/{configuration_id}",
    response_model=DailyReportConfigurationResponse,
    summary="Get report configuration profile",
)
async def get_daily_report_configuration(
    configuration_id: str = Path(..., description="Configuration ID"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    return await service.get_configuration(configuration_id)


# -----------------------------------------------------------------------------
# 2. Generation Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/generate",
    response_model=CanonicalDailyRiskReport,
    status_code=status.HTTP_201_CREATED,
    summary="Generate or retrieve an idempotent daily risk report",
)
async def generate_daily_report(
    req: DailyReportGenerateRequest,
    user_id: str = Query("CURRENT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    return await service.generate_daily_report(req=req, user_id=user_id)


# -----------------------------------------------------------------------------
# 3. Archive & Structured Data Retrieval Endpoints
# -----------------------------------------------------------------------------
@router.get(
    "/archive",
    response_model=List[DailyReportRunResponse],
    summary="List archived daily report runs",
)
async def list_report_archive(
    portfolio_id: Optional[str] = Query(None, description="Portfolio filter"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    generation_status: Optional[str] = Query(None, description="Status filter"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    return await service.list_report_archive(
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
        generation_status=generation_status,
    )


@router.get(
    "/archive/{report_run_id}/data",
    response_model=CanonicalDailyRiskReport,
    summary="Get full canonical structured report data",
)
async def get_report_structured_data(
    report_run_id: str = Path(..., description="Report run ID"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    return await service.get_report_data(report_run_id)


@router.get(
    "/archive/{report_run_id}/csv",
    summary="Download CSV tabular export of the daily report",
)
async def export_report_csv(
    report_run_id: str = Path(..., description="Report run ID"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    report = await service.get_report_data(report_run_id)
    csv_bytes = service._render_csv(report)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=daily_report_{report.portfolio.portfolio_id}_{report.reporting_date}.csv"},
    )


@router.get(
    "/archive/{report_run_id}/pdf",
    summary="Download immutable archived PDF report artifact",
)
async def export_report_pdf(
    report_run_id: str = Path(..., description="Report run ID"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    report = await service.get_report_data(report_run_id)
    pdf_bytes = service._render_mock_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=daily_report_{report.portfolio.portfolio_id}_{report.reporting_date}.pdf"},
    )


@router.get(
    "/archive/{report_run_id}/verify",
    response_model=DailyReportIntegrityVerificationResponse,
    summary="Verify cryptographic SHA-256 integrity of archived report artifacts",
)
async def verify_report_integrity(
    report_run_id: str = Path(..., description="Report run ID"),
    db: AsyncSession = Depends(get_db),
):
    service = DailyRiskReportService(db)
    return await service.verify_report_integrity(report_run_id)
