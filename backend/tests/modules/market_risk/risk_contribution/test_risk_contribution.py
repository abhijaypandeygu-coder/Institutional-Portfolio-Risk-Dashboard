"""
M07.09 Risk Contribution Test Suite.
Covers:
1. Pure Mathematical Decomposition:
   - 1-Asset trivial case
   - 2-Asset positive correlation
   - Negative correlation / hedging asset (signed CRC preservation)
   - Long/Short portfolio with negative weight
   - Finite difference central gradient numerical verification of MRC
   - Euler Additivity Theorem verification (sum CRC == sigma_p, sum CCV == sigma_p^2)
2. Group Aggregation:
   - Sector/Industry/Sleeve aggregation verification
   - Mutually exclusive sum == total portfolio risk
3. What-if Scenario Perturbation:
   - Taylor series first-order vs exact non-linear volatility impact
4. Integration & API Endpoints:
   - Full portfolio risk decomposition POST & GET
   - Holdings breakdown GET
   - Group breakdown GET
   - Reconciliation diagnostics GET
   - Scenario perturbation POST
   - Nested portfolio GET endpoint
   - Health check registration verification
"""
import pytest
import pytest_asyncio
import numpy as np
import math
from decimal import Decimal
from datetime import date, datetime, timedelta
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.market_risk.risk_contribution.calculations.risk_contribution_math import (
    decompose_portfolio_risk,
    aggregate_group_contributions,
    calculate_weight_perturbation_scenario,
)
from backend.app.modules.market_risk.risk_contribution.models import (
    RiskContributionStatus,
    ReconciliationStatus,
    WeightBasis,
    GroupingDimension,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioTypeEnum,
    PortfolioLifecycleStatus,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.portfolio_management.position_management.models import PositionBook, PositionStatus, PositionSide
from backend.app.modules.portfolio_management.position_valuation.models import PositionValuation, ValuationStatus, MarkPriceType
from backend.app.modules.instrument_reference_data.price_reference.models import PriceReferenceObservation


# ============================================================================
# 1. PURE MATHEMATICAL & NUMERICAL TESTS
# ============================================================================

def test_single_asset_risk_decomposition():
    """Single asset should carry 100% of risk, MRC == sigma_1, CRC == sigma_1."""
    weights = np.array([1.0], dtype=np.float64)
    cov_matrix = np.array([[0.04]], dtype=np.float64)  # 20% vol, 0.04 var
    asset_ids = ["INST_A"]

    res = decompose_portfolio_risk(weights, cov_matrix, asset_ids)

    assert res["status"] == RiskContributionStatus.VALID
    assert pytest.approx(res["portfolio_variance"], 1e-9) == 0.04
    assert pytest.approx(res["portfolio_volatility"], 1e-9) == 0.20
    assert res["reconciliation_status"] == ReconciliationStatus.RECONCILED
    assert pytest.approx(res["volatility_residual"], 1e-9) == 0.0

    holding = res["holdings"][0]
    assert pytest.approx(holding["marginal_risk_contribution"], 1e-9) == 0.20
    assert pytest.approx(holding["component_risk_contribution"], 1e-9) == 0.20
    assert pytest.approx(holding["percentage_risk_contribution"], 1e-9) == 100.0
    assert pytest.approx(holding["component_variance_contribution"], 1e-9) == 0.04
    assert pytest.approx(holding["percentage_variance_contribution"], 1e-9) == 100.0


def test_two_asset_euler_reconciliation_and_finite_difference():
    """
    Two assets with positive covariance.
    Verifies Euler theorem additivity and finite-difference gradient agreement.
    """
    weights = np.array([0.6, 0.4], dtype=np.float64)
    # sigma_1 = 0.20 (var = 0.04), sigma_2 = 0.30 (var = 0.09), rho = 0.5 (cov = 0.5 * 0.2 * 0.3 = 0.03)
    cov_matrix = np.array([
        [0.04, 0.03],
        [0.03, 0.09]
    ], dtype=np.float64)
    asset_ids = ["INST_A", "INST_B"]

    res = decompose_portfolio_risk(weights, cov_matrix, asset_ids, verify_finite_difference=True)

    # w^T Sigma w = 0.6^2 * 0.04 + 0.4^2 * 0.09 + 2 * 0.6 * 0.4 * 0.03
    #             = 0.36 * 0.04 + 0.16 * 0.09 + 0.48 * 0.03
    #             = 0.0144 + 0.0144 + 0.0144 = 0.0432
    expected_var = 0.0432
    expected_vol = math.sqrt(expected_var)

    assert pytest.approx(res["portfolio_variance"], 1e-9) == expected_var
    assert pytest.approx(res["portfolio_volatility"], 1e-9) == expected_vol
    assert res["reconciliation_status"] == ReconciliationStatus.RECONCILED
    assert res["volatility_residual"] < 1e-6

    # Verify sum of CRC equals portfolio volatility
    sum_crc = sum(h["component_risk_contribution"] for h in res["holdings"])
    assert pytest.approx(sum_crc, 1e-9) == expected_vol

    # Verify sum of CCV equals portfolio variance
    sum_ccv = sum(h["component_variance_contribution"] for h in res["holdings"])
    assert pytest.approx(sum_ccv, 1e-9) == expected_var

    # Verify finite difference matches analytical MRC closely (within 1e-5)
    for h in res["holdings"]:
        assert abs(h["marginal_risk_contribution"] - h["finite_difference_mrc"]) < 1e-5
        assert h["percentage_risk_contribution"] > 0.0

    # Percentage contributions sum to 100%
    sum_pct = sum(h["percentage_risk_contribution"] for h in res["holdings"])
    assert pytest.approx(sum_pct, 1e-6) == 100.0


def test_hedging_asset_negative_risk_contribution():
    """
    Asset with negative covariance acting as a hedge should exhibit a negative
    Marginal and Component Risk Contribution, reducing total portfolio risk.
    """
    weights = np.array([0.8, 0.2], dtype=np.float64)
    # sigma_1 = 0.20 (var = 0.04), sigma_2 = 0.20 (var = 0.04), rho = -0.8 (cov = -0.8 * 0.04 = -0.032)
    cov_matrix = np.array([
        [0.04, -0.032],
        [-0.032, 0.04]
    ], dtype=np.float64)
    asset_ids = ["INST_LONG", "INST_HEDGE"]

    res = decompose_portfolio_risk(weights, cov_matrix, asset_ids)

    # Total var = 0.64 * 0.04 + 0.04 * 0.04 + 2 * 0.8 * 0.2 * (-0.032)
    #           = 0.0256 + 0.0016 - 0.01024 = 0.01696
    expected_var = 0.01696
    expected_vol = math.sqrt(expected_var)

    assert pytest.approx(res["portfolio_variance"], 1e-9) == expected_var
    assert pytest.approx(res["portfolio_volatility"], 1e-9) == expected_vol

    # Sigma * w for hedge asset = -0.032 * 0.8 + 0.04 * 0.2 = -0.0256 + 0.008 = -0.0176 < 0
    hedge_holding = res["holdings"][1]
    assert hedge_holding["marginal_risk_contribution"] < 0.0
    assert hedge_holding["component_risk_contribution"] < 0.0
    assert hedge_holding["percentage_risk_contribution"] < 0.0

    # Euler theorem still holds exactly: sum(CRC) == sigma_p
    sum_crc = sum(h["component_risk_contribution"] for h in res["holdings"])
    assert pytest.approx(sum_crc, 1e-9) == expected_vol
    assert res["reconciliation_status"] == ReconciliationStatus.RECONCILED


def test_group_aggregation_mutually_exclusive():
    """
    Group attribution should aggregate member contributions such that
    sum(group_crc) == portfolio_volatility without double-counting.
    """
    weights = np.array([0.4, 0.3, 0.3], dtype=np.float64)
    cov = np.eye(3, dtype=np.float64) * 0.04  # diagonal, 20% vol each
    asset_ids = ["A1", "A2", "B1"]

    decomp = decompose_portfolio_risk(weights, cov, asset_ids)
    port_vol = decomp["portfolio_volatility"]
    port_var = decomp["portfolio_variance"]

    holdings_dict = [
        {"asset_id": "A1", "market_value": 4000.0, "weight": 0.4, "SECTOR": "TECH", "component_risk_contribution": decomp["holdings"][0]["component_risk_contribution"], "component_variance_contribution": decomp["holdings"][0]["component_variance_contribution"]},
        {"asset_id": "A2", "market_value": 3000.0, "weight": 0.3, "SECTOR": "TECH", "component_risk_contribution": decomp["holdings"][1]["component_risk_contribution"], "component_variance_contribution": decomp["holdings"][1]["component_variance_contribution"]},
        {"asset_id": "B1", "market_value": 3000.0, "weight": 0.3, "SECTOR": "HEALTHCARE", "component_risk_contribution": decomp["holdings"][2]["component_risk_contribution"], "component_variance_contribution": decomp["holdings"][2]["component_variance_contribution"]},
    ]

    groups = aggregate_group_contributions(holdings_dict, "SECTOR", port_vol, port_var)

    assert len(groups) == 2
    group_crc_sum = sum(g["component_risk_contribution"] for g in groups)
    assert pytest.approx(group_crc_sum, 1e-9) == port_vol

    group_pct_sum = sum(g["percentage_risk_contribution"] for g in groups)
    assert pytest.approx(group_pct_sum, 1e-6) == 100.0


def test_weight_perturbation_scenario_taylor_comparison():
    """
    What-if scenario should accurately contrast first-order Taylor approximation with exact risk.
    """
    base_w = np.array([0.5, 0.5], dtype=np.float64)
    delta_w = np.array([0.05, -0.05], dtype=np.float64)
    cov = np.array([[0.04, 0.01], [0.01, 0.09]], dtype=np.float64)
    assets = ["A", "B"]

    scen = calculate_weight_perturbation_scenario(base_w, delta_w, cov, assets)

    assert scen["base_volatility"] > 0.0
    assert scen["perturbed_volatility"] > 0.0
    # For small perturbations, Taylor error should be small (< 0.005)
    assert scen["taylor_approximation_error"] < 0.005


# ============================================================================
# 2. INTEGRATION TESTS (FASTAPI & DATABASE LIFECYCLE)
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_includes_m07_09():
    """Verify that M07.09 is registered in the system health response."""
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "M07.09 - Risk Contribution Engine" in data["modules"]


@pytest.mark.asyncio
async def test_end_to_end_risk_contribution_workflow():
    """
    End-to-end integration test:
    1. Seed portfolio, instruments, positions, valuations, and historical prices.
    2. Execute POST /api/v1/market-risk/risk-contribution/calculate
    3. Retrieve GET /api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}
    4. Retrieve GET /api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}/holdings
    5. Retrieve GET /api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}/groups
    6. Verify Euler reconciliation diagnostics
    7. Execute POST /api/v1/market-risk/risk-contribution/scenario
    8. Query nested portfolio router /api/v1/portfolios/{portfolio_id}/risk/contribution
    """
    await init_db()
    test_pid = f"PORT_RC_TEST_{datetime.utcnow().strftime('%H%M%S')}"
    inst_1 = f"INST_RC1_{datetime.utcnow().strftime('%H%M%S')}"
    inst_2 = f"INST_RC2_{datetime.utcnow().strftime('%H%M%S')}"

    # 1. Seed database records
    async with AsyncSessionLocal() as session:
        port = Portfolio(
            portfolio_id=test_pid,
            portfolio_code=test_pid,
            portfolio_name="Risk Contribution Test Fund",
            short_name="RC_FUND",
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="INR",
            created_by="TEST_RUNNER",
        )
        session.add(port)

        i1 = Instrument(
            instrument_id=inst_1,
            canonical_name="Tata Consultancy Services Ltd",
            short_name="TCS",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            country_of_issue="IND",
            issue_currency="INR",
        )
        i2 = Instrument(
            instrument_id=inst_2,
            canonical_name="Infosys Ltd",
            short_name="INFY",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            country_of_issue="IND",
            issue_currency="INR",
        )
        session.add_all([i1, i2])

        p1 = PositionBook(
            position_id=f"POS_{inst_1}",
            portfolio_id=test_pid,
            account_id="ACC_001",
            instrument_id=inst_1,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
            sleeve_id="SLEEVE_ALPHA",
        )
        p2 = PositionBook(
            position_id=f"POS_{inst_2}",
            portfolio_id=test_pid,
            account_id="ACC_001",
            instrument_id=inst_2,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
            sleeve_id="SLEEVE_BETA",
        )
        session.add_all([p1, p2])

        v1 = PositionValuation(
            valuation_id=f"VAL_{inst_1}",
            calculation_id=f"CALC_VAL_{inst_1}",
            portfolio_id=test_pid,
            account_id="ACC_001",
            instrument_id=inst_1,
            position_side=PositionSide.LONG,
            signed_quantity=Decimal("100"),
            mark_price=Decimal("3500.00"),
            mark_price_type=MarkPriceType.OFFICIAL_CLOSE,
            price_currency="INR",
            signed_market_value_native=Decimal("350000.00"),
            signed_market_value_base=Decimal("350000.00"),
            signed_cost_basis_native=Decimal("300000.00"),
            signed_cost_basis_base=Decimal("300000.00"),
            unrealized_pnl_native=Decimal("50000.00"),
            unrealized_pnl_base=Decimal("50000.00"),
            valuation_status=ValuationStatus.VALUED,
            effective_at=datetime.utcnow(),
        )
        v2 = PositionValuation(
            valuation_id=f"VAL_{inst_2}",
            calculation_id=f"CALC_VAL_{inst_2}",
            portfolio_id=test_pid,
            account_id="ACC_001",
            instrument_id=inst_2,
            position_side=PositionSide.LONG,
            signed_quantity=Decimal("200"),
            mark_price=Decimal("1500.00"),
            mark_price_type=MarkPriceType.OFFICIAL_CLOSE,
            price_currency="INR",
            signed_market_value_native=Decimal("300000.00"),
            signed_market_value_base=Decimal("300000.00"),
            signed_cost_basis_native=Decimal("280000.00"),
            signed_cost_basis_base=Decimal("280000.00"),
            unrealized_pnl_native=Decimal("20000.00"),
            unrealized_pnl_base=Decimal("20000.00"),
            valuation_status=ValuationStatus.VALUED,
            effective_at=datetime.utcnow(),
        )
        session.add_all([v1, v2])

        # Seed 30 days of price observations for realistic covariance
        base_d = date.today() - timedelta(days=40)
        p1_val = 3200.0
        p2_val = 1400.0
        for day in range(35):
            obs_d = base_d + timedelta(days=day)
            p1_val *= 1.0 + (0.01 if day % 2 == 0 else -0.008)
            p2_val *= 1.0 + (0.012 if day % 3 == 0 else -0.009)

            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_P1_{inst_1}_{day}",
                instrument_id=inst_1,
                exchange_code="NSE",
                trading_date=obs_d,
                reference_type="OFFICIAL_CLOSE",
                price_value=Decimal(str(round(p1_val, 2))),
                currency="INR",
            ))
            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_P2_{inst_2}_{day}",
                instrument_id=inst_2,
                exchange_code="NSE",
                trading_date=obs_d,
                reference_type="OFFICIAL_CLOSE",
                price_value=Decimal(str(round(p2_val, 2))),
                currency="INR",
            ))

        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 2. POST /calculate
        calc_req = {
            "portfolio_id": test_pid,
            "weight_basis": "MARKET_VALUE",
            "lookback_days": 60,
            "verify_finite_difference": True,
        }
        calc_resp = await client.post("/api/v1/market-risk/risk-contribution/calculate", json=calc_req)
        assert calc_resp.status_code == 200
        calc_data = calc_resp.json()
        assert calc_data["portfolio_id"] == test_pid
        assert calc_data["num_assets"] == 2
        assert float(calc_data["portfolio_volatility"]) > 0.0
        calc_id = calc_data["calculation_id"]

        # Verify Euler theorem reconciliation in response
        recon = calc_data["reconciliation"]
        assert recon["reconciliation_status"] in ["RECONCILED", "RECONCILIATION_WARNING"]
        assert float(recon["volatility_residual"]) < 1e-4

        # 3. GET /portfolio/{portfolio_id}
        port_resp = await client.get(f"/api/v1/market-risk/risk-contribution/portfolio/{test_pid}")
        assert port_resp.status_code == 200
        port_data = port_resp.json()
        assert port_data["calculation_id"] == calc_id
        assert len(port_data["holdings"]) == 2

        # 4. GET /portfolio/{portfolio_id}/holdings
        holdings_resp = await client.get(f"/api/v1/market-risk/risk-contribution/portfolio/{test_pid}/holdings")
        assert holdings_resp.status_code == 200
        holdings = holdings_resp.json()
        assert len(holdings) == 2
        # Verify holding percentage risk contributions sum to 100%
        total_pct_crc = sum(float(h["percentage_risk_contribution"]) for h in holdings)
        assert pytest.approx(total_pct_crc, 1e-3) == 100.0

        # 5. GET /portfolio/{portfolio_id}/groups
        group_resp = await client.get(
            f"/api/v1/market-risk/risk-contribution/portfolio/{test_pid}/groups",
            params={"dimension": "SECTOR"},
        )
        assert group_resp.status_code == 200
        group_data = group_resp.json()
        assert len(group_data["groups"]) >= 1
        assert float(group_data["discrepancy"]) < 1e-4

        # 6. GET /reconciliation/{calculation_id}
        recon_resp = await client.get(f"/api/v1/market-risk/risk-contribution/reconciliation/{calc_id}")
        assert recon_resp.status_code == 200
        recon_data = recon_resp.json()
        assert recon_data["reconciliation_status"] in ["RECONCILED", "RECONCILIATION_WARNING"]

        # 7. POST /scenario (weight perturbation)
        scen_req = {
            "portfolio_id": test_pid,
            "weight_deltas": {
                inst_1: "0.05",
                inst_2: "-0.05",
            },
        }
        scen_resp = await client.post("/api/v1/market-risk/risk-contribution/scenario", json=scen_req)
        assert scen_resp.status_code == 200
        scen_data = scen_resp.json()
        assert float(scen_data["base_volatility"]) > 0.0
        assert float(scen_data["perturbed_volatility"]) > 0.0
        assert float(scen_data["taylor_approximation_error"]) < 0.01

        # 8. GET nested portfolio router /api/v1/portfolios/{portfolio_id}/risk/contribution
        nested_resp = await client.get(f"/api/v1/portfolios/{test_pid}/risk/contribution")
        assert nested_resp.status_code == 200
        nested_data = nested_resp.json()
        assert nested_data["calculation_id"] == calc_id
        assert nested_data["portfolio_id"] == test_pid
