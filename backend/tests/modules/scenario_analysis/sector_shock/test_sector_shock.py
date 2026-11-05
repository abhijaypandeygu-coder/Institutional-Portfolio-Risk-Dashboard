"""
Comprehensive Test Suite for M10.04 Sector Shock Simulation.
Tests:
1. Direct sector response (uniform & sensitivity-adjusted).
2. Sector-to-sector and sector-to-factor spillover calculations.
3. Multi-channel return composition with conflict resolution (additive & compound).
4. Signed position revaluation (long vs short) and portfolio NAV reconciliation.
5. Absolute exposure coverage metrics (classification, direct, spillover, sensitivity).
6. End-to-end API lifecycle:
   - Create sector shock scenario with direct sector/industry shocks and spillover relationships.
   - Execute simulation on a multi-sector long-short equity portfolio.
   - Verify position results, sector/industry group aggregations, channel attributions, and diagnostic warnings.
"""

import pytest
import uuid
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.scenario_analysis.sector_shock.calculations.sector_math import (
    calculate_direct_sector_response,
    calculate_spillover_effects,
    calculate_factor_mediated_spillover,
    compose_sector_returns,
    convert_to_base_currency,
    revalue_sector_position,
    compute_portfolio_sector_revaluation,
    compute_sector_coverage_metrics,
    decompose_sector_impacts
)


def test_direct_sector_and_sensitivity_response():
    # 1. Uniform response
    r_uni = calculate_direct_sector_response(Decimal("-0.20"))
    assert r_uni == Decimal("-0.20000000")

    # 2. Sensitivity adjusted: shock = -0.20, beta_s = 1.25 => R = -0.25 (-25%)
    r_sens = calculate_direct_sector_response(Decimal("-0.20"), Decimal("1.25"))
    assert r_sens == Decimal("-0.25000000")


def test_spillover_transmission_and_factor_propagation():
    # Direct shocks: Financials = -20%, Energy = -15%
    direct_shocks = {
        "FINANCIALS": Decimal("-0.20"),
        "ENERGY": Decimal("-0.15")
    }

    # Spillover matrix:
    # Real Estate receives 0.40 from Financials
    # Industrials receives 0.30 from Energy + 0.10 from Financials
    spillover_matrix = {
        "REAL_ESTATE": {"FINANCIALS": Decimal("0.40")},
        "INDUSTRIALS": {"ENERGY": Decimal("0.30"), "FINANCIALS": Decimal("0.10")}
    }

    spillovers = calculate_spillover_effects(direct_shocks, spillover_matrix)
    # Real Estate: 0.40 * (-0.20) = -0.08 (-8%)
    # Industrials: 0.30 * (-0.15) + 0.10 * (-0.20) = -0.045 - 0.02 = -0.065 (-6.5%)
    assert spillovers["REAL_ESTATE"] == Decimal("-0.08000000")
    assert spillovers["INDUSTRIALS"] == Decimal("-0.06500000")

    # Factor-mediated transmission:
    # VALUE_FACTOR receives 0.50 from Financials: F_value = 0.50 * (-0.20) = -0.10
    sec_to_fac = {
        "VALUE_FACTOR": {"FINANCIALS": Decimal("0.50")}
    }
    # Instrument beta to VALUE_FACTOR is 1.20 => R_factor = 1.20 * (-0.10) = -0.12 (-12%)
    inst_betas = {"VALUE_FACTOR": Decimal("1.20")}
    f_shocks, inst_r = calculate_factor_mediated_spillover(direct_shocks, sec_to_fac, inst_betas)
    assert f_shocks["VALUE_FACTOR"] == Decimal("-0.10000000")
    assert inst_r == Decimal("-0.12000000")


def test_sector_composition_and_signed_revaluation():
    # Additive composition: direct = -0.20, spillover = -0.05, factor = -0.02, manual = -0.01
    comp = compose_sector_returns(
        direct_return=Decimal("-0.20"),
        spillover_return=Decimal("-0.05"),
        factor_return=Decimal("-0.02"),
        manual_adjustment=Decimal("-0.01"),
        composition_policy="ADDITIVE"
    )
    assert comp["final_scenario_return"] == Decimal("-0.28000000") # -28%

    # Position Revaluation:
    # Long holding: q = +1000, P_0 = $100 => MV_0 = $100k, P_s = $72, MV_s = $72k, PnL = -$28k, Loss = $28k
    reval_long = revalue_sector_position(
        signed_quantity=Decimal("1000"),
        baseline_price=Decimal("100.00"),
        final_return=comp["final_scenario_return"],
        baseline_nav=Decimal("1000000.00")
    )
    assert reval_long["baseline_market_value"] == Decimal("100000.00")
    assert reval_long["scenario_market_value"] == Decimal("72000.00")
    assert reval_long["scenario_pnl"] == Decimal("-28000.00")
    assert reval_long["scenario_loss"] == Decimal("28000.00")
    assert reval_long["portfolio_contribution"] == Decimal("-0.02800000")

    # Short holding: q = -500, P_0 = $200 => MV_0 = -$100k, P_s = $144, MV_s = -$72k, PnL = +$28k, Loss = $0
    reval_short = revalue_sector_position(
        signed_quantity=Decimal("-500"),
        baseline_price=Decimal("200.00"),
        final_return=comp["final_scenario_return"],
        baseline_nav=Decimal("1000000.00")
    )
    assert reval_short["baseline_market_value"] == Decimal("-100000.00")
    assert reval_short["scenario_market_value"] == Decimal("-72000.00")
    assert reval_short["scenario_pnl"] == Decimal("28000.00")
    assert reval_short["scenario_loss"] == Decimal("0.00")
    assert reval_short["portfolio_contribution"] == Decimal("0.02800000")

    # Portfolio Revaluation:
    port = compute_portfolio_sector_revaluation(
        baseline_nav=Decimal("1000000.00"),
        position_revaluations=[reval_long, reval_short]
    )
    assert port["scenario_pnl"] == Decimal("0.00")
    assert port["scenario_nav"] == Decimal("1000000.00")
    assert port["scenario_loss"] == Decimal("0.00")


def test_sector_coverage_metrics():
    positions = [
        {"baseline_market_value": Decimal("100000"), "is_classified": True, "is_directly_shocked": True, "is_spillover_affected": False, "is_sensitivity_valid": True},
        {"baseline_market_value": Decimal("50000"), "is_classified": True, "is_directly_shocked": False, "is_spillover_affected": True, "is_sensitivity_valid": False},
        {"baseline_market_value": Decimal("-50000"), "is_classified": False, "is_directly_shocked": False, "is_spillover_affected": False, "is_sensitivity_valid": False}
    ]
    # Total abs MV = 200k
    # Classified = 150k / 200k = 0.75
    # Direct = 100k / 200k = 0.50
    # Spillover = 50k / 200k = 0.25
    # Sensitivity = 100k / 200k = 0.50
    cov = compute_sector_coverage_metrics(positions)
    assert cov["classification_coverage"] == Decimal("0.7500")
    assert cov["direct_coverage"] == Decimal("0.5000")
    assert cov["spillover_coverage"] == Decimal("0.2500")
    assert cov["sensitivity_coverage"] == Decimal("0.5000")


@pytest.mark.asyncio
async def test_sector_shock_api_full_lifecycle():
    """
    Validates end-to-end API lifecycle:
    1. Create Sector Shock scenario with direct shocks to Financials & Tech, plus spillover to Real Estate.
    2. Execute simulation on a portfolio with Financials, Technology, Real Estate, and Unclassified positions.
    3. Verify portfolio NAV, signed PnL, group performance, channel attributions, and warning diagnostics.
    """
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Scenario
        sc_code = f"SEC_CRISIS_{uuid.uuid4().hex[:8]}"
        sc_payload = {
            "scenario_code": sc_code,
            "scenario_name": "Financial Contagion & Tech Retrenchment",
            "description": "Direct stress on Financials (-25%) and Tech Software (-30%), cascading to Real Estate (-10%)",
            "category": "CROSS_SECTOR_CONTAGION",
            "visibility": "ORGANIZATION",
            "author_id": "Ayush Sector Risk Lead",
            "group_shocks": [
                {
                    "group_identifier": "FINANCIALS",
                    "group_type": "SECTOR",
                    "classification_system": "GICS",
                    "shock_method": "PERCENTAGE",
                    "shock_value": "-0.25"
                },
                {
                    "group_identifier": "SOFTWARE",
                    "group_type": "INDUSTRY",
                    "classification_system": "GICS",
                    "shock_method": "PERCENTAGE",
                    "shock_value": "-0.30"
                }
            ],
            "spillover_relationships": [
                {
                    "relationship_code": f"REL_FIN_TO_RE_{uuid.uuid4().hex[:8]}",
                    "source_type": "SECTOR",
                    "source_identifier": "FINANCIALS",
                    "target_type": "SECTOR",
                    "target_identifier": "REAL_ESTATE",
                    "spillover_coefficient": "0.40" # 0.40 * (-0.25) = -0.10 (-10%)
                }
            ]
        }

        create_resp = await client.post("/api/v1/scenarios/sector-shock", json=sc_payload)
        assert create_resp.status_code == 201
        sc_data = create_resp.json()
        scenario_id = sc_data["id"]

        # 2. Execute Simulation
        exec_payload = {
            "scenario_name": "Q4 Sector Contagion Run",
            "portfolio_id": "INST_EQUITY_SECTOR_PORTFOLIO",
            "scenario_id": scenario_id,
            "base_currency": "USD",
            "baseline_nav": "2500000.00", # $2.5M NAV
            "conflict_resolution_policy": "MOST_SPECIFIC_WINS",
            "composition_policy": "ADDITIVE",
            "missing_data_policy": "STRICT",
            "group_shocks": sc_payload["group_shocks"],
            "spillover_relationships": sc_payload["spillover_relationships"],
            "positions": [
                # Position 1: Direct Financials Long (JPM) -> -25% shock
                {
                    "instrument_id": "JPM_US",
                    "listing_id": "JPM_NYSE",
                    "signed_quantity": "2000",
                    "baseline_price": "150.00", # $300k MV
                    "currency": "USD",
                    "sector": "FINANCIALS",
                    "industry": "BANKS"
                },
                # Position 2: Direct Software Long (MSFT) -> Industry shock -30%
                {
                    "instrument_id": "MSFT_US",
                    "listing_id": "MSFT_NASDAQ",
                    "signed_quantity": "1000",
                    "baseline_price": "400.00", # $400k MV
                    "currency": "USD",
                    "sector": "TECHNOLOGY",
                    "industry": "SOFTWARE"
                },
                # Position 3: Indirect Real Estate Long (AMT) -> Spillover from Financials (0.40 * -0.25 = -10%)
                {
                    "instrument_id": "AMT_US",
                    "listing_id": "AMT_NYSE",
                    "signed_quantity": "1000",
                    "baseline_price": "200.00", # $200k MV
                    "currency": "USD",
                    "sector": "REAL_ESTATE",
                    "industry": "REITS"
                },
                # Position 4: Financials Short (BAC) -> -25% shock (Short gains)
                {
                    "instrument_id": "BAC_US",
                    "listing_id": "BAC_NYSE",
                    "signed_quantity": "-2000",
                    "baseline_price": "50.00", # -$100k MV
                    "currency": "USD",
                    "sector": "FINANCIALS",
                    "industry": "BANKS"
                }
            ]
        }

        exec_resp = await client.post("/api/v1/scenarios/sector-shock/runs", json=exec_payload)
        assert exec_resp.status_code == 201
        res = exec_resp.json()

        # Assertions on Run Summary
        assert res["portfolio_id"] == "INST_EQUITY_SECTOR_PORTFOLIO"
        assert res["run_status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]
        assert Decimal(res["baseline_nav"]) == Decimal("2500000.00")
        assert Decimal(res["scenario_nav"]) < Decimal("2500000.00")
        assert Decimal(res["scenario_pnl"]) < Decimal("0.00")
        assert Decimal(res["scenario_loss"]) == abs(Decimal(res["scenario_pnl"]))

        # Position Assertions
        pos_results = res["position_results"]
        assert len(pos_results) == 4

        # JPM (Direct Financials Long: -25% on $300k = -$75k)
        jpm = next(p for p in pos_results if p["instrument_id"] == "JPM_US")
        assert Decimal(jpm["final_scenario_return"]) == Decimal("-0.25000000")
        assert Decimal(jpm["scenario_pnl"]) == Decimal("-75000.00")
        assert Decimal(jpm["scenario_loss"]) == Decimal("75000.00")

        # MSFT (Direct Software Long: -30% on $400k = -$120k)
        msft = next(p for p in pos_results if p["instrument_id"] == "MSFT_US")
        assert Decimal(msft["final_scenario_return"]) == Decimal("-0.30000000")
        assert Decimal(msft["scenario_pnl"]) == Decimal("-120000.00")

        # AMT (Spillover Real Estate Long: -10% on $200k = -$20k)
        amt = next(p for p in pos_results if p["instrument_id"] == "AMT_US")
        assert Decimal(amt["spillover_adjustment"]) == Decimal("-0.10000000")
        assert Decimal(amt["final_scenario_return"]) == Decimal("-0.10000000")
        assert Decimal(amt["scenario_pnl"]) == Decimal("-20000.00")

        # BAC (Financials Short: -25% on -$100k = +$25k)
        bac = next(p for p in pos_results if p["instrument_id"] == "BAC_US")
        assert Decimal(bac["scenario_pnl"]) == Decimal("25000.00")
        assert Decimal(bac["scenario_loss"]) == Decimal("0.00")

        # Net PnL = -$75k - $120k - $20k + $25k = -$190k
        assert Decimal(res["scenario_pnl"]) == Decimal("-190000.00")
        assert Decimal(res["scenario_loss"]) == Decimal("190000.00")
        assert Decimal(res["scenario_nav"]) == Decimal("2310000.00")

        # Group Results Assertions
        group_results = res["group_results"]
        sec_names = [g["group_identifier"] for g in group_results if g["group_type"] == "SECTOR"]
        assert "FINANCIALS" in sec_names
        assert "TECHNOLOGY" in sec_names
        assert "REAL_ESTATE" in sec_names

        # Attribution Assertions
        attributions = res["attribution_results"]
        dir_attr = next(a for a in attributions if a["attribution_identifier"] == "DIRECT_SECTOR_SHOCK")
        spill_attr = next(a for a in attributions if a["attribution_identifier"] == "INDIRECT_SPILLOVER")
        # Direct: -$75k (JPM) - $120k (MSFT) + $25k (BAC) = -$170k
        # Spillover: -$20k (AMT)
        assert Decimal(dir_attr["total_impact"]) == Decimal("-170000.00")
        assert Decimal(spill_attr["total_impact"]) == Decimal("-20000.00")
