"""
M08.01 Factor Definition API Router.
Endpoints:
- GET  /api/v1/factors: List factors with filters
- POST /api/v1/factors: Create factor definition
- GET  /api/v1/factors/{factor_id}: Get factor detail
- POST /api/v1/factors/{factor_id}/versions: Create new immutable factor version
- POST /api/v1/factors/seed: Seed canonical factors (Market, Size, Value, Momentum, Quality)
- POST /api/v1/factors/versions/{version_id}/governance: Lifecycle transition (SUBMIT, APPROVE, ACTIVATE, etc.)
- GET  /api/v1/factor-models: List factor models
- POST /api/v1/factor-models: Create factor model with pinned factor versions
- GET  /api/v1/factor-models/{model_id}: Get factor model detail
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorFamily,
    MarketScope,
    FactorLifecycleStatus,
)
from backend.app.modules.factor_risk.factor_definition.schemas import (
    FactorDefinitionResponse,
    FactorDefinitionVersionResponse,
    CreateFactorDefinitionRequest,
    CreateFactorVersionRequest,
    GovernanceActionRequest,
    FactorModelResponse,
    CreateFactorModelRequest,
)
from backend.app.modules.factor_risk.factor_definition.services.service import (
    FactorDefinitionService,
)

router = APIRouter(prefix="/api/v1/factors", tags=["M08.01 - Factor Definition"])
models_router = APIRouter(prefix="/api/v1/factor-models", tags=["M08.01 - Factor Models"])


@router.get("", response_model=List[FactorDefinitionResponse])
async def list_factors(
    family: Optional[FactorFamily] = Query(None, description="Filter by factor family"),
    market: Optional[MarketScope] = Query(None, description="Filter by market scope"),
    status: Optional[FactorLifecycleStatus] = Query(None, description="Filter by lifecycle status"),
    session: AsyncSession = Depends(get_db),
):
    """List equity factors in registry."""
    service = FactorDefinitionService(session)
    factors = await service.repo.list_factors(family=family, market=market, status=status)
    return [service._build_factor_response(f) for f in factors]


@router.post("", response_model=FactorDefinitionResponse)
async def create_factor(
    request: CreateFactorDefinitionRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create a new factor definition identity and v1 specification."""
    service = FactorDefinitionService(session)
    try:
        return await service.create_factor(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/seed", response_model=List[FactorDefinitionResponse])
async def seed_canonical_factors(
    market: MarketScope = Query(MarketScope.INDIA, description="INDIA or UNITED_STATES"),
    session: AsyncSession = Depends(get_db),
):
    """Seed mandatory initial factor universe (Market, Size, Value, Momentum, Quality)."""
    service = FactorDefinitionService(session)
    return await service.seed_canonical_equity_factors(market=market)


@router.get("/{factor_id}", response_model=FactorDefinitionResponse)
async def get_factor(
    factor_id: str = Path(..., description="Factor identifier"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve factor details and latest version specification."""
    service = FactorDefinitionService(session)
    factor = await service.repo.get_factor_by_id(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return service._build_factor_response(factor)


@router.post("/{factor_id}/versions", response_model=FactorDefinitionVersionResponse)
async def create_new_factor_version(
    factor_id: str = Path(..., description="Factor identifier"),
    request: CreateFactorVersionRequest = ...,
    session: AsyncSession = Depends(get_db),
):
    """Create a new immutable version for an existing factor."""
    service = FactorDefinitionService(session)
    try:
        return await service.create_new_version(factor_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/versions/{version_id}/governance", response_model=FactorDefinitionVersionResponse)
async def apply_governance_action(
    version_id: str = Path(..., description="Version identifier"),
    request: GovernanceActionRequest = ...,
    session: AsyncSession = Depends(get_db),
):
    """Execute governance lifecycle transition (SUBMIT, APPROVE, ACTIVATE, REJECT, DEPRECATE)."""
    service = FactorDefinitionService(session)
    try:
        return await service.apply_governance_action(version_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------------------
# FACTOR MODELS API
# ----------------------------------------------------------------------------

@models_router.get("", response_model=List[FactorModelResponse])
async def list_factor_models(
    session: AsyncSession = Depends(get_db),
):
    """List factor models."""
    service = FactorDefinitionService(session)
    models = await service.repo.list_models()
    return [service._build_model_response(m) for m in models]


@models_router.post("", response_model=FactorModelResponse)
async def create_factor_model(
    request: CreateFactorModelRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create a factor model composed of exact pinned factor definition versions."""
    service = FactorDefinitionService(session)
    try:
        return await service.create_factor_model(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@models_router.get("/{model_id}", response_model=FactorModelResponse)
async def get_factor_model(
    model_id: str = Path(..., description="Model identifier"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve factor model specification and pinned members."""
    service = FactorDefinitionService(session)
    model = await service.repo.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return service._build_model_response(model)

