"""
M08.02 Factor Exposure API Router.
Endpoints:
- POST /api/v1/factor-exposures/returns: Ingest verified factor return series observations
- POST /api/v1/factor-exposures/configs: Create versioned estimation profile
- GET  /api/v1/factor-exposures/configs: List estimation configurations
- POST /api/v1/factor-exposures/estimate: Execute multi-factor loading estimation
- GET  /api/v1/factor-exposures/runs/{run_id}: Retrieve execution run details and loadings
- GET  /api/v1/instruments/{instrument_id}/factor-exposures: Get instrument factor loadings
- GET  /api/v1/portfolios/{portfolio_id}/factor-exposures: Get portfolio factor exposure snapshot
- GET  /api/v1/portfolios/{portfolio_id}/factor-exposures/history: Retrieve historical exposure series
- POST /api/v1/factor-exposures/compare: Compare two snapshots with exact Weight vs. Loading decomposition
"""
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.factor_exposure.schemas import (
    IngestFactorReturnsRequest,
    CreateEstimationConfigRequest,
    EstimationConfigResponse,
    RunEstimationRequest,
    FactorLoadingRunResponse,
    InstrumentFactorLoadingResponse,
    PortfolioFactorExposureResponse,
    CompareFactorExposuresRequest,
    CompareFactorExposuresResponse,
)
from backend.app.modules.factor_risk.factor_exposure.services.service import (
    FactorExposureService,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    WeightingBasis,
)

router = APIRouter(prefix="/api/v1/factor-exposures", tags=["M08.02 - Factor Exposure"])
portfolio_router = APIRouter(prefix="/api/v1/portfolios", tags=["M08.02 - Portfolio Factor Exposure"])
instrument_router = APIRouter(prefix="/api/v1/instruments", tags=["M08.02 - Instrument Factor Exposure"])


# 1. Factor Returns Ingestion
@router.post("/returns")
async def ingest_factor_returns(
    request: IngestFactorReturnsRequest,
    session: AsyncSession = Depends(get_db),
):
    """Ingest actual historical factor return series for a specific factor version."""
    service = FactorExposureService(session)
    return await service.ingest_factor_returns(request)


# 2. Estimation Configurations
@router.post("/configs", response_model=EstimationConfigResponse)
async def create_estimation_config(
    request: CreateEstimationConfigRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create version-controlled estimation profile with deterministic hash."""
    service = FactorExposureService(session)
    try:
        return await service.create_estimation_config(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/configs", response_model=List[EstimationConfigResponse])
async def list_estimation_configs(
    session: AsyncSession = Depends(get_db),
):
    """List all available estimation profiles."""
    service = FactorExposureService(session)
    configs = await service.repo.list_configs()
    return [EstimationConfigResponse.model_validate(c) for c in configs]


# 3. Factor Loading Estimation Execution
@router.post("/estimate", response_model=FactorLoadingRunResponse)
async def run_factor_loading_estimation(
    request: RunEstimationRequest,
    session: AsyncSession = Depends(get_db),
):
    """Execute multi-factor regression solver across target instruments."""
    service = FactorExposureService(session)
    try:
        return await service.run_factor_loading_estimation(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs/{run_id}", response_model=FactorLoadingRunResponse)
async def get_loading_run(
    run_id: str = Path(..., description="Loading run identifier"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve execution run status, data window, and counts."""
    service = FactorExposureService(session)
    run = await service.repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return FactorLoadingRunResponse.model_validate(run)


# 4. Instrument Factor Loadings
@instrument_router.get("/{instrument_id}/factor-exposures", response_model=List[InstrumentFactorLoadingResponse])
async def get_instrument_factor_loadings(
    instrument_id: str = Path(..., description="Canonical instrument identifier"),
    factor_model_version_id: Optional[str] = Query(None, description="Filter by model version ID"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve latest estimated factor loadings for an instrument."""
    service = FactorExposureService(session)
    loadings = await service.repo.get_latest_instrument_loadings(
        instrument_id=instrument_id,
        factor_model_version_id=factor_model_version_id,
    )
    return [InstrumentFactorLoadingResponse.model_validate(l) for l in loadings]


# 5. Portfolio Factor Exposure
@portfolio_router.get("/{portfolio_id}/factor-exposures", response_model=PortfolioFactorExposureResponse)
async def get_portfolio_factor_exposure(
    portfolio_id: str = Path(..., description="Portfolio identifier"),
    factor_model_version_id: str = Query(..., description="Target factor model version ID"),
    as_of_date: Optional[date] = Query(None, description="Evaluation date (default: today)"),
    weighting_basis: WeightingBasis = Query(WeightingBasis.NAV_WEIGHTED, description="NAV_WEIGHTED or GROSS_NORMALIZED"),
    session: AsyncSession = Depends(get_db),
):
    """Calculate and retrieve aggregate portfolio factor exposures using signed NAV weights."""
    service = FactorExposureService(session)
    try:
        return await service.aggregate_portfolio_factor_exposure(
            portfolio_id=portfolio_id,
            factor_model_version_id=factor_model_version_id,
            as_of_date=as_of_date,
            weighting_basis=weighting_basis,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@portfolio_router.get("/{portfolio_id}/factor-exposures/history", response_model=List[PortfolioFactorExposureResponse])
async def get_portfolio_exposure_history(
    portfolio_id: str = Path(..., description="Portfolio identifier"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    factor_code: Optional[str] = Query(None, description="Filter by factor code"),
    factor_model_version_id: Optional[str] = Query(None, description="Filter by model version ID"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve historical snapshots of portfolio factor exposures."""
    service = FactorExposureService(session)
    records = await service.repo.get_portfolio_exposure_history(
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
        factor_code=factor_code,
        factor_model_version_id=factor_model_version_id,
    )
    # Group by as_of_date and loading_run_id
    grouped: Dict[tuple, List] = {}
    for r in records:
        key = (r.as_of_date, r.loading_run_id)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(r)

    results = []
    for (d, run_id), items in grouped.items():
        first = items[0]
        exp_items = [
            {
                "factor_id": i.factor_id,
                "factor_code": i.factor_code,
                "factor_position": i.factor_position,
                "exposure_value": i.exposure_value,
                "standardized_exposure_value": i.standardized_exposure_value,
                "gross_normalized_exposure": i.gross_normalized_exposure,
                "tilt_classification": i.tilt_classification,
                "quality_status": i.quality_status,
            }
            for i in items
        ]
        results.append(
            PortfolioFactorExposureResponse(
                portfolio_id=portfolio_id,
                loading_run_id=run_id,
                factor_model_id=first.factor_model_id,
                factor_model_version_id=first.factor_model_version_id,
                as_of_date=d,
                weighting_basis=first.weighting_basis,
                portfolio_base_currency=first.portfolio_base_currency,
                nav_reference=first.nav_reference,
                gross_market_value=first.gross_market_value,
                covered_signed_weight=first.covered_signed_weight,
                covered_absolute_weight=first.covered_absolute_weight,
                missing_signed_weight=first.missing_signed_weight,
                missing_absolute_weight=first.missing_absolute_weight,
                coverage_percentage=first.coverage_percentage,
                holding_count=first.holding_count,
                covered_holding_count=first.covered_holding_count,
                uncovered_holding_count=first.uncovered_holding_count,
                calculation_timestamp=first.calculation_timestamp,
                restatement_status=first.restatement_status,
                exposures=exp_items,
            )
        )
    return results


# 6. Exposure Change Attribution & Comparison
@router.post("/compare", response_model=CompareFactorExposuresResponse)
async def compare_factor_exposures(
    request: CompareFactorExposuresRequest,
    session: AsyncSession = Depends(get_db),
):
    """Decompose factor exposure change between two dates into Weight vs. Loading effects."""
    service = FactorExposureService(session)
    try:
        return await service.compare_factor_exposures(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

