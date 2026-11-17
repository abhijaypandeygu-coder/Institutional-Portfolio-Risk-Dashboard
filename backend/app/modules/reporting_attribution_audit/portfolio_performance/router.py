"""
FastAPI router for M14.02 — Portfolio Performance Reports.
Mounted under /api/v1/reports/performance.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.portfolio_performance.schemas.performance_report_schemas import (
    PerformanceReportConfigCreate,
    PerformanceReportConfigUpdate,
    PerformanceReportConfigResponse,
    PerformanceReportGenerateRequest,
    CanonicalPerformanceReport,
    PerformanceReportRunResponse,
    PerformanceIntegrityVerificationResponse,
    ReturnObservationSchema,
    PnLComponentSchema,
    BenchmarkObservationSchema,
    PerformanceCaveatSchema,
)
from backend.app.modules.reporting_attribution_audit.portfolio_performance.services.performance_report_service import (
    PortfolioPerformanceReportService,
)

router = APIRouter(prefix="/reports/performance", tags=["M14.02 — Portfolio Performance Reports"])


# -----------------------------------------------------------------------------
# 1. Configuration Endpoints
# -----------------------------------------------------------------------------
@router.post("/configurations", response_model=PerformanceReportConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_configuration(
    req: PerformanceReportConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    config = await service.create_configuration(req)
    return config


@router.get("/configurations/{configuration_id}", response_model=PerformanceReportConfigResponse)
async def get_configuration(
    configuration_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    config = await service.get_configuration(configuration_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config


# -----------------------------------------------------------------------------
# 2. Generation & Execution
# -----------------------------------------------------------------------------
@router.post("/generate", response_model=CanonicalPerformanceReport)
async def generate_performance_report(
    req: PerformanceReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    return await service.generate_performance_report(req)


@router.get("/runs/{report_run_id}", response_model=CanonicalPerformanceReport)
async def get_performance_report_by_run(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    return await service.build_canonical_report(report_run_id)


@router.get("/runs/{report_run_id}/returns", response_model=List[ReturnObservationSchema])
async def get_run_returns(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    rep = await service.build_canonical_report(report_run_id)
    return rep.return_observations


@router.get("/runs/{report_run_id}/pnl", response_model=List[PnLComponentSchema])
async def get_run_pnl(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    rep = await service.build_canonical_report(report_run_id)
    return rep.pnl_breakdown.components


@router.get("/runs/{report_run_id}/benchmark", response_model=List[BenchmarkObservationSchema])
async def get_run_benchmark(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    rep = await service.build_canonical_report(report_run_id)
    return rep.benchmark_observations


@router.get("/runs/{report_run_id}/caveats", response_model=List[PerformanceCaveatSchema])
async def get_run_caveats(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    rep = await service.build_canonical_report(report_run_id)
    return rep.caveats


# -----------------------------------------------------------------------------
# 3. Archive & Version Retrieval
# -----------------------------------------------------------------------------
@router.get("/archive/{portfolio_id}", response_model=List[PerformanceReportRunResponse])
async def list_portfolio_report_runs(
    portfolio_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    return await service.list_portfolio_runs(portfolio_id, limit=limit)


@router.get("/archive/{report_run_id}/data", response_model=CanonicalPerformanceReport)
async def get_archived_report_data(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    return await service.build_canonical_report(report_run_id)


# -----------------------------------------------------------------------------
# 4. Artifact Download & Cryptographic Integrity Verification
# -----------------------------------------------------------------------------
@router.get("/artifact/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from backend.app.modules.reporting_attribution_audit.portfolio_performance.models.performance_report_models import PerformanceReportArtifact
    q = select(PerformanceReportArtifact).where(PerformanceReportArtifact.id == artifact_id)
    art = (await db.execute(q)).scalars().first()
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")

    content = art.content_data or ""
    headers = {
        "Content-Disposition": f"attachment; filename={art.storage_reference.split('/')[-1]}",
        "X-Artifact-SHA256": art.content_hash,
    }
    return Response(content=content, media_type=art.content_type, headers=headers)


@router.get("/artifact/{artifact_id}/verify", response_model=PerformanceIntegrityVerificationResponse)
async def verify_artifact_integrity(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioPerformanceReportService(db)
    return await service.verify_artifact_integrity(artifact_id)
