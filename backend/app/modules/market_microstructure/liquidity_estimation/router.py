"""
M09.03 Liquidity Estimation - FastAPI Router.
Mounted under /api/v1/market-microstructure/liquidity
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.liquidity_estimation.schemas import (
    MetricConfigRequest,
    MetricConfigResponse,
    ScoreProfileRequest,
    ScoreProfileResponse,
    BucketPolicyRequest,
    BucketPolicyResponse,
    VolumeAggregateResponse,
    TurnoverAggregateResponse,
    RollingStatisticsResponse,
    DirectCalculationRequest,
    LiquidityScoreResponse,
    LiquidityBucketResponse,
    LiquidityOverviewResponse,
    LiquidityScreenRequest,
    DirectTradeInput,
)
from backend.app.modules.market_microstructure.liquidity_estimation.services.service import LiquidityEstimationService
from backend.app.modules.market_microstructure.liquidity_estimation.calculations.liquidity_math import (
    compute_subscores,
    compute_data_availability_score,
    compute_composite_liquidity_score,
    classify_liquidity_bucket,
    _normalize_tz,
)

router = APIRouter(prefix="/liquidity", tags=["Market Microstructure - Liquidity Estimation"])


# 1. Direct on-the-fly score calculation
@router.post("/calculate", response_model=LiquidityScoreResponse, summary="Direct liquidity score calculation")
async def direct_calculate_score(req: DirectCalculationRequest):
    subscores = compute_subscores(
        spread_bps=req.spread_bps,
        depth_notional=float(req.depth_notional) if req.depth_notional is not None else None,
        turnover_val=float(req.turnover_amount) if req.turnover_amount is not None else None,
        peer_spreads=req.peer_spreads,
        peer_depths=req.peer_depths,
        peer_turnovers=req.peer_turnovers
    )
    s_avail, _ = compute_data_availability_score(
        spread_coverage=req.spread_coverage,
        depth_coverage=req.depth_coverage,
        turnover_coverage=req.turnover_coverage
    )
    res = compute_composite_liquidity_score(
        spread_subscore=subscores["spread_subscore"],
        depth_subscore=subscores["depth_subscore"],
        turnover_subscore=subscores["turnover_subscore"],
        availability_subscore=s_avail,
        weights=req.weights,
        actual_spread_cov=req.spread_coverage,
        actual_depth_cov=req.depth_coverage,
        actual_turnover_cov=req.turnover_coverage
    )
    return LiquidityScoreResponse(
        instrument_id=req.instrument_id,
        as_of_timestamp=datetime.now(timezone.utc),
        composite_liquidity_score=res["composite_score"],
        scoring_status=res["status"],
        status_reason=res["reason"],
        spread_subscore=res["spread_subscore"],
        depth_subscore=res["depth_subscore"],
        turnover_subscore=res["turnover_subscore"],
        availability_subscore=res["availability_subscore"],
        spread_contribution=res["spread_contribution"],
        depth_contribution=res["depth_contribution"],
        turnover_contribution=res["turnover_contribution"],
        availability_contribution=res["availability_contribution"],
        spread_raw_value=req.spread_bps,
        depth_raw_value=req.depth_notional,
        turnover_raw_value=req.turnover_amount,
        currency=req.currency
    )


# 2. Configurations
@router.post("/configs/metrics", response_model=MetricConfigResponse, summary="Create metric configuration")
async def create_metric_config(req: MetricConfigRequest, db: AsyncSession = Depends(get_db)):
    srv = LiquidityEstimationService(db)
    cfg = await srv.create_metric_config(req.model_dump())
    return MetricConfigResponse.model_validate(cfg)


@router.post("/configs/scoring-profiles", response_model=ScoreProfileResponse, summary="Create scoring profile")
async def create_scoring_profile(req: ScoreProfileRequest, db: AsyncSession = Depends(get_db)):
    srv = LiquidityEstimationService(db)
    cfg = await srv.create_score_profile(req.model_dump())
    return ScoreProfileResponse.model_validate(cfg)


@router.post("/configs/bucket-policies", response_model=BucketPolicyResponse, summary="Create bucket policy")
async def create_bucket_policy(req: BucketPolicyRequest, db: AsyncSession = Depends(get_db)):
    srv = LiquidityEstimationService(db)
    pol = await srv.create_bucket_policy(req.model_dump())
    return BucketPolicyResponse.model_validate(pol)


# 3. Aggregations (Volume & Turnover)
@router.post("/trades/aggregate", summary="Aggregate trades into volume and turnover records")
async def aggregate_trades(
    instrument_id: str,
    exchange: str = "NSE",
    venue: str = "NSE_CASH",
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    currency: str = "USD",
    direct_trades: Optional[List[DirectTradeInput]] = None,
    db: AsyncSession = Depends(get_db)
):
    srv = LiquidityEstimationService(db)
    raw_trades = [t.model_dump() for t in direct_trades] if direct_trades else None
    vol, tov = await srv.aggregate_trades(
        instrument_id=instrument_id,
        exchange=exchange,
        venue=venue,
        start_time=start_time,
        end_time=end_time,
        currency=currency,
        direct_trades=raw_trades
    )
    return {
        "volume": VolumeAggregateResponse.model_validate(vol),
        "turnover": TurnoverAggregateResponse.model_validate(tov)
    }


# 4. Rolling Statistics
@router.post("/statistics/rolling", response_model=RollingStatisticsResponse, summary="Compute rolling volume and turnover statistics")
async def compute_rolling_stats(
    instrument_id: str,
    venue: str = "NSE_CASH",
    as_of: datetime = Query(default_factory=lambda: datetime.now(timezone.utc)),
    lookback_sessions: int = 20,
    currency: str = "USD",
    db: AsyncSession = Depends(get_db)
):
    srv = LiquidityEstimationService(db)
    stats = await srv.compute_rolling_statistics(
        instrument_id=instrument_id,
        venue=venue,
        as_of=as_of,
        lookback_sessions=lookback_sessions,
        currency=currency
    )
    return RollingStatisticsResponse.model_validate(stats)


# 5. Evaluate Composite Score & Bucket
@router.post("/evaluate", summary="Evaluate and persist composite liquidity score and bucket")
async def evaluate_liquidity(
    instrument_id: str,
    exchange: str = "NSE",
    venue: str = "NSE_CASH",
    as_of: datetime = Query(default_factory=lambda: datetime.now(timezone.utc)),
    score_config_code: str = "DEFAULT_SCORE_PROFILE",
    bucket_policy_code: str = "DEFAULT_BUCKET_POLICY",
    currency: str = "USD",
    spread_bps: Optional[float] = None,
    depth_notional: Optional[Decimal] = None,
    turnover_amount: Optional[Decimal] = None,
    peer_spreads: Optional[List[float]] = None,
    peer_depths: Optional[List[float]] = None,
    peer_turnovers: Optional[List[float]] = None,
    db: AsyncSession = Depends(get_db)
):
    srv = LiquidityEstimationService(db)
    score_snap, bucket_snap = await srv.evaluate_liquidity_score_and_bucket(
        instrument_id=instrument_id,
        exchange=exchange,
        venue=venue,
        as_of=as_of,
        score_config_code=score_config_code,
        bucket_policy_code=bucket_policy_code,
        currency=currency,
        override_spread_bps=spread_bps,
        override_depth_notional=depth_notional,
        override_turnover=turnover_amount,
        override_peer_spreads=peer_spreads,
        override_peer_depths=peer_depths,
        override_peer_turnovers=peer_turnovers
    )
    return {
        "score": LiquidityScoreResponse.model_validate(score_snap),
        "bucket": LiquidityBucketResponse.model_validate(bucket_snap)
    }


# 6. Current Liquidity Overview
@router.get("/{instrument_id}/current", response_model=LiquidityOverviewResponse, summary="Get current liquidity overview")
async def get_current_overview(
    instrument_id: str,
    exchange: str = "NSE",
    venue: str = "NSE_CASH",
    currency: str = "USD",
    db: AsyncSession = Depends(get_db)
):
    srv = LiquidityEstimationService(db)
    score_snap = await srv.repo.get_latest_score_snapshot(instrument_id)
    bucket_snap = await srv.repo.get_latest_bucket_snapshot(instrument_id)
    rolling_stat = await srv.repo.get_latest_rolling_statistics(instrument_id)

    return LiquidityOverviewResponse(
        instrument_id=instrument_id,
        exchange=exchange,
        venue=venue,
        currency=currency,
        current_traded_volume=score_snap.turnover_raw_value if score_snap else None,
        current_turnover=score_snap.turnover_raw_value if score_snap else None,
        average_daily_volume=rolling_stat.average_daily_volume if rolling_stat else None,
        average_daily_turnover=rolling_stat.average_daily_turnover if rolling_stat else None,
        spread_bps=score_snap.spread_raw_value if score_snap else None,
        depth_notional=score_snap.depth_raw_value if score_snap else None,
        composite_score=score_snap.composite_liquidity_score if score_snap else None,
        liquidity_bucket=bucket_snap.bucket_name if bucket_snap else "INSUFFICIENT_DATA",
        scoring_status=score_snap.scoring_status if score_snap else "INSUFFICIENT_DATA",
        as_of_timestamp=score_snap.as_of_timestamp if score_snap else datetime.now(timezone.utc)
    )


# 7. Screening API
@router.post("/screen", summary="Screen instruments by liquidity metrics and score")
async def screen_instruments(req: LiquidityScreenRequest, db: AsyncSession = Depends(get_db)):
    srv = LiquidityEstimationService(db)
    results = await srv.repo.screen_instruments(
        min_score=req.min_score,
        max_score=req.max_score,
        bucket=req.bucket,
        limit=req.limit,
        offset=req.offset
    )
    return {
        "count": len(results),
        "results": results,
        "filters": req.model_dump()
    }

