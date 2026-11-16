"""
FastAPI router for M12.02 Market Alerts.
Prefix: /api/v1/market-alerts
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.market_alerts.services.market_alerts_service import MarketAlertsService
from backend.app.modules.risk_alerts.market_alerts.schemas.market_alerts_schemas import (
    MarketAlertRuleCreate,
    MarketAlertRuleUpdate,
    MarketAlertRuleResponse,
    PriceMovementEvaluationRequest,
    VolatilityEvaluationRequest,
    MarketBandEvaluationRequest,
    TradingStatusEventRequest,
    MarketWideEventRequest,
    MarketEventResponse,
    ReviewLabelCreate,
    MarketOverviewResponse,
)

router = APIRouter(prefix="/api/v1/market-alerts", tags=["M12.02 Market Alerts"])


# -----------------------------------------------------------------
# Health & Overview
# -----------------------------------------------------------------
@router.get("/health", response_model=Dict[str, str])
async def health_check():
    return {
        "status": "HEALTHY",
        "module": "M12.02",
        "description": "Market Alerts Detection Engine",
    }


@router.get("/overview", response_model=MarketOverviewResponse)
async def get_market_overview(
    market: str = Query("INDIA", description="INDIA or US"),
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.get_market_overview(market=market)


# -----------------------------------------------------------------
# Rule Management
# -----------------------------------------------------------------
@router.post("/rules", response_model=MarketAlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_market_alert_rule(
    req: MarketAlertRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.create_rule(req)


@router.put("/rules/{rule_id}", response_model=MarketAlertRuleResponse)
async def update_market_alert_rule(
    rule_id: str,
    req: MarketAlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    rule = await service.update_rule(rule_id, req)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.get("/rules", response_model=List[MarketAlertRuleResponse])
async def list_market_alert_rules(
    rule_type: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.list_rules(rule_type=rule_type, market=market)


# -----------------------------------------------------------------
# Evaluators & Detection Triggers
# -----------------------------------------------------------------
@router.post("/evaluate/price-movement", response_model=Optional[MarketEventResponse])
async def evaluate_price_movement(
    req: PriceMovementEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.evaluate_price_movement(req)


@router.post("/evaluate/volatility-spike", response_model=Optional[MarketEventResponse])
async def evaluate_volatility_spike(
    req: VolatilityEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.evaluate_volatility_spike(req)


@router.post("/evaluate/market-band", response_model=Optional[MarketEventResponse])
async def evaluate_market_band(
    req: MarketBandEvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.evaluate_market_band(req)


@router.post("/events/trading-status", response_model=Optional[MarketEventResponse])
async def process_trading_status_event(
    req: TradingStatusEventRequest,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    _, event = await service.process_trading_status_event(req)
    return event


@router.post("/events/market-wide", response_model=MarketEventResponse)
async def process_market_wide_event(
    req: MarketWideEventRequest,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.process_market_wide_event(req)


# -----------------------------------------------------------------
# Market Events Listing & Details
# -----------------------------------------------------------------
@router.get("", response_model=List[MarketEventResponse])
async def list_market_events(
    event_type: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
    event_state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    return await service.list_market_events(
        event_type=event_type,
        market=market,
        exchange=exchange,
        event_state=event_state,
        limit=limit,
    )


@router.get("/{event_id}", response_model=MarketEventResponse)
async def get_market_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    event = await service.get_market_event_detail(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Market event not found")
    return event


@router.post("/{event_id}/review", response_model=Dict[str, str])
async def add_review_label(
    event_id: str,
    req: ReviewLabelCreate,
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    label = await service.add_review_label(event_id, req)
    if not label:
        raise HTTPException(status_code=404, detail="Market event not found")
    return {"status": "SUCCESS", "review_label": label.review_label}


@router.get("/halts/active", response_model=List[Dict[str, Any]])
async def list_active_halts(
    db: AsyncSession = Depends(get_db),
):
    service = MarketAlertsService(db)
    halts = await service.list_active_halts(active_only=True)
    return [
        {
            "id": h.id,
            "instrument_id": h.instrument_id,
            "exchange": h.exchange,
            "normalized_status": h.normalized_status,
            "halt_reason": h.halt_reason,
            "halt_start_timestamp": h.halt_start_timestamp,
        }
        for h in halts
    ]
