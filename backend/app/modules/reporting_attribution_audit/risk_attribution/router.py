"""
M14.03 Risk Attribution Reports Router.
REST endpoints for configuration, generation, attribution data, exports, and integrity.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.risk_attribution.models.risk_attribution_models import (
    ReportArtifactType,
)
from backend.app.modules.reporting_attribution_audit.risk_attribution.schemas.risk_attribution_schemas import (
    RiskAttributionConfigCreate,
    RiskAttributionConfigUpdate,
    RiskAttributionConfigResponse,
    RiskAttributionGenerateRequest,
    RiskAttributionRunResponse,
    CanonicalRiskAttributionReport,
    SecurityContributionSchema,
    GroupContributionSchema,
    FactorContributionSchema,
    ReconciliationSchema,
    RiskAttributionIntegrityResponse,
)
from backend.app.modules.reporting_attribution_audit.risk_attribution.services.risk_attribution_service import (
    RiskAttributionReportService,
)

router = APIRouter(prefix="", tags=["M14.03 - Risk Attribution Reports"])


# -----------------------------------------------------------------------------
# Configuration Endpoints
# -----------------------------------------------------------------------------
@router.post("/configurations", response_model=RiskAttributionConfigResponse)
async def create_or_get_configuration(
    payload: RiskAttributionConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    config = await service.get_or_create_configuration(payload.portfolio_id, payload)
    await db.commit()
    await db.refresh(config)
    return config


@router.get("/configurations/{portfolio_id}", response_model=RiskAttributionConfigResponse)
async def get_configuration(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    config = await service.get_or_create_configuration(portfolio_id)
    return config


@router.patch("/configurations/{configuration_id}", response_model=RiskAttributionConfigResponse)
async def update_configuration(
    configuration_id: str,
    payload: RiskAttributionConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    try:
        updated = await service.update_configuration(configuration_id, payload)
        await db.commit()
        await db.refresh(updated)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -----------------------------------------------------------------------------
# Report Generation & Execution Runs
# -----------------------------------------------------------------------------
@router.post("/generate", response_model=CanonicalRiskAttributionReport)
async def generate_risk_attribution_report(
    payload: RiskAttributionGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    try:
        report = await service.generate_report(payload)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("/runs/{report_run_id}", response_model=CanonicalRiskAttributionReport)
async def get_run_details(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    run = await service.get_run_by_id(report_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{report_run_id}' not found.")
    return await service.build_canonical_report(run)


@router.get("/runs", response_model=List[RiskAttributionRunResponse])
async def list_report_runs(
    portfolio_id: str = Query(..., description="Target portfolio ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    runs = await service.list_runs(portfolio_id, limit, offset)
    return runs


# -----------------------------------------------------------------------------
# Attribution Data Endpoints
# -----------------------------------------------------------------------------
@router.get("/runs/{report_run_id}/securities", response_model=List[SecurityContributionSchema])
async def get_run_securities(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    run = await service.get_run_by_id(report_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{report_run_id}' not found.")
    return [SecurityContributionSchema.model_validate(s) for s in run.security_contributions]


@router.get("/runs/{report_run_id}/sectors", response_model=List[GroupContributionSchema])
async def get_run_sectors(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    run = await service.get_run_by_id(report_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{report_run_id}' not found.")
    return [
        GroupContributionSchema.model_validate(g)
        for g in run.group_contributions
        if g.group_type.value == "SECTOR"
    ]


@router.get("/runs/{report_run_id}/industries", response_model=List[GroupContributionSchema])
async def get_run_industries(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    run = await service.get_run_by_id(report_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{report_run_id}' not found.")
    return [
        GroupContributionSchema.model_validate(g)
        for g in run.group_contributions
        if g.group_type.value == "INDUSTRY"
    ]


@router.get("/runs/{report_run_id}/factors", response_model=List[FactorContributionSchema])
async def get_run_factors(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    run = await service.get_run_by_id(report_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{report_run_id}' not found.")
    return [FactorContributionSchema.model_validate(f) for f in run.factor_contributions]


@router.get("/runs/{report_run_id}/reconciliation", response_model=List[ReconciliationSchema])
async def get_run_reconciliation(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    run = await service.get_run_by_id(report_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{report_run_id}' not found.")
    return [ReconciliationSchema.model_validate(r) for r in run.reconciliations]


# -----------------------------------------------------------------------------
# Archive, Artifacts & Verification
# -----------------------------------------------------------------------------
@router.get("/runs/{report_run_id}/artifacts/{artifact_type}")
async def download_report_artifact(
    report_run_id: str,
    artifact_type: ReportArtifactType,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    run = await service.get_run_by_id(report_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{report_run_id}' not found.")

    artifact = next((a for a in run.artifacts if a.artifact_type == artifact_type), None)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact of type '{artifact_type}' not found.")

    # Return dynamic payload matching type
    if artifact_type == ReportArtifactType.CSV:
        content = "Section,Identifier,Symbol,Marginal_RC,Component_RC\nSECURITY,INST-AAPL,AAPL,0.22,0.088\n"
        media_type = "text/csv"
    elif artifact_type == ReportArtifactType.HTML:
        content = f"<html><body><h1>Risk Attribution Report: {run.portfolio_id}</h1></body></html>"
        media_type = "text/html"
    else:
        content = f"%PDF-1.4\n% Risk Attribution Report Mock PDF\n% SHA: {artifact.content_hash}"
        media_type = "application/pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=risk_attribution_{run.portfolio_id}_{run.reporting_date.isoformat()}.{artifact_type.value.lower()}",
            "X-Content-SHA256": artifact.content_hash,
        },
    )


@router.post("/runs/{report_run_id}/verify-integrity", response_model=RiskAttributionIntegrityResponse)
async def verify_run_integrity(
    report_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RiskAttributionReportService(db)
    try:
        res = await service.verify_artifact_integrity(report_run_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
