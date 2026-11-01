"""
M05.07 - Portfolio History Router.
FastAPI endpoints for snapshot capture, bitemporal querying, change timeline, and risk manifests.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.portfolio_history.schemas import (
    PortfolioBookSnapshotCreateRequest,
    PortfolioBookSnapshotResponse,
    PortfolioChangeRecordCreateRequest,
    PortfolioChangeRecordResponse,
    BitemporalStateQueryRequest,
    BitemporalStateResponse,
    RiskRunInputManifestCreateRequest,
    RiskRunInputManifestResponse,
)
from backend.app.modules.portfolio_management.portfolio_history.services.service import (
    PortfolioHistoryService,
)

router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/history",
    tags=["Portfolio History (M05.07)"],
)


@router.post("/snapshots", response_model=PortfolioBookSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def capture_snapshot(
    portfolio_id: str,
    request: PortfolioBookSnapshotCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    if request.portfolio_id != portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio ID in route does not match request body",
        )
    service = PortfolioHistoryService(session)
    return await service.capture_snapshot(request)


@router.get("/snapshots", response_model=List[PortfolioBookSnapshotResponse])
async def list_snapshots(
    portfolio_id: str,
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    service = PortfolioHistoryService(session)
    snaps = await service.repo.get_snapshots_for_portfolio(portfolio_id, limit=limit)
    return [service._to_snapshot_response(s) for s in snaps]


@router.post("/query-as-of", response_model=BitemporalStateResponse)
async def query_historical_state(
    portfolio_id: str,
    request: BitemporalStateQueryRequest,
    session: AsyncSession = Depends(get_db),
):
    if request.portfolio_id != portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio ID in route does not match request body",
        )
    service = PortfolioHistoryService(session)
    return await service.query_bitemporal_state(request)


@router.post("/timeline", response_model=PortfolioChangeRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_change_record(
    portfolio_id: str,
    request: PortfolioChangeRecordCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    if request.portfolio_id != portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio ID in route does not match request body",
        )
    service = PortfolioHistoryService(session)
    return await service.record_change_event(request)


@router.get("/timeline", response_model=List[PortfolioChangeRecordResponse])
async def get_timeline(
    portfolio_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    knowledge_cutoff: Optional[datetime] = None,
    instrument_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    service = PortfolioHistoryService(session)
    return await service.get_change_timeline(
        portfolio_id=portfolio_id,
        start_time=start_time,
        end_time=end_time,
        knowledge_cutoff=knowledge_cutoff,
        instrument_id=instrument_id,
    )


@router.post("/risk-manifests", response_model=RiskRunInputManifestResponse, status_code=status.HTTP_201_CREATED)
async def create_risk_run_manifest(
    portfolio_id: str,
    request: RiskRunInputManifestCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    if request.portfolio_id != portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio ID in route does not match request body",
        )
    service = PortfolioHistoryService(session)
    try:
        return await service.create_risk_run_input_manifest(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/risk-manifests/{manifest_id}", response_model=RiskRunInputManifestResponse)
async def get_risk_run_manifest(
    portfolio_id: str,
    manifest_id: str,
    session: AsyncSession = Depends(get_db),
):
    service = PortfolioHistoryService(session)
    manifest = await service.get_risk_run_input_manifest(manifest_id)
    if not manifest or manifest.portfolio_id != portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk run input manifest {manifest_id} not found for portfolio {portfolio_id}",
        )
    return manifest
