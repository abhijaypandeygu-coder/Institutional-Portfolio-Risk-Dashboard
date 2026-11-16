"""
FastAPI router for M11.01 Portfolio Risk Limits.
Mounts endpoints for profile management, versioning, assignments, and limit evaluations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.portfolio_risk_limits.schemas.limit_schemas import (
    ProfileCreate,
    ProfileResponse,
    AssignmentCreate,
    AssignmentResponse,
    EvaluationRequest,
    PortfolioEvaluationResponse,
)
from backend.app.modules.risk_limits.portfolio_risk_limits.services.limit_service import (
    PortfolioRiskLimitService,
)

router = APIRouter(
    prefix="/api/v1/risk-limits",
    tags=["M11.01 — Portfolio Risk Limits"]
)


@router.get("/health")
async def health_check():
    """Health check for M11.01 Portfolio Risk Limits module."""
    return {
        "status": "healthy",
        "module": "M11.01 - Portfolio Risk Limits",
        "description": "Portfolio Risk Limits & Threshold Evaluation Engine"
    }


@router.post("/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: ProfileCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Creates a new risk-limit profile and initial version.
    """
    service = PortfolioRiskLimitService(session)
    try:
        profile = await service.create_profile(payload)
        await session.commit()
        return ProfileResponse(
            id=profile.id,
            profile_code=profile.profile_code,
            profile_name=profile.profile_name,
            description=profile.description,
            profile_category=profile.profile_category,
            mandate_type=profile.mandate_type,
            portfolio_type=profile.portfolio_type,
            base_currency_policy=profile.base_currency_policy,
            status=profile.status,
            owner_id=profile.owner_id,
            is_active=profile.is_active,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")


@router.get("/profiles", response_model=List[ProfileResponse])
async def list_profiles(
    session: AsyncSession = Depends(get_db)
):
    """
    Lists all configured risk-limit profiles.
    """
    service = PortfolioRiskLimitService(session)
    profiles = await service.list_profiles()
    res = []
    for p in profiles:
        res.append(
            ProfileResponse(
                id=p.id,
                profile_code=p.profile_code,
                profile_name=p.profile_name,
                description=p.description,
                profile_category=p.profile_category,
                mandate_type=p.mandate_type,
                portfolio_type=p.portfolio_type,
                base_currency_policy=p.base_currency_policy,
                status=p.status,
                owner_id=p.owner_id,
                is_active=p.is_active,
                created_at=p.created_at,
                updated_at=p.updated_at
            )
        )
    return res


@router.get("/profiles/{profile_code}", response_model=ProfileResponse)
async def get_profile(
    profile_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves profile by code or ID.
    """
    service = PortfolioRiskLimitService(session)
    p = await service.get_profile(profile_code)
    if not p:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_code}' not found")
    return ProfileResponse(
        id=p.id,
        profile_code=p.profile_code,
        profile_name=p.profile_name,
        description=p.description,
        profile_category=p.profile_category,
        mandate_type=p.mandate_type,
        portfolio_type=p.portfolio_type,
        base_currency_policy=p.base_currency_policy,
        status=p.status,
        owner_id=p.owner_id,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at
    )


@router.post("/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_profile(
    payload: AssignmentCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Assigns an approved risk-limit profile to a portfolio or mandate.
    """
    service = PortfolioRiskLimitService(session)
    try:
        assign = await service.assign_profile(payload)
        await session.commit()
        return assign
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign profile: {str(e)}")


@router.post("/portfolios/{portfolio_id}/evaluate", response_model=PortfolioEvaluationResponse)
async def evaluate_portfolio_limits(
    portfolio_id: str,
    payload: EvaluationRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Evaluates observed portfolio risk metrics against effective risk limits.
    """
    service = PortfolioRiskLimitService(session)
    try:
        payload.portfolio_id = portfolio_id
        res = await service.evaluate_portfolio_limits(payload)
        await session.commit()
        return PortfolioEvaluationResponse.model_validate(res)
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")
