"""
Integration tests for M09.07 Position Liquidation.
Verifies:
1. Long liquidation (SELL) and short covering (BUY) side determination and target creation
2. Target decomposition: cumulative vs incremental quantities and remaining positions
3. Horizon estimation and schedule simulation across participation rates and schedule types
4. Reconciled cost decomposition (spread, depth concession, impact, slippage, fees, opportunity cost)
5. Partial liquidation comparison (10%, 25%, 50%, 75%, 90%, 100%)
6. Portfolio-level concurrent (critical-path duration) vs sequential liquidation
7. Historical calibration recording and retrieval
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.market_microstructure.position_liquidation.calculations.liquidation_math import (
    IntervalProfile,
    PositionLiquidationMath,
)


def test_position_liquidation_math_side_and_targets():
    # Long position (SELL)
    side, abs_qty = PositionLiquidationMath.determine_liquidation_side(Decimal("10000.0"))
    assert side == "SELL"
    assert abs_qty == Decimal("10000.0")

    # Short position (BUY)
    side_short, abs_short = PositionLiquidationMath.determine_liquidation_side(Decimal("-5000.0"))
    assert side_short == "BUY"
    assert abs_short == Decimal("5000.0")

    # Default targets: 10%, 25%, 50%, 75%, 90%, 100%
    targets = PositionLiquidationMath.build_reduction_targets(abs_qty)
    assert len(targets) == 6
    assert targets[0].target_percentage == Decimal("0.10")
    assert targets[0].cumulative_target_quantity == Decimal("1000.0")
    assert targets[0].incremental_target_quantity == Decimal("1000.0")
    assert targets[0].remaining_quantity == Decimal("9000.0")

    assert targets[1].target_percentage == Decimal("0.25")
    assert targets[1].cumulative_target_quantity == Decimal("2500.0")
    assert targets[1].incremental_target_quantity == Decimal("1500.0")
    assert targets[1].remaining_quantity == Decimal("7500.0")

    assert targets[-1].target_percentage == Decimal("1.00")
    assert targets[-1].cumulative_target_quantity == Decimal("10000.0")
    assert targets[-1].remaining_quantity == Decimal("0.0")


def test_schedule_simulation_and_cost_reconciliation():
    base_time = datetime.now(timezone.utc)
    # 20 intervals of 10,000 volume each -> Total volume = 200,000
    intervals = [
        IntervalProfile(
            interval_index=i,
            interval_start=base_time + timedelta(minutes=5 * (i - 1)),
            interval_end=base_time + timedelta(minutes=5 * i),
            expected_volume=Decimal("10000.0"),
            session_index=1,
        )
        for i in range(1, 21)
    ]

    target_qty = Decimal("5000.0")
    participation = Decimal("0.10")  # 10% -> 1,000 per interval cap

    # At 1,000 per interval, 5,000 takes exactly 5 intervals
    schedule, residual, completion_ts, status = PositionLiquidationMath.simulate_schedule(
        target_quantity=target_qty,
        intervals=intervals,
        participation_rate=participation,
        schedule_type="PARTICIPATION_CAPPED",
        reference_price=Decimal("150.0"),
        side="SELL",
        spread=Decimal("0.04"),
    )

    assert len(schedule) == 5
    assert residual == Decimal("0.0")
    assert status == "FULLY_LIQUIDATED_ESTIMATED"
    assert completion_ts is not None

    costs = PositionLiquidationMath.calculate_cost_decomposition(
        liquidated_qty=target_qty,
        target_qty=target_qty,
        residual_qty=residual,
        reference_price=Decimal("150.0"),
        spread=Decimal("0.04"),
        side="SELL",
        avg_participation=participation,
    )

    assert costs["total_cost"] > Decimal("0.0")
    assert costs["spread_cost"] == target_qty * Decimal("0.02")  # 5,000 * 0.02 = 100.0
    assert costs["opportunity_cost"] == Decimal("0.0")  # Fully executed


@pytest.mark.asyncio
async def test_create_and_get_liquidation_plan_api():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_body = {
            "plan_name": "AAPL Position Exit Plan",
            "portfolio_id": "PORT-GROWTH-01",
            "position_id": "POS-AAPL-100",
            "instrument_id": "INST-AAPL",
            "venue_id": "XNAS",
            "starting_signed_quantity": 8000,
            "benchmark_price": 180.0,
            "benchmark_type": "MIDPOINT",
            "spread": 0.05,
            "maximum_participation_rate": 0.10,
            "execution_schedule": "PARTICIPATION_CAPPED",
        }
        resp = await ac.post("/api/v1/market-microstructure/liquidation/plans", json=req_body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["liquidation_side"] == "SELL"
        assert len(data["targets"]) == 6
        assert len(data["horizon_results"]) == 6
        assert len(data["cost_results"]) == 6

        plan_id = data["plan_id"]

        # Fetch plan by ID
        get_resp = await ac.get(f"/api/v1/market-microstructure/liquidation/plans/{plan_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["plan_id"] == plan_id
        assert Decimal(str(get_data["starting_absolute_quantity"])) == Decimal("8000")


@pytest.mark.asyncio
async def test_partial_comparison_endpoint():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_body = {
            "plan_name": "TSLA Short Cover Plan",
            "portfolio_id": "PORT-TECH-02",
            "position_id": "POS-TSLA-200",
            "instrument_id": "INST-TSLA",
            "starting_signed_quantity": -3000,
            "benchmark_price": 220.0,
            "spread": 0.10,
            "maximum_participation_rate": 0.15,
        }
        resp = await ac.post("/api/v1/market-microstructure/liquidation/plans", json=req_body)
        assert resp.status_code == 201
        plan_id = resp.json()["plan_id"]
        assert resp.json()["liquidation_side"] == "BUY"

        comp_resp = await ac.get(f"/api/v1/market-microstructure/liquidation/plans/{plan_id}/partial-comparison")
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert comp_data["liquidation_side"] == "BUY"
        assert len(comp_data["targets"]) == 6
        assert comp_data["targets"][0]["percentage"] == 10.0
        assert comp_data["targets"][-1]["percentage"] == 100.0
        # Check incremental vs cumulative cost monotonic behavior
        prev_cost = 0.0
        for tgt in comp_data["targets"]:
            assert tgt["cumulative_cost"] >= prev_cost
            prev_cost = tgt["cumulative_cost"]


@pytest.mark.asyncio
async def test_portfolio_liquidation_concurrent_vs_sequential():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        positions = [
            {"instrument_id": "INST-MSFT", "quantity": 10000, "price": 400.0, "spread": 0.05},
            {"instrument_id": "INST-AMZN", "quantity": -5000, "price": 180.0, "spread": 0.04},
        ]

        # Test CONCURRENT (Critical Path duration)
        req_concurrent = {
            "portfolio_id": "PORT-GLOBAL-ALPHA",
            "schedule_mode": "CONCURRENT",
            "participation_rate": 0.10,
            "positions": positions,
        }
        resp_c = await ac.post("/api/v1/market-microstructure/liquidation/portfolio", json=req_concurrent)
        assert resp_c.status_code == 200
        data_c = resp_c.json()
        assert data_c["position_count"] == 2
        assert float(data_c["long_liquidation_cost"]) > 0
        assert float(data_c["short_covering_cost"]) > 0
        assert data_c["portfolio_duration_seconds"] == data_c["critical_path_duration_seconds"]

        # Test SEQUENTIAL (Sum of durations)
        req_sequential = {
            "portfolio_id": "PORT-GLOBAL-ALPHA",
            "schedule_mode": "SEQUENTIAL",
            "participation_rate": 0.10,
            "positions": positions,
        }
        resp_s = await ac.post("/api/v1/market-microstructure/liquidation/portfolio", json=req_sequential)
        assert resp_s.status_code == 200
        data_s = resp_s.json()
        assert data_s["portfolio_duration_seconds"] >= data_c["portfolio_duration_seconds"]


@pytest.mark.asyncio
async def test_historical_model_calibration_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        now = datetime.now(timezone.utc)
        calib_req = {
            "model_id": "MODEL-ALMGREN-CHRISS-LIQ",
            "model_version": "v1.2.0",
            "calibration_start": (now - timedelta(days=90)).isoformat(),
            "calibration_end": now.isoformat(),
            "training_sample_count": 1250,
            "duration_mae_seconds": 185.5,
            "duration_rmse_seconds": 240.2,
            "cost_mae_bps": 2.35,
            "cost_rmse_bps": 3.82,
            "prediction_bias_bps": 0.15,
        }
        post_resp = await ac.post("/api/v1/market-microstructure/liquidation/calibrations", json=calib_req)
        assert post_resp.status_code == 201
        data = post_resp.json()
        assert data["model_id"] == "MODEL-ALMGREN-CHRISS-LIQ"
        assert data["validation_status"] == "VALIDATED"

        list_resp = await ac.get("/api/v1/market-microstructure/liquidation/calibrations")
        assert list_resp.status_code == 200
        runs = list_resp.json()
        assert len(runs) >= 1
        assert any(r["model_id"] == "MODEL-ALMGREN-CHRISS-LIQ" for r in runs)
