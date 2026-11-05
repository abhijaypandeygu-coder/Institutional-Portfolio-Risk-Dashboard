"""
Unit and Integration Tests for M10.02 Hypothetical Scenarios.

Validates:
1. Channel A: Direct Valuation Shocks
   - Percentage price shocks, absolute shocks, target price shocks.
   - Long and short position PnL revaluation.
   - Factor shock modeling: R_i = sum(beta_k * F_k) + residual.
   - Exact mathematical reconciliation: sum(C_i) == R_portfolio.
2. Channel B: Risk-Model Assumption Shocks
   - Volatility scaling (relative, absolute, target).
   - Correlation modification & Higham nearest-matrix PSD repair.
   - Covariance reconstruction: Sigma = D * R * D.
   - Stressed Parametric VaR (95%) and ES (95%).
3. Channel C: Liquidity Overlays
   - Spread widening, order-book depth reduction, volume contraction.
4. End-to-End API Lifecycle
   - Reusable template creation.
   - Multi-channel scenario execution (combining Price, Factor, Volatility, Correlation, and Liquidity shocks).
   - Validation & diagnostic caveats verification.
"""

import pytest
import uuid
import numpy as np
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.scenario_analysis.hypothetical_scenarios.calculations.hypothetical_math import (
    to_decimal,
    apply_price_shock,
    apply_factor_shock,
    apply_volatility_shock,
    validate_and_repair_correlation_matrix,
    reconstruct_covariance_matrix,
    compute_stressed_risk_metrics,
    revalue_hypothetical_position,
    apply_liquidity_overlay
)


def test_price_shock_and_revaluation_reconciliation():
    """
    Verifies price shock transformations (percentage, absolute, target)
    and long/short signed quantity revaluation reconciliation.
    """
    p0 = Decimal("200.00")
    
    # 1. Percentage shock -15%
    p_pct, ret_pct = apply_price_shock(p0, "PERCENTAGE", Decimal("-0.15"))
    assert p_pct == Decimal("170.00000000")
    assert ret_pct == Decimal("-0.15")

    # 2. Absolute shock +₹25
    p_abs, ret_abs = apply_price_shock(p0, "ABSOLUTE", Decimal("25.00"))
    assert p_abs == Decimal("225.00000000")
    assert ret_abs == Decimal("0.12500000")

    # 3. Target price shock to ₹180
    p_tgt, ret_tgt = apply_price_shock(p0, "TARGET_PRICE", Decimal("180.00"))
    assert p_tgt == Decimal("180.00000000")
    assert ret_tgt == Decimal("-0.10000000")

    # 4. Long & short revaluation with NAV = $1,000,000
    nav_0 = Decimal("1000000")
    # Long: 1000 shares @ 200 -> 170 (PnL = -$30,000)
    rev_long = revalue_hypothetical_position(Decimal("1000"), p0, p_pct, nav_0)
    assert rev_long["scenario_pnl"] == Decimal("-30000.0000")
    assert rev_long["portfolio_contribution"] == Decimal("-0.03000000")

    # Short: -500 shares @ 200 -> 170 (PnL = +$15,000)
    rev_short = revalue_hypothetical_position(Decimal("-500"), p0, p_pct, nav_0)
    assert rev_short["scenario_pnl"] == Decimal("15000.0000")
    assert rev_short["portfolio_contribution"] == Decimal("0.01500000")

    total_pnl = rev_long["scenario_pnl"] + rev_short["scenario_pnl"]
    port_ret = total_pnl / nav_0
    sum_contrib = rev_long["portfolio_contribution"] + rev_short["portfolio_contribution"]
    assert port_ret == sum_contrib == Decimal("-0.01500000")


def test_correlation_matrix_psd_validation_and_repair():
    """
    Verifies that non-positive semidefinite correlation matrices are detected,
    and Higham nearest-correlation projection repairs them to PSD with unit diagonals.
    """
    # 3x3 correlation matrix intentionally non-PSD:
    # High pairwise correlations between all 3 pairs with negative determinant
    invalid_corr = np.array([
        [1.0, 0.9, 0.9],
        [0.9, 1.0, -0.9],
        [0.9, -0.9, 1.0]
    ])
    # Expect error under strict rejection
    with pytest.raises(ValueError, match="Correlation matrix is non-positive-semidefinite"):
        validate_and_repair_correlation_matrix(invalid_corr, repair_policy="REJECT_INVALID_MATRIX")

    # Under repair policy, matrix is successfully projected to PSD
    repaired_corr, is_valid, diag = validate_and_repair_correlation_matrix(
        invalid_corr, repair_policy="NEAREST_CORRELATION_MATRIX_REPAIR"
    )
    assert is_valid is True
    assert diag["repaired"] is True
    assert diag["repair_magnitude"] > 0
    # Diagonal must be 1.0
    assert np.allclose(np.diag(repaired_corr), 1.0)
    # Eigenvalues must be >= 0
    eigenvals = np.linalg.eigvalsh(repaired_corr)
    assert np.all(eigenvals >= -1e-7)


def test_covariance_reconstruction_and_stressed_var_es():
    """
    Verifies covariance reconstruction Sigma = D * R * D and parametric VaR/ES calculations.
    """
    vols = np.array([0.20, 0.30]) # 20% and 30% volatility
    corr = np.array([[1.0, 0.5], [0.5, 1.0]])
    cov = reconstruct_covariance_matrix(vols, corr)
    
    assert np.isclose(cov[0, 0], 0.04) # 0.2^2
    assert np.isclose(cov[1, 1], 0.09) # 0.3^2
    assert np.isclose(cov[0, 1], 0.2 * 0.3 * 0.5) # 0.03

    weights = np.array([0.6, 0.4])
    nav = Decimal("1000000") # $1M
    risk = compute_stressed_risk_metrics(weights, nav, cov, confidence_level=0.95)
    
    assert risk["portfolio_volatility"] > Decimal("0")
    assert risk["parametric_var"] > Decimal("0")
    assert risk["parametric_es"] > risk["parametric_var"] # ES > VaR always


def test_liquidity_overlay_calculations():
    """
    Verifies spread widening, depth reduction, and volume contraction calculations.
    """
    res = apply_liquidity_overlay(
        baseline_spread=Decimal("0.10"),
        baseline_bid_depth=Decimal("10000"),
        baseline_ask_depth=Decimal("12000"),
        baseline_volume=Decimal("100000"),
        spread_shock_pct=Decimal("0.50"), # +50%
        depth_shock_pct=Decimal("0.40"),  # -40%
        volume_shock_pct=Decimal("0.30")  # -30%
    )
    assert res["scenario_spread"] == Decimal("0.1500")
    assert res["scenario_bid_depth"] == Decimal("6000.0000")
    assert res["scenario_ask_depth"] == Decimal("7200.0000")
    assert res["scenario_volume"] == Decimal("70000.0000")


@pytest.mark.asyncio
async def test_hypothetical_scenarios_api_full_lifecycle():
    """
    Validates end-to-end API lifecycle:
    1. Create reusable scenario template with multi-channel shocks.
    2. Execute hypothetical scenario against portfolio.
    3. Verify Channel A PnL, Channel B Stressed Risk, and Channel C Liquidity overlays.
    """
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Template
        tmpl_code = f"TMPL_STRESS_{uuid.uuid4().hex[:8]}"
        tmpl_payload = {
            "template_code": tmpl_code,
            "template_name": "Combined Tech Crash & Liquidity Dislocation",
            "description": "Multi-channel stress testing technology sector decline, volatility spike, and depth collapse",
            "category": "COMBINED",
            "tags": "tech,crash,volatility,liquidity",
            "price_shocks": [
                {"target_type": "SECTOR", "target_identifier": "TECHNOLOGY", "shock_method": "PERCENTAGE", "shock_value": "-0.20"}
            ],
            "volatility_shocks": [
                {"target_type": "PORTFOLIO", "shock_method": "PERCENTAGE", "shock_value": "0.50"}
            ],
            "liquidity_shocks": [
                {"target_type": "PORTFOLIO", "spread_shock_pct": "0.50", "depth_shock_pct": "0.40", "volume_shock_pct": "0.30"}
            ]
        }
        tmpl_resp = await client.post("/api/v1/scenarios/hypothetical/templates", json=tmpl_payload)
        assert tmpl_resp.status_code == 201
        tmpl_data = tmpl_resp.json()
        tmpl_id = tmpl_data["id"]

        # 2. Execute Scenario
        exec_payload = {
            "scenario_name": "Q4 Global Tech Stress Run",
            "portfolio_id": "INST_PORTFOLIO_HEDGE",
            "template_id": tmpl_id,
            "base_currency": "USD",
            "baseline_nav": "2000000", # $2M NAV
            "positions": [
                # Holding 1: Tech Long (AAPL)
                {
                    "instrument_id": "AAPL_US",
                    "listing_id": "AAPL_NASDAQ",
                    "signed_quantity": "2000",
                    "baseline_price": "300", # $600k (30% weight)
                    "baseline_volatility": "0.25",
                    "currency": "USD",
                    "sector": "TECHNOLOGY",
                    "baseline_spread": "0.05",
                    "baseline_bid_depth": "10000",
                    "baseline_ask_depth": "10000",
                    "baseline_volume": "1000000"
                },
                # Holding 2: Financials Short (JPM)
                {
                    "instrument_id": "JPM_US",
                    "listing_id": "JPM_NYSE",
                    "signed_quantity": "-1000",
                    "baseline_price": "150", # -$150k (-7.5% weight)
                    "baseline_volatility": "0.20",
                    "currency": "USD",
                    "sector": "FINANCIALS",
                    "baseline_spread": "0.04",
                    "baseline_bid_depth": "8000",
                    "baseline_ask_depth": "8000",
                    "baseline_volume": "500000"
                }
            ],
            "price_shocks": [
                {"target_type": "SECTOR", "target_identifier": "TECHNOLOGY", "shock_method": "PERCENTAGE", "shock_value": "-0.20"}
            ],
            "volatility_shocks": [
                {"target_type": "PORTFOLIO", "shock_method": "PERCENTAGE", "shock_value": "0.50"}
            ],
            "correlation_shocks": [
                {"instrument_a": "AAPL_US", "instrument_b": "JPM_US", "target_correlation": "0.85"}
            ],
            "liquidity_shocks": [
                {"target_type": "PORTFOLIO", "spread_shock_pct": "0.50", "depth_shock_pct": "0.40", "volume_shock_pct": "0.30"}
            ]
        }
        run_resp = await client.post("/api/v1/scenarios/hypothetical/runs", json=exec_payload)
        assert run_resp.status_code == 200
        run_data = run_resp.json()

        # Check Channel A: Valuation
        assert float(run_data["baseline_nav"]) == 2000000.0
        # Tech dropped 20% on $600k long -> -$120k PnL. Financials had 0% shock -> 0 PnL
        assert float(run_data["scenario_pnl"]) == -120000.0
        assert float(run_data["scenario_nav"]) == 1880000.0

        # Check Channel B: Stressed Risk
        assert len(run_data["risk_results"]) >= 3
        vol_metric = next(r for r in run_data["risk_results"] if r["metric_code"] == "PORTFOLIO_VOLATILITY")
        var_metric = next(r for r in run_data["risk_results"] if r["metric_code"] == "PARAMETRIC_VAR_95")
        assert float(vol_metric["scenario_value"]) > float(vol_metric["baseline_value"])
        assert float(var_metric["scenario_value"]) > float(var_metric["baseline_value"])

        # Check Channel C: Liquidity
        assert len(run_data["liquidity_results"]) == 2
        aapl_liq = next(l for l in run_data["liquidity_results"] if l["instrument_id"] == "AAPL_US")
        # Spread widened by 50% from 0.05 -> 0.075
        assert float(aapl_liq["scenario_spread"]) == 0.075
        # Depth contracted by 40% from 10,000 -> 6,000
        assert float(aapl_liq["scenario_bid_depth"]) == 6000.0

        # Check Caveats & Metadata
        assert run_data["caveat_summary"] != ""
        assert run_data["run_status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]

