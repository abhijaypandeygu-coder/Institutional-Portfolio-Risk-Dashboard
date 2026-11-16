"""
FastAPI router for M11.04 Liquidity Limits.
Endpoints for:
- Configurations (/liquidity-limits)
- Profiles (/liquidity-limit-profiles)
- Profile assignments (/liquidity-limit-assignments)
- Portfolio evaluations (/liquidity-limits/evaluate)
- Pre-trade proposed order simulations (/liquidity-limits/evaluate/proposed-order)
- Breaches & Exceptions (/liquidity-limits/breaches, /liquidity-limits/exceptions)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.liquidity_limits.schemas.liquidity_limit_schemas import (
    LiquidityLimitConfigCreate,
    LiquidityLimitConfigResponse,
    LiquidityProfileCreate,
    LiquidityProfileResponse,
    LiquidityAssignmentCreate,
    LiquidityAssignmentResponse,
    LiquidityEvaluationRequest,
    LiquidityEvaluationResponse,
    ProposedOrderLiquidityRequest,
    ProposedOrderLiquidityResponse,
)
from backend.app.modules.risk_limits.liquidity_limits.services.liquidity_limit_service import (
    LiquidityLimitService,
)

router = APIRouter(
    prefix="/api/v1/risk-limits",
    tags=["M11.04 — Liquidity Limits"]
)


@router.get("/liquidity-limits/health")
async def health_check():
    """Health check endpoint for M11.04 Liquidity Limits."""
    return {
        "status": "healthy",
        "module": "M11.04 - Liquidity Limits",
        "description": "Position & Portfolio Liquidity Restrictions & Horizon Controls Engine"
    }


# Configurations
@router.post("/liquidity-limits", response_model=LiquidityLimitConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_liquidity_limit_configuration(
    payload: LiquidityLimitConfigCreate,
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    try:
        config = await service.create_configuration(payload)
        await session.commit()
        return LiquidityLimitConfigResponse.model_validate(config)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Liquidity limit creation failed: {str(e)}")


@router.get("/liquidity-limits", response_model=List[LiquidityLimitConfigResponse])
async def list_liquidity_limit_configurations(
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    configs = await service.list_configurations(portfolio_id)
    return [LiquidityLimitConfigResponse.model_validate(c) for c in configs]


# Profiles
@router.post("/liquidity-limit-profiles", response_model=LiquidityProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_liquidity_limit_profile(
    payload: LiquidityProfileCreate,
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    try:
        profile = await service.create_profile(payload)
        await session.commit()
        loaded = await service.get_profile(profile.id)
        return LiquidityProfileResponse.model_validate(loaded)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Profile creation failed: {str(e)}")


@router.get("/liquidity-limit-profiles", response_model=List[LiquidityProfileResponse])
async def list_liquidity_limit_profiles(
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    profiles = await service.list_profiles()
    return [LiquidityProfileResponse.model_validate(p) for p in profiles]


# Assignments
@router.post("/liquidity-limit-assignments", response_model=LiquidityAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_liquidity_limit_profile(
    payload: LiquidityAssignmentCreate,
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    try:
        assignment = await service.assign_profile(payload)
        await session.commit()
        return LiquidityAssignmentResponse.model_validate(assignment)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")


# Evaluations
@router.post("/liquidity-limits/evaluate", response_model=LiquidityEvaluationResponse)
async def evaluate_portfolio_liquidity_limits(
    payload: LiquidityEvaluationRequest,
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    try:
        eval_run = await service.evaluate_portfolio_liquidity(payload)
        await session.commit()
        loaded = await service.repo.get_latest_evaluation(payload.portfolio_id)
        return LiquidityEvaluationResponse.model_validate(loaded or eval_run)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Liquidity evaluation failed: {str(e)}")


# Proposed Order Pre-trade Simulation
@router.post("/liquidity-limits/evaluate/proposed-order", response_model=ProposedOrderLiquidityResponse)
async def evaluate_proposed_order_liquidity(
    payload: ProposedOrderLiquidityRequest,
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    try:
        res = await service.evaluate_proposed_order(payload)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pre-trade liquidity evaluation failed: {str(e)}")


# Breaches & Exceptions
@router.get("/liquidity-limits/breaches")
async def list_liquidity_limit_breaches(
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    breaches = await service.repo.list_breaches(portfolio_id)
    return breaches


@router.get("/liquidity-limits/exceptions")
async def list_liquidity_data_exceptions(
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    service = LiquidityLimitService(session)
    exceptions = await service.repo.list_exceptions(portfolio_id)
    return exceptions

