"""FastAPI router for M14.05 Liquidity Reports."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.liquidity.models.liquidity_report_models import (
    LiquidityArtifactType,
)
from backend.app.modules.reporting_attribution_audit.liquidity.schemas.liquidity_report_schemas import (
    LiquidityReportCreateRequest,
    CanonicalLiquidityReport,
    LiquidityReportSummaryResponse,
    LiquidityReportIntegrityResponse,
    LiquidityProfileSummarySchema,
    PositionLiquiditySchema,
    LiquidationEstimateSchema,
    IlliquidityConcentrationSchema,
    StressComparisonSchema,
    LimitImplicationSchema,
    LiquidityReconciliationSchema,
    LiquidityArtifactSchema,
)
from backend.app.modules.reporting_attribution_audit.liquidity.services.liquidity_report_service import (
    LiquidityReportService,
)

router = APIRouter(prefix="", tags=["M14.05 Liquidity Reports"])


@router.post(
    "",
    response_model=CanonicalLiquidityReport,
    status_code=status.HTTP_201_CREATED,
    summary="Create & generate institutional liquidity report",
)
async def create_liquidity_report(
    request: LiquidityReportCreateRequest,
    regeneration_reason: Optional[str] = Query(None, description="Reason if regenerating report version"),
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    try:
        return await service.create_and_generate_report(request, regeneration_reason=regeneration_reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "",
    response_model=List[LiquidityReportSummaryResponse],
    summary="List historical liquidity reports",
)
async def list_liquidity_reports(
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    return await service.list_reports(portfolio_id=portfolio_id)


@router.get(
    "/{report_id}",
    response_model=CanonicalLiquidityReport,
    summary="Get canonical liquidity report by ID",
)
async def get_liquidity_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    try:
        return await service.get_canonical_report(report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{report_id}/profile",
    response_model=LiquidityProfileSummarySchema,
    summary="Get portfolio liquidity profile metrics",
)
async def get_liquidity_profile(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.profile


@router.get(
    "/{report_id}/positions",
    response_model=List[PositionLiquiditySchema],
    summary="Get instrument-level liquidity table",
)
async def get_position_liquidity(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.positions


@router.get(
    "/{report_id}/liquidation",
    response_model=List[LiquidationEstimateSchema],
    summary="Get liquidation time and cost estimates",
)
async def get_liquidation_estimates(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.liquidations


@router.get(
    "/{report_id}/concentration",
    response_model=List[IlliquidityConcentrationSchema],
    summary="Get illiquidity concentration breakdowns",
)
async def get_illiquidity_concentration(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.concentrations


@router.get(
    "/{report_id}/stress",
    response_model=List[StressComparisonSchema],
    summary="Get liquidity stress comparisons",
)
async def get_liquidity_stress(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.stress_comparisons


@router.get(
    "/{report_id}/limits",
    response_model=List[LimitImplicationSchema],
    summary="Get liquidity limit utilization and projected exceedances",
)
async def get_liquidity_limits(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.limits


@router.get(
    "/{report_id}/reconciliation",
    response_model=List[LiquidityReconciliationSchema],
    summary="Get liquidity reconciliation results",
)
async def get_liquidity_reconciliation(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.reconciliations


@router.get(
    "/{report_id}/artifacts",
    response_model=List[LiquidityArtifactSchema],
    summary="Get report artifact references",
)
async def get_liquidity_artifacts(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    report = await service.get_canonical_report(report_id)
    return report.artifacts


@router.get(
    "/{report_id}/verify/{artifact_type}",
    response_model=LiquidityReportIntegrityResponse,
    summary="Cryptographically verify artifact SHA-256 hash",
)
async def verify_artifact_hash(
    report_id: str,
    artifact_type: LiquidityArtifactType,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityReportService(db)
    try:
        return await service.verify_artifact_integrity(report_id, artifact_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
