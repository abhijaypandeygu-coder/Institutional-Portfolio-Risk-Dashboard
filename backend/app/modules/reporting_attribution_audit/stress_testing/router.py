"""
M14.04 Stress Testing Reports Router.
REST endpoints for creating, generating, querying, exporting, and verifying stress reports.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.stress_testing.models.stress_report_models import (
    StressArtifactType,
)
from backend.app.modules.reporting_attribution_audit.stress_testing.schemas.stress_report_schemas import (
    StressReportCreateRequest,
    CanonicalStressReport,
    StressReportSummaryResponse,
    ScenarioDescriptionSchema,
    PositionStressResultSchema,
    SensitivityItemSchema,
    LimitImplicationSchema,
    StressReconciliationSchema,
    StressReportIntegrityResponse,
)
from backend.app.modules.reporting_attribution_audit.stress_testing.services.stress_report_service import (
    StressTestingReportService,
)

router = APIRouter(prefix="", tags=["M14.04 - Stress Testing Reports"])


@router.post("", response_model=CanonicalStressReport)
async def create_stress_report(
    payload: StressReportCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    try:
        report = await service.generate_stress_report(payload)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("", response_model=List[StressReportSummaryResponse])
async def list_stress_reports(
    portfolio_id: str = Query(..., description="Portfolio identifier"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    reports = await service.list_reports(portfolio_id, limit, offset)
    return reports


@router.get("/{report_id}", response_model=CanonicalStressReport)
async def get_stress_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    report = await service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Stress report '{report_id}' not found.")
    return await service.build_canonical_report(report)


@router.post("/{report_id}/generate", response_model=CanonicalStressReport)
async def regenerate_stress_report(
    report_id: str,
    payload: StressReportCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    payload.force_regenerate = True
    report = await service.generate_stress_report(payload)
    return report


@router.get("/{report_id}/scenarios", response_model=List[ScenarioDescriptionSchema])
async def get_report_scenarios(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    report = await service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Stress report '{report_id}' not found.")
    return [ScenarioDescriptionSchema.model_validate(s) for s in report.scenarios]


@router.get("/{report_id}/positions", response_model=List[PositionStressResultSchema])
async def get_report_positions(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    report = await service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Stress report '{report_id}' not found.")
    return [PositionStressResultSchema.model_validate(p) for p in report.position_results]


@router.get("/{report_id}/sensitivity", response_model=List[SensitivityItemSchema])
async def get_report_sensitivity(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    report = await service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Stress report '{report_id}' not found.")
    return [SensitivityItemSchema.model_validate(s) for s in report.sensitivities]


@router.get("/{report_id}/limits", response_model=List[LimitImplicationSchema])
async def get_report_limits(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    report = await service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Stress report '{report_id}' not found.")
    return [LimitImplicationSchema.model_validate(l) for l in report.limit_results]


@router.get("/{report_id}/reconciliation", response_model=List[StressReconciliationSchema])
async def get_report_reconciliation(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    report = await service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Stress report '{report_id}' not found.")
    return [StressReconciliationSchema.model_validate(r) for r in report.reconciliations]


@router.get("/{report_id}/artifacts/{artifact_type}")
async def download_stress_artifact(
    report_id: str,
    artifact_type: StressArtifactType,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    report = await service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Stress report '{report_id}' not found.")

    artifact = next((a for a in report.artifacts if a.artifact_type == artifact_type), None)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact of type '{artifact_type}' not found.")

    if artifact_type == StressArtifactType.CSV:
        content = "Section,Identifier,Name,Stressed_PnL\nSCENARIO,SCEN-01,Crash,-1500000.00\n"
        media_type = "text/csv"
    elif artifact_type == StressArtifactType.HTML:
        content = f"<html><body><h1>{report.report_name}</h1></body></html>"
        media_type = "text/html"
    else:
        content = f"%PDF-1.4\n% Stress Report Mock PDF\n% SHA: {artifact.file_hash}"
        media_type = "application/pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={report.report_code}.{artifact_type.value.lower()}",
            "X-Content-SHA256": artifact.file_hash,
        },
    )


@router.post("/{report_id}/verify-integrity", response_model=StressReportIntegrityResponse)
async def verify_stress_report_integrity(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = StressTestingReportService(db)
    try:
        return await service.verify_artifact_integrity(report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
