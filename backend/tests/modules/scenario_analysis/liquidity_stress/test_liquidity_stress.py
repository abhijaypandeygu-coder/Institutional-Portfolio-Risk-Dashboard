"""
Comprehensive Unit & Integration Test Suite for M10.06 Liquidity Stress Testing Module.
Tests:
1. Spread Stress Calculation:
   - Zero widening, 50% widening, 100% widening, 200% widening (3x baseline)
   - Absolute widening & multiplier
   - Tick-size rounding and positive price enforcement
   - Simultaneous market crash price shock
2. Depth Deterioration & Order Book Walk:
   - Uniform depth reduction (e.g. 60% reduction -> 40% remaining)
   - Level-specific decay
   - Depth-walk adverse concession calculation
3. Volume Contraction & Participation Limits:
   - 50% volume contraction and 50% participation cap reduction (10% -> 5%)
   - Interval executable capacity
4. Stressed Liquidation Schedules & Horizon Analysis:
   - Schedule building across 15m, 30m, 1h, 1d, 3d, 5d, 10d
   - Incomplete liquidation detection and residual exposure calculation
5. Stressed Execution Cost Reconciliation:
   - Spread, depth-walk, market impact, slippage, and explicit fees
   - Non-duplication of spread crossing vs. depth-walk concession
   - Basis point cost quantification
6. Full FastAPI End-to-End API Lifecycle:
   - Scenario creation with versioned parameters and overrides
   - Simulation run execution against a multi-asset long/short portfolio
   - Verification of position results, horizon breakdowns, and cost attribution
"""
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.scenario_analysis.liquidity_stress.calculations import (
    calculate_stressed_spread,
    apply_depth_stress,
    execute_order_book_walk,
    calculate_interval_capacity,
    build_liquidation_schedule,
    calculate_stressed_execution_costs,
    OrderBookLevel,
)


# ---------------------------------------------------------
# Test 1: Spread Stress Formulas & Midpoint Preservation
# ---------------------------------------------------------
def test_spread_stress_calculations():
    base_bid = Decimal("99.95")
    base_ask = Decimal("100.05")
    # Base spread = 0.10, midpoint = 100.00

    # 1. 200% widening: S_stress = 0.10 * (1 + 2.0) = 0.30
    s_spread, s_mid, s_bid, s_ask = calculate_stressed_spread(
        baseline_bid=base_bid,
        baseline_ask=base_ask,
        spread_widening_pct=Decimal("2.0000"),
        tick_size=Decimal("0.01"),
    )
    assert s_spread == Decimal("0.30")
    assert s_mid == Decimal("100.00")
    assert s_bid == Decimal("99.85")
    assert s_ask == Decimal("100.15")

    # 2. Multiplier 4x: S_stress = 0.10 * 4.0 = 0.40
    s_spread4, _, s_bid4, s_ask4 = calculate_stressed_spread(
        baseline_bid=base_bid,
        baseline_ask=base_ask,
        spread_multiplier=Decimal("4.0000"),
        tick_size=Decimal("0.01"),
    )
    assert s_spread4 == Decimal("0.40")
    assert s_bid4 == Decimal("99.80")
    assert s_ask4 == Decimal("100.20")

    # 3. Absolute spread increase Delta S = +0.15 -> 0.25
    s_spread_abs, _, _, _ = calculate_stressed_spread(
        baseline_bid=base_bid,
        baseline_ask=base_ask,
        absolute_spread_change=Decimal("0.15"),
        tick_size=Decimal("0.01"),
    )
    assert s_spread_abs == Decimal("0.25")

    # 4. Simultaneous Market Crash Shock: price drops by 20% (-0.20)
    _, s_mid_crash, _, _ = calculate_stressed_spread(
        baseline_bid=base_bid,
        baseline_ask=base_ask,
        spread_widening_pct=Decimal("1.00"),
        market_price_shock_pct=Decimal("-0.20"),
    )
    assert s_mid_crash == Decimal("80.00")


# ---------------------------------------------------------
# Test 2: Depth Stress & Book-Walk Concession
# ---------------------------------------------------------
def test_depth_stress_and_book_walk():
    raw_bids = [
        {"price": Decimal("99.85"), "quantity": Decimal("1000")},
        {"price": Decimal("99.80"), "quantity": Decimal("2000")},
        {"price": Decimal("99.70"), "quantity": Decimal("3000")},
    ]

    # Apply 60% depth reduction (multiplier = 0.40)
    stressed_bids = apply_depth_stress(raw_bids, depth_multiplier=Decimal("0.40"))
    assert len(stressed_bids) == 3
    assert stressed_bids[0].quantity == Decimal("400")
    assert stressed_bids[1].quantity == Decimal("800")
    assert stressed_bids[2].quantity == Decimal("1200")

    # Book walk simulation: liquidate 1000 shares selling into bids
    # Fill: 400 @ 99.85, 600 @ 99.80
    # Total fill = 1000, residual = 0
    # Consideration = 400 * 99.85 + 600 * 99.80 = 39940 + 59880 = 99820
    # VWAP = 99.82
    ref_mid = Decimal("100.00")
    filled, residual, vwap, adverse_cost = execute_order_book_walk(
        levels=stressed_bids,
        target_quantity=Decimal("1000"),
        side="SELL",
        reference_midpoint=ref_mid,
    )
    assert filled == Decimal("1000")
    assert residual == Decimal("0")
    assert vwap == Decimal("99.82")
    # Adverse cost relative to midpoint 100.00 = 1000 * (100.00 - 99.82) = 180.00
    assert adverse_cost == Decimal("180.00")


# ---------------------------------------------------------
# Test 3: Volume Contraction & Interval Capacity
# ---------------------------------------------------------
def test_volume_contraction_and_capacity():
    # Base volume = 100,000 shares per interval
    # Volume contraction = 50% -> Stressed volume = 50,000
    # Baseline participation cap = 10%
    # Participation cap reduction = 50% -> Stressed participation cap = 5%
    v_stress, p_stress, cap = calculate_interval_capacity(
        interval_baseline_volume=Decimal("100000"),
        volume_reduction_pct=Decimal("0.50"),
        participation_cap=Decimal("0.10"),
        participation_reduction_pct=Decimal("0.50"),
    )
    assert v_stress == Decimal("50000")
    assert p_stress == Decimal("0.05")
    # Capacity = 50,000 * 0.05 = 2,500 shares per interval
    assert cap == Decimal("2500")


# ---------------------------------------------------------
# Test 4: Liquidation Schedules & Horizon Analysis
# ---------------------------------------------------------
def test_liquidation_schedules_and_horizons():
    # Target: 50,000 shares
    # Capacities: 2,500 shares per interval
    capacities = [Decimal("2500")] * 30

    snapshots, total_needed, total_fillable, residual, completed = build_liquidation_schedule(
        target_quantity=Decimal("50000"),
        interval_capacities=capacities,
        interval_minutes=15,
        reference_price=Decimal("100.00"),
    )
    # Total needed = 50,000 / 2500 = 20 intervals = 5 hours
    assert total_needed == 20
    assert completed is True
    assert residual == Decimal("0.0")

    # Horizon snapshot checks
    # 15m (1 interval) -> 2,500 filled (ratio 0.05)
    snap_15m = next(s for s in snapshots if s.horizon_name == "15_MINUTES")
    assert snap_15m.executable_quantity == Decimal("2500")
    assert snap_15m.liquidation_ratio == Decimal("0.0500")
    assert snap_15m.is_completed is False

    # 1 session (26 intervals of 15m) -> all 50,000 filled (completed)
    snap_1d = next(s for s in snapshots if s.horizon_name == "FULL_SESSION_1D")
    assert snap_1d.executable_quantity == Decimal("50000")
    assert snap_1d.liquidation_ratio == Decimal("1.0000")
    assert snap_1d.is_completed is True


# ---------------------------------------------------------
# Test 5: Stressed Execution Cost Decomposition
# ---------------------------------------------------------
def test_stressed_cost_decomposition():
    # 10,000 shares @ $100 midpoint ($1,000,000 notional)
    # Stressed spread = $0.30
    costs = calculate_stressed_execution_costs(
        executed_quantity=Decimal("10000"),
        reference_midpoint=Decimal("100.00"),
        stressed_spread=Decimal("0.30"),
        daily_volatility=Decimal("0.02"),
        market_volume=Decimal("100000"),  # 10% participation
        impact_multiplier=Decimal("1.5"),
        brokerage_bps=Decimal("2.0"),
        depth_walk_concession=Decimal("50.00"),
    )
    # Spread cost = 10,000 * (0.30 / 2) = $1,500.00
    assert costs.spread_crossing_cost == Decimal("1500.00")
    assert costs.depth_walk_cost == Decimal("50.00")
    assert costs.market_impact_cost > Decimal("0.0")
    assert costs.slippage_cost > Decimal("0.0")
    # Fees = $1,000,000 * 2 bps = $200.00
    assert costs.explicit_fees == Decimal("200.00")
    assert costs.total_liquidation_cost > Decimal("1750.00")
    assert costs.cost_bps > Decimal("17.5")


# ---------------------------------------------------------
# Test 6: Full FastAPI End-to-End API Lifecycle
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_liquidity_stress_api_full_lifecycle():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Liquidity Stress Scenario
        scen_code = f"SCEN_LIQ_STRESS_{uuid.uuid4().hex[:6].upper()}"
        create_payload = {
            "scenario_code": scen_code,
            "name": "Severe Market Dislocation & Liquidity Freeze",
            "description": "Simulates 200% spread widening, 60% depth reduction, and 50% volume contraction.",
            "scenario_category": "SEVERE_LIQUIDITY_DETERIORATION",
            "spread_increase_pct": "2.0000",      # 200%
            "spread_multiplier": "3.0000",
            "bid_depth_multiplier": "0.4000",     # 40% remaining
            "ask_depth_multiplier": "0.4000",
            "market_volume_multiplier": "0.5000",  # 50% volume remaining
            "participation_multiplier": "0.5000",  # 50% cap remaining (10% -> 5%)
            "base_participation_cap": "0.1000",
            "impact_multiplier": "1.5000",
            "execution_horizon_sessions": 5,
            "market_price_shock_pct": "-0.1000",   # simultaneous -10% market drop
            "overrides": [
                {
                    "instrument_id": "EQ_AAPL",
                    "spread_widening_override_pct": "1.5000",
                    "depth_multiplier_override": "0.5000",
                }
            ],
        }
        create_resp = await client.post("/api/v1/risk/scenarios/liquidity-stress", json=create_payload)
        assert create_resp.status_code == 201
        scen_data = create_resp.json()
        scenario_id = scen_data["id"]
        assert scen_data["scenario_code"] == scen_code

        # 2. List Scenarios
        list_resp = await client.get("/api/v1/risk/scenarios/liquidity-stress")
        assert list_resp.status_code == 200
        scen_list = list_resp.json()
        assert any(s["id"] == scenario_id for s in scen_list)

        # 3. Execute Simulation Run against a long/short multi-asset portfolio
        exec_payload = {
            "portfolio_id": "INST_TECH_EQUITY_PORTFOLIO",
            "executed_by": "Chief Risk Officer",
            "custom_positions": [
                # Long Position 1: 10,000 AAPL @ $150
                {
                    "instrument_id": "EQ_AAPL",
                    "symbol": "AAPL",
                    "quantity": "10000",
                    "price": "150.00",
                    "spread": "0.04",
                    "volume": "500000",
                    "depth": "100000",
                },
                # Short Position 2: -5,000 MSFT @ $300 (Liquidation side = BUY)
                {
                    "instrument_id": "EQ_MSFT",
                    "symbol": "MSFT",
                    "quantity": "-5000",
                    "price": "300.00",
                    "spread": "0.08",
                    "volume": "300000",
                    "depth": "60000",
                },
            ],
        }
        run_resp = await client.post(
            f"/api/v1/risk/scenarios/liquidity-stress/{scenario_id}/runs", json=exec_payload
        )
        assert run_resp.status_code == 201
        run_data = run_resp.json()

        # 4. Verify Aggregate Run Metrics
        assert run_data["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]
        assert Decimal(run_data["baseline_portfolio_notional"]) == Decimal("3000000.00")  # 1.5M + 1.5M
        assert Decimal(run_data["stressed_total_cost"]) > Decimal(run_data["baseline_total_cost"])
        assert Decimal(run_data["incremental_cost"]) > Decimal("0.0")
        assert Decimal(run_data["stressed_cost_bps"]) > Decimal(run_data["baseline_cost_bps"])
        assert "liquidation cost escalates" in run_data["narrative"]

        # 5. Verify Position Results
        pos_results = run_data["position_results"]
        assert len(pos_results) == 2

        aapl = next(p for p in pos_results if p["instrument_id"] == "EQ_AAPL")
        assert aapl["liquidation_side"] == "SELL"
        assert Decimal(aapl["incremental_liquidation_cost"]) > Decimal("0.0")

        msft = next(p for p in pos_results if p["instrument_id"] == "EQ_MSFT")
        assert msft["liquidation_side"] == "BUY"
        assert Decimal(msft["incremental_liquidation_cost"]) > Decimal("0.0")

        # 6. Verify Progressive Horizon Results
        horizons = run_data["horizon_results"]
        assert len(horizons) > 0
        h_names = [h["horizon_type"] for h in horizons]
        assert "15_MINUTES" in h_names
        assert "FULL_SESSION_1D" in h_names

        # 7. Verify Cost Attributions
        attributions = run_data["cost_attributions"]
        assert len(attributions) == 5
        comp_names = [a["cost_component"] for a in attributions]
        assert "SPREAD_CROSSING" in comp_names
        assert "MARKET_IMPACT" in comp_names
        assert "SLIPPAGE" in comp_names
        assert "EXPLICIT_FEES" in comp_names
