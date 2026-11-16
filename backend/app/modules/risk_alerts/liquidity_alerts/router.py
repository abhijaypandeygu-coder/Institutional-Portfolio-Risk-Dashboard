"""
FastAPI router for M12.03 Liquidity Alerts.
Prefix: /api/v1/liquidity-alerts
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.liquidity_alerts.services.liquidity_alerts_service import LiquidityAlertsService
from backend.app.modules.risk_alerts.liquidity_alerts.schemas.liquidity_alerts_schemas import (
    LiquidityAlertRuleCreate,
    LiquidityAlertRuleUpdate,
    LiquidityAlertRuleResponse,
    SpreadEvaluationRequest,
    DepthEvaluationRequest,
    LiquidityScoreEvaluationRequest,
    LiquidationRiskEvaluationRequest,
    LiquidityAlertEventResponse,
    LiquidityOverviewResponse,
    LiquidityReviewLabelCreate,
)

router = APIRouter(prefix="/api/v1/liquidity-alerts", tags=["M12.03 Liquidity Alerts"])


# -----------------------------------------------------------------
# Health & Overview
# -----------------------------------------------------------------
@router.get("/health", response_model=Dict[str, str])
async def health_check():
    return {
        "status": "HEALTHY",
        "module": "M12.03",
        "description": "Liquidity Alerts Engine",
    }


@router.get("/overview", response_model=LiquidityOverviewResponse)
async def get_liquidity_overview(
    market: str = Query("INDIA", description="INDIA or US"),
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.get_overview(market=market)


# -----------------------------------------------------------------
# Rule Management
# -----------------------------------------------------------------
@router.post("/rules", response_model=LiquidityAlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_liquidity_rule(
    req: LiquidityAlertRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.create_rule(req)


@router.put("/rules/{rule_id}", response_model=LiquidityAlertRuleResponse)
async def update_liquidity_rule(
    rule_id: str,
    req: LiquidityAlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    rule = await service.update_rule(rule_id, req)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.get("/rules", response_model=List[LiquidityAlertRuleResponse])
async def list_liquidity_rules(
    rule_type: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.list_rules(rule_type=rule_type, market=market)


# -----------------------------------------------------------------
# Detection Evaluation Endpoints
# -----------------------------------------------------------------
@router.post("/evaluate/spread", response_model=Optional[LiquidityAlertEventResponse])
async def evaluate_spread_widening(
    req: SpreadEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.evaluate_spread_widening(req)


@router.post("/evaluate/depth", response_model=Optional[LiquidityAlertEventResponse])
async def evaluate_depth_deterioration(
    req: DepthEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.evaluate_depth_deterioration(req)


@router.post("/evaluate/score", response_model=Optional[LiquidityAlertEventResponse])
async def evaluate_liquidity_score(
    req: LiquidityScoreEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.evaluate_liquidity_score(req)


@router.post("/evaluate/liquidation-risk", response_model=Optional[LiquidityAlertEventResponse])
async def evaluate_liquidation_risk(
    req: LiquidationRiskEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.evaluate_liquidation_risk(req)


# -----------------------------------------------------------------
# Event Listing & Review
# -----------------------------------------------------------------
@router.get("", response_model=List[LiquidityAlertEventResponse])
async def list_liquidity_events(
    event_type: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    instrument_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    return await service.list_events(
        event_type=event_type,
        market=market,
        instrument_id=instrument_id,
        limit=limit,
    )


@router.get("/{event_id}", response_model=LiquidityAlertEventResponse)
async def get_liquidity_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    event = await service.get_event_detail(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Liquidity alert event not found")
    return event


@router.post("/{event_id}/review", response_model=Dict[str, str])
async def add_review_label(
    event_id: str,
    req: LiquidityReviewLabelCreate,
    db: AsyncSession = Depends(get_db),
):
    service = LiquidityAlertsService(db)
    label = await service.add_review_label(event_id, req)
    if not label:
        raise HTTPException(status_code=404, detail="Liquidity alert event not found")
    return {"status": "SUCCESS", "review_label": label.review_label}
