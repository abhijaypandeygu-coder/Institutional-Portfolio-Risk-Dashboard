"""
FastAPI router for M11.02 Position Limits.
Mounts endpoints for:
- Configurations (/position-limits)
- Profiles (/position-limit-profiles)
- Assignments (/position-limit-assignments)
- Evaluations (/position-limits/evaluate)
- Proposed-order pre-trade evaluation (/position-limits/evaluate/proposed-order)
- Breaches & Audit (/position-limits/breaches)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.position_limits.schemas.position_limit_schemas import (
    ConfigurationCreate,
    ConfigurationResponse,
    ProfileCreate,
    ProfileResponse,
    AssignmentCreate,
    AssignmentResponse,
    PortfolioEvaluationRequest,
    PortfolioEvaluationResponse,
    ProposedOrderRequest,
    ProposedOrderEvaluationResponse,
)
from backend.app.modules.risk_limits.position_limits.services.position_limit_service import (
    PositionLimitService,
)

router = APIRouter(
    prefix="/api/v1/risk-limits",
    tags=["M11.02 — Position Limits"]
)


@router.get("/position-limits/health")
async def health_check():
    """Health check endpoint for M11.02 Position Limits."""
    return {
        "status": "healthy",
        "module": "M11.02 - Position Limits",
        "description": "Position Limits & Concentration Controls Engine"
    }


# Configurations
@router.post("/position-limits", response_model=ConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_position_limit_configuration(
    payload: ConfigurationCreate,
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    try:
        config = await service.create_configuration(payload)
        await session.commit()
        return ConfigurationResponse.model_validate(config)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Configuration creation failed: {str(e)}")


@router.get("/position-limits", response_model=List[ConfigurationResponse])
async def list_position_limit_configurations(
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    configs = await service.list_configurations(portfolio_id)
    return [ConfigurationResponse.model_validate(c) for c in configs]


# Profiles
@router.post("/position-limit-profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_position_limit_profile(
    payload: ProfileCreate,
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    try:
        profile = await service.create_profile(payload)
        await session.commit()
        # Retrieve freshly with eager loaded configurations
        loaded_profile = await service.get_profile(profile.id)
        return ProfileResponse.model_validate(loaded_profile)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Profile creation failed: {str(e)}")


@router.get("/position-limit-profiles", response_model=List[ProfileResponse])
async def list_position_limit_profiles(
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    profiles = await service.list_profiles()
    return [ProfileResponse.model_validate(p) for p in profiles]


# Assignments
@router.post("/position-limit-assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_position_limit_profile(
    payload: AssignmentCreate,
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    try:
        assignment = await service.assign_profile(payload)
        await session.commit()
        return AssignmentResponse.model_validate(assignment)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")


# Evaluations
@router.post("/position-limits/evaluate", response_model=PortfolioEvaluationResponse)
async def evaluate_portfolio_position_limits(
    payload: PortfolioEvaluationRequest,
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    try:
        eval_run = await service.evaluate_portfolio_positions(payload)
        await session.commit()
        return PortfolioEvaluationResponse.model_validate(eval_run)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/position-limits/evaluate/proposed-order", response_model=ProposedOrderEvaluationResponse)
async def evaluate_proposed_order(
    payload: ProposedOrderRequest,
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    try:
        result = await service.evaluate_proposed_order(payload)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proposed order evaluation failed: {str(e)}")


@router.get("/position-limits/breaches")
async def list_position_limit_breaches(
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    service = PositionLimitService(session)
    breaches = await service.repo.list_breaches(portfolio_id)
    return breaches
