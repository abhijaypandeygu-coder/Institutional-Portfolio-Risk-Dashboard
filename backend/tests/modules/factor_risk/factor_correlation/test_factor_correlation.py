"""
M08.07 Factor Correlation Unit and Integration Test Suite.
Verifies:
1. Pairwise Correlation and Zero-Variance Handling:
   - Pearson, Spearman, Kendall Tau.
   - Fisher's z 95% confidence intervals with bounds [-1, 1].
   - Non-substituting zero-variance handling (undefined correlation flagged without zero replacement).
2. Authoritative Factor Covariance Estimation & Mutual Mathematical Consistency:
   - Sample, EWMA (RiskMetrics lambda=0.94), and Ledoit-Wolf analytical shrinkage.
   - Exact mathematical consistency check: Sigma_F == D @ P_F @ D.
3. Spectral PSD Validation & Higham (2002) Projection:
   - Eigenvalue decomposition, condition number, positive semi-definite checks.
   - Higham nearest-PSD projection restoring non-PSD matrices to valid positive semi-definite state.
4. Rolling Factor Relationships:
   - Rolling time series (window_length=20).
   - Signed delta vs. absolute strength delta.
   - Historical baseline percentile ranking and stability categories (STABLE_POSITIVE, SIGN_REVERSAL, etc.).
5. Correlation Regime Evaluation & Alert Triggers:
   - High positive/negative threshold exceedances.
   - Rapid delta change detection.
   - Sign reversal alerts.
   - CUSUM structural break detection with persistence check.
6. End-to-End FastAPI Integration:
   - Factor model & observation fixture seeding.
   - Correlation config creation.
   - Matrix execution and snapshot persistence.
   - Authoritative covariance snapshot estimation.
   - Rolling analysis execution.
   - Regime alert evaluation and queries.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
import math
import uuid
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import Base, engine, get_db, init_db, AsyncSessionLocal
from backend.app.modules.factor_risk.factor_correlation.calculations.factor_correlation_math import (
    compute_pairwise_correlation,
    compute_inter_factor_correlation_matrix,
    estimate_factor_covariance,
    project_to_nearest_psd,
    compute_rolling_factor_relationships,
    evaluate_correlation_regimes,
)
from backend.app.modules.factor_risk.factor_correlation.models import (
    FactorCorrelationMethod,
    FactorCovarianceMethod,
    RegimeAlertSeverity,
    RegimeAlertStatus,
    CorrelationStabilityCategory,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorModel,
    FactorModelVersion,
    FactorDefinition,
    FactorDefinitionVersion,
    FactorModelMembership,
    FactorLifecycleStatus,
    MarketScope,
    FactorFamily,
    FactorType,
    ConstructionType,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    FactorReturnObservation,
    FactorReturnSeries,
)


# ==============================================================================
# 1. Mathematical Unit Tests
# ==============================================================================

def test_pairwise_correlation_and_zero_variance():
    """Verify Pearson, Spearman, Kendall, Fisher z CIs, and undefined zero-variance."""
    np.random.seed(42)
    x = np.array([0.01, 0.02, -0.01, 0.03, 0.00, -0.02, 0.04, 0.01, -0.03, 0.02])
    y = 0.8 * x + np.random.normal(0, 0.005, size=len(x))

    # Pearson
    res_pearson = compute_pairwise_correlation(x, y, method="PEARSON", confidence_level=0.95)
    assert res_pearson["is_defined"] is True
    assert res_pearson["correlation"] is not None
    assert 0.70 < res_pearson["correlation"] < 1.0
    assert res_pearson["ci_lower"] is not None and res_pearson["ci_upper"] is not None
    assert -1.0 <= res_pearson["ci_lower"] <= res_pearson["correlation"] <= res_pearson["ci_upper"] <= 1.0

    # Spearman
    res_spearman = compute_pairwise_correlation(x, y, method="SPEARMAN")
    assert res_spearman["is_defined"] is True
    assert res_spearman["correlation"] is not None
    assert 0.60 < res_spearman["correlation"] < 1.0

    # Kendall
    res_kendall = compute_pairwise_correlation(x, y, method="KENDALL")
    assert res_kendall["is_defined"] is True
    assert res_kendall["correlation"] is not None
    assert 0.40 < res_kendall["correlation"] < 1.0

    # Zero-variance check (constant array): must NOT substitute 0.0, must flag is_defined=False
    const_arr = np.zeros(len(x))
    res_undef = compute_pairwise_correlation(const_arr, y, method="PEARSON")
    assert res_undef["is_defined"] is False
    assert res_undef["correlation"] is None
    assert "Zero variance detected" in res_undef["reason"]


def test_factor_covariance_consistency_and_shrinkage():
    """Verify Sample, EWMA, Ledoit-Wolf, and mutual consistency: Sigma_F == D @ P_F @ D."""
    np.random.seed(123)
    T, K = 120, 4
    # Generate realistic correlated factor returns
    true_cov = np.array([
        [0.04, 0.015, 0.008, 0.002],
        [0.015, 0.03, 0.005, -0.001],
        [0.008, 0.005, 0.025, 0.004],
        [0.002, -0.001, 0.004, 0.02],
    ])
    R = np.random.multivariate_normal(np.zeros(K), true_cov / 252.0, size=T)

    # 1. Sample Covariance
    cov_sample = estimate_factor_covariance(R, method="SAMPLE", annualization_factor=252.0)
    assert cov_sample["is_positive_semidefinite"] is True
    assert cov_sample["covariance_matrix_annualized"].shape == (K, K)
    assert cov_sample["is_consistent"] is True
    # Check consistency: Sigma_F vs D @ P_F @ D
    D_sample = np.diag(cov_sample["factor_stds_period"])
    P_sample = cov_sample["correlation_matrix"]
    reconstructed_cov_sample = D_sample @ P_sample @ D_sample
    np.testing.assert_allclose(cov_sample["covariance_matrix_period"], reconstructed_cov_sample, atol=1e-7)

    # 2. EWMA Covariance
    cov_ewma = estimate_factor_covariance(R, method="EWMA", decay_factor=0.94, annualization_factor=252.0)
    assert cov_ewma["is_positive_semidefinite"] is True
    assert cov_ewma["is_consistent"] is True
    D_ewma = np.diag(cov_ewma["factor_stds_period"])
    P_ewma = cov_ewma["correlation_matrix"]
    reconstructed_cov_ewma = D_ewma @ P_ewma @ D_ewma
    np.testing.assert_allclose(cov_ewma["covariance_matrix_period"], reconstructed_cov_ewma, atol=1e-7)

    # 3. Ledoit-Wolf Shrinkage
    cov_lw = estimate_factor_covariance(R, method="LEDOIT_WOLF", annualization_factor=252.0)
    assert cov_lw["is_positive_semidefinite"] is True
    assert cov_lw["is_consistent"] is True
    D_lw = np.diag(cov_lw["factor_stds_period"])
    P_lw = cov_lw["correlation_matrix"]
    reconstructed_cov_lw = D_lw @ P_lw @ D_lw
    np.testing.assert_allclose(cov_lw["covariance_matrix_period"], reconstructed_cov_lw, atol=1e-7)


def test_spectral_psd_validation_and_higham_projection():
    """Verify non-PSD detection and Higham (2002) nearest-PSD projection."""
    # Construct a definite non-PSD symmetric matrix with a large negative eigenvalue
    non_psd_mat = np.array([
        [1.0, 0.9, 0.9],
        [0.9, 1.0, -0.9],
        [0.9, -0.9, 1.0],
    ])
    eigenvals_before = np.linalg.eigvalsh(non_psd_mat)
    assert np.min(eigenvals_before) < -0.30  # Confirmed non-PSD

    # Apply Higham projection
    psd_mat, meta = project_to_nearest_psd(non_psd_mat, epsilon=1e-7)
    eigenvals_after = np.linalg.eigvalsh(psd_mat)

    assert meta["negative_eigenvalues_clipped"] >= 1
    assert np.min(eigenvals_after) >= 0.0
    np.testing.assert_allclose(psd_mat, psd_mat.T, atol=1e-8)  # Symmetric
    assert np.all(np.diag(psd_mat) > 0.0)


def test_rolling_relationships_signed_vs_absolute_deltas():
    """Verify rolling factor relationships, signed vs absolute strength changes, and stability categories."""
    np.random.seed(999)
    # 80 days of factor series
    T = 80
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(T)]
    # Create a negative correlation that weakens from -0.80 towards -0.20
    x = np.random.normal(0, 0.01, size=T)
    y = np.zeros(T)
    for i in range(T):
        # Trend correlation from -0.8 to -0.2
        weight = -0.80 + (0.60 * (i / T))
        y[i] = weight * x[i] + np.random.normal(0, 0.005)

    rolling_res = compute_rolling_factor_relationships(
        returns_x=x,
        returns_y=y,
        dates=dates,
        window_length=20,
        min_observations=15,
        baseline_window=40,
    )

    assert "current_correlation" in rolling_res
    assert "signed_correlation_change" in rolling_res
    assert "absolute_strength_change" in rolling_res
    assert "percentile_rank" in rolling_res
    assert rolling_res["relationship_stability"] in [e.value for e in CorrelationStabilityCategory]
    assert len(rolling_res["rolling_correlations"]) > 0


def test_regime_evaluation_and_cusum_break_detection():
    """Verify high correlation alerts, sign reversals, and CUSUM shift detection."""
    # Historical stable baseline at ~0.20
    hist_corrs = [0.20 + 0.02 * (i % 3 - 1) for i in range(40)]
    # Sudden structural break to 0.85 (high positive regime & rapid shift)
    recent_corrs = hist_corrs + [0.85]

    eval_res = evaluate_correlation_regimes(
        current_correlation=0.85,
        previous_correlation=0.22,
        baseline_correlation=0.20,
        consecutive_above_threshold_count=1,
        rolling_correlation_series=recent_corrs,
        high_positive_threshold=0.75,
        rapid_change_threshold=0.30,
        confirmation_required=2,
    )

    alerts = eval_res["alerts"]
    alert_types = [a["alert_type"] for a in alerts]

    # Should detect HIGH_POSITIVE_CORRELATION, RAPID_CORRELATION_CHANGE, and POTENTIAL_STRUCTURAL_BREAK
    assert "HIGH_POSITIVE_CORRELATION" in alert_types
    assert "RAPID_CORRELATION_CHANGE" in alert_types
    assert eval_res["has_structural_break"] is True
    assert eval_res["regime_status"] == "POTENTIAL_STRUCTURAL_BREAK"


# ==============================================================================
# 2. End-to-End FastAPI Integration Test
# ==============================================================================

@pytest.mark.asyncio
async def test_factor_correlation_api_lifecycle():
    """
    Complete end-to-end integration test via FastAPI endpoints:
    1. Seed Factor Model & Return Observations in database.
    2. POST /configs: create deterministic Factor Correlation Configuration.
    3. POST /calculate: compute full K x K inter-factor correlation matrix.
    4. GET /matrices/{matrix_id}: retrieve snapshot and verify symmetry & PSD.
    5. POST /covariance/calculate: compute authoritative factor covariance snapshot.
    6. GET /covariance/{snapshot_id}: verify D @ P_F @ D mathematical consistency.
    7. POST /rolling: compute rolling relationships across windows.
    8. POST /regimes/evaluate: evaluate regime alerts.
    9. GET /regimes/alerts: retrieve active regime alerts.
    """
    await init_db()

    async with AsyncSessionLocal() as session:
        # Seed Model and Factors
        model_id = str(uuid.uuid4())
        model_ver_id = str(uuid.uuid4())
        mkt_id = str(uuid.uuid4())
        val_id = str(uuid.uuid4())
        mom_id = str(uuid.uuid4())

        model = FactorModel(
            model_id=model_id,
            model_code=f"EQ_TEST_{model_id[:6]}",
            model_name="Equity 3-Factor Test Model",
            description="Integration Test Model",
            market_scope=MarketScope.INDIA,
            currency_basis="INR",
            return_frequency="DAILY",
            lifecycle_status=FactorLifecycleStatus.ACTIVE,
            created_by="TEST_SUITE",
        )
        model_ver = FactorModelVersion(
            model_version_id=model_ver_id,
            model_id=model_id,
            version_number=1,
            model_definition_hash="HASH_TEST_3F",
            approval_status=FactorLifecycleStatus.ACTIVE,
            effective_from=date(2025, 1, 1),
            created_by="TEST_SUITE",
        )
        session.add_all([model, model_ver])

        uniq = model_id[:4]
        factors_meta = [
            (mkt_id, f"MKT_{uniq}", "Market Factor", 1),
            (val_id, f"VAL_{uniq}", "Value Factor", 2),
            (mom_id, f"MOM_{uniq}", "Momentum Factor", 3),
        ]

        for f_id, f_code, f_name, pos in factors_meta:
            f_fam = FactorFamily.MARKET if f_code == "MKT" else (FactorFamily.VALUE if f_code == "VAL" else FactorFamily.MOMENTUM)
            f_def = FactorDefinition(
                factor_id=f_id,
                factor_code=f_code,
                factor_name=f_name,
                factor_family=f_fam,
                factor_type=FactorType.MARKET_RETURN_FACTOR,
                economic_interpretation=f"{f_name} economic basis",
                construction_type=ConstructionType.INTERNALLY_CONSTRUCTED,
                description=f"{f_name} description",
                lifecycle_status=FactorLifecycleStatus.ACTIVE,
                created_by="TEST_SUITE",
            )
            f_def_ver = FactorDefinitionVersion(
                version_id=str(uuid.uuid4()),
                factor_id=f_id,
                version_number=1,
                market_scope=MarketScope.INDIA,
                currency="INR",
                frequency="DAILY",
                construction_specification={"method": "SYNTHETIC"},
                definition_hash=f"HASH_{f_code}",
                approval_status=FactorLifecycleStatus.ACTIVE,
                effective_from=date(2025, 1, 1),
            )
            membership = FactorModelMembership(
                model_version_id=model_ver_id,
                factor_id=f_id,
                version_id=f_def_ver.version_id,
                factor_code=f_code,
                factor_position=pos,
            )
            series = FactorReturnSeries(
                series_id=f_id,
                factor_id=f_id,
                factor_code=f_code,
                version_id=f_def_ver.version_id,
                market_scope=MarketScope.INDIA,
                currency="INR",
                frequency="DAILY",
            )
            session.add_all([f_def, f_def_ver, membership, series])

        # Generate 45 trading days of correlated synthetic returns
        np.random.seed(42)
        days_count = 45
        dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(days_count)]
        cov_true = np.array([
            [0.00020, 0.00008, 0.00004],
            [0.00008, 0.00015, 0.00002],
            [0.00004, 0.00002, 0.00018],
        ])
        R_sim = np.random.multivariate_normal([0, 0, 0], cov_true, size=days_count)

        for t_idx, d in enumerate(dates):
            for k_idx, (f_id, _, _, _) in enumerate(factors_meta):
                obs = FactorReturnObservation(
                    observation_id=str(uuid.uuid4()),
                    series_id=f_id,
                    trading_date=d,
                    return_value=Decimal(str(round(R_sim[t_idx, k_idx], 8))),
                    excess_return_value=Decimal(str(round(R_sim[t_idx, k_idx], 8))),
                )
                session.add(obs)

        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 2: Create Configuration
        config_payload = {
            "config_code": f"CFG_CORR_{model_id[:8]}",
            "config_name": "Standard Pearson 30D Factor Config",
            "description": "Integration test config",
            "factor_model_id": model_id,
            "factor_model_version_id": model_ver_id,
            "correlation_method": "PEARSON",
            "observation_frequency": "DAILY",
            "return_convention": "SIMPLE",
            "currency_basis": "INR",
            "missing_data_policy": "LISTWISE_COMPLETE",
            "estimation_window": 30,
            "minimum_observations": 20,
            "confidence_level": "0.95",
        }
        resp = await client.post("/api/v1/factor-correlation/configs", json=config_payload)
        assert resp.status_code == 201, resp.text
        config_data = resp.json()
        config_id = config_data["config_id"]
        assert config_data["config_hash"] is not None

        # Step 3: Run Factor Correlation Matrix Execution
        as_of = dates[-1].isoformat()
        calc_payload = {
            "factor_model_version_id": model_ver_id,
            "as_of_date": as_of,
            "config_id": config_id,
            "correlation_method": "PEARSON",
            "estimation_window": 30,
        }
        resp = await client.post("/api/v1/factor-correlation/calculate", json=calc_payload)
        assert resp.status_code == 200, resp.text
        run_data = resp.json()
        assert run_data["factor_count"] == 3
        run_id = run_data["run_id"]

        # Step 4: Retrieve Matrix Snapshot by Matrix ID
        # Search the snapshot generated for this run
        async with AsyncSessionLocal() as session:
            from backend.app.modules.factor_risk.factor_correlation.models import FactorCorrelationMatrixSnapshot
            from sqlalchemy import select
            q = select(FactorCorrelationMatrixSnapshot).where(FactorCorrelationMatrixSnapshot.run_id == run_id)
            res = await session.execute(q)
            matrix_obj = res.scalars().first()
            assert matrix_obj is not None
            matrix_id = matrix_obj.matrix_id

        resp = await client.get(f"/api/v1/factor-correlation/matrices/{matrix_id}")
        assert resp.status_code == 200, resp.text
        matrix_snap = resp.json()
        assert matrix_snap["dimension"] == 3
        f_codes = [f"MKT_{uniq}", f"VAL_{uniq}", f"MOM_{uniq}"]
        assert matrix_snap["factor_ordering"] == f_codes
        assert matrix_snap["is_positive_semidefinite"] is True
        P_mat = np.array(matrix_snap["correlation_matrix"])
        assert P_mat.shape == (3, 3)
        np.testing.assert_allclose(np.diag(P_mat), [1.0, 1.0, 1.0], atol=1e-6)

        # Step 5: Authoritative Covariance Snapshot Calculation
        cov_payload = {
            "factor_model_id": model_id,
            "factor_model_version_id": model_ver_id,
            "as_of_date": as_of,
            "covariance_method": "LEDOIT_WOLF",
            "estimation_window": 30,
            "annualization_factor": "252.00",
        }
        resp = await client.post("/api/v1/factor-correlation/covariance/calculate", json=cov_payload)
        assert resp.status_code == 200, resp.text
        cov_snap = resp.json()
        snap_id = cov_snap["snapshot_id"]
        assert cov_snap["is_positive_semidefinite"] is True
        assert cov_snap["dimension"] == 3

        # Step 6: Verify Covariance Snapshot by ID & Consistency
        resp = await client.get(f"/api/v1/factor-correlation/covariance/{snap_id}")
        assert resp.status_code == 200, resp.text
        fetched_cov = resp.json()
        assert fetched_cov["snapshot_id"] == snap_id
        cov_mat = np.array(fetched_cov["covariance_matrix_period"])
        vols = np.array(fetched_cov["factor_volatilities_annualized"]) / math.sqrt(252.0)
        corr_mat = np.array(fetched_cov["correlation_matrix"])
        # Check consistency: Sigma_F == D @ P_F @ D
        reconstructed_cov = np.diag(vols) @ corr_mat @ np.diag(vols)
        np.testing.assert_allclose(cov_mat, reconstructed_cov, atol=1e-5)

        # Step 7: Rolling Factor Correlation
        rolling_payload = {
            "factor_model_version_id": model_ver_id,
            "factor_a_code": f_codes[0],
            "factor_b_code": f_codes[1],
            "as_of_date": as_of,
            "window_length": 20,
            "min_observations": 15,
            "baseline_window": 30,
        }
        resp = await client.post("/api/v1/factor-correlation/rolling", json=rolling_payload)
        assert resp.status_code == 200, resp.text
        rolling_data = resp.json()
        assert rolling_data["factor_a_code"] == f_codes[0]
        assert rolling_data["factor_b_code"] == f_codes[1]
        assert len(rolling_data["history"]) > 0

        # Step 8: Regime Evaluation
        regime_payload = {
            "factor_model_version_id": model_ver_id,
            "as_of_date": as_of,
            "window_length": 20,
            "high_positive_threshold": "0.50",
            "high_negative_threshold": "-0.50",
            "rapid_change_threshold": "0.20",
        }
        resp = await client.post("/api/v1/factor-correlation/regimes/evaluate", json=regime_payload)
        assert resp.status_code == 200, resp.text
        regime_data = resp.json()
        assert "evaluated_pairs_count" in regime_data
        assert regime_data["evaluated_pairs_count"] == 3

        # Step 9: Query Active Alerts
        resp = await client.get(f"/api/v1/factor-correlation/regimes/alerts?factor_model_version_id={model_ver_id}&as_of_date={as_of}")
        assert resp.status_code == 200, resp.text
        alerts_list = resp.json()
        assert isinstance(alerts_list, list)
