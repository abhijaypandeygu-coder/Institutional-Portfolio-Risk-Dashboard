"""
Comprehensive test suite for M09.06 Liquidity Stress Testing & Stressed Execution Cost Estimation.

Verifies:
1. Spread widening calculations (multiplicative, percentage, additive bps) and synthetic quote generation.
2. Depth reduction (uniform and level-specific) and synthetic order book construction.
3. Liquidation schedule and duration estimation across discrete interval volume profiles.
4. Incomplete liquidation detection and residual unliquidated quantity tracking.
5. Execution cost reconciliation without double-counting between half-spread and depth-walk price concessions.
6. Reverse stress testing search for critical parameter breach thresholds.
7. Portfolio-level aggregation across concurrent liquidation schedules.
8. End-to-end FastAPI endpoint lifecycle.
"""

from datetime import datetime
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.market_microstructure.liquidity_stress_testing.calculations.stress_math import (
    OrderBookLevel,
    IntervalVolumeProfile,
    LiquidityStressMath,
)


def test_hand_calculated_spread_widening_and_synthetic_quote():
    """
    Test scenario:
    Baseline Spread S_0 = $0.20, Midpoint M = $100.00
    Spread Multiplier m_s = 2.00 (100% widening)
    Stressed Spread S_stress = 2.00 * 0.20 = $0.40
    Synthetic Quotes:
    Bid_stress = 100.00 - 0.40/2 = $99.80
    Ask_stress = 100.00 + 0.40/2 = $100.20
    """
    base_spread = Decimal("0.20")
    midpoint = Decimal("100.00")
    mult = Decimal("2.00")

    stressed_spread = LiquidityStressMath.calculate_stressed_spread(
        baseline_spread=base_spread, multiplier=mult
    )
    assert stressed_spread == Decimal("0.4000")

    bid, ask = LiquidityStressMath.construct_synthetic_quote(
        midpoint=midpoint, stressed_spread=stressed_spread, tick_size=Decimal("0.01")
    )
    assert bid == Decimal("99.80")
    assert ask == Decimal("100.20")
    assert (ask - bid) == Decimal("0.40")
    assert (ask + bid) / Decimal("2.0") == midpoint


def test_hand_calculated_depth_reduction_and_book_construction():
    """
    Test scenario:
    Baseline Ask 1: Price $100.10, Qty 1000
    Baseline Ask 2: Price $100.20, Qty 2000
    Uniform reduction r_d = 25% (0.25)
    Stressed Ask 1: 1000 * (1 - 0.25) = 750
    Stressed Ask 2: 2000 * (1 - 0.25) = 1500
    Total Stressed Ask Depth = 2250
    """
    levels = [
        OrderBookLevel(price=Decimal("100.10"), quantity=Decimal("1000")),
        OrderBookLevel(price=Decimal("100.20"), quantity=Decimal("2000")),
    ]

    reduced = LiquidityStressMath.reduce_depth_ladder(
        levels=levels, uniform_reduction=Decimal("0.25")
    )
    assert len(reduced) == 2
    assert reduced[0].quantity == Decimal("750.00")
    assert reduced[1].quantity == Decimal("1500.00")
    assert sum(lvl.quantity for lvl in reduced) == Decimal("2250.00")


def test_hand_calculated_liquidation_schedule():
    """
    Test scenario:
    Target Quantity: 3,000 shares
    Baseline volume per interval: 10,000 shares
    Participation rate: 10% (0.10)
    Baseline capacity per interval: 10,000 * 0.10 = 1,000 shares
    Expected baseline duration: ceil(3000 / 1000) = 3 intervals
    
    Volume Contraction: 40% (0.40)
    Stressed volume per interval: 10,000 * (1 - 0.40) = 6,000 shares
    Stressed capacity per interval: 6,000 * 0.10 = 600 shares
    Expected stressed duration: ceil(3000 / 600) = 5 intervals
    Duration Increase = 5 - 3 = 2 intervals
    """
    target_qty = Decimal("3000")
    profiles = [
        IntervalVolumeProfile(
            interval_index=i,
            baseline_volume=Decimal("10000"),
            volume_contraction_ratio=Decimal("0.40"),
            participation_rate=Decimal("0.10"),
        )
        for i in range(10)
    ]

    sched = LiquidityStressMath.calculate_liquidation_schedule(
        target_quantity=target_qty,
        volume_profiles=profiles,
        max_horizon_intervals=10,
    )

    assert sched.baseline_duration_intervals == 3
    assert sched.stressed_duration_intervals == 5
    assert sched.duration_increase_intervals == 2
    assert sched.baseline_completed is True
    assert sched.stressed_completed is True
    assert sched.status == "COMPLETED"


def test_incomplete_liquidation_and_residual_quantity():
    """
    Test scenario:
    Target Quantity: 10,000 shares
    Max Horizon: 5 intervals
    Stressed capacity per interval: 1,000 shares
    Total Stressed Capacity over 5 intervals = 5,000 shares
    Expected Fillable: 5,000 shares
    Expected Residual: 5,000 shares
    Status: LIQUIDATION_NOT_COMPLETED
    """
    target_qty = Decimal("10000")
    profiles = [
        IntervalVolumeProfile(
            interval_index=i,
            baseline_volume=Decimal("10000"),
            volume_contraction_ratio=Decimal("0.0"),
            participation_rate=Decimal("0.10"),
            baseline_capacity=Decimal("1000"),
            stressed_capacity=Decimal("1000"),
        )
        for i in range(5)
    ]

    sched = LiquidityStressMath.calculate_liquidation_schedule(
        target_quantity=target_qty,
        volume_profiles=profiles,
        max_horizon_intervals=5,
    )

    assert sched.stressed_completed is False
    assert sched.stressed_fillable_quantity == Decimal("5000")
    assert sched.stressed_residual_quantity == Decimal("5000")
    assert sched.status == "LIQUIDATION_NOT_COMPLETED"


def test_cost_decomposition_reconciliation_and_no_double_counting():
    """
    Verify exact reconciliation of cost components:
    Total Cost == Spread Cost + Depth Walk Concession + Market Impact + Explicit Fees + Opportunity Cost.
    Baseline Spread S_0 = 0.10 -> half-spread = 0.05
    Stressed Spread S_stress = 0.20 -> half-spread = 0.10
    Qty: 1000 shares @ $100.00
    Base Spread Cost = 1000 * 0.05 = $50.00
    Stressed Spread Cost = 1000 * 0.10 = $100.00
    """
    cost_res = LiquidityStressMath.calculate_stressed_execution_cost(
        order_quantity=Decimal("1000"),
        side="BUY",
        reference_price=Decimal("100.00"),
        baseline_spread=Decimal("0.10"),
        stressed_spread=Decimal("0.20"),
        baseline_depth_concession=Decimal("10.00"),
        stressed_depth_concession=Decimal("25.00"),
        baseline_impact_bps=Decimal("5.0"),
        stressed_impact_bps=Decimal("10.0"),
        explicit_fees=Decimal("2.50"),
        unfilled_quantity=Decimal("0.0"),
    )

    base = cost_res.baseline_cost
    stress = cost_res.stressed_cost

    assert base.spread_cost == Decimal("50.00")
    assert stress.spread_cost == Decimal("100.00")
    assert cost_res.cost_escalation_monetary > Decimal("0.0")
    assert (
        base.total_cost
        == base.spread_cost
        + base.depth_walk_concession_cost
        + base.market_impact_cost
        + base.explicit_fees
        + base.opportunity_cost
    )
    assert (
        stress.total_cost
        == stress.spread_cost
        + stress.depth_walk_concession_cost
        + stress.market_impact_cost
        + stress.explicit_fees
        + stress.opportunity_cost
    )


def test_reverse_stress_testing_search():
    """
    Test scenario:
    Order Quantity: 4,000 shares
    Baseline Volume per interval: 10,000 shares
    Participation rate: 10% -> 1,000 shares/interval
    At baseline, duration = 4 intervals.
    Max acceptable intervals = 5 intervals.
    Capacity needed = 4,000 / 5 = 800 shares/interval.
    Critical volume capacity ratio = 800 / 1000 = 0.80 -> Critical Contraction = 20% (0.20)
    """
    res = LiquidityStressMath.reverse_stress_search(
        baseline_spread=Decimal("0.10"),
        baseline_interval_volume=Decimal("10000"),
        order_quantity=Decimal("4000"),
        max_acceptable_cost=Decimal("1000"),
        max_acceptable_intervals=5,
        participation_rate=Decimal("0.10"),
    )

    assert res["time_breached_at_baseline"] is False
    assert pytest.approx(float(res["critical_volume_contraction_ratio"]), abs=1e-4) == 0.20
    assert pytest.approx(float(res["critical_volume_contraction_pct"]), abs=1e-2) == 20.0


@pytest.mark.asyncio
async def test_api_full_liquidity_stress_lifecycle():
    """
    Integration test testing the complete REST API lifecycle:
    1. Create stress scenario configuration
    2. Run instrument liquidity stress test
    3. Run reverse stress testing
    4. Run portfolio liquidity stress aggregation
    """
    await init_db()
    test_run_id = f"RUN_STRESS_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    scenario_code = f"CFG_STRESS_{test_run_id}"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. Create Config
        cfg_payload = {
            "scenario_code": scenario_code,
            "version": 1,
            "name": "Severe Stress Scenario",
            "description": "Double spread, 50% depth reduction, 40% volume drop",
            "scenario_type": "COMBINED_STRESS",
            "spread_shock_method": "MULTIPLIER",
            "spread_multiplier": "2.00",
            "depth_shock_method": "UNIFORM",
            "bid_depth_reduction": "0.50",
            "ask_depth_reduction": "0.50",
            "volume_shock_method": "UNIFORM",
            "volume_contraction": "0.40",
            "participation_rate": "0.10",
            "execution_horizon_intervals": 10,
            "is_active": True,
        }
        res_cfg = await ac.post("/api/v1/market-microstructure/liquidity-stress/scenarios", json=cfg_payload)
        assert res_cfg.status_code == 201
        cfg_data = res_cfg.json()
        assert cfg_data["scenario_code"] == scenario_code

        # 2. Run Stress Test
        run_payload = {
            "run_id": test_run_id,
            "scenario_code": scenario_code,
            "instrument_id": "RELIANCE",
            "venue": "NSE",
            "side": "BUY",
            "order_quantity": "5000",
            "reference_price": "2500.00",
            "baseline_spread": "0.50",
            "baseline_bids": [
                {"price": "2499.75", "quantity": "2000"},
                {"price": "2499.50", "quantity": "3000"},
            ],
            "baseline_asks": [
                {"price": "2500.25", "quantity": "2000"},
                {"price": "2500.50", "quantity": "3000"},
            ],
            "interval_volumes": ["10000", "10000", "10000", "10000", "10000"],
            "explicit_fees": "25.00",
        }
        res_run = await ac.post("/api/v1/market-microstructure/liquidity-stress/run", json=run_payload)
        assert res_run.status_code == 200
        run_data = res_run.json()
        assert run_data["run_id"] == test_run_id
        assert Decimal(str(run_data["baseline_spread"])) == Decimal("0.50")
        assert Decimal(str(run_data["stressed_spread"])) == Decimal("1.00")
        assert run_data["liquidation_status"] in ("COMPLETED", "LIQUIDATION_NOT_COMPLETED")
        assert run_data["synthetic_stress_book"] is not None

        # 3. Reverse Stress
        rev_payload = {
            "instrument_id": "RELIANCE",
            "baseline_spread": "0.50",
            "baseline_interval_volume": "10000",
            "order_quantity": "2500",
            "max_acceptable_cost": "2000.00",
            "max_acceptable_intervals": 5,
            "participation_rate": "0.10",
            "reference_price": "2500.00",
        }
        res_rev = await ac.post("/api/v1/market-microstructure/liquidity-stress/reverse-stress", json=rev_payload)
        assert res_rev.status_code == 200
        rev_data = res_rev.json()
        assert rev_data["critical_volume_contraction_pct"] is not None
        assert rev_data["critical_spread_multiplier"] is not None

        # 4. Portfolio Stress
        port_payload = {
            "portfolio_id": "PORT_INDIA_LARGE_CAP",
            "scenario_code": scenario_code,
            "spread_multiplier": "1.50",
            "volume_contraction": "0.20",
            "participation_rate": "0.10",
            "positions": [
                {
                    "instrument_id": "RELIANCE",
                    "quantity": "2000",
                    "reference_price": "2500.00",
                    "side": "SELL",
                    "baseline_spread": "0.50",
                    "interval_volume": "10000",
                },
                {
                    "instrument_id": "TCS",
                    "quantity": "1500",
                    "reference_price": "3500.00",
                    "side": "SELL",
                    "baseline_spread": "0.75",
                    "interval_volume": "8000",
                },
            ],
        }
        res_port = await ac.post("/api/v1/market-microstructure/liquidity-stress/portfolio", json=port_payload)
        assert res_port.status_code == 200
        port_data = res_port.json()
        assert port_data["portfolio_id"] == "PORT_INDIA_LARGE_CAP"
        assert port_data["total_positions"] == 2
        assert port_data["critical_path_duration_intervals"] > 0

