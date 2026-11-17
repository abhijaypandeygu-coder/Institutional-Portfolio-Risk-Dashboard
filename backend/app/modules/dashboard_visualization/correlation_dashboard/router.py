"""
M13.05 — Correlation Dashboard API Router.

Exposes REST endpoints for:
1. POST /api/v1/dashboard/correlation/universe/resolve
2. POST /api/v1/dashboard/correlation/matrix
3. POST /api/v1/dashboard/correlation/compare
4. POST /api/v1/dashboard/correlation/clusters
5. POST /api/v1/dashboard/correlation/outliers
6. GET  /api/v1/dashboard/correlation/pair/{instrument_a_id}/{instrument_b_id}
7. GET  /api/v1/dashboard/correlation/preferences
8. PUT  /api/v1/dashboard/correlation/preferences
9. POST /api/v1/dashboard/correlation/universes
10. GET  /api/v1/dashboard/correlation/universes
11. DELETE /api/v1/dashboard/correlation/universes/{universe_id}
12. POST /api/v1/dashboard/correlation/investigations
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.correlation_dashboard.schemas import (
    UniverseResolveRequest,
    UniverseResolveResponse,
    CorrelationMatrixViewRequest,
    CorrelationMatrixViewResponse,
    MatrixComparisonRequest,
    MatrixComparisonResponse,
    CorrelationClusteringRequest,
    CorrelationClusteringResponse,
    CorrelationOutliersRequest,
    CorrelationOutliersResponse,
    CorrelationPairDetailResponse,
    CorrelationEstimatorType,
    CorrelationDashboardPreferenceCreate,
    CorrelationDashboardPreferenceResponse,
    CorrelationSavedUniverseCreate,
    CorrelationSavedUniverseResponse,
    CorrelationInvestigationCreate,
    CorrelationInvestigationResponse,
)
from backend.app.modules.dashboard_visualization.correlation_dashboard.services.correlation_dashboard_service import (
    CorrelationDashboardService,
)

router = APIRouter()


def _get_current_user_id(x_user_id: Optional[str] = Header("default_user", alias="X-User-ID")) -> str:
    return x_user_id or "default_user"


# ---------------------------------------------------------------------------
# Universe Resolution
# ---------------------------------------------------------------------------

@router.post(
    "/correlation/universe/resolve",
    response_model=UniverseResolveResponse,
    summary="Resolve Instrument Universe",
    description="Resolves eligible portfolio holdings, sector groups, or custom instrument lists with canonical metadata.",
)
async def resolve_universe(
    req: UniverseResolveRequest,
    session: AsyncSession = Depends(get_db),
) -> UniverseResolveResponse:
    return await CorrelationDashboardService.resolve_universe(session, req)


# ---------------------------------------------------------------------------
# Correlation Matrix & Comparison
# ---------------------------------------------------------------------------

@router.post(
    "/correlation/matrix",
    response_model=CorrelationMatrixViewResponse,
    summary="Get Correlation Matrix View",
    description="Calculates or retrieves authoritative pairwise correlation matrix with PSD diagnostics and configurable sorting.",
)
async def get_correlation_matrix(
    req: CorrelationMatrixViewRequest,
    session: AsyncSession = Depends(get_db),
) -> CorrelationMatrixViewResponse:
    return await CorrelationDashboardService.get_matrix_view(session, req)


@router.post(
    "/correlation/compare",
    response_model=MatrixComparisonResponse,
    summary="Compare Two Correlation Matrices",
    description="Computes difference matrix ΔC = C_current - C_comparison across lookback periods or dates.",
)
async def compare_correlation_matrices(
    req: MatrixComparisonRequest,
    session: AsyncSession = Depends(get_db),
) -> MatrixComparisonResponse:
    return await CorrelationDashboardService.compare_matrices(session, req)


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

@router.post(
    "/correlation/clusters",
    response_model=CorrelationClusteringResponse,
    summary="Hierarchical Correlation Clustering",
    description="Groups securities into clusters using d_ij = sqrt(2*(1 - rho)) and returns dendrogram tree nodes.",
)
async def compute_clusters(
    req: CorrelationClusteringRequest,
    session: AsyncSession = Depends(get_db),
) -> CorrelationClusteringResponse:
    return await CorrelationDashboardService.compute_clusters(session, req)


# ---------------------------------------------------------------------------
# Outliers & Anomalies
# ---------------------------------------------------------------------------

@router.post(
    "/correlation/outliers",
    response_model=CorrelationOutliersResponse,
    summary="Detect Correlation Outliers & Anomalies",
    description="Scans for high positive/negative threshold crossings, large changes, and sign reversals.",
)
async def detect_correlation_outliers(
    req: CorrelationOutliersRequest,
    session: AsyncSession = Depends(get_db),
) -> CorrelationOutliersResponse:
    return await CorrelationDashboardService.detect_outliers(session, req)


# ---------------------------------------------------------------------------
# Pair Detail, Scatter & Trend
# ---------------------------------------------------------------------------

@router.get(
    "/correlation/pair/{instrument_a_id}/{instrument_b_id}",
    response_model=CorrelationPairDetailResponse,
    summary="Get Pair-Level Detail & Diagnostics",
    description="Returns exact statistics, least-squares scatter points, and rolling correlation trend for a pair.",
)
async def get_pair_detail(
    instrument_a_id: str = Path(..., description="First instrument ID"),
    instrument_b_id: str = Path(..., description="Second instrument ID"),
    portfolio_id: Optional[str] = Query(None, description="Optional portfolio context"),
    lookback_days: int = Query(60, ge=5, le=2520, description="Lookback days"),
    estimator: CorrelationEstimatorType = Query(CorrelationEstimatorType.PEARSON, description="Estimator type"),
    as_of: Optional[date] = Query(None, description="As of date"),
    session: AsyncSession = Depends(get_db),
) -> CorrelationPairDetailResponse:
    return await CorrelationDashboardService.get_pair_detail(
        session=session,
        instrument_a_id=instrument_a_id,
        instrument_b_id=instrument_b_id,
        portfolio_id=portfolio_id,
        lookback_days=lookback_days,
        estimator=estimator,
        as_of=as_of,
    )


# ---------------------------------------------------------------------------
# User Preferences & Saved Universes
# ---------------------------------------------------------------------------

@router.get(
    "/correlation/preferences",
    response_model=CorrelationDashboardPreferenceResponse,
    summary="Get Dashboard Preferences",
)
async def get_preferences(
    user_id: str = Depends(_get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> CorrelationDashboardPreferenceResponse:
    return await CorrelationDashboardService.get_preferences(session, user_id)


@router.put(
    "/correlation/preferences",
    response_model=CorrelationDashboardPreferenceResponse,
    summary="Save Dashboard Preferences",
)
async def save_preferences(
    data: CorrelationDashboardPreferenceCreate,
    user_id: str = Depends(_get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> CorrelationDashboardPreferenceResponse:
    return await CorrelationDashboardService.save_preferences(session, user_id, data)


@router.post(
    "/correlation/universes",
    response_model=CorrelationSavedUniverseResponse,
    summary="Save Custom Universe",
)
async def save_universe(
    data: CorrelationSavedUniverseCreate,
    user_id: str = Depends(_get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> CorrelationSavedUniverseResponse:
    return await CorrelationDashboardService.save_universe(session, user_id, data)


@router.get(
    "/correlation/universes",
    response_model=List[CorrelationSavedUniverseResponse],
    summary="List Saved Universes",
)
async def list_universes(
    user_id: str = Depends(_get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> List[CorrelationSavedUniverseResponse]:
    return await CorrelationDashboardService.list_universes(session, user_id)


@router.delete(
    "/correlation/universes/{universe_id}",
    summary="Delete Saved Universe",
)
async def delete_universe(
    universe_id: str = Path(...),
    user_id: str = Depends(_get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    deleted = await CorrelationDashboardService.delete_universe(session, universe_id, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Universe not found or unauthorized")
    return {"status": "SUCCESS", "deleted_universe_id": universe_id}


# ---------------------------------------------------------------------------
# Investigation Log
# ---------------------------------------------------------------------------

@router.post(
    "/correlation/investigations",
    response_model=CorrelationInvestigationResponse,
    summary="Record Outlier Investigation",
)
async def record_investigation(
    data: CorrelationInvestigationCreate,
    user_id: str = Depends(_get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> CorrelationInvestigationResponse:
    return await CorrelationDashboardService.record_investigation(session, user_id, data)
