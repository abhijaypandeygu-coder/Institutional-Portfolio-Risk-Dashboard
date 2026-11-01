"""REST API Router for M05.01 - Portfolio Creation."""
import json
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
)
from backend.app.modules.portfolio_management.portfolio_creation.schemas import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    BaseCurrencyChangeRequest,
    PortfolioResponse,
    PortfolioStrategyCreateRequest,
    PortfolioStrategyResponse,
    PortfolioStrategyAssignRequest,
    PortfolioStrategyAssignmentResponse,
    PortfolioMandateCreateRequest,
    PortfolioMandateResponse,
    PortfolioMandateAssignRequest,
    PortfolioMandateAssignmentResponse,
    PortfolioBenchmarkAssignRequest,
    PortfolioBenchmarkResponse,
    PortfolioOwnershipAssignRequest,
    PortfolioOwnershipResponse,
    PortfolioHierarchyAssignRequest,
    PortfolioHierarchyResponse,
    PortfolioValuationSettingsRequest,
    PortfolioValuationSettingsResponse,
    PortfolioAccountingSettingsRequest,
    PortfolioAccountingSettingsResponse,
    PortfolioLimitCreateRequest,
    PortfolioLimitResponse,
    PortfolioConfigurationSnapshotResponse,
    LifecycleTransitionRequest,
    LifecycleEventResponse,
    PortfolioOperationalMetricsResponse,
)
from backend.app.modules.portfolio_management.portfolio_creation.services.service import PortfolioCreationService

router = APIRouter(prefix="/portfolios", tags=["Portfolio Creation"])


# ---------------------------------------------------------------------------
# METRICS & STRATEGIES/MANDATES CATALOG
# ---------------------------------------------------------------------------
@router.get("/metrics/operational", response_model=PortfolioOperationalMetricsResponse)
async def get_operational_metrics(db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.get_operational_metrics()


@router.get("/strategies", response_model=List[PortfolioStrategyResponse])
async def list_strategies(db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_strategies()


@router.post("/strategies", response_model=PortfolioStrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(payload: PortfolioStrategyCreateRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.create_strategy(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/mandates", response_model=List[PortfolioMandateResponse])
async def list_mandates(db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_mandates()


@router.post("/mandates", response_model=PortfolioMandateResponse, status_code=status.HTTP_201_CREATED)
async def create_mandate(payload: PortfolioMandateCreateRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.create_mandate(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# PORTFOLIO REGISTRATION & CRUD
# ---------------------------------------------------------------------------
@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_portfolio(payload: PortfolioCreateRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.create_portfolio(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[PortfolioResponse])
@router.get("/", response_model=List[PortfolioResponse], include_in_schema=False)
async def list_portfolios(
    lifecycle_status: Optional[PortfolioLifecycleStatus] = None,
    base_currency: Optional[str] = None,
    portfolio_type: Optional[PortfolioTypeEnum] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    service = PortfolioCreationService(db)
    return await service.repo.list_portfolios(
        status=lifecycle_status,
        base_currency=base_currency,
        portfolio_type=portfolio_type,
        limit=limit,
        offset=offset
    )


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    pf = await service.repo.get_by_id(portfolio_id)
    if not pf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Portfolio '{portfolio_id}' not found.")
    return pf


@router.patch("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(portfolio_id: str, payload: PortfolioUpdateRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.update_portfolio(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{portfolio_id}/change-base-currency", response_model=PortfolioResponse)
async def change_base_currency(portfolio_id: str, payload: BaseCurrencyChangeRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.change_base_currency(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# STRATEGY & MANDATE ASSIGNMENTS
# ---------------------------------------------------------------------------
@router.post("/{portfolio_id}/strategies", response_model=PortfolioStrategyAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_strategy(portfolio_id: str, payload: PortfolioStrategyAssignRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.assign_strategy(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/strategies", response_model=List[PortfolioStrategyAssignmentResponse])
async def list_portfolio_strategies(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_strategy_assignments(portfolio_id)


@router.post("/{portfolio_id}/mandates", response_model=PortfolioMandateAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_mandate(portfolio_id: str, payload: PortfolioMandateAssignRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.assign_mandate(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/mandates", response_model=List[PortfolioMandateAssignmentResponse])
async def list_portfolio_mandates(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_mandate_assignments(portfolio_id)


# ---------------------------------------------------------------------------
# BENCHMARK ASSOCIATIONS
# ---------------------------------------------------------------------------
@router.post("/{portfolio_id}/benchmarks", response_model=PortfolioBenchmarkResponse, status_code=status.HTTP_201_CREATED)
async def assign_benchmark(portfolio_id: str, payload: PortfolioBenchmarkAssignRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.assign_benchmark(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/benchmarks", response_model=List[PortfolioBenchmarkResponse])
async def list_portfolio_benchmarks(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_benchmarks(portfolio_id)


# ---------------------------------------------------------------------------
# OWNERSHIP ASSOCIATIONS
# ---------------------------------------------------------------------------
@router.post("/{portfolio_id}/ownership", response_model=PortfolioOwnershipResponse, status_code=status.HTTP_201_CREATED)
async def assign_ownership(portfolio_id: str, payload: PortfolioOwnershipAssignRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.assign_ownership(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/ownership", response_model=List[PortfolioOwnershipResponse])
async def list_portfolio_ownerships(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_ownerships(portfolio_id)


# ---------------------------------------------------------------------------
# HIERARCHY & SLEEVES
# ---------------------------------------------------------------------------
@router.post("/{portfolio_id}/hierarchy", response_model=PortfolioHierarchyResponse, status_code=status.HTTP_201_CREATED)
async def assign_hierarchy(portfolio_id: str, payload: PortfolioHierarchyAssignRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.assign_hierarchy(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/children", response_model=List[PortfolioHierarchyResponse])
async def list_child_portfolios(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_child_relationships(portfolio_id)


@router.get("/{portfolio_id}/ancestors", response_model=List[PortfolioHierarchyResponse])
async def list_parent_portfolios(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_parent_relationships(portfolio_id)


# ---------------------------------------------------------------------------
# VALUATION & ACCOUNTING SETTINGS
# ---------------------------------------------------------------------------
@router.post("/{portfolio_id}/valuation-settings", response_model=PortfolioValuationSettingsResponse)
async def update_valuation_settings(portfolio_id: str, payload: PortfolioValuationSettingsRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.update_valuation_settings(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/valuation-settings", response_model=PortfolioValuationSettingsResponse)
async def get_valuation_settings(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    settings_obj = await service.repo.get_valuation_settings(portfolio_id)
    if not settings_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Valuation settings not found.")
    return settings_obj


@router.post("/{portfolio_id}/accounting-settings", response_model=PortfolioAccountingSettingsResponse)
async def update_accounting_settings(portfolio_id: str, payload: PortfolioAccountingSettingsRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.update_accounting_settings(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/accounting-settings", response_model=PortfolioAccountingSettingsResponse)
async def get_accounting_settings(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    settings_obj = await service.repo.get_accounting_settings(portfolio_id)
    if not settings_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accounting settings not found.")
    return settings_obj


# ---------------------------------------------------------------------------
# LIMITS
# ---------------------------------------------------------------------------
@router.post("/{portfolio_id}/limits", response_model=PortfolioLimitResponse, status_code=status.HTTP_201_CREATED)
async def create_limit(portfolio_id: str, payload: PortfolioLimitCreateRequest, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.create_limit(portfolio_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/limits", response_model=List[PortfolioLimitResponse])
async def list_limits(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_limits(portfolio_id)


# ---------------------------------------------------------------------------
# LIFECYCLE MANAGEMENT
# ---------------------------------------------------------------------------
@router.post("/{portfolio_id}/submit", response_model=PortfolioResponse)
async def submit_for_approval(portfolio_id: str, req: Optional[LifecycleTransitionRequest] = None, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.transition_lifecycle(portfolio_id, PortfolioLifecycleStatus.PENDING_APPROVAL, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{portfolio_id}/approve", response_model=PortfolioResponse)
async def approve_portfolio(portfolio_id: str, req: Optional[LifecycleTransitionRequest] = None, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.transition_lifecycle(portfolio_id, PortfolioLifecycleStatus.APPROVED, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{portfolio_id}/activate", response_model=PortfolioResponse)
async def activate_portfolio(portfolio_id: str, req: Optional[LifecycleTransitionRequest] = None, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.transition_lifecycle(portfolio_id, PortfolioLifecycleStatus.ACTIVE, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{portfolio_id}/suspend", response_model=PortfolioResponse)
async def suspend_portfolio(portfolio_id: str, req: Optional[LifecycleTransitionRequest] = None, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.transition_lifecycle(portfolio_id, PortfolioLifecycleStatus.SUSPENDED, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{portfolio_id}/resume", response_model=PortfolioResponse)
async def resume_portfolio(portfolio_id: str, req: Optional[LifecycleTransitionRequest] = None, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.transition_lifecycle(portfolio_id, PortfolioLifecycleStatus.ACTIVE, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{portfolio_id}/close", response_model=PortfolioResponse)
async def close_portfolio(portfolio_id: str, req: Optional[LifecycleTransitionRequest] = None, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    try:
        return await service.transition_lifecycle(portfolio_id, PortfolioLifecycleStatus.CLOSED, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{portfolio_id}/lifecycle-history", response_model=List[LifecycleEventResponse])
async def list_lifecycle_history(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    return await service.repo.list_lifecycle_events(portfolio_id)


# ---------------------------------------------------------------------------
# CONFIGURATION REPRODUCIBILITY & POINT-IN-TIME
# ---------------------------------------------------------------------------
@router.get("/{portfolio_id}/configuration/as-of", response_model=PortfolioConfigurationSnapshotResponse)
async def get_configuration_as_of(portfolio_id: str, as_of_date: date = Query(...), db: AsyncSession = Depends(get_db)):
    service = PortfolioCreationService(db)
    ver = await service.repo.get_configuration_as_of(portfolio_id, as_of_date)
    if not ver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No configuration snapshot found for date {as_of_date}.")
    return PortfolioConfigurationSnapshotResponse(
        portfolio_id=ver.portfolio_id,
        version_number=ver.version_number,
        valid_from=ver.valid_from,
        valid_to=ver.valid_to,
        recorded_at=ver.recorded_at,
        created_by=ver.created_by,
        change_reason=ver.change_reason,
        snapshot=json.loads(ver.snapshot_json),
    )

