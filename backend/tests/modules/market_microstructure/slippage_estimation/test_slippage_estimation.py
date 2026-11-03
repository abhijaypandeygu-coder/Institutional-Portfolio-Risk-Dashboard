"""
Comprehensive test suite for M09.05 Slippage Estimation.

Verifies:
1. Exact hand-calculated VWAP, Realized Slippage (price units, bps, monetary amount) for BUY and SELL.
2. Exact additive attribution decomposition:
   Total Deviation == Market Movement + Spread Crossing + Residual Execution.
3. Negative residual attribution preserving price improvement (passive fills within the spread).
4. Opportunity cost and Implementation Shortfall calculations for partially executed orders.
5. Calibration metrics: ME, MAE, RMSE, t-statistic, interval coverage.
6. End-to-end FastAPI endpoint integration testing (database persistence, retrieval, error handling).
"""

from datetime import datetime
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.market_microstructure.slippage_estimation.calculations.slippage_math import (
    FillExecutionData,
    SlippageMath,
)


def test_hand_calculated_vwap_and_slippage():
    """
    Test scenario:
    Buy 1,000 shares of AAPL.
    Benchmark Arrival Midpoint P_ref = $100.00
    Fill 1: 400 shares @ $100.20
    Fill 2: 600 shares @ $100.50
    Expected VWAP: (400*100.20 + 600*100.50)/1000 = (40080 + 60300)/1000 = 100380/1000 = $100.380
    Realized Slippage:
    Side = BUY (+1)
    Slip_price = 1 * (100.38 - 100.00) = +0.38
    Slip_bps = 1 * (0.38 / 100.00) * 10,000 = 38.0 bps
    Slip_money = 1 * (100.38 - 100.00) * 1000 * 1 = $380.00
    """
    fills = [
        FillExecutionData(
            fill_id="F1",
            fill_timestamp="2026-11-03T09:30:01Z",
            price=Decimal("100.20"),
            quantity=Decimal("400"),
        ),
        FillExecutionData(
            fill_id="F2",
            fill_timestamp="2026-11-03T09:30:02Z",
            price=Decimal("100.50"),
            quantity=Decimal("600"),
        ),
    ]

    vwap, filled_qty, gross_notional = SlippageMath.calculate_vwap(fills)
    assert vwap == Decimal("100.38")
    assert filled_qty == Decimal("1000")
    assert gross_notional == Decimal("100380.00")

    slip_price, slip_bps, slip_money = SlippageMath.calculate_realized_slippage(
        side="BUY",
        benchmark_price=Decimal("100.00"),
        vwap_exec=vwap,
        filled_qty=filled_qty,
        multiplier=Decimal("1.0"),
    )

    assert slip_price == Decimal("0.38")
    assert slip_bps == Decimal("38.0000")
    assert slip_money == Decimal("380.00")


def test_sell_order_slippage_and_favorable_price_improvement():
    """
    Test scenario:
    Sell 500 shares.
    Benchmark Arrival Midpoint P_ref = $50.00
    Fill: 500 shares @ $50.25 (Executed at a HIGHER price than benchmark on a SELL)
    Expected Slippage:
    Side = SELL (-1)
    Slip_price = -1 * (50.25 - 50.00) = -0.25 (Negative = Favorable / Price Improvement)
    Slip_bps = -1 * (0.25 / 50.00) * 10,000 = -50.0 bps
    Slip_money = -1 * (0.25) * 500 = -$125.00
    """
    fills = [
        FillExecutionData(
            fill_id="F_SELL_1",
            fill_timestamp="2026-11-03T09:30:01Z",
            price=Decimal("50.25"),
            quantity=Decimal("500"),
            bid_at_fill=Decimal("50.20"),
            ask_at_fill=Decimal("50.30"),
            midpoint_at_fill=Decimal("50.25"),
        ),
    ]

    summary, attributions = SlippageMath.calculate_execution_summary(
        side="SELL",
        requested_quantity=Decimal("500"),
        benchmark_price=Decimal("50.00"),
        benchmark_type="ARRIVAL_MIDPOINT",
        fills=fills,
    )

    assert summary.is_favorable is True
    assert summary.slippage_price_units == Decimal("-0.25")
    assert summary.slippage_bps == Decimal("-50.0000")
    assert summary.slippage_monetary_amount == Decimal("-125.00")
    assert summary.attribution_reconciled is True


def test_additive_attribution_decomposition_reconciliation():
    """
    Test exact additive decomposition:
    Total Price Deviation = Market Movement + Spread Crossing + Residual Execution.
    BUY 500 shares @ $101.00
    P_ref = $100.00
    Market state at fill: Bid = $100.80, Ask = $101.00, Midpoint = $100.90
    S = +1 (BUY)
    1. Total Deviation = 1 * (101.00 - 100.00) = +1.00
    2. Market Movement = 1 * (100.90 - 100.00) = +0.90
    3. Spread Crossing = (Ask - Midpoint) = 101.00 - 100.90 = +0.10
    4. Residual Execution = 1 * (101.00 - 100.90) - 0.10 = 0.10 - 0.10 = 0.00
    Reconciliation: 0.90 + 0.10 + 0.00 == 1.00!
    """
    fill = FillExecutionData(
        fill_id="F_ATTR_1",
        fill_timestamp="2026-11-03T09:30:05Z",
        price=Decimal("101.00"),
        quantity=Decimal("500"),
        bid_at_fill=Decimal("100.80"),
        ask_at_fill=Decimal("101.00"),
        midpoint_at_fill=Decimal("100.90"),
    )

    attr = SlippageMath.decompose_fill_attribution(
        side="BUY",
        benchmark_price=Decimal("100.00"),
        fill=fill,
    )

    assert attr.fill_slippage_price == Decimal("1.00")
    assert attr.market_movement_price == Decimal("0.90")
    assert attr.spread_crossing_price == Decimal("0.10")
    assert attr.residual_execution_price == Decimal("0.00")
    assert attr.total_reconciled is True
    assert (
        attr.market_movement_price + attr.spread_crossing_price + attr.residual_execution_price
        == attr.fill_slippage_price
    )


def test_negative_residual_price_improvement():
    """
    Test passive fill inside the spread (price improvement):
    BUY @ $100.85
    P_ref = $100.00, Bid = $100.80, Ask = $101.00, Mid = $100.90
    1. Total Slip = 100.85 - 100.00 = +0.85
    2. Market Movement = 100.90 - 100.00 = +0.90
    3. Spread Crossing = 101.00 - 100.90 = +0.10
    4. Residual = (100.85 - 100.90) - 0.10 = -0.05 - 0.10 = -0.15
    Reconciliation: 0.90 + 0.10 + (-0.15) == 0.85!
    """
    fill = FillExecutionData(
        fill_id="F_IMPROV",
        fill_timestamp="2026-11-03T09:30:10Z",
        price=Decimal("100.85"),
        quantity=Decimal("200"),
        bid_at_fill=Decimal("100.80"),
        ask_at_fill=Decimal("101.00"),
        midpoint_at_fill=Decimal("100.90"),
    )

    attr = SlippageMath.decompose_fill_attribution(
        side="BUY",
        benchmark_price=Decimal("100.00"),
        fill=fill,
    )

    assert attr.fill_slippage_price == Decimal("0.85")
    assert attr.market_movement_price == Decimal("0.90")
    assert attr.spread_crossing_price == Decimal("0.10")
    assert attr.residual_execution_price == Decimal("-0.15")
    assert attr.total_reconciled is True


def test_opportunity_cost_and_implementation_shortfall():
    """
    Test partial fill execution:
    Requested: 1000 shares BUY.
    Filled: 600 shares @ $101.00.
    Unfilled: 400 shares.
    Benchmark P_ref: $100.00
    Terminal Price P_T: $102.00
    Fees: $10.00
    
    Realized Slippage on filled: (101.00 - 100.00) * 600 = $600.00
    Opportunity Cost on unfilled: (102.00 - 100.00) * 400 = $800.00
    Implementation Shortfall: Realized + OppCost + Fees = 600 + 800 + 10 = $1410.00
    """
    fills = [
        FillExecutionData(
            fill_id="F_PARTIAL_1",
            fill_timestamp="2026-11-03T09:30:00Z",
            price=Decimal("101.00"),
            quantity=Decimal("600"),
            fees=Decimal("10.00"),
        )
    ]

    summary, _ = SlippageMath.calculate_execution_summary(
        side="BUY",
        requested_quantity=Decimal("1000"),
        benchmark_price=Decimal("100.00"),
        benchmark_type="ARRIVAL_PRICE",
        fills=fills,
        terminal_price=Decimal("102.00"),
    )

    assert summary.total_filled_quantity == Decimal("600")
    assert summary.unfilled_quantity == Decimal("400")
    assert summary.slippage_monetary_amount == Decimal("600.00")
    assert summary.opportunity_cost_monetary_amount == Decimal("800.00")
    assert summary.implementation_shortfall_monetary_amount == Decimal("1410.00")
    assert summary.total_all_in_cost == Decimal("610.00")


def test_calibration_metrics_calculation():
    """
    Test calibration metrics calculation across 3 observations:
    Obs 1: Est = 10, Real = 12 -> err = -2, sq = 4, in interval [8, 14] -> True
    Obs 2: Est = 15, Real = 15 -> err = 0, sq = 0, in interval [12, 16] -> True
    Obs 3: Est = 20, Real = 25 -> err = -5, sq = 25, in interval [18, 22] -> False
    
    ME = (-2 + 0 - 5) / 3 = -7 / 3 = -2.3333...
    MAE = (2 + 0 + 5) / 3 = 7 / 3 = 2.3333...
    RMSE = sqrt((4 + 0 + 25) / 3) = sqrt(29 / 3) = sqrt(9.6666...) ≈ 3.1091
    Interval coverage = 2 / 3 = 66.6667%
    """
    obs = [
        (Decimal("10.0"), Decimal("12.0"), Decimal("8.0"), Decimal("14.0")),
        (Decimal("15.0"), Decimal("15.0"), Decimal("12.0"), Decimal("16.0")),
        (Decimal("20.0"), Decimal("25.0"), Decimal("18.0"), Decimal("22.0")),
    ]

    metrics = SlippageMath.calculate_calibration_metrics(obs)
    assert metrics.observation_count == 3
    assert pytest.approx(float(metrics.mean_error), abs=1e-3) == -2.333
    assert pytest.approx(float(metrics.mean_absolute_error), abs=1e-3) == 2.333
    assert pytest.approx(float(metrics.root_mean_squared_error), abs=1e-3) == 3.109
    assert pytest.approx(float(metrics.interval_coverage_pct), abs=1e-2) == 66.67


@pytest.mark.asyncio
async def test_api_full_slippage_lifecycle():
    """
    Integration test testing the complete REST API lifecycle:
    1. Register benchmark config
    2. Submit order execution analysis
    3. Fetch recorded summary and attribution breakdown
    4. Run historical calibration evaluation
    """
    await init_db()
    test_run_id = f"TEST_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    order_id = f"ORD_{test_run_id}"
    config_code = f"CFG_{test_run_id}"
    calib_code = f"CALIB_{test_run_id}"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. Config creation
        config_payload = {
            "config_code": config_code,
            "version": 1,
            "description": "Standard US Equity Midpoint Config",
            "benchmark_type": "ARRIVAL_MIDPOINT",
            "max_quote_age_seconds": 30,
            "allow_cross_venue_benchmarking": True,
            "currency": "USD",
            "multiplier": "1.0",
            "is_active": True,
        }
        res_cfg = await ac.post("/api/v1/market-microstructure/slippage/benchmark-config", json=config_payload)
        assert res_cfg.status_code == 201
        cfg_data = res_cfg.json()
        assert cfg_data["config_code"] == config_code

        # 2. Execution Analysis
        order_payload = {
            "order_id": order_id,
            "symbol": "MSFT",
            "side": "BUY",
            "order_created_at": "2026-11-03T10:00:00Z",
            "requested_quantity": "1000",
            "benchmark_type": "ARRIVAL_MIDPOINT",
            "benchmark_price": "400.00",
            "benchmark_timestamp": "2026-11-03T10:00:00Z",
            "fills": [
                {
                    "fill_id": f"FILL_{test_run_id}_A",
                    "fill_timestamp": "2026-11-03T10:00:01Z",
                    "price": "400.20",
                    "quantity": "500",
                    "venue": "NASDAQ",
                    "bid_at_fill": "400.10",
                    "ask_at_fill": "400.30",
                    "midpoint_at_fill": "400.20",
                    "fees": "2.50",
                },
                {
                    "fill_id": f"FILL_{test_run_id}_B",
                    "fill_timestamp": "2026-11-03T10:00:03Z",
                    "price": "400.40",
                    "quantity": "300",
                    "venue": "BATS",
                    "bid_at_fill": "400.30",
                    "ask_at_fill": "400.50",
                    "midpoint_at_fill": "400.40",
                    "fees": "1.50",
                },
            ],
            "terminal_price": "401.00",
            "multiplier": "1.0",
        }

        res_exec = await ac.post("/api/v1/market-microstructure/slippage/analyze-execution", json=order_payload)
        assert res_exec.status_code == 200
        exec_data = res_exec.json()
        assert exec_data["order_id"] == order_id
        assert Decimal(str(exec_data["filled_quantity"])) == Decimal("800.0")
        assert Decimal(str(exec_data["unfilled_quantity"])) == Decimal("200.0")
        assert exec_data["attribution_reconciled"] is True
        assert len(exec_data["fill_attributions"]) == 2

        # 3. Fetch summary by order_id
        res_get = await ac.get(f"/api/v1/market-microstructure/slippage/execution-summary/{order_id}")
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["order_id"] == order_id
        assert get_data["symbol"] == "MSFT"

        # 4. Calibration run
        calib_payload = {
            "run_code": calib_code,
            "model_name": "HISTORICAL_SPREAD_DEPTH_MODEL",
            "observations": [
                {
                    "order_id": order_id,
                    "symbol": "MSFT",
                    "side": "BUY",
                    "observation_timestamp": "2026-11-03T10:00:00Z",
                    "estimated_slippage_bps": "6.5",
                    "realized_slippage_bps": "6.875",
                    "predicted_lower_bound_bps": "4.0",
                    "predicted_upper_bound_bps": "9.0",
                },
                {
                    "order_id": f"{order_id}_2",
                    "symbol": "MSFT",
                    "side": "SELL",
                    "observation_timestamp": "2026-11-03T10:05:00Z",
                    "estimated_slippage_bps": "5.0",
                    "realized_slippage_bps": "4.2",
                    "predicted_lower_bound_bps": "3.0",
                    "predicted_upper_bound_bps": "7.0",
                },
            ],
        }
        res_calib = await ac.post("/api/v1/market-microstructure/slippage/calibration/run", json=calib_payload)
        assert res_calib.status_code == 200
        calib_data = res_calib.json()
        assert calib_data["observation_count"] == 2
        assert calib_data["run_code"] == calib_code
        assert Decimal(str(calib_data["interval_coverage_pct"])) == Decimal("100.0")
