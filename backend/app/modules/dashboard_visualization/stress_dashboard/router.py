"""
FastAPI Router for M13.07 — Stress Testing Dashboard.

Endpoints:
- GET  /api/v1/dashboard/stress/scenarios
- GET  /api/v1/dashboard/stress/scenarios/{scenario_id}
- GET  /api/v1/dashboard/stress/results/{calculation_id}
- GET  /api/v1/dashboard/stress/results/{calculation_id}/positions
- GET  /api/v1/dashboard/stress/results/{calculation_id}/distribution
- POST /api/v1/dashboard/stress/compare
- GET  /api/v1/dashboard/stress/attribution/{calculation_id}
- GET  /api/v1/dashboard/stress/preferences
- POST /api/v1/dashboard/stress/preferences
- GET  /api/v1/dashboard/stress/saved-views
- POST /api/v1/dashboard/stress/saved-views
- GET  /api/v1/dashboard/stress/annotations
- POST /api/v1/dashboard/stress/annotations
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.stress_dashboard.services.stress_dashboard_service import (
    StressDashboardService,
)
from backend.app.modules.dashboard_visualization.stress_dashboard.schemas.stress_dashboard_schemas import (
    ScenarioMetadataItem,
    ScenarioDefinitionDetail,
    PositionStressResult,
    ScenarioDetailResultResponse,
    MonteCarloDistributionResponse,
    ScenarioComparisonResponse,
    StressAttributionResponse,
    StressPreferenceCreateRequest,
    StressPreferenceResponse,
    StressSavedViewCreateRequest,
    StressSavedViewResponse,
    StressAnnotationCreateRequest,
    StressAnnotationResponse,
)

router = APIRouter(prefix="/api/v1/dashboard/stress", tags=["Dashboard - Stress Testing"])


# ---------------------------------------------------------------------------
# 1. Scenario Library & Definitions
# ---------------------------------------------------------------------------
@router.get("/scenarios", response_model=List[ScenarioMetadataItem])
async def list_scenarios(
    portfolio_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Lists registered historical, hypothetical, and Monte Carlo scenarios."""
    svc = StressDashboardService(db)
    return await svc.list_scenarios(portfolio_id=portfolio_id, category=category)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDefinitionDetail)
async def get_scenario_definition(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves detailed definition, shock parameters, and assumptions for a scenario."""
    svc = StressDashboardService(db)
    return await svc.get_scenario_definition(scenario_id=scenario_id)


# ---------------------------------------------------------------------------
# 2. Scenario Results & Positions
# ---------------------------------------------------------------------------
@router.get("/results/{calculation_id}", response_model=ScenarioDetailResultResponse)
async def get_scenario_result(
    calculation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns stressed portfolio NAV, P&L, percentage change, and position impacts."""
    svc = StressDashboardService(db)
    return await svc.get_scenario_result(calculation_id=calculation_id)


@router.get("/results/{calculation_id}/positions", response_model=List[PositionStressResult])
async def get_scenario_positions(
    calculation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns position-level revaluations and loss contributions for a calculation."""
    svc = StressDashboardService(db)
    res = await svc.get_scenario_result(calculation_id=calculation_id)
    return res.positions


# ---------------------------------------------------------------------------
# 3. Monte Carlo Distribution & Quantiles
# ---------------------------------------------------------------------------
@router.get("/results/{calculation_id}/distribution", response_model=MonteCarloDistributionResponse)
async def get_monte_carlo_distribution(
    calculation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns simulated terminal P&L histogram, quantiles, and tail risk (VaR/ES)."""
    svc = StressDashboardService(db)
    return await svc.get_monte_carlo_distribution(calculation_id=calculation_id)


# ---------------------------------------------------------------------------
# 4. Scenario Comparison
# ---------------------------------------------------------------------------
@router.post("/compare", response_model=ScenarioComparisonResponse)
async def compare_scenarios(
    portfolio_id: str = Query(...),
    calculation_ids: List[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Assembles side-by-side comparison across multiple stress scenario calculations."""
    svc = StressDashboardService(db)
    return await svc.compare_scenarios(portfolio_id=portfolio_id, calculation_ids=calculation_ids)


# ---------------------------------------------------------------------------
# 5. Stress Loss Attribution
# ---------------------------------------------------------------------------
@router.get("/attribution/{calculation_id}", response_model=StressAttributionResponse)
async def get_loss_attribution(
    calculation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns position, sector, and factor loss attribution with reconciliation status."""
    svc = StressDashboardService(db)
    return await svc.get_loss_attribution(calculation_id=calculation_id)


# ---------------------------------------------------------------------------
# 6. Preferences, Saved Views, and Annotations
# ---------------------------------------------------------------------------
@router.get("/preferences", response_model=StressPreferenceResponse)
async def get_user_preferences(
    user_id: str = Query("default_user"),
    dashboard_name: str = Query("Default Stress Testing Dashboard"),
    db: AsyncSession = Depends(get_db),
):
    svc = StressDashboardService(db)
    return await svc.get_or_create_user_preferences(user_id=user_id, dashboard_name=dashboard_name)


@router.post("/preferences", response_model=StressPreferenceResponse)
async def update_user_preferences(
    req: StressPreferenceCreateRequest,
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = StressDashboardService(db)
    return await svc.update_user_preferences(user_id=user_id, req=req)


@router.get("/saved-views", response_model=List[StressSavedViewResponse])
async def list_saved_views(
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = StressDashboardService(db)
    return await svc.list_saved_views(user_id=user_id)


@router.post("/saved-views", response_model=StressSavedViewResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_view(
    req: StressSavedViewCreateRequest,
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = StressDashboardService(db)
    return await svc.create_saved_view(user_id=user_id, req=req)


@router.get("/annotations", response_model=List[StressAnnotationResponse])
async def list_annotations(
    scenario_id: Optional[str] = Query(None),
    calculation_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    svc = StressDashboardService(db)
    return await svc.list_annotations(scenario_id=scenario_id, calculation_id=calculation_id)


@router.post("/annotations", response_model=StressAnnotationResponse, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    req: StressAnnotationCreateRequest,
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = StressDashboardService(db)
    return await svc.create_annotation(user_id=user_id, req=req)
