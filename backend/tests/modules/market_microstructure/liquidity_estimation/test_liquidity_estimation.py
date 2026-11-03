"""
M09.03 Liquidity Estimation - Comprehensive Test Suite.
Verifies:
1. Hand-calculated trade volume and turnover summation, cancellation exclusion, duplicate prevention.
2. Rolling statistics (ADV, ADTV, CV, percentiles, intraday pace).
3. Component subscores (spread inverse rank, depth rank, turnover rank) and availability score.
4. Composite liquidity score with hard coverage gates and contribution weights.
5. Liquidity bucket classification (score thresholds, relative percentiles, insufficient data status).
6. End-to-end FastAPI endpoint lifecycle.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.modules.market_microstructure.liquidity_estimation.calculations.liquidity_math import (
    compute_traded_volume_and_turnover,
    compute_series_statistics,
    compute_intraday_pace,
    compute_percentile_rank,
    compute_subscores,
    compute_data_availability_score,
    compute_composite_liquidity_score,
    classify_liquidity_bucket,
)


def test_hand_calculated_volume_and_turnover():
    """
    Test Section 5.2 & 7.1 hand-calculated trade volume and turnover:
    Trade 1: Price 100.00, Qty 500  -> Val = 50,000
    Trade 2: Price 100.20, Qty 700  -> Val = 70,140
    Trade 3: Price 100.15, Qty 300  -> Val = 30,045
    Trade 4: Price 100.30, Qty 900  -> Val = 90,270
    Trade 5: Canceled trade (Price 105.00, Qty 1000) -> should be excluded!
    Trade 6: Duplicate of Trade 1 -> should be deduplicated!
    Total Volume = 500 + 700 + 300 + 900 = 2,400
    Total Turnover = 50,000 + 70,140 + 30,045 + 90,270 = 240,455.00
    """
    trades = [
        {"trade_id": "T1", "price": "100.00", "quantity": "500", "status": "ACTIVE"},
        {"trade_id": "T2", "price": "100.20", "quantity": "700", "status": "ACTIVE"},
        {"trade_id": "T3", "price": "100.15", "quantity": "300", "status": "ACTIVE"},
        {"trade_id": "T4", "price": "100.30", "quantity": "900", "status": "ACTIVE"},
        {"trade_id": "T5", "price": "105.00", "quantity": "1000", "status": "CANCELED"},
        {"trade_id": "T1", "price": "100.00", "quantity": "500", "status": "ACTIVE"},  # duplicate
    ]
    res = compute_traded_volume_and_turnover(trades, instrument_multiplier=Decimal("1.0"))
    assert res["eligible_trade_count"] == 4
    assert res["traded_volume"] == Decimal("2400.0")
    assert res["turnover"] == Decimal("240455.00")


def test_series_statistics_and_pace():
    """
    Verifies mean, median, stddev, cv, and percentiles for daily volumes.
    Sample: [1000, 2000, 3000, 4000, 5000]
    Mean = 3000
    Median = 3000
    StdDev (sample ddof=1) = 1581.13883
    CV = 1581.13883 / 3000 = 0.527046
    """
    vols = [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]
    stats = compute_series_statistics(vols)
    assert stats["mean"] == 3000.0
    assert stats["median"] == 3000.0
    assert pytest.approx(stats["std_dev"], rel=1e-3) == 1581.1388
    assert pytest.approx(stats["cv"], rel=1e-3) == 0.5270
    assert stats["min"] == 1000.0
    assert stats["max"] == 5000.0
    assert stats["p50"] == 3000.0

    # Intraday Pace
    # Current cum = 2500, historical at same time = [2000, 2500, 3000] -> median = 2500 -> pace = 1.0
    pace = compute_intraday_pace(2500.0, [2000.0, 2500.0, 3000.0])
    assert pace == 1.0
    pace_high = compute_intraday_pace(5000.0, [2000.0, 2500.0, 3000.0])
    assert pace_high == 2.0


def test_percentile_rank_and_subscores():
    """
    Test percentile rank and subscore directions:
    Lower spread gives higher subscore: S_spread = 100 - PR(Spread)
    Higher depth gives higher subscore: S_depth = PR(Depth)
    Higher turnover gives higher subscore: S_turnover = PR(Turnover)
    """
    peer_spreads = [5.0, 10.0, 15.0, 20.0, 25.0]  # bps
    peer_depths = [100000.0, 200000.0, 300000.0, 400000.0, 500000.0]  # notional
    peer_turnovers = [1000000.0, 2000000.0, 3000000.0, 4000000.0, 5000000.0]

    subscores = compute_subscores(
        spread_bps=5.0,  # lowest spread -> PR=10% -> S_spread = 90%
        depth_notional=500000.0,  # highest depth -> PR=90% -> S_depth = 90%
        turnover_val=5000000.0,  # highest turnover -> PR=90% -> S_turnover = 90%
        peer_spreads=peer_spreads,
        peer_depths=peer_depths,
        peer_turnovers=peer_turnovers
    )

    assert subscores["spread_subscore"] == 90.0
    assert subscores["depth_subscore"] == 90.0
    assert subscores["turnover_subscore"] == 90.0


def test_composite_liquidity_score_and_eligibility():
    """
    Test composite liquidity score calculation:
    w_s=0.25, w_d=0.30, w_t=0.30, w_a=0.15
    S_spread = 80.0 -> contrib = 20.0
    S_depth = 70.0  -> contrib = 21.0
    S_turnover = 90.0 -> contrib = 27.0
    S_avail = 100.0 -> contrib = 15.0
    Total score = 20.0 + 21.0 + 27.0 + 15.0 = 83.0
    """
    s_avail, _ = compute_data_availability_score(1.0, 1.0, 1.0)
    assert s_avail == 100.0

    weights = {"spread_weight": 0.25, "depth_weight": 0.30, "turnover_weight": 0.30, "availability_weight": 0.15}
    score_eval = compute_composite_liquidity_score(
        spread_subscore=80.0,
        depth_subscore=70.0,
        turnover_subscore=90.0,
        availability_subscore=s_avail,
        weights=weights,
        actual_spread_cov=1.0,
        actual_depth_cov=1.0,
        actual_turnover_cov=1.0
    )
    assert score_eval["status"] == "ACTIVE"
    assert score_eval["composite_score"] == 83.0
    assert score_eval["spread_contribution"] == 20.0
    assert score_eval["depth_contribution"] == 21.0
    assert score_eval["turnover_contribution"] == 27.0
    assert score_eval["availability_contribution"] == 15.0

    # Gate failure: missing turnover or insufficient coverage
    bad_eval = compute_composite_liquidity_score(
        spread_subscore=80.0,
        depth_subscore=70.0,
        turnover_subscore=None,
        availability_subscore=s_avail,
        weights=weights,
        actual_spread_cov=1.0,
        actual_depth_cov=1.0,
        actual_turnover_cov=0.2  # fails min coverage 0.50
    )
    assert bad_eval["status"] == "INSUFFICIENT_DATA"
    assert bad_eval["composite_score"] is None


def test_bucket_classification():
    """
    Test bucket classification:
    Score 85.0 -> VERY_HIGH_LIQUIDITY (rank 1)
    Score 65.0 -> HIGH_LIQUIDITY (rank 2)
    Score 45.0 -> MODERATE_LIQUIDITY (rank 3)
    Score 25.0 -> LOW_LIQUIDITY (rank 4)
    Score 15.0 -> VERY_LOW_LIQUIDITY (rank 5)
    None (Insufficient data) -> INSUFFICIENT_DATA (rank 6)
    """
    b1 = classify_liquidity_bucket(85.0, "ACTIVE")
    assert b1["bucket_name"] == "VERY_HIGH_LIQUIDITY"
    assert b1["bucket_rank"] == 1

    b2 = classify_liquidity_bucket(65.0, "ACTIVE")
    assert b2["bucket_name"] == "HIGH_LIQUIDITY"
    assert b2["bucket_rank"] == 2

    b3 = classify_liquidity_bucket(45.0, "ACTIVE")
    assert b3["bucket_name"] == "MODERATE_LIQUIDITY"
    assert b3["bucket_rank"] == 3

    b4 = classify_liquidity_bucket(25.0, "ACTIVE")
    assert b4["bucket_name"] == "LOW_LIQUIDITY"
    assert b4["bucket_rank"] == 4

    b5 = classify_liquidity_bucket(15.0, "ACTIVE")
    assert b5["bucket_name"] == "VERY_LOW_LIQUIDITY"
    assert b5["bucket_rank"] == 5

    b6 = classify_liquidity_bucket(None, "INSUFFICIENT_DATA")
    assert b6["bucket_name"] == "INSUFFICIENT_DATA"
    assert b6["bucket_rank"] == 6


@pytest.mark.asyncio
async def test_liquidity_estimation_api_lifecycle():
    """
    Full lifecycle test of M09.03 Liquidity Estimation endpoints:
    1. Direct calculation endpoint
    2. Create metric and score configurations
    3. Aggregate trades into volume and turnover
    4. Compute rolling statistics
    5. Evaluate score and bucket
    6. Fetch current overview
    7. Screen instruments
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Direct calculate
        calc_payload = {
            "instrument_id": "EQ_INFY_NSE",
            "exchange": "NSE",
            "venue": "NSE_CASH",
            "currency": "INR",
            "spread_bps": 2.5,
            "depth_notional": 5000000.0,
            "turnover_amount": 25000000.0,
            "spread_coverage": 1.0,
            "depth_coverage": 1.0,
            "turnover_coverage": 1.0,
            "peer_spreads": [1.0, 2.5, 5.0, 10.0],
            "peer_depths": [1000000.0, 3000000.0, 5000000.0, 8000000.0],
            "peer_turnovers": [10000000.0, 20000000.0, 25000000.0, 50000000.0]
        }
        res_calc = await client.post("/api/v1/market-microstructure/liquidity/calculate", json=calc_payload)
        assert res_calc.status_code == 200
        calc_data = res_calc.json()
        assert calc_data["scoring_status"] == "ACTIVE"
        assert calc_data["composite_liquidity_score"] is not None

        # 2. Configs
        res_cfg = await client.post(
            "/api/v1/market-microstructure/liquidity/configs/metrics",
            json={
                "config_code": "CFG_LIQ_TEST_01",
                "name": "Test Metric Policy",
                "market": "NSE",
                "currency": "INR"
            }
        )
        assert res_cfg.status_code == 200

        # 3. Aggregate trades
        res_agg = await client.post(
            "/api/v1/market-microstructure/liquidity/trades/aggregate",
            params={
                "instrument_id": "EQ_INFY_NSE",
                "exchange": "NSE",
                "venue": "NSE_CASH",
                "start_time": "2026-11-03T09:15:00Z",
                "end_time": "2026-11-03T10:15:00Z",
                "currency": "INR"
            },
            json=[
                {"trade_id": "TR_001", "price": 1500.0, "quantity": 100, "timestamp": "2026-11-03T09:20:00Z", "status": "ACTIVE"},
                {"trade_id": "TR_002", "price": 1502.5, "quantity": 200, "timestamp": "2026-11-03T09:25:00Z", "status": "ACTIVE"}
            ]
        )
        assert res_agg.status_code == 200
        agg_data = res_agg.json()
        assert Decimal(str(agg_data["volume"]["traded_volume"])) == Decimal("300.0")

        # 4. Compute rolling stats
        res_stats = await client.post(
            "/api/v1/market-microstructure/liquidity/statistics/rolling",
            params={
                "instrument_id": "EQ_INFY_NSE",
                "venue": "NSE_CASH",
                "as_of": "2026-11-03T11:00:00Z",
                "lookback_sessions": 5,
                "currency": "INR"
            }
        )
        assert res_stats.status_code == 200
        assert res_stats.json()["eligible_session_count"] >= 1

        # 5. Evaluate score and bucket
        res_eval = await client.post(
            "/api/v1/market-microstructure/liquidity/evaluate",
            params={
                "instrument_id": "EQ_INFY_NSE",
                "exchange": "NSE",
                "venue": "NSE_CASH",
                "currency": "INR",
                "spread_bps": 3.0,
                "depth_notional": 2000000.0,
                "turnover_amount": 10000000.0
            }
        )
        assert res_eval.status_code == 200
        eval_data = res_eval.json()
        assert eval_data["score"]["composite_liquidity_score"] is not None
        assert eval_data["bucket"]["bucket_name"] in [
            "VERY_HIGH_LIQUIDITY", "HIGH_LIQUIDITY", "MODERATE_LIQUIDITY", "LOW_LIQUIDITY", "VERY_LOW_LIQUIDITY"
        ]

        # 6. Current overview
        res_cur = await client.get("/api/v1/market-microstructure/liquidity/EQ_INFY_NSE/current")
        assert res_cur.status_code == 200
        assert res_cur.json()["instrument_id"] == "EQ_INFY_NSE"

        # 7. Screen instruments
        res_screen = await client.post(
            "/api/v1/market-microstructure/liquidity/screen",
            json={"min_score": 10.0, "limit": 10}
        )
        assert res_screen.status_code == 200
        assert "results" in res_screen.json()
