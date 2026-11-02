"""
M07.10 Risk Forecasting API Router.
Endpoints:
- POST /api/v1/market-risk/forecast/volatility: Generate forward-looking risk forecast
- GET  /api/v1/market-risk/forecast/volatility: Retrieve latest or rolling risk forecast
- POST /api/v1/market-risk/forecast/compare: Multi-model walk-forward comparison
- POST /api/v1/market-risk/forecast/{calculation_id}/evaluate: Evaluate forecast against realized proxy
- GET  /api/v1/market-risk/forecast/monitoring-events: Retrieve monitoring alerts
- GET  /api/v1/portfolios/{portfolio_id}/risk/forecast: Nested portfolio risk forecast
"""
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.risk_forecasting.models import (
    ForecastModelType,
    ForecastCalculationScope,
    RealizedVarianceProxyType,
)
from backend.app.modules.market_risk.risk_forecasting.schemas import (
    VolatilityForecastRequest,
    VolatilityForecastResponse,
    ModelComparisonRequest,
    ModelComparisonResponse,
    ForecastEvaluationItem,
    MonitoringEventResponse,
)
from backend.app.modules.market_risk.risk_forecasting.services.service import (
    RiskForecastingService,
)

router = APIRouter(prefix="/api/v1/market-risk/forecast", tags=["Market Risk - Risk Forecasting"])
portfolio_nested_router = APIRouter(prefix="/api/v1/portfolios", tags=["Portfolio Risk Forecasting"])


@router.post("/volatility", response_model=VolatilityForecastResponse)
async def generate_volatility_forecast(
    request: VolatilityForecastRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Generate and persist point-in-time risk forecasts across Rolling, EWMA, or GARCH(1,1).
    """
    service = RiskForecastingService(session)
    return await service.generate_forecast(request)


@router.get("/volatility", response_model=VolatilityForecastResponse)
async def get_volatility_forecast(
    scope: ForecastCalculationScope = Query(ForecastCalculationScope.INSTRUMENT),
    entity_id: str = Query(..., description="instrument_id or portfolio_id"),
    model_name: Optional[ForecastModelType] = Query(None, description="ROLLING_HISTORICAL, EWMA, or GARCH_1_1"),
    as_of: Optional[date] = Query(None, description="Forecast origin cutoff date"),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve the latest persisted volatility forecast or calculate on demand.
    """
    service = RiskForecastingService(session)
    return await service.get_latest_forecast(scope=scope, entity_id=entity_id, model_name=model_name, as_of=as_of)


@router.post("/compare", response_model=ModelComparisonResponse)
async def compare_forecasting_models(
    request: ModelComparisonRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Walk-forward side-by-side performance comparison across competing forecasting models.
    """
    service = RiskForecastingService(session)
    return await service.compare_models(request)


@router.post("/{calculation_id}/evaluate", response_model=ForecastEvaluationItem)
async def evaluate_forecast(
    calculation_id: str = Path(..., description="Calculation run identifier"),
    realized_proxy: RealizedVarianceProxyType = Query(RealizedVarianceProxyType.SQUARED_RETURN),
    session: AsyncSession = Depends(get_db),
):
    """
    Ex-post evaluation of a forecast against subsequently realized returns after horizon maturity.
    """
    service = RiskForecastingService(session)
    try:
        return await service.evaluate_forecast(calculation_id=calculation_id, realized_proxy_type=realized_proxy)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/monitoring-events", response_model=List[MonitoringEventResponse])
async def list_monitoring_events(
    entity_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve forecast risk monitoring events and persistent underforecasting alerts.
    """
    service = RiskForecastingService(session)
    events = await service.repo.list_monitoring_events(entity_id=entity_id, limit=limit)
    return [
        MonitoringEventResponse(
            id=e.id,
            entity_id=e.entity_id,
            model_name=e.model_name,
            event_type=e.event_type,
            detected_at=e.detected_at,
            observed_metric=e.observed_metric,
            observed_value=e.observed_value,
            threshold_value=e.threshold_value,
            details=e.details,
        )
        for e in events
    ]


# Nested Portfolio Endpoint
@portfolio_nested_router.get("/{portfolio_id}/risk/forecast", response_model=VolatilityForecastResponse)
async def get_portfolio_volatility_forecast(
    portfolio_id: str = Path(..., description="Portfolio identifier"),
    model_name: Optional[ForecastModelType] = Query(None),
    as_of: Optional[date] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """
    Portfolio-scoped endpoint for forward-looking risk forecasting.
    """
    service = RiskForecastingService(session)
    return await service.get_latest_forecast(
        scope=ForecastCalculationScope.PORTFOLIO,
        entity_id=portfolio_id,
        model_name=model_name,
        as_of=as_of,
    )
