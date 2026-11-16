"""
FastAPI router for M12.04 Portfolio Alerts.
Prefix: /api/v1/portfolio-alerts
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.portfolio_alerts.services.portfolio_alerts_service import PortfolioAlertsService
from backend.app.modules.risk_alerts.portfolio_alerts.schemas.portfolio_alerts_schemas import (
    PortfolioAlertRuleCreate,
    PortfolioAlertRuleUpdate,
    PortfolioAlertRuleResponse,
    PortfolioLossEvaluationRequest,
    ConcentrationEvaluationRequest,
    PositionMovementEvaluationRequest,
    CashMovementEvaluationRequest,
    ReconciliationBreakEvaluationRequest,
    PortfolioAlertEventResponse,
    PortfolioAlertOverviewResponse,
)

router = APIRouter(prefix="/api/v1/portfolio-alerts", tags=["M12.04 Portfolio Alerts"])


# -----------------------------------------------------------------
# Health & Overview
# -----------------------------------------------------------------
@router.get("/health", response_model=Dict[str, str])
async def health_check():
    return {
        "status": "HEALTHY",
        "module": "M12.04",
        "description": "Portfolio Alerts Engine",
    }


@router.get("/overview", response_model=PortfolioAlertOverviewResponse)
async def get_portfolio_alert_overview(
    portfolio_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.get_overview(portfolio_id=portfolio_id)


# -----------------------------------------------------------------
# Rule Management
# -----------------------------------------------------------------
@router.post("/rules", response_model=PortfolioAlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio_alert_rule(
    req: PortfolioAlertRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.create_rule(req)


@router.put("/rules/{rule_id}", response_model=PortfolioAlertRuleResponse)
async def update_portfolio_alert_rule(
    rule_id: str,
    req: PortfolioAlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    rule = await service.update_rule(rule_id, req)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.get("/rules", response_model=List[PortfolioAlertRuleResponse])
async def list_portfolio_alert_rules(
    portfolio_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.list_rules(portfolio_id=portfolio_id, category=category)


# -----------------------------------------------------------------
# Evaluation Triggers
# -----------------------------------------------------------------
@router.post("/evaluate/loss", response_model=Optional[PortfolioAlertEventResponse])
async def evaluate_portfolio_loss(
    req: PortfolioLossEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.evaluate_portfolio_loss(req)


@router.post("/evaluate/concentration", response_model=Optional[PortfolioAlertEventResponse])
async def evaluate_concentration_change(
    req: ConcentrationEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.evaluate_concentration_change(req)


@router.post("/evaluate/position-movement", response_model=Optional[PortfolioAlertEventResponse])
async def evaluate_position_movement(
    req: PositionMovementEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.evaluate_position_movement(req)


@router.post("/evaluate/cash-movement", response_model=Optional[PortfolioAlertEventResponse])
async def evaluate_cash_movement(
    req: CashMovementEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.evaluate_cash_movement(req)


@router.post("/evaluate/reconciliation-break", response_model=Optional[PortfolioAlertEventResponse])
async def evaluate_reconciliation_break(
    req: ReconciliationBreakEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.evaluate_reconciliation_break(req)


# -----------------------------------------------------------------
# Event Retrieval
# -----------------------------------------------------------------
@router.get("", response_model=List[PortfolioAlertEventResponse])
async def list_portfolio_alerts(
    portfolio_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    return await service.list_events(portfolio_id=portfolio_id, category=category, limit=limit)


@router.get("/{event_id}", response_model=PortfolioAlertEventResponse)
async def get_portfolio_alert_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioAlertsService(db)
    event = await service.get_event_detail(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Portfolio alert not found")
    return event

