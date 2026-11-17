"""
FastAPI router for M13.02 — Risk Overview.

Exposes REST endpoints under:
/api/v1/dashboard/portfolios/{portfolio_id}/risk-overview
/api/v1/dashboard/portfolios/{portfolio_id}/risk-overview/var
/api/v1/dashboard/portfolios/{portfolio_id}/risk-overview/expected-shortfall
/api/v1/dashboard/portfolios/{portfolio_id}/risk-overview/volatility
/api/v1/dashboard/portfolios/{portfolio_id}/risk-overview/drawdown
/api/v1/dashboard/portfolios/{portfolio_id}/risk-overview/history
/api/v1/dashboard/portfolios/{portfolio_id}/risk-overview/methodology
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.risk_overview.schemas.risk_overview_schemas import (
    RiskOverviewResponse,
    VaRMetricCard,
    ExpectedShortfallMetricCard,
    VolatilityMetricCard,
    DrawdownMetricCard,
    RiskHistoryResponse,
    VolatilityType,
)
from backend.app.modules.dashboard_visualization.risk_overview.services.risk_overview_service import (
    RiskOverviewService,
    VaRPresentationService,
    ExpectedShortfallPresentationService,
    VolatilityPresentationService,
    DrawdownPresentationService,
)

router = APIRouter(tags=["M13.02 — Risk Overview"])


@router.get(
    "/{portfolio_id}/risk-overview",
    response_model=RiskOverviewResponse,
    summary="Consolidated Risk Overview Dashboard",
    description="Returns consolidated VaR, Expected Shortfall, Volatility, and Drawdown presentation cards with failure isolation and quality summary.",
)
async def get_consolidated_risk_overview(
    portfolio_id: str,
    as_of: Optional[date] = Query(None, description="Optional valuation date filter (YYYY-MM-DD)"),
    confidence_level: Decimal = Query(Decimal("0.99"), description="VaR/ES confidence level (0.90, 0.95, 0.975, 0.99, 0.995)"),
    horizon_days: int = Query(1, description="Holding horizon in trading days (1, 5, 10)"),
    var_methodology: str = Query("HISTORICAL_SIMULATION", description="VaR methodology: HISTORICAL_SIMULATION, PARAMETRIC, MONTE_CARLO"),
    volatility_lookback: int = Query(60, description="Volatility lookback window (20, 60, 90, 252)"),
    volatility_type: VolatilityType = Query(VolatilityType.REALIZED, description="REALIZED or FORECAST"),
    drawdown_period: str = Query("1_year", description="Drawdown lookback period (1_month, 3_months, 6_months, 1_year, ytd, all)"),
    session: AsyncSession = Depends(get_db),
):
    service = RiskOverviewService(session)
    try:
        return await service.get_risk_overview(
            portfolio_id=portfolio_id,
            as_of=as_of,
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            var_methodology=var_methodology,
            volatility_lookback=volatility_lookback,
            volatility_type=volatility_type,
            drawdown_period=drawdown_period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate risk overview: {exc}")


@router.get(
    "/{portfolio_id}/risk-overview/var",
    response_model=VaRMetricCard,
    summary="Value at Risk Card",
    description="Retrieves the authoritative M07.02 VaR metric card under specified confidence, horizon, and methodology.",
)
async def get_var_metric(
    portfolio_id: str,
    confidence_level: Decimal = Query(Decimal("0.99"), description="Confidence level"),
    horizon_days: int = Query(1, description="Holding horizon in trading days"),
    methodology: str = Query("HISTORICAL_SIMULATION", description="Methodology"),
    as_of: Optional[date] = Query(None, description="Valuation date"),
    session: AsyncSession = Depends(get_db),
):
    service = VaRPresentationService(session)
    return await service.get_var_card(
        portfolio_id=portfolio_id,
        confidence_level=confidence_level,
        horizon_days=horizon_days,
        methodology=methodology,
        as_of=as_of,
    )


@router.get(
    "/{portfolio_id}/risk-overview/expected-shortfall",
    response_model=ExpectedShortfallMetricCard,
    summary="Expected Shortfall Card",
    description="Retrieves the authoritative M07.03 Expected Shortfall metric card representing modeled tail loss.",
)
async def get_es_metric(
    portfolio_id: str,
    confidence_level: Decimal = Query(Decimal("0.99"), description="Confidence level matching VaR"),
    horizon_days: int = Query(1, description="Holding horizon in trading days"),
    methodology: str = Query("HISTORICAL_SIMULATION", description="Methodology"),
    as_of: Optional[date] = Query(None, description="Valuation date"),
    session: AsyncSession = Depends(get_db),
):
    service = ExpectedShortfallPresentationService(session)
    return await service.get_es_card(
        portfolio_id=portfolio_id,
        confidence_level=confidence_level,
        horizon_days=horizon_days,
        methodology=methodology,
        as_of=as_of,
    )


@router.get(
    "/{portfolio_id}/risk-overview/volatility",
    response_model=VolatilityMetricCard,
    summary="Volatility Card",
    description="Retrieves the authoritative M07.01 Volatility metric card.",
)
async def get_volatility_metric(
    portfolio_id: str,
    lookback_window: int = Query(60, description="Lookback window in trading days"),
    volatility_type: VolatilityType = Query(VolatilityType.REALIZED, description="REALIZED or FORECAST"),
    as_of: Optional[date] = Query(None, description="Valuation date"),
    session: AsyncSession = Depends(get_db),
):
    service = VolatilityPresentationService(session)
    return await service.get_volatility_card(
        portfolio_id=portfolio_id,
        lookback_window=lookback_window,
        volatility_type=volatility_type,
        as_of=as_of,
    )


@router.get(
    "/{portfolio_id}/risk-overview/drawdown",
    response_model=DrawdownMetricCard,
    summary="Drawdown Card",
    description="Retrieves the authoritative M07.04 Current and Maximum Drawdown metrics with recovery context.",
)
async def get_drawdown_metric(
    portfolio_id: str,
    measurement_period: str = Query("1_year", description="Measurement window"),
    as_of: Optional[date] = Query(None, description="Valuation date"),
    session: AsyncSession = Depends(get_db),
):
    service = DrawdownPresentationService(session)
    return await service.get_drawdown_card(
        portfolio_id=portfolio_id,
        measurement_period=measurement_period,
        as_of=as_of,
    )


@router.get(
    "/{portfolio_id}/risk-overview/history",
    response_model=RiskHistoryResponse,
    summary="Historical Risk Time-Series",
    description="Retrieves authoritative historical time series for VaR, Expected Shortfall, Volatility, or Drawdown underwater series.",
)
async def get_risk_metric_history(
    portfolio_id: str,
    metric: str = Query(..., description="Target metric: VAR, EXPECTED_SHORTFALL, VOLATILITY, DRAWDOWN"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    confidence_level: Decimal = Query(Decimal("0.99"), description="Confidence level for VaR/ES"),
    horizon_days: int = Query(1, description="Holding horizon in trading days"),
    lookback_window: int = Query(60, description="Lookback window for volatility"),
    session: AsyncSession = Depends(get_db),
):
    service = RiskOverviewService(session)
    return await service.get_metric_history(
        portfolio_id=portfolio_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        confidence_level=confidence_level,
        horizon_days=horizon_days,
        lookback_window=lookback_window,
    )


@router.get(
    "/{portfolio_id}/risk-overview/methodology",
    summary="Risk Calculation Methodology Metadata",
    description="Returns detailed mathematical formulation, assumptions, and M07 model version metadata for all four risk categories.",
)
async def get_risk_methodology(
    portfolio_id: str,
    session: AsyncSession = Depends(get_db),
):
    service = RiskOverviewService(session)
    try:
        overview = await service.get_risk_overview(portfolio_id=portfolio_id)
        return {
            "portfolio_id": portfolio_id,
            "var_methodology": overview.var.methodology_details,
            "expected_shortfall_methodology": overview.expected_shortfall.methodology_details,
            "volatility_methodology": overview.volatility.methodology_details,
            "drawdown_methodology": overview.drawdown.methodology_details,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
