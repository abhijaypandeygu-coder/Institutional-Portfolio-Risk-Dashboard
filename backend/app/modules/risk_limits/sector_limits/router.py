"""
FastAPI router for M11.03 Sector Limits.
Mounts endpoints for:
- Sector limit configurations (/sector-limits)
- Sector limit profiles (/sector-limit-profiles)
- Profile assignments (/sector-limit-assignments)
- Evaluations (/sector-limits/evaluate)
- Breaches (/sector-limits/breaches)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.sector_limits.schemas.sector_limit_schemas import (
    SectorLimitConfigCreate,
    SectorLimitConfigResponse,
    SectorProfileCreate,
    SectorProfileResponse,
    SectorAssignmentCreate,
    SectorAssignmentResponse,
    SectorEvaluationRequest,
    SectorEvaluationResponse,
)
from backend.app.modules.risk_limits.sector_limits.services.sector_limit_service import (
    SectorLimitService,
)

router = APIRouter(
    prefix="/api/v1/risk-limits",
    tags=["M11.03 — Sector Limits"]
)


@router.get("/sector-limits/health")
async def health_check():
    """Health check endpoint for M11.03 Sector Limits."""
    return {
        "status": "healthy",
        "module": "M11.03 - Sector Limits",
        "description": "Sector & Industry Concentration & Active Exposure Controls Engine"
    }


# Configurations
@router.post("/sector-limits", response_model=SectorLimitConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_sector_limit_configuration(
    payload: SectorLimitConfigCreate,
    session: AsyncSession = Depends(get_db)
):
    service = SectorLimitService(session)
    try:
        config = await service.create_configuration(payload)
        await session.commit()
        return SectorLimitConfigResponse.model_validate(config)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Sector limit creation failed: {str(e)}")


@router.get("/sector-limits", response_model=List[SectorLimitConfigResponse])
async def list_sector_limit_configurations(
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    service = SectorLimitService(session)
    configs = await service.list_configurations(portfolio_id)
    return [SectorLimitConfigResponse.model_validate(c) for c in configs]


# Profiles
@router.post("/sector-limit-profiles", response_model=SectorProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_sector_limit_profile(
    payload: SectorProfileCreate,
    session: AsyncSession = Depends(get_db)
):
    service = SectorLimitService(session)
    try:
        profile = await service.create_profile(payload)
        await session.commit()
        loaded = await service.get_profile(profile.id)
        return SectorProfileResponse.model_validate(loaded)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Profile creation failed: {str(e)}")


@router.get("/sector-limit-profiles", response_model=List[SectorProfileResponse])
async def list_sector_limit_profiles(
    session: AsyncSession = Depends(get_db)
):
    service = SectorLimitService(session)
    profiles = await service.list_profiles()
    return [SectorProfileResponse.model_validate(p) for p in profiles]


# Assignments
@router.post("/sector-limit-assignments", response_model=SectorAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_sector_limit_profile(
    payload: SectorAssignmentCreate,
    session: AsyncSession = Depends(get_db)
):
    service = SectorLimitService(session)
    try:
        assignment = await service.assign_profile(payload)
        await session.commit()
        return SectorAssignmentResponse.model_validate(assignment)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")


# Evaluations
@router.post("/sector-limits/evaluate", response_model=SectorEvaluationResponse)
async def evaluate_portfolio_sector_limits(
    payload: SectorEvaluationRequest,
    session: AsyncSession = Depends(get_db)
):
    service = SectorLimitService(session)
    try:
        eval_run = await service.evaluate_portfolio_sectors(payload)
        await session.commit()
        loaded = await service.repo.get_latest_evaluation(payload.portfolio_id)
        return SectorEvaluationResponse.model_validate(loaded or eval_run)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Sector evaluation failed: {str(e)}")


@router.get("/sector-limits/breaches")
async def list_sector_limit_breaches(
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    service = SectorLimitService(session)
    breaches = await service.repo.list_breaches(portfolio_id)
    return breaches

