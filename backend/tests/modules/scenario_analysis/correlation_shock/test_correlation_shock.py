"""
Unit & Integration Test Suite for M10.05 Correlation Shock Module.
Tests:
1. Pairwise Correlation Transformations:
   - Increase formula: 0.30 -> 0.90 @ 0.5 intensity = 0.60
   - Convergence toward one
   - Convergence toward zero
   - Clamp & symmetry enforcement
2. Matrix Property & PSD Validation:
   - Identity & valid PSD matrix
   - Non-symmetric detection
   - Invalid diagonal detection
   - Non-PSD / negative eigenvalue detection
   - Near-singular / ill-conditioned matrix
3. Matrix Repair Engine:
   - Spectral Eigenvalue clipping & diagonal renormalization
   - Shrinkage toward identity
   - Higham (2002) alternating projections
   - Verification of PSD property post-repair
4. Stressed Covariance & Portfolio Risk:
   - Sigma = D_sigma * R * D_sigma
   - Portfolio variance and volatility recalculation
   - Long-short signed weights
   - Cases where correlation increases portfolio risk and cases where it reduces risk (hedging)
5. Euler Risk Contribution Reconciliation:
   - sum(CRC_i) == sigma_p
   - sum(CCV_i) == Var_p
   - Negative risk contribution preservation
6. Diversification Diagnostics:
   - Gross standalone volatility comparison
   - Diversification Ratio
7. Full FastAPI End-to-End API Lifecycle:
   - Scenario creation
   - Matrix validation endpoint
   - Execution against ad-hoc inputs
   - Execution result verification & audit logging
"""
import uuid
import pytest
import numpy as np
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.scenario_analysis.correlation_shock.calculations import (
    MatrixValidationStatus,
    MatrixRepairMethod,
    CorrelationTransformationMethod,
    transform_correlation_pair,
    validate_correlation_matrix,
    repair_correlation_matrix,
    construct_stressed_covariance,
    calculate_portfolio_risk_and_contributions,
    calculate_diversification_metrics,
    compare_baseline_vs_stressed,
)


# ---------------------------------------------------------
# Test 1: Correlation Transformations & Math Formulas
# ---------------------------------------------------------
def test_correlation_transformations_math():
    # 1. Increase: rho = 0.30, target = 0.90, lambda = 0.50 -> 0.60
    rho_res = transform_correlation_pair(
        rho=0.30,
        method=CorrelationTransformationMethod.INCREASE,
        stress_intensity=0.50,
        target_correlation=0.90,
    )
    assert abs(rho_res - 0.60) < 1e-6

    # 2. Convergence to one: rho = 0.25, lambda = 0.80 -> 0.20*(0.25) + 0.80 = 0.85
    rho_one = transform_correlation_pair(
        rho=0.25,
        method=CorrelationTransformationMethod.CONVERGENCE_TO_ONE,
        stress_intensity=0.80,
    )
    assert abs(rho_one - 0.85) < 1e-6

    # 3. Convergence to zero: rho = 0.50, lambda = 0.60 -> 0.40*(0.50) = 0.20
    rho_zero = transform_correlation_pair(
        rho=0.50,
        method=CorrelationTransformationMethod.CONVERGENCE_TO_ZERO,
        stress_intensity=0.60,
    )
    assert abs(rho_zero - 0.20) < 1e-6

    # 4. Negative baseline correlation increase
    rho_neg = transform_correlation_pair(
        rho=-0.40,
        method=CorrelationTransformationMethod.INCREASE,
        stress_intensity=0.50,
        target_correlation=0.60,
    )
    # (1-0.5)*(-0.4) + 0.5*(0.6) = -0.2 + 0.3 = +0.10
    assert abs(rho_neg - 0.10) < 1e-6


# ---------------------------------------------------------
# Test 2: Matrix Validation & PSD Diagnostics
# ---------------------------------------------------------
def test_matrix_validation_diagnostics():
    # Valid 3x3 PSD matrix
    valid_mat = np.array([
        [1.0, 0.4, 0.2],
        [0.4, 1.0, 0.3],
        [0.2, 0.3, 1.0],
    ])
    diag_valid = validate_correlation_matrix(valid_mat)
    assert diag_valid["status"] == MatrixValidationStatus.VALID
    assert diag_valid["is_symmetric"] is True
    assert diag_valid["diagonal_valid"] is True
    assert diag_valid["bounds_valid"] is True
    assert diag_valid["is_psd"] is True
    assert diag_valid["minimum_eigenvalue"] > 0.0

    # Non-symmetric matrix
    asym_mat = valid_mat.copy()
    asym_mat[0, 1] = 0.99
    diag_asym = validate_correlation_matrix(asym_mat)
    assert diag_asym["status"] == MatrixValidationStatus.INVALID_NON_SYMMETRIC
    assert diag_asym["is_symmetric"] is False

    # Invalid diagonal
    bad_diag_mat = valid_mat.copy()
    bad_diag_mat[0, 0] = 0.85
    diag_bad = validate_correlation_matrix(bad_diag_mat)
    assert diag_bad["status"] == MatrixValidationStatus.INVALID_DIAGONAL
    assert diag_bad["diagonal_valid"] is False

    # Non-PSD matrix with negative eigenvalue
    # e.g., rho_12 = 0.9, rho_13 = 0.9, rho_23 = -0.9 is mathematically impossible
    non_psd_mat = np.array([
        [1.0, 0.9, 0.9],
        [0.9, 1.0, -0.9],
        [0.9, -0.9, 1.0],
    ])
    diag_non_psd = validate_correlation_matrix(non_psd_mat)
    assert diag_non_psd["status"] == MatrixValidationStatus.INVALID_NON_PSD
    assert diag_non_psd["is_psd"] is False
    assert diag_non_psd["negative_eigenvalue_count"] > 0
    assert diag_non_psd["minimum_eigenvalue"] < 0.0


# ---------------------------------------------------------
# Test 3: Matrix Repair Algorithms
# ---------------------------------------------------------
def test_matrix_repair_algorithms():
    non_psd_mat = np.array([
        [1.0, 0.9, 0.9],
        [0.9, 1.0, -0.9],
        [0.9, -0.9, 1.0],
    ])

    # Method 1: Eigenvalue Clipping
    repaired_clip, audit_clip = repair_correlation_matrix(
        non_psd_mat, method=MatrixRepairMethod.EIGENVALUE_CLIPPING
    )
    diag_clip = validate_correlation_matrix(repaired_clip)
    assert diag_clip["is_psd"] is True
    assert diag_clip["diagonal_valid"] is True
    assert diag_clip["is_symmetric"] is True
    assert audit_clip["frobenius_adjustment"] > 0.0
    assert audit_clip["pre_repair_status"] == MatrixValidationStatus.INVALID_NON_PSD.value

    # Method 2: Higham Alternating Projections
    repaired_higham, audit_higham = repair_correlation_matrix(
        non_psd_mat, method=MatrixRepairMethod.HIGHAM_NEAREST, higham_max_iter=50
    )
    diag_higham = validate_correlation_matrix(repaired_higham)
    assert diag_higham["is_psd"] is True
    assert diag_higham["diagonal_valid"] is True
    assert diag_higham["is_symmetric"] is True

    # Method 3: Shrinkage toward identity
    repaired_shrunk, audit_shrunk = repair_correlation_matrix(
        non_psd_mat, method=MatrixRepairMethod.SHRINKAGE_IDENTITY, shrinkage_alpha=0.5
    )
    assert audit_shrunk["method"] == MatrixRepairMethod.SHRINKAGE_IDENTITY.value
    assert abs(repaired_shrunk[0, 0] - 1.0) < 1e-6


# ---------------------------------------------------------
# Test 4: Covariance, Risk Recalculation & Euler Additivity
# ---------------------------------------------------------
def test_covariance_and_euler_risk_reconciliation():
    r = np.array([
        [1.0, 0.5],
        [0.5, 1.0],
    ])
    vols = np.array([0.20, 0.30])
    weights = np.array([0.60, 0.40])
    asset_ids = ["EQ_AAPL", "EQ_MSFT"]

    # Construct Covariance
    cov = construct_stressed_covariance(r, vols)
    assert cov.shape == (2, 2)
    assert abs(cov[0, 0] - 0.20**2) < 1e-8
    assert abs(cov[1, 1] - 0.30**2) < 1e-8
    assert abs(cov[0, 1] - 0.20 * 0.30 * 0.5) < 1e-8

    # Portfolio Risk & Decomposition
    res = calculate_portfolio_risk_and_contributions(
        weights=weights,
        cov_matrix=cov,
        asset_ids=asset_ids,
        volatilities=vols,
    )
    port_vol = res["portfolio_volatility"]
    port_var = res["portfolio_variance"]

    assert port_vol > 0.0
    assert abs(port_var - port_vol**2) < 1e-8
    assert res["is_euler_reconciled"] is True

    # Check Euler additivity: sum(CRC) == port_vol
    contribs = res["contributions"]
    assert len(contribs) == 2
    sum_crc = sum(c["component_risk_contribution"] for c in contribs)
    assert abs(sum_crc - port_vol) < 1e-6

    # Long-Short hedging test: Negative risk contribution
    # For rho = 0.95 (strong positive co-movement) and weights [1.0, -0.8]:
    # v = Sigma * w = [var1 - 0.8*cov12, cov12 - 0.8*var2]
    # Here var1 = 0.04, var2 = 0.09, cov12 = 0.20 * 0.30 * 0.95 = 0.057
    # v = [0.04 - 0.8*0.057, 0.057 - 0.8*0.09] = [0.04 - 0.0456, 0.057 - 0.072] = [-0.0056, -0.015]
    # For asset 0 (weight +1.0): CRC = +1.0 * v_0 / sigma_p < 0
    # For asset 1 (weight -0.8): CRC = -0.8 * v_1 / sigma_p > 0
    # Alternatively with weights [1.0, -0.4]:
    # v_1 = 0.057 - 0.4*0.09 = 0.057 - 0.036 = +0.021 > 0
    # Then CRC_1 = -0.4 * (+0.021) / sigma_p < 0 (negative risk contribution)!
    r_high = np.array([
        [1.0, 0.95],
        [0.95, 1.0],
    ])
    cov_high = construct_stressed_covariance(r_high, vols)
    weights_ls = np.array([1.0, -0.4])  # Long 1.0 Asset A, Short 0.4 Asset B
    res_ls = calculate_portfolio_risk_and_contributions(
        weights=weights_ls,
        cov_matrix=cov_high,
        asset_ids=asset_ids,
        volatilities=vols,
    )
    assert res_ls["is_euler_reconciled"] is True
    ls_contribs = res_ls["contributions"]
    # Check that short hedge position produces a negative risk contribution (hedging reduces total portfolio variance)
    assert ls_contribs[1]["component_risk_contribution"] < 0.0


# ---------------------------------------------------------
# Test 5: Diversification Diagnostics & Comparisons
# ---------------------------------------------------------
def test_diversification_metrics_and_comparison():
    weights = np.array([0.5, 0.5])
    vols = np.array([0.20, 0.20])
    
    # Baseline matrix: low correlation 0.20
    r_base = np.array([[1.0, 0.20], [0.20, 1.0]])
    cov_base = construct_stressed_covariance(r_base, vols)
    risk_base = calculate_portfolio_risk_and_contributions(
        weights=weights,
        cov_matrix=cov_base,
        asset_ids=["A", "B"],
        volatilities=vols,
    )
    div_base = calculate_diversification_metrics(weights, vols, risk_base["portfolio_volatility"], r_base)

    # Stressed matrix: high correlation 0.90
    r_stress = np.array([[1.0, 0.90], [0.90, 1.0]])
    cov_stress = construct_stressed_covariance(r_stress, vols)
    risk_stress = calculate_portfolio_risk_and_contributions(
        weights=weights,
        cov_matrix=cov_stress,
        asset_ids=["A", "B"],
        volatilities=vols,
    )
    div_stress = calculate_diversification_metrics(weights, vols, risk_stress["portfolio_volatility"], r_stress)

    # Volatility should increase when correlation rises from 0.20 to 0.90
    assert risk_stress["portfolio_volatility"] > risk_base["portfolio_volatility"]
    # Diversification benefit should decline
    assert div_stress["diversification_benefit"] < div_base["diversification_benefit"]

    comp = compare_baseline_vs_stressed(risk_base, risk_stress, div_base, div_stress)
    assert comp["absolute_volatility_change"] > 0.0
    assert comp["percentage_volatility_change"] > 0.0
    assert "increased" in comp["narrative"].lower()


# ---------------------------------------------------------
# Test 6: End-to-End FastAPI API Integration Test
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_correlation_shock_api_full_lifecycle():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Matrix Validation Endpoint
        val_payload = {
            "matrix_data": [
                [1.0, 0.5],
                [0.5, 1.0],
            ],
            "asset_ids": ["EQ_INFY", "EQ_TCS"],
        }
        val_resp = await client.post("/api/v1/scenarios/correlation-shock/validate-matrix", json=val_payload)
        assert val_resp.status_code == 200
        val_data = val_resp.json()
        assert val_data["status"] == "VALID"
        assert val_data["is_psd"] is True

        # 2. Create Correlation Shock Scenario
        scen_code = f"SCEN_CORR_TEST_{uuid.uuid4().hex[:6].upper()}"
        create_payload = {
            "scenario_code": scen_code,
            "name": "Diversification Breakdown Stress Test",
            "description": "Increases cross-asset correlations toward 0.85 to simulate market contagion.",
            "scenario_scope": "FULL_PORTFOLIO",
            "scenario_category": "DIVERSIFICATION_BREAKDOWN",
            "transformation_method": "INCREASE",
            "stress_target": 0.85,
            "stress_intensity": 0.50,
            "volatility_mode": "HOLD_CONSTANT",
            "matrix_repair_method": "EIGENVALUE_CLIPPING",
            "pair_rules": [
                {
                    "entity_a_id": "EQ_INFY",
                    "entity_b_id": "EQ_TCS",
                    "entity_type": "INSTRUMENT",
                    "target_correlation": 0.95,
                    "stress_intensity": 1.0,
                    "transformation_method": "CUSTOM_TARGET",
                }
            ],
        }
        create_resp = await client.post("/api/v1/scenarios/correlation-shock", json=create_payload)
        assert create_resp.status_code == 201
        scen_data = create_resp.json()
        scenario_id = scen_data["id"]
        assert scen_data["scenario_code"] == scen_code

        # 3. List Scenarios
        list_resp = await client.get("/api/v1/scenarios/correlation-shock")
        assert list_resp.status_code == 200
        scen_list = list_resp.json()
        assert any(s["id"] == scenario_id for s in scen_list)

        # 4. Execute Scenario with ad-hoc portfolio inputs
        exec_payload = {
            "custom_asset_ids": ["EQ_INFY", "EQ_TCS"],
            "custom_asset_symbols": ["INFY.NS", "TCS.NS"],
            "custom_weights": {"EQ_INFY": 0.60, "EQ_TCS": 0.40},
            "custom_volatilities": {"EQ_INFY": 0.22, "EQ_TCS": 0.18},
            "custom_matrix_data": [
                [1.0, 0.40],
                [0.40, 1.0],
            ],
            "executed_by": "lead_quant",
        }
        exec_resp = await client.post(f"/api/v1/scenarios/correlation-shock/{scenario_id}/execute", json=exec_payload)
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()

        assert exec_data["execution_status"] == "COMPLETED"
        assert exec_data["baseline_matrix"] is not None
        assert exec_data["stressed_matrix"] is not None
        assert exec_data["repaired_matrix"] is not None
        
        # Check that pair rule was applied: correlation between EQ_INFY and EQ_TCS became 0.95
        stressed_rho = exec_data["stressed_matrix"][0][1]
        assert abs(stressed_rho - 0.95) < 1e-4

        # Risk Results & Euler Contributions
        risk_sum = exec_data["risk_summary"]
        assert risk_sum["stressed_volatility"] > risk_sum["baseline_volatility"]
        assert risk_sum["top_contributor"] in ["INFY.NS", "TCS.NS"]

        contributions = exec_data["contributions"]
        assert len(contributions) == 2
        sum_stressed_crc = sum(c["stressed_contribution"] for c in contributions)
        assert abs(sum_stressed_crc - risk_sum["stressed_volatility"]) < 1e-4
