"""
M06.02 Net Exposure FastAPI Router.
Endpoints for calculating, querying, and monitoring directional net exposure,
ratios, breakdowns, contributions, and threshold events.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_management.net_exposure.models import (
    NetDenominatorType,
    NeutralityThresholdType,
    NetExposurePolicy,
)
from backend.app.modules.risk_management.net_exposure.schemas import (
    NetExposureCalculateRequest,
    NetExposureSummaryResponse,
    NetExposureContributionResponse,
    NetExposureBreakdownResponse,
    DirectionalThresholdEventResponse,
    NetExposurePolicyCreateRequest,
    NetExposurePolicyResponse,
)
from backend.app.modules.risk_management.net_exposure.services.service import (
    NetExposureService,
)

router = APIRouter(
    tags=["Risk Management - Net Exposure (M06.02)"],
)


@router.get("/api/v1/portfolios/{portfolio_id}/risk/net-exposure", response_model=NetExposureSummaryResponse)
async def get_portfolio_net_exposure(
    portfolio_id: str,
    as_of: Optional[datetime] = None,
    reporting_currency: Optional[str] = None,
    denominator_type: NetDenominatorType = NetDenominatorType.NAV,
    custom_denominator_value: Optional[Decimal] = None,
    neutrality_threshold_type: Optional[NeutralityThresholdType] = NeutralityThresholdType.RELATIVE,
    absolute_neutrality_threshold: Optional[Decimal] = None,
    relative_neutrality_threshold: Optional[Decimal] = Decimal("0.020000"),
    session: AsyncSession = Depends(get_db),
):
    service = NetExposureService(session)
    req = NetExposureCalculateRequest(
        as_of=as_of,
        reporting_currency=reporting_currency,
        denominator_type=denominator_type,
        custom_denominator_value=custom_denominator_value,
        neutrality_threshold_type=neutrality_threshold_type,
        absolute_neutrality_threshold=absolute_neutrality_threshold,
        relative_neutrality_threshold=relative_neutrality_threshold,
    )
    return await service.calculate_portfolio_net_exposure(portfolio_id, req)


@router.post(
    "/api/v1/portfolios/{portfolio_id}/risk/net-exposure/calculate",
    response_model=NetExposureSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def calculate_portfolio_net_exposure_endpoint(
    portfolio_id: str,
    request: NetExposureCalculateRequest,
    session: AsyncSession = Depends(get_db),
):
    service = NetExposureService(session)
    return await service.calculate_portfolio_net_exposure(portfolio_id, request)


@router.get("/api/v1/portfolio-groups/{group_id}/risk/net-exposure", response_model=NetExposureSummaryResponse)
async def get_group_net_exposure(
    group_id: str,
    as_of: Optional[datetime] = None,
    reporting_currency: Optional[str] = None,
    denominator_type: NetDenominatorType = NetDenominatorType.NAV,
    custom_denominator_value: Optional[Decimal] = None,
    session: AsyncSession = Depends(get_db),
):
    service = NetExposureService(session)
    req = NetExposureCalculateRequest(
        as_of=as_of,
        reporting_currency=reporting_currency,
        denominator_type=denominator_type,
        custom_denominator_value=custom_denominator_value,
    )
    return await service.calculate_group_net_exposure(group_id, req)


@router.post(
    "/api/v1/portfolio-groups/{group_id}/risk/net-exposure/calculate",
    response_model=NetExposureSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def calculate_group_net_exposure_endpoint(
    group_id: str,
    request: NetExposureCalculateRequest,
    session: AsyncSession = Depends(get_db),
):
    service = NetExposureService(session)
    return await service.calculate_group_net_exposure(group_id, request)


@router.get("/api/v1/risk/net-exposure/runs/{run_id}/contributions", response_model=List[NetExposureContributionResponse])
async def get_run_contributions(run_id: str, session: AsyncSession = Depends(get_db)):
    service = NetExposureService(session)
    conts = await service.repo.get_contributions(run_id)
    return [NetExposureContributionResponse.model_validate(c) for c in conts]


@router.get("/api/v1/risk/net-exposure/runs/{run_id}/breakdowns", response_model=List[NetExposureBreakdownResponse])
async def get_run_breakdowns(run_id: str, session: AsyncSession = Depends(get_db)):
    service = NetExposureService(session)
    bdowns = await service.repo.get_breakdowns(run_id)
    return [NetExposureBreakdownResponse.model_validate(b) for b in bdowns]


@router.get("/api/v1/risk/net-exposure/runs/{run_id}/threshold-events", response_model=List[DirectionalThresholdEventResponse])
async def get_run_threshold_events(run_id: str, session: AsyncSession = Depends(get_db)):
    service = NetExposureService(session)
    events = await service.repo.get_threshold_events(run_id)
    return [DirectionalThresholdEventResponse.model_validate(e) for e in events]


@router.post("/api/v1/risk/net-exposure/policies", response_model=NetExposurePolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_net_exposure_policy(
    payload: NetExposurePolicyCreateRequest, session: AsyncSession = Depends(get_db)
):
    service = NetExposureService(session)
    import uuid
    policy_id = f"NET-POL-{uuid.uuid4().hex[:10].upper()}"
    pol = NetExposurePolicy(
        id=policy_id,
        policy_name=payload.policy_name,
        portfolio_id=payload.portfolio_id,
        group_id=payload.group_id,
        reporting_currency=payload.reporting_currency,
        denominator_type=payload.denominator_type.value,
        neutrality_threshold_type=payload.neutrality_threshold_type.value,
        absolute_neutrality_threshold=payload.absolute_neutrality_threshold,
        relative_neutrality_threshold=payload.relative_neutrality_threshold,
        combined_threshold_semantics=payload.combined_threshold_semantics,
        max_net_long_ratio=payload.max_net_long_ratio,
        max_net_short_ratio=payload.max_net_short_ratio,
        warning_buffer_pct=payload.warning_buffer_pct,
    )
    pol = await service.repo.save_policy(pol)
    return pol

