"""
M09.04 Market Impact - FastAPI Router.
Mounted under /api/v1/market-microstructure/impact
"""

from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.market_impact.schemas import (
    MarketImpactConfigRequest,
    MarketImpactConfigResponse,
    ImpactModelConfigRequest,
    ImpactModelConfigResponse,
    DirectDepthWalkRequest,
    DepthWalkResponse,
    DepthWalkLevelResponse,
    OrderSizeSensitivityRequest,
    ScenarioCreateRequest,
    ScenarioResponse,
    EmpiricalPredictRequest,
    EmpiricalPredictResponse,
    ValidationRunRequest,
    ValidationRunResponse,
    DepthLevelInput,
)
from backend.app.modules.market_microstructure.market_impact.services.service import MarketImpactService
from backend.app.modules.market_microstructure.market_impact.calculations.impact_math import (
    simulate_depth_walk,
    compute_order_size_sensitivity,
    compute_participation_cap,
    compute_execution_schedule,
    compute_square_root_impact,
    compute_empirical_regression_impact,
    compute_kyle_order_flow_impact,
)

router = APIRouter(prefix="/impact", tags=["Market Microstructure - Market Impact Analytics"])


# 1. Direct Depth Walk Simulation
@router.post("/depth-walk/simulate", response_model=DepthWalkResponse, summary="Simulate static displayed-book depth walk")
async def simulate_direct_depth_walk(req: DirectDepthWalkRequest):
    raw_levels = [l.model_dump() for l in req.levels]
    sim = simulate_depth_walk(
        side=req.side,
        proposed_quantity=req.proposed_quantity,
        levels=raw_levels,
        reference_price=req.reference_price,
        instrument_multiplier=req.instrument_multiplier
    )
    return DepthWalkResponse(
        side=sim["side"],
        proposed_quantity=sim["proposed_quantity"],
        reference_price=sim["reference_price"],
        visible_fill_quantity=sim["visible_fill_quantity"],
        residual_unfilled_quantity=sim["residual_unfilled_quantity"],
        fill_percentage=sim["fill_percentage"],
        average_execution_price=sim["average_execution_price"],
        marginal_execution_price=sim["marginal_execution_price"],
        gross_execution_value=sim["gross_execution_value"],
        estimated_cost_amount=sim["estimated_cost_amount"],
        estimated_cost_bps=sim["estimated_cost_bps"],
        spread_crossing_bps=sim["spread_crossing_bps"],
        additional_depth_bps=sim["additional_depth_bps"],
        consumed_level_count=sim["consumed_level_count"],
        available_level_count=sim["available_level_count"],
        consumed_levels=[DepthWalkLevelResponse(**cl) for cl in sim["consumed_levels"]]
    )


# 2. Order-Size Sensitivity
@router.post("/sensitivity", summary="Evaluate cost and price impact across multiple order sizes")
async def evaluate_order_size_sensitivity(req: OrderSizeSensitivityRequest):
    raw_levels = [l.model_dump() for l in req.levels]
    results = compute_order_size_sensitivity(
        side=req.side,
        sizes=req.sizes,
        levels=raw_levels,
        reference_price=req.reference_price,
        instrument_multiplier=req.instrument_multiplier
    )
    return {
        "side": req.side.upper(),
        "reference_price": req.reference_price,
        "scenarios_evaluated": len(results),
        "results": results
    }


# 3. Direct Empirical Prediction
@router.post("/predict", response_model=EmpiricalPredictResponse, summary="Predict market impact using empirical models")
async def predict_market_impact(req: EmpiricalPredictRequest):
    if req.model_type.upper() == "SQUARE_ROOT":
        pred = compute_square_root_impact(
            order_quantity=req.order_quantity,
            expected_horizon_volume=req.expected_horizon_volume,
            horizon_volatility=req.volatility,
            impact_coefficient_y=req.impact_coefficient_y
        )
        return EmpiricalPredictResponse(
            model_type="SQUARE_ROOT",
            impact_bps=pred.get("impact_bps"),
            standard_error_bps=pred.get("standard_error_bps"),
            prediction_lower_bps=pred.get("prediction_lower_bps"),
            prediction_upper_bps=pred.get("prediction_upper_bps"),
            status=pred.get("status", "VALID")
        )
    elif req.model_type.upper() == "KYLE_OFI":
        pred = compute_kyle_order_flow_impact(
            signed_order_flow=req.signed_order_flow or req.order_quantity
        )
        return EmpiricalPredictResponse(
            model_type="KYLE_OFI",
            price_change=pred.get("price_change"),
            status=pred.get("status", "VALID")
        )
    else:
        # EMPIRICAL_REGRESSION
        pr = req.order_quantity / req.expected_horizon_volume if req.expected_horizon_volume > 0.0 else 0.0
        pred = compute_empirical_regression_impact(
            participation_rate=pr,
            spread_bps=req.spread_bps,
            depth_notional=req.depth_notional,
            volatility=req.volatility,
            regime_multiplier=req.regime_multiplier
        )
        return EmpiricalPredictResponse(
            model_type="EMPIRICAL_REGRESSION",
            impact_bps=pred.get("impact_bps"),
            temporary_impact_bps=pred.get("temporary_impact_bps"),
            permanent_impact_bps=pred.get("permanent_impact_bps"),
            standard_error_bps=pred.get("standard_error_bps"),
            prediction_lower_bps=pred.get("prediction_lower_bps"),
            prediction_upper_bps=pred.get("prediction_upper_bps"),
            status=pred.get("status", "VALID")
        )


# 4. Configuration Management
@router.post("/configs", response_model=MarketImpactConfigResponse, summary="Create market impact configuration")
async def create_impact_config(req: MarketImpactConfigRequest, db: AsyncSession = Depends(get_db)):
    srv = MarketImpactService(db)
    cfg = await srv.create_impact_config(req.model_dump())
    return MarketImpactConfigResponse.model_validate(cfg)


@router.post("/models", response_model=ImpactModelConfigResponse, summary="Register or update impact model configuration")
async def create_model_config(req: ImpactModelConfigRequest, db: AsyncSession = Depends(get_db)):
    srv = MarketImpactService(db)
    cfg = await srv.create_model_config(req.model_dump())
    return ImpactModelConfigResponse.model_validate(cfg)


# 5. Scenarios & Persistent Depth Walk Execution
@router.post("/scenarios", response_model=ScenarioResponse, summary="Create hypothetical order scenario")
async def create_scenario(req: ScenarioCreateRequest, db: AsyncSession = Depends(get_db)):
    srv = MarketImpactService(db)
    scen = await srv.create_scenario(req.model_dump())
    return ScenarioResponse.model_validate(scen)


@router.post("/scenarios/{scenario_id}/execute-depth-walk", response_model=DepthWalkResponse, summary="Execute and record depth walk for a scenario")
async def execute_depth_walk(
    scenario_id: str,
    levels: Optional[List[DepthLevelInput]] = None,
    source_book_snapshot_id: Optional[str] = None,
    instrument_multiplier: Decimal = Decimal("1.0"),
    db: AsyncSession = Depends(get_db)
):
    srv = MarketImpactService(db)
    scen = await srv.repo.get_scenario(scenario_id)
    if not scen:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    raw_levels = [l.model_dump() for l in levels] if levels else None
    walk = await srv.execute_depth_walk(
        scenario_id=scenario_id,
        side=scen.order_side,
        proposed_quantity=scen.proposed_quantity,
        reference_price=scen.reference_price,
        levels=raw_levels,
        source_book_snapshot_id=source_book_snapshot_id,
        instrument_multiplier=instrument_multiplier
    )
    walk_levels = await srv.repo.get_depth_walk_levels(walk.depth_walk_id)

    return DepthWalkResponse(
        depth_walk_id=walk.depth_walk_id,
        side=walk.order_side,
        proposed_quantity=walk.proposed_quantity,
        reference_price=walk.reference_price,
        visible_fill_quantity=walk.visible_fill_quantity,
        residual_unfilled_quantity=walk.residual_unfilled_quantity,
        fill_percentage=walk.fill_percentage,
        average_execution_price=walk.average_execution_price,
        marginal_execution_price=walk.marginal_execution_price,
        gross_execution_value=walk.gross_execution_value,
        estimated_cost_amount=walk.estimated_cost_amount,
        estimated_cost_bps=walk.estimated_cost_bps,
        spread_crossing_bps=walk.spread_crossing_bps,
        additional_depth_bps=walk.additional_depth_bps,
        consumed_level_count=walk.consumed_level_count,
        available_level_count=walk.available_level_count,
        consumed_levels=[DepthWalkLevelResponse(
            level_index=cl.level_index,
            price=cl.price,
            available_quantity=cl.available_quantity,
            consumed_quantity=cl.consumed_quantity,
            remaining_quantity=cl.remaining_quantity,
            executed_value=cl.executed_value
        ) for cl in walk_levels]
    )


# 6. Horizon Comparison Endpoint
@router.post("/horizons/compare", summary="Compare market impact across execution horizons")
async def compare_execution_horizons(
    order_quantity: float,
    daily_volume: float,
    daily_volatility: float,
    horizons_minutes: List[int] = Query(default=[1, 5, 15, 30, 60]),
    impact_coefficient_y: float = 0.50
):
    """
    Compares expected square-root impact across execution horizons (scaled by trading session: 390 mins).
    """
    session_minutes = 390.0
    results = []
    for h in horizons_minutes:
        h_ratio = min(max(h / session_minutes, 0.001), 1.0)
        h_vol = daily_volume * h_ratio
        h_volatility = daily_volatility * math.sqrt(h_ratio)
        res = compute_square_root_impact(
            order_quantity=order_quantity,
            expected_horizon_volume=h_vol,
            horizon_volatility=h_volatility,
            impact_coefficient_y=impact_coefficient_y
        )
        res["horizon_minutes"] = h
        res["expected_horizon_volume"] = h_vol
        results.append(res)
    return {"horizons_evaluated": len(results), "comparisons": results}


# 7. Model Validation Run Recording
@router.post("/validation/record", response_model=ValidationRunResponse, summary="Record backtest and validation run")
async def record_validation(req: ValidationRunRequest, db: AsyncSession = Depends(get_db)):
    srv = MarketImpactService(db)
    run = await srv.record_validation_run(req.model_dump())
    return ValidationRunResponse.model_validate(run)
