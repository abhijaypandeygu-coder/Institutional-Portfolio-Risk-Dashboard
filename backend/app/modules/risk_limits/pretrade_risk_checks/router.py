"""
FastAPI router for M11.09 Pre-trade Risk Checks.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.pretrade_risk_checks.schemas.pretrade_risk_schemas import (
    ProposedOrderInput,
    OrderValidationResult,
    PretradeDecisionResponse,
    AuthorizationValidationResponse,
    PretradeDashboardSummary,
)
from backend.app.modules.risk_limits.pretrade_risk_checks.services.pretrade_risk_service import PretradeRiskService

router = APIRouter(prefix="/api/v1/pretrade", tags=["M11.09 Pre-trade Risk Checks"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "module": "M11.09 — Pre-trade Risk Checks",
        "version": "1.0.0",
        "capabilities": [
            "order_validation",
            "portfolio_simulation",
            "position_limit_evaluation",
            "sector_limit_evaluation",
            "exposure_limit_evaluation",
            "var_incremental_evaluation",
            "liquidity_participation_check",
            "funding_validation",
            "data_freshness_gate",
            "decision_engine",
            "risk_reservations",
            "execution_authorization",
        ]
    }


@router.get("/dashboard", response_model=PretradeDashboardSummary)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    svc = PretradeRiskService(db)
    return await svc.get_dashboard_summary()


@router.post("/orders/validate", response_model=OrderValidationResult)
async def validate_order(payload: ProposedOrderInput, db: AsyncSession = Depends(get_db)):
    svc = PretradeRiskService(db)
    return svc.validate_order_parameters(payload)


@router.post("/orders/evaluate", response_model=PretradeDecisionResponse)
async def evaluate_order(payload: ProposedOrderInput, db: AsyncSession = Depends(get_db)):
    svc = PretradeRiskService(db)
    return await svc.evaluate_proposed_order(payload)


@router.get("/authorizations/{authorization_id}/validate", response_model=AuthorizationValidationResponse)
async def validate_authorization(authorization_id: str, db: AsyncSession = Depends(get_db)):
    svc = PretradeRiskService(db)
    return await svc.validate_authorization(authorization_id)
