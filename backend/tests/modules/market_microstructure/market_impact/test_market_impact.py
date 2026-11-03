"""
M09.04 Market Impact - Comprehensive Test Suite.
Verifies:
1. Section 7.2 Hand-Calculated Buy-Side Depth Walk:
   - Levels: Ask 1 (100.05, 500), Ask 2 (100.10, 700), Ask 3 (100.15, 1000), Ask 4 (100.20, 1200)
   - Proposed Qty: 1500
   - Consumed: 500 @ 100.05 + 700 @ 100.10 + 300 @ 100.15 = 1500, Value = 150,140.00
   - Avg Price = 150,140 / 1500 = 100.093333...
   - Marginal Price = 100.15
2. Sell-Side Depth Walk & Partial Incomplete Depth (Residual Unfilled Qty):
   - When requested size exceeds visible liquidity, residual > 0.
3. Order-Size Sensitivity & Marginal Cost Increments:
   - MarginalCost(Q1, Q2) = (Cost(Q2) - Cost(Q1)) / (Q2 - Q1).
4. Participation Rate Constraint & Horizon Schedule Generation.
5. Empirical Impact Models:
   - Square-Root Impact: I_bps = Y * sigma_H * sqrt(Q / V_H) * 10,000
   - Log-Linear Empirical Regression & Kyle OFI model.
6. Full FastAPI End-to-End API Lifecycle.
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.modules.market_microstructure.market_impact.calculations.impact_math import (
    simulate_depth_walk,
    compute_order_size_sensitivity,
    compute_participation_cap,
    compute_execution_schedule,
    compute_square_root_impact,
    compute_empirical_regression_impact,
    compute_kyle_order_flow_impact,
)


def test_hand_calculated_buy_side_depth_walk():
    """
    Verifies Section 7.2 hand-calculated buy-side depth walk:
    Ask Level 1: 100.05, Qty 500
    Ask Level 2: 100.10, Qty 700
    Ask Level 3: 100.15, Qty 1000
    Ask Level 4: 100.20, Qty 1200
    Proposed Buy Qty: 1500
    Consumes:
    - 500 @ 100.05 = 50,025
    - 700 @ 100.10 = 70,070
    - 300 @ 100.15 = 30,045
    Total Executed Value = 150,140
    Average Execution Price = 150,140 / 1,500 = 100.0933333333333333333333333
    Marginal Execution Price = 100.15
    """
    levels = [
        {"price": "100.05", "quantity": "500"},
        {"price": "100.10", "quantity": "700"},
        {"price": "100.15", "quantity": "1000"},
        {"price": "100.20", "quantity": "1200"},
    ]
    ref_midpoint = Decimal("100.025")  # hypothetical midpoint
    res = simulate_depth_walk(
        side="BUY",
        proposed_quantity=Decimal("1500"),
        levels=levels,
        reference_price=ref_midpoint,
        instrument_multiplier=Decimal("1.0")
    )

    assert res["visible_fill_quantity"] == Decimal("1500")
    assert res["residual_unfilled_quantity"] == Decimal("0")
    assert res["fill_percentage"] == 100.0
    assert res["gross_execution_value"] == Decimal("150140.00")
    assert res["marginal_execution_price"] == Decimal("100.15")
    assert pytest.approx(float(res["average_execution_price"]), rel=1e-5) == 100.093333

    # Cost amount = 1500 * (100.093333 - 100.025)
    expected_cost = Decimal("150140.00") - (Decimal("1500") * ref_midpoint)
    assert res["estimated_cost_amount"] == expected_cost
    assert len(res["consumed_levels"]) == 3


def test_sell_side_depth_walk_and_residual_unfilled():
    """
    Tests sell-side order depth walk and exhaustion of visible liquidity:
    Bid Level 1: 99.95, Qty 400
    Bid Level 2: 99.90, Qty 600
    Total visible bid liquidity = 1000
    Proposed Sell Qty: 1500
    Expected:
    - Visible fill = 1000
    - Residual unfilled = 500
    - Fill % = 66.6667%
    - Consumes 400 @ 99.95 (39,980) + 600 @ 99.90 (59,940) = 99,920
    - Avg Execution Price = 99,920 / 1000 = 99.92
    - Marginal Price = 99.90
    """
    levels = [
        {"price": "99.95", "quantity": "400"},
        {"price": "99.90", "quantity": "600"},
    ]
    ref_midpoint = Decimal("100.00")
    res = simulate_depth_walk(
        side="SELL",
        proposed_quantity=Decimal("1500"),
        levels=levels,
        reference_price=ref_midpoint
    )

    assert res["visible_fill_quantity"] == Decimal("1000")
    assert res["residual_unfilled_quantity"] == Decimal("500")
    assert pytest.approx(res["fill_percentage"], rel=1e-3) == 66.6667
    assert res["gross_execution_value"] == Decimal("99920.00")
    assert res["average_execution_price"] == Decimal("99.92")
    assert res["marginal_execution_price"] == Decimal("99.90")


def test_order_size_sensitivity_and_marginal_cost():
    """
    Tests order size sensitivity and marginal cost between increments:
    Levels: Ask 1 (100.05, 500), Ask 2 (100.10, 700)
    Sizes: [500, 1000]
    At 500: cost = 500 * (100.05 - 100.00) = 25.0
    At 1000: cost = 500 * 0.05 + 500 * 0.10 = 25.0 + 50.0 = 75.0
    Marginal cost between 500 and 1000 = (75.0 - 25.0) / 500 = 50.0 / 500 = 0.10 per unit!
    """
    levels = [
        {"price": "100.05", "quantity": "500"},
        {"price": "100.10", "quantity": "700"},
    ]
    sizes = [Decimal("500"), Decimal("1000")]
    res = compute_order_size_sensitivity(
        side="BUY",
        sizes=sizes,
        levels=levels,
        reference_price=Decimal("100.00")
    )
    assert len(res) == 2
    assert res[0]["estimated_cost_amount"] == Decimal("25.00")
    assert res[1]["estimated_cost_amount"] == Decimal("75.00")
    assert pytest.approx(res[1]["marginal_incremental_unit_cost"], rel=1e-4) == 0.10


def test_participation_cap_and_execution_schedules():
    """
    Tests participation rate caps and uniform / volume-proportional schedule slicing.
    """
    # 1. Participation cap
    # Proposed: 2000, Market Vol: 10,000, Max PR: 10% -> Max Fillable = 1000, Residual = 1000
    p_cap = compute_participation_cap(
        proposed_quantity=Decimal("2000"),
        expected_market_volume=Decimal("10000"),
        max_participation_rate=0.10
    )
    assert p_cap["expected_fillable_quantity"] == Decimal("1000.00")
    assert p_cap["residual_quantity"] == Decimal("1000.00")
    assert p_cap["is_volume_constrained"] is True

    # 2. Execution schedule
    # Uniform 3 slices of 900 -> [300, 300, 300]
    sched_uni = compute_execution_schedule(Decimal("900"), 3, schedule_type="UNIFORM")
    assert sched_uni == [Decimal("300"), Decimal("300"), Decimal("300")]

    # Volume proportional profile [100, 200, 300] (sum 600) -> 900 * [1/6, 2/6, 3/6] = [150, 300, 450]
    sched_vol = compute_execution_schedule(Decimal("900"), 3, schedule_type="VOLUME_PROPORTIONAL", volume_profile=[100, 200, 300])
    assert sched_vol == [Decimal("150"), Decimal("300"), Decimal("450")]


def test_empirical_impact_models():
    """
    Tests Square-Root impact law, Log-Linear regression, and Kyle OFI model.
    """
    # 1. Square-Root Impact:
    # Q = 10,000, V_H = 1,000,000 -> PR = 0.01 -> sqrt(0.01) = 0.1
    # sigma_H = 0.02 (2%), Y = 0.50
    # I_bps = 0.50 * 0.02 * 0.1 * 10,000 = 10.0 bps
    sq_res = compute_square_root_impact(
        order_quantity=10000.0,
        expected_horizon_volume=1000000.0,
        horizon_volatility=0.02,
        impact_coefficient_y=0.50
    )
    assert sq_res["status"] == "VALID"
    assert sq_res["impact_bps"] == 10.0
    assert sq_res["standard_error_bps"] == 2.0  # 20% of 10.0
    assert sq_res["prediction_lower_bps"] == pytest.approx(10.0 - 1.96 * 2.0, rel=1e-3)
    assert sq_res["prediction_upper_bps"] == pytest.approx(10.0 + 1.96 * 2.0, rel=1e-3)

    # 2. Kyle OFI Model:
    # Delta_P = lambda * OFI = 0.0002 * 50,000 = 10.0
    kyle_res = compute_kyle_order_flow_impact(signed_order_flow=50000.0, lambda_coefficient=0.0002)
    assert kyle_res["price_change"] == 10.0

    # 3. Empirical Regression:
    reg_res = compute_empirical_regression_impact(
        participation_rate=0.05,
        spread_bps=4.0,
        depth_notional=2000000.0,
        volatility=0.015
    )
    assert reg_res["status"] == "VALID"
    assert reg_res["impact_bps"] > 0.0
    assert reg_res["temporary_impact_bps"] + reg_res["permanent_impact_bps"] == pytest.approx(reg_res["impact_bps"], rel=1e-3)


@pytest.mark.asyncio
async def test_market_impact_api_lifecycle():
    """
    Full end-to-end API lifecycle test:
    1. Direct depth walk simulation
    2. Order-size sensitivity evaluation
    3. Empirical model prediction
    4. Config creation & scenario persistence
    5. Persistent depth walk execution
    6. Horizon comparison
    7. Validation run recording
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Direct Depth Walk
        dw_payload = {
            "side": "BUY",
            "proposed_quantity": 1000,
            "reference_price": 2500.0,
            "levels": [
                {"price": 2500.5, "quantity": 400},
                {"price": 2501.0, "quantity": 800}
            ]
        }
        res_dw = await client.post("/api/v1/market-microstructure/impact/depth-walk/simulate", json=dw_payload)
        assert res_dw.status_code == 200
        dw_data = res_dw.json()
        assert Decimal(str(dw_data["visible_fill_quantity"])) == Decimal("1000.0")
        assert dw_data["fill_percentage"] == 100.0

        # 2. Sensitivity
        sens_payload = {
            "side": "BUY",
            "sizes": [500, 1000, 1500],
            "reference_price": 2500.0,
            "levels": [
                {"price": 2500.5, "quantity": 800},
                {"price": 2501.0, "quantity": 800}
            ]
        }
        res_sens = await client.post("/api/v1/market-microstructure/impact/sensitivity", json=sens_payload)
        assert res_sens.status_code == 200
        assert res_sens.json()["scenarios_evaluated"] == 3

        # 3. Direct Predict
        pred_payload = {
            "model_type": "SQUARE_ROOT",
            "order_quantity": 5000,
            "expected_horizon_volume": 500000,
            "volatility": 0.02
        }
        res_pred = await client.post("/api/v1/market-microstructure/impact/predict", json=pred_payload)
        assert res_pred.status_code == 200
        assert res_pred.json()["impact_bps"] is not None

        # 4. Create Config & Scenario
        res_cfg = await client.post(
            "/api/v1/market-microstructure/impact/configs",
            json={"config_code": "CFG_IMP_TEST", "name": "Institutional Impact Policy"}
        )
        assert res_cfg.status_code == 200

        res_scen = await client.post(
            "/api/v1/market-microstructure/impact/scenarios",
            json={
                "instrument_id": "EQ_RELIANCE_NSE",
                "order_side": "BUY",
                "proposed_quantity": 1000,
                "reference_price": 2500.0
            }
        )
        assert res_scen.status_code == 200
        scen_id = res_scen.json()["scenario_id"]

        # 5. Execute Depth Walk for Scenario
        res_exec = await client.post(
            f"/api/v1/market-microstructure/impact/scenarios/{scen_id}/execute-depth-walk",
            json=[
                {"price": 2500.5, "quantity": 600},
                {"price": 2501.0, "quantity": 600}
            ]
        )
        assert res_exec.status_code == 200
        assert Decimal(str(res_exec.json()["visible_fill_quantity"])) == Decimal("1000.0")

        # 6. Horizon comparison
        res_hor = await client.post(
            "/api/v1/market-microstructure/impact/horizons/compare",
            params={
                "order_quantity": 10000,
                "daily_volume": 1000000,
                "daily_volatility": 0.02
            }
        )
        assert res_hor.status_code == 200
        assert res_hor.json()["horizons_evaluated"] == 5

        # 7. Validation run record
        res_val = await client.post(
            "/api/v1/market-microstructure/impact/validation/record",
            json={
                "model_code": "SQUARE_ROOT_DEFAULT",
                "sample_count": 250,
                "mae": 1.25,
                "rmse": 1.85,
                "mean_bias_error": 0.05,
                "interval_coverage_pct": 94.8
            }
        )
        assert res_val.status_code == 200
        assert res_val.json()["validation_status"] == "PASSED"
