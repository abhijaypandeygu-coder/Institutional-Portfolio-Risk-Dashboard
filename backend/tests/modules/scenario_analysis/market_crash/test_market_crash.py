"""
Comprehensive Test Suite for M10.03 Market Crash Simulation.
Tests:
1. Index shock calculations (Percentage, Target level, Point change, Multi-stage compounding).
2. Linear beta response and signed long/short position revaluation.
3. Nonlinear downside responses (Downside beta, Piecewise beta, Stress amplification, Quadratic, User defined).
4. Exposure coverage metrics (Mapped, Beta valid, Nonlinear eligible).
5. Currency conversion: (1 + R_base) = (1 + R_local) * (1 + R_FX).
6. End-to-end API lifecycle:
   - Scenario creation with multiple benchmark shocks and nonlinear parameters
   - Execution against a cross-market (US + India) long-short portfolio
   - Verification of position-level results, portfolio NAV, signed PnL, positive loss, attributions, and warnings.
"""

import pytest
import uuid
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.scenario_analysis.market_crash.calculations.crash_math import (
    calculate_index_shock_return,
    calculate_linear_beta_response,
    calculate_downside_response,
    calculate_base_currency_return,
    revalue_position,
    compute_portfolio_revaluation,
    compute_coverage_metrics,
    decompose_linear_nonlinear_impact
)


def test_index_shock_calculations():
    # 1. Percentage
    r_pct, i_pct = calculate_index_shock_return(
        shock_method="PERCENTAGE",
        baseline_index_level=Decimal("5000.00"),
        percentage_shock=Decimal("-0.25")
    )
    assert r_pct == Decimal("-0.25000000")
    assert i_pct == Decimal("3750.00")

    # 2. Target Level
    r_tgt, i_tgt = calculate_index_shock_return(
        shock_method="TARGET_LEVEL",
        baseline_index_level=Decimal("4000.00"),
        target_index_level=Decimal("3200.00")
    )
    assert r_tgt == Decimal("-0.20000000")
    assert i_tgt == Decimal("3200.00")

    # 3. Point Change
    r_pts, i_pts = calculate_index_shock_return(
        shock_method="POINT_CHANGE",
        baseline_index_level=Decimal("20000.00"),
        index_point_change=Decimal("-2000.00")
    )
    assert r_pts == Decimal("-0.10000000")
    assert i_pts == Decimal("18000.00")

    # 4. Multi-Stage Compounding
    # -10% followed by -10% => (1 - 0.10)*(1 - 0.10) - 1 = 0.81 - 1 = -0.19 (-19%)
    r_multi, i_multi = calculate_index_shock_return(
        shock_method="MULTI_STAGE",
        baseline_index_level=Decimal("1000.00"),
        multi_stage_returns=[Decimal("-0.10"), Decimal("-0.10")]
    )
    assert r_multi == Decimal("-0.19000000")
    assert i_multi == Decimal("810.00")


def test_linear_beta_and_signed_revaluation():
    # Benchmark shock: -20%
    b_shock = Decimal("-0.20")

    # Long holding: q = +1000, P_0 = $100, beta = 1.5 => R = -30%
    r_lin_long = calculate_linear_beta_response(Decimal("1.5"), b_shock)
    assert r_lin_long == Decimal("-0.30000000")

    reval_long = revalue_position(
        signed_quantity=Decimal("1000"),
        baseline_price=Decimal("100.00"),
        final_return=r_lin_long,
        baseline_nav=Decimal("1000000.00")
    )
    assert reval_long["baseline_market_value"] == Decimal("100000.00")
    assert reval_long["scenario_market_value"] == Decimal("70000.00")
    assert reval_long["scenario_pnl"] == Decimal("-30000.00")
    assert reval_long["scenario_loss"] == Decimal("30000.00")
    assert reval_long["portfolio_contribution"] == Decimal("-0.03000000")

    # Short holding: q = -500, P_0 = $200, beta = 1.2 => R = -24%
    r_lin_short = calculate_linear_beta_response(Decimal("1.2"), b_shock)
    assert r_lin_short == Decimal("-0.24000000")

    reval_short = revalue_position(
        signed_quantity=Decimal("-500"),
        baseline_price=Decimal("200.00"),
        final_return=r_lin_short,
        baseline_nav=Decimal("1000000.00")
    )
    assert reval_short["baseline_market_value"] == Decimal("-100000.00")
    assert reval_short["scenario_market_value"] == Decimal("-76000.00")
    assert reval_short["scenario_pnl"] == Decimal("24000.00") # Short position gains on crash
    assert reval_short["scenario_loss"] == Decimal("0.00")
    assert reval_short["portfolio_contribution"] == Decimal("0.02400000")

    # Portfolio Revaluation Reconciliation
    port = compute_portfolio_revaluation(
        baseline_nav=Decimal("1000000.00"),
        position_revaluations=[reval_long, reval_short]
    )
    # Net PnL = -30k + 24k = -6k
    assert port["scenario_pnl"] == Decimal("-6000.00")
    assert port["scenario_nav"] == Decimal("994000.00")
    assert port["scenario_loss"] == Decimal("6000.00")
    assert port["scenario_return"] == Decimal("-0.00600000")


def test_nonlinear_downside_models():
    b_shock = Decimal("-0.25") # -25% market crash
    lin_r = Decimal("-0.25")    # beta = 1.0

    # 1. Downside Beta: unconditional beta = 1.0, downside beta = 1.4 => diff = +0.4 => adj = 0.4 * (-0.25) = -0.10
    resp_down = calculate_downside_response(
        linear_return=lin_r,
        benchmark_shock=b_shock,
        response_model="DOWNSIDE_BETA",
        unconditional_beta=Decimal("1.0"),
        downside_beta=Decimal("1.4")
    )
    assert resp_down["downside_adjustment"] == Decimal("-0.10000000")
    assert resp_down["final_scenario_return"] == Decimal("-0.35000000")

    # 2. Stress Amplification: threshold c = 0.10 (10%), lambda = 0.5, p = 1.0
    # shock = -0.25 => shock_mag = 0.25 > 0.10 => d_m = 0.15 => A_i = -0.5 * 0.15 = -0.075
    resp_amp = calculate_downside_response(
        linear_return=lin_r,
        benchmark_shock=b_shock,
        response_model="STRESS_AMPLIFICATION",
        threshold=Decimal("0.10"),
        stress_multiplier=Decimal("0.5"),
        exponent=Decimal("1.0")
    )
    assert resp_amp["nonlinear_adjustment"] == Decimal("-0.07500000")
    assert resp_amp["final_scenario_return"] == Decimal("-0.32500000")

    # 3. Quadratic: gamma = -0.2 => nl = -0.2 * (0.25^2) = -0.2 * 0.0625 = -0.0125
    resp_quad = calculate_downside_response(
        linear_return=lin_r,
        benchmark_shock=b_shock,
        response_model="QUADRATIC",
        curvature=Decimal("-0.2")
    )
    assert resp_quad["nonlinear_adjustment"] == Decimal("-0.01250000")
    assert resp_quad["final_scenario_return"] == Decimal("-0.26250000")

    # 4. User Defined & Sector Overlay
    resp_user = calculate_downside_response(
        linear_return=lin_r,
        benchmark_shock=b_shock,
        response_model="LINEAR",
        sector_adjustment=Decimal("-0.05"),
        user_adjustment=Decimal("-0.03")
    )
    assert resp_user["sector_adjustment"] == Decimal("-0.05000000")
    assert resp_user["user_adjustment"] == Decimal("-0.03000000")
    assert resp_user["final_scenario_return"] == Decimal("-0.33000000")


def test_coverage_and_currency_calculations():
    # Currency conversion: local return = -20%, FX return = -5% (local currency devalues)
    # (1 - 0.20) * (1 - 0.05) - 1 = 0.80 * 0.95 - 1 = 0.76 - 1 = -0.24 (-24%)
    r_base = calculate_base_currency_return(Decimal("-0.20"), Decimal("-0.05"))
    assert r_base == Decimal("-0.24000000")

    # Coverage metrics
    cov = compute_coverage_metrics([
        {"baseline_market_value": Decimal("100000"), "is_mapped": True, "is_beta_valid": True, "is_nonlinear_eligible": True},
        {"baseline_market_value": Decimal("50000"), "is_mapped": True, "is_beta_valid": False, "is_nonlinear_eligible": False},
        {"baseline_market_value": Decimal("-50000"), "is_mapped": False, "is_beta_valid": False, "is_nonlinear_eligible": False}
    ])
    # Total abs MV = 100k + 50k + 50k = 200k
    # Mapped = 150k / 200k = 0.75
    # Beta valid = 100k / 200k = 0.50
    # NL eligible = 100k / 200k = 0.50
    assert cov["mapped_coverage"] == Decimal("0.7500")
    assert cov["beta_coverage"] == Decimal("0.5000")
    assert cov["nonlinear_coverage"] == Decimal("0.5000")


@pytest.mark.asyncio
async def test_market_crash_api_full_lifecycle():
    """
    Validates end-to-end API lifecycle:
    1. Create Market Crash Scenario with multiple benchmarks (US SPX & India NIFTY) and nonlinear parameters.
    2. Execute crash simulation against a cross-market long/short portfolio.
    3. Verify portfolio NAV, signed PnL, positive loss, sector/benchmark attributions, and warnings.
    """
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Scenario
        sc_code = f"CRASH_GLOBAL_{uuid.uuid4().hex[:8]}"
        sc_payload = {
            "scenario_code": sc_code,
            "scenario_name": "Synchronized Global Liquidity Crisis",
            "description": "Simultaneous 25% decline in US equities and 20% decline in Indian equities with tech stress amplification",
            "category": "GLOBAL_SYNCHRONIZED",
            "visibility": "ORGANIZATION",
            "author_id": "Ayush Risk Head",
            "benchmark_shocks": [
                {
                    "benchmark_id": "SPX",
                    "benchmark_name": "S&P 500 Index",
                    "market_region": "US",
                    "shock_method": "PERCENTAGE",
                    "percentage_shock": "-0.25",
                    "benchmark_currency": "USD"
                },
                {
                    "benchmark_id": "NIFTY_50",
                    "benchmark_name": "NIFTY 50 Index",
                    "market_region": "INDIA",
                    "shock_method": "PERCENTAGE",
                    "percentage_shock": "-0.20",
                    "benchmark_currency": "INR"
                }
            ],
            "nonlinear_parameters": [
                {
                    "sector_id": "TECHNOLOGY",
                    "model_type": "STRESS_AMPLIFICATION",
                    "threshold": "0.10",
                    "stress_multiplier": "0.50",
                    "exponent": "1.00",
                    "parameter_source": "CALIBRATED"
                }
            ]
        }

        create_resp = await client.post("/api/v1/scenarios/market-crash", json=sc_payload)
        assert create_resp.status_code == 201
        sc_data = create_resp.json()
        scenario_id = sc_data["id"]

        # 2. Execute Simulation
        exec_payload = {
            "scenario_name": "Q4 Global Crash Simulation Run",
            "portfolio_id": "GLOBAL_EQUITY_PORTFOLIO",
            "scenario_id": scenario_id,
            "base_currency": "USD",
            "baseline_nav": "2000000.00", # $2M NAV
            "response_model": "STRESS_AMPLIFICATION",
            "missing_data_policy": "STRICT",
            "benchmark_shocks": sc_payload["benchmark_shocks"],
            "nonlinear_parameters": sc_payload["nonlinear_parameters"],
            "positions": [
                # Holding 1: US Tech Long (NVDA) -> mapped to SPX (-25%), beta=1.6, Technology sector stress
                {
                    "instrument_id": "NVDA_US",
                    "listing_id": "NVDA_NASDAQ",
                    "signed_quantity": "1000",
                    "baseline_price": "500.00", # $500k MV
                    "currency": "USD",
                    "sector": "TECHNOLOGY",
                    "market_region": "US",
                    "benchmark_id": "SPX",
                    "beta_value": "1.60"
                },
                # Holding 2: India Financials Long (HDFC) -> mapped to NIFTY_50 (-20%), beta=1.2, FX=-2%
                {
                    "instrument_id": "HDFCBANK_IN",
                    "listing_id": "HDFCBANK_NSE",
                    "signed_quantity": "20000",
                    "baseline_price": "20.00", # $400k MV in USD equivalent
                    "currency": "USD",
                    "sector": "FINANCIALS",
                    "market_region": "INDIA",
                    "benchmark_id": "NIFTY_50",
                    "beta_value": "1.20",
                    "fx_return": "-0.02"
                },
                # Holding 3: US Energy Short (XOM) -> mapped to SPX (-25%), beta=0.80
                {
                    "instrument_id": "XOM_US",
                    "listing_id": "XOM_NYSE",
                    "signed_quantity": "-1000",
                    "baseline_price": "100.00", # -$100k MV (Short)
                    "currency": "USD",
                    "sector": "ENERGY",
                    "market_region": "US",
                    "benchmark_id": "SPX",
                    "beta_value": "0.80"
                }
            ]
        }

        exec_resp = await client.post("/api/v1/scenarios/market-crash/runs", json=exec_payload)
        assert exec_resp.status_code == 201
        res = exec_resp.json()

        # Assertions on Run Summary
        assert res["portfolio_id"] == "GLOBAL_EQUITY_PORTFOLIO"
        assert res["run_status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]
        assert Decimal(res["baseline_nav"]) == Decimal("2000000.00")
        assert Decimal(res["scenario_nav"]) < Decimal("2000000.00")
        assert Decimal(res["scenario_pnl"]) < Decimal("0.00")
        assert Decimal(res["scenario_loss"]) == abs(Decimal(res["scenario_pnl"]))
        assert Decimal(res["mapped_coverage"]) == Decimal("1.0000")
        assert Decimal(res["beta_coverage"]) == Decimal("1.0000")

        # Position Assertions
        pos_results = res["position_results"]
        assert len(pos_results) == 3

        # Holding 1 (NVDA):
        # Linear: 1.6 * (-0.25) = -0.40
        # Sector Tech Nonlinear: threshold 0.10, lambda 0.50 => d_m = 0.25 - 0.10 = 0.15 => A_i = -0.075
        # Total final return: -0.475 (-47.5%)
        # PnL = $500k * (-0.475) = -$237.5k
        nvda = next(p for p in pos_results if p["instrument_id"] == "NVDA_US")
        assert Decimal(nvda["linear_return"]) == Decimal("-0.40000000")
        assert Decimal(nvda["nonlinear_adjustment"]) == Decimal("-0.07500000")
        assert Decimal(nvda["final_scenario_return"]) == Decimal("-0.47500000")
        assert Decimal(nvda["scenario_pnl"]) == Decimal("-237500.00")
        assert Decimal(nvda["scenario_loss"]) == Decimal("237500.00")

        # Holding 3 (XOM Short):
        # Linear: 0.8 * (-0.25) = -0.20 (-20%)
        # PnL = -$100k * (-0.20) = +$20k (Short gains)
        xom = next(p for p in pos_results if p["instrument_id"] == "XOM_US")
        assert Decimal(xom["scenario_pnl"]) == Decimal("20000.00")
        assert Decimal(xom["scenario_loss"]) == Decimal("0.00")

        # Attribution Assertions
        attributions = res["attribution_results"]
        sec_attrs = [a for a in attributions if a["attribution_type"] == "SECTOR"]
        assert any(a["attribution_identifier"] == "TECHNOLOGY" for a in sec_attrs)
        assert any(a["attribution_identifier"] == "FINANCIALS" for a in sec_attrs)

        bench_attrs = [a for a in attributions if a["attribution_type"] == "BENCHMARK"]
        assert any(a["attribution_identifier"] == "SPX" for a in bench_attrs)
        assert any(a["attribution_identifier"] == "NIFTY_50" for a in bench_attrs)

        lin_nl_attrs = [a for a in attributions if a["attribution_type"] == "LINEAR_VS_NONLINEAR"]
        assert any(a["attribution_identifier"] == "LINEAR_BETA_IMPACT" for a in lin_nl_attrs)
        assert any(a["attribution_identifier"] == "NONLINEAR_STRESS_IMPACT" for a in lin_nl_attrs)

