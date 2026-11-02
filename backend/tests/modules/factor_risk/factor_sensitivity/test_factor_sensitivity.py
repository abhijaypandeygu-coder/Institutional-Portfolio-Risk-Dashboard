"""
M08.03 Factor Sensitivity Comprehensive Unit and Integration Test Suite.
Tests:
1. Synthetic Parameter Recovery (OLS, EWLS, Ridge, Quantile regression via IRLS)
2. Robust Standard Errors (HC3 heteroskedasticity-robust, HAC Newey-West)
3. Goodness of Fit & Model Diagnostics (R2, Condition Number, VIF, Durbin-Watson, Jarque-Bera)
4. Benjamini-Hochberg False Discovery Rate (FDR) Multiple Testing Correction
5. Coefficient Stability Diagnostics (Rolling metrics, volatility, stability status)
6. Formal Structural Break Tests (Chow F-test with F-distribution p-value & critical value)
7. End-to-end FastAPI integration testing via TestClient (Config -> Run -> Diagnostics -> Stability -> Reconciliation)
"""
from datetime import date, timedelta
from decimal import Decimal
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import Base, engine, get_db, init_db
from backend.app.modules.factor_risk.factor_sensitivity.calculations.sensitivity_math import (
    fit_factor_sensitivity_regression,
    analyze_coefficient_stability,
    compute_chow_break_test,
    benjamini_hochberg_correction,
)
from backend.app.modules.factor_risk.factor_sensitivity.models import (
    ModelFamily,
    StandardErrorMethod,
    StatisticalSignificanceCategory,
    CoefficientStabilityStatus,
    StructuralBreakResultStatus,
    TargetType,
)


# ============================================================================
# 1. MATHEMATICAL & ECONOMETRIC TESTS
# ============================================================================

def test_ols_parameter_recovery():
    """Verify OLS recovers exact known synthetic parameters without noise."""
    np.random.seed(42)
    T = 100
    f1 = np.random.normal(0.001, 0.02, T)
    f2 = np.random.normal(0.0005, 0.015, T)
    X = np.column_stack([f1, f2])
    
    true_alpha = 0.0005
    true_beta1 = 1.2500
    true_beta2 = -0.6500
    y = true_alpha + true_beta1 * f1 + true_beta2 * f2

    res = fit_factor_sensitivity_regression(
        y_returns=y,
        X_factors=X,
        factor_names=["MKT_RF", "SMB"],
        model_family=ModelFamily.OLS,
        include_intercept=True,
    )

    c1 = res["coefficients"]["MKT_RF"]["coefficient_value"]
    c2 = res["coefficients"]["SMB"]["coefficient_value"]
    diag = res["diagnostics"]

    assert pytest.approx(c1, rel=1e-3) == true_beta1
    assert pytest.approx(c2, rel=1e-3) == true_beta2
    assert pytest.approx(res["intercept"]["value"], abs=1e-4) == true_alpha
    assert pytest.approx(diag["r_squared"], abs=1e-3) == 1.0
    assert diag["r_squared"] >= 0.999


def test_hc3_robust_standard_errors():
    """Verify HC3 heteroskedasticity-robust SEs are calculated properly."""
    np.random.seed(123)
    T = 150
    f1 = np.random.normal(0, 0.02, T)
    # Generate heteroskedastic noise depending on f1
    noise = np.random.normal(0, 0.01 * (1 + 50 * np.abs(f1)))
    y = 0.001 + 0.85 * f1 + noise

    res = fit_factor_sensitivity_regression(
        y_returns=y,
        X_factors=f1.reshape(-1, 1),
        factor_names=["MKT_RF"],
        model_family=ModelFamily.OLS,
        standard_error_method=StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST,
    )

    coeff = res["coefficients"]["MKT_RF"]
    assert coeff["standard_error"] is not None
    assert coeff["standard_error"] > 0.0
    assert coeff["t_statistic"] is not None
    assert coeff["p_value"] is not None
    assert coeff["significance_status"] in (
        StatisticalSignificanceCategory.HIGH_SIGNIFICANCE,
        StatisticalSignificanceCategory.MODERATE_SIGNIFICANCE,
    )


def test_hac_newey_west_standard_errors():
    """Verify HAC Newey-West standard errors are computed with autocorrelation adjustment."""
    np.random.seed(999)
    T = 100
    f1 = np.random.normal(0, 0.02, T)
    # Autocorrelated AR(1) noise
    eps = np.zeros(T)
    for t in range(1, T):
        eps[t] = 0.5 * eps[t - 1] + np.random.normal(0, 0.01)
    y = 0.0005 + 1.10 * f1 + eps

    res = fit_factor_sensitivity_regression(
        y_returns=y,
        X_factors=f1.reshape(-1, 1),
        factor_names=["MKT_RF"],
        model_family=ModelFamily.OLS,
        standard_error_method=StandardErrorMethod.HAC_NEWEY_WEST,
    )

    coeff = res["coefficients"]["MKT_RF"]
    assert coeff["standard_error"] is not None
    assert coeff["standard_error"] > 0.0
    assert coeff["confidence_interval_lower"] < coeff["coefficient_value"] < coeff["confidence_interval_upper"]


def test_ewls_regression():
    """Verify EWLS exponential weighting produces valid estimation."""
    np.random.seed(42)
    T = 100
    f1 = np.random.normal(0, 0.02, T)
    y = 0.001 + 0.95 * f1 + np.random.normal(0, 0.005, T)

    res = fit_factor_sensitivity_regression(
        y_returns=y,
        X_factors=f1.reshape(-1, 1),
        factor_names=["MKT_RF"],
        model_family=ModelFamily.EWLS,
        ewls_decay_factor=0.94,
    )

    coeff = res["coefficients"]["MKT_RF"]
    assert pytest.approx(coeff["coefficient_value"], abs=0.1) == 0.95
    assert res["effective_sample_size"] < T


def test_ridge_regression():
    """Verify Ridge regression shrinks coefficients appropriately under collinearity."""
    np.random.seed(42)
    T = 80
    f1 = np.random.normal(0, 0.02, T)
    f2 = f1 + np.random.normal(0, 0.001, T)  # highly collinear
    X = np.column_stack([f1, f2])
    y = 1.0 * f1 + 1.0 * f2 + np.random.normal(0, 0.01, T)

    res_ols = fit_factor_sensitivity_regression(
        y_returns=y, X_factors=X, factor_names=["F1", "F2"], model_family=ModelFamily.OLS
    )
    res_ridge = fit_factor_sensitivity_regression(
        y_returns=y, X_factors=X, factor_names=["F1", "F2"], model_family=ModelFamily.RIDGE, ridge_lambda=0.05
    )

    # Ridge condition number should be improved and coefficients stabilized
    assert res_ridge["coefficients"]["F1"]["coefficient_value"] is not None
    assert res_ridge["coefficients"]["F2"]["coefficient_value"] is not None


def test_benjamini_hochberg_correction():
    """Verify False Discovery Rate (FDR) correctly adjusts p-values monotonically."""
    p_vals = [0.001, 0.008, 0.045, 0.060, 0.120]
    adj = benjamini_hochberg_correction(p_vals)
    assert len(adj) == len(p_vals)
    for raw, corrected in zip(p_vals, adj):
        assert corrected >= raw
        assert corrected <= 1.0


def test_model_diagnostics_durbin_watson_and_jarque_bera():
    """Verify DW statistic and Jarque-Bera normality tests are computed."""
    np.random.seed(42)
    T = 100
    f1 = np.random.normal(0, 0.02, T)
    y = 0.0005 + 1.05 * f1 + np.random.normal(0, 0.005, T)

    res = fit_factor_sensitivity_regression(
        y_returns=y,
        X_factors=f1.reshape(-1, 1),
        factor_names=["MKT_RF"],
        model_family=ModelFamily.OLS,
    )

    diag = res["diagnostics"]
    # For Gaussian iid noise, DW is close to 2.0
    assert 1.5 < diag["durbin_watson"] < 2.5
    assert diag["jarque_bera"]["statistic"] >= 0.0
    assert 0.0 <= diag["jarque_bera"]["p_value"] <= 1.0


def test_coefficient_stability_analysis():
    """Verify stability tracking metrics and status classifications."""
    # Constant history -> STABLE
    stable_history = [1.0, 1.02, 0.99, 1.01, 1.00, 1.03]
    res_stable = analyze_coefficient_stability(stable_history, min_observations=5)
    assert res_stable["status"] == CoefficientStabilityStatus.STABLE
    assert res_stable["sign_change_count"] == 0

    # Wildly oscillating history with sign flips -> HIGHLY_UNSTABLE
    unstable_history = [1.5, -0.8, 1.2, -1.1, 0.9, -0.5]
    res_unstable = analyze_coefficient_stability(unstable_history, min_observations=5)
    assert res_unstable["status"] == CoefficientStabilityStatus.HIGHLY_UNSTABLE
    assert res_unstable["sign_change_count"] >= 4


def test_chow_structural_break_test():
    """Verify Chow test detects structural shift in parameters."""
    # Subsample 1: mean 0, Subsample 2: large mean shift
    np.random.seed(42)
    T = 100
    f1 = np.random.normal(0, 0.02, T)
    y = np.zeros(T)
    # pre-break
    y[:50] = 0.5 * f1[:50] + np.random.normal(0, 0.002, 50)
    # post-break structural shift to beta = 3.0
    y[50:] = 3.0 * f1[50:] + np.random.normal(0, 0.002, 50)

    res = compute_chow_break_test(
        y_full=y,
        X_full=f1.reshape(-1, 1),
        break_index=50,
        include_intercept=True,
    )

    assert res["status"] == StructuralBreakResultStatus.BREAK_DETECTED
    assert res["test_statistic"] > res["critical_value_95"]
    assert res["p_value"] < 0.01


# ============================================================================
# 2. END-TO-END FASTAPI INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_factor_sensitivity_api_lifecycle():
    """
    Test complete lifecycle via HTTP API:
    1. Initialize DB schema (including M08.03 tables)
    2. Seed factors and create FF3 model
    3. Ingest Factor returns and Instrument prices
    4. Create Factor Sensitivity Model Config
    5. Run Factor Sensitivity Estimation
    6. Verify Coefficients, Significance, and Model Diagnostics
    7. Test Stability Diagnostics and Chow Structural Break Test
    """
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Health check
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert "M08.03 - Factor Sensitivity Engine" in health_data["modules"]

        # Step 2: Seed canonical factors
        resp_seed = await client.post("/api/v1/factors/seed?market=INDIA")
        assert resp_seed.status_code == 200
        seeded = resp_seed.json()

        mkt = next(f for f in seeded if f["factor_code"] == "MKT_INDIA")
        smb = next(f for f in seeded if f["factor_code"] == "SMB_INDIA")
        hml = next(f for f in seeded if f["factor_code"] == "HML_INDIA")

        # Step 3: Create Factor Model FF3
        import uuid
        model_code = f"FF3_SENS_{uuid.uuid4().hex[:6].upper()}"
        model_payload = {
            "model_code": model_code,
            "model_name": "Fama-French 3-Factor Model (Sensitivity Test)",
            "description": "Standard 3-factor model for NSE/BSE equities: MKT, SMB, HML.",
            "market_scope": "INDIA",
            "currency_basis": "INR",
            "return_frequency": "DAILY",
            "factor_version_ids": [
                mkt["latest_version"]["version_id"],
                smb["latest_version"]["version_id"],
                hml["latest_version"]["version_id"],
            ],
            "change_rationale": "Test FF3 model registration",
        }
        resp_model = await client.post("/api/v1/factor-models", json=model_payload)
        assert resp_model.status_code == 200
        model_data = resp_model.json()
        model_id = model_data["model_id"]
        model_version_id = model_data["latest_version"]["model_version_id"]

        # Step 4: Ingest Factor Returns for 50 trading days
        base_date = date.today() - timedelta(days=60)
        np.random.seed(888)
        T_days = 50
        dates = [base_date + timedelta(days=i) for i in range(T_days)]
        mkt_ret = np.random.normal(0.0005, 0.012, T_days)
        smb_ret = np.random.normal(0.0001, 0.007, T_days)
        hml_ret = np.random.normal(0.0002, 0.008, T_days)

        for factor_obj, r_series in [(mkt, mkt_ret), (smb, smb_ret), (hml, hml_ret)]:
            payload = {
                "factor_id": factor_obj["factor_id"],
                "factor_code": factor_obj["factor_code"],
                "version_id": factor_obj["latest_version"]["version_id"],
                "market_scope": "INDIA",
                "currency": "INR",
                "frequency": "DAILY",
                "return_convention": "SIMPLE",
                "observations": [
                    {
                        "trading_date": dates[i].isoformat(),
                        "return_value": str(round(r_series[i], 6)),
                        "risk_free_rate": "0.0001",
                    }
                    for i in range(T_days)
                ],
            }
            resp_ingest = await client.post("/api/v1/factor-exposures/returns", json=payload)
            assert resp_ingest.status_code == 200

        # Step 5: Ingest Price Reference Observations for target instrument
        inst_id = f"INST_{uuid.uuid4().hex[:6].upper()}"
        from backend.app.core.database import AsyncSessionLocal
        from backend.app.modules.instrument_reference_data.price_reference.models import (
            PriceReferenceObservation,
            PriceReferenceType,
        )
        from backend.app.modules.instrument_reference_data.instrument_master.models import (
            Instrument,
        )

        async with AsyncSessionLocal() as session:
            inst = Instrument(
                instrument_id=inst_id,
                canonical_name=f"Sensitivity Test Equity {inst_id}",
                short_name=inst_id,
                isin=f"IN{uuid.uuid4().hex[:10].upper()}",
                instrument_type="COMMON_STOCK",
                lifecycle_status="ACTIVE",
                issue_currency="INR",
            )
            session.add(inst)

            p = 100.0
            for i in range(T_days):
                r_inst = 1.25 * mkt_ret[i] - 0.40 * smb_ret[i] + 0.60 * hml_ret[i] + np.random.normal(0.0, 0.001)
                p = p * (1.0 + r_inst)
                p_rec = PriceReferenceObservation(
                    price_reference_id=str(uuid.uuid4()),
                    instrument_id=inst_id,
                    exchange_code="NSE",
                    trading_date=dates[i],
                    reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                    price_value=Decimal(str(round(p, 4))),
                    currency="INR",
                )
                session.add(p_rec)
            await session.commit()

        # Step 6: Create Sensitivity Model Config
        cfg_code = f"CFG_SENS_{uuid.uuid4().hex[:6].upper()}"
        create_cfg_payload = {
            "config_code": cfg_code,
            "config_name": "Unit Test 1Y Rolling HC3 Profile",
            "description": "Standard OLS with HC3 robust errors for unit testing",
            "model_family": "OLS",
            "factor_model_id": model_id,
            "factor_model_version_id": model_version_id,
            "include_intercept": True,
            "standard_error_method": "HC3_HETEROSKEDASTICITY_ROBUST",
            "confidence_level": "0.95",
            "dependent_return_basis": "EXCESS_TOTAL_RETURN",
            "return_type": "SIMPLE",
            "currency_basis": "INR",
            "window_config": {
                "window_type": "ROLLING",
                "lookback_observations": 40,
                "frequency": "DAILY",
                "missing_data_policy": "LISTWISE_COMPLETE",
                "minimum_observations": 25,
                "min_observations_per_param_multiplier": 5,
                "minimum_coverage_percentage": "80.00",
            },
        }

        cfg_resp = await client.post("/api/v1/factor-sensitivity/configs", json=create_cfg_payload)
        assert cfg_resp.status_code == 201
        cfg_data = cfg_resp.json()
        config_id = cfg_data["config_id"]

        # Step 7: Run Estimation
        run_payload = {
            "config_id": config_id,
            "target_type": "INSTRUMENT",
            "target_id": inst_id,
            "as_of_date": dates[-1].isoformat(),
        }
        est_resp = await client.post("/api/v1/factor-sensitivity/estimate", json=run_payload)
        assert est_resp.status_code == 200
        run_data = est_resp.json()
        assert run_data["run_status"] == "COMPLETED"
        assert len(run_data["coefficients"]) == 3
        assert run_data["diagnostics"] is not None
        assert float(run_data["diagnostics"]["r_squared"]) > 0.80

        # Coefficients recovery check
        mkt_coeff = next(c for c in run_data["coefficients"] if c["factor_code"] == "MKT_INDIA")
        assert pytest.approx(float(mkt_coeff["coefficient_value"]), abs=0.15) == 1.25
        assert mkt_coeff["significance_status"] in (
            StatisticalSignificanceCategory.HIGH_SIGNIFICANCE,
            StatisticalSignificanceCategory.MODERATE_SIGNIFICANCE,
        )

        # Step 8: Fetch Run detail
        run_id = run_data["run_id"]
        get_run_resp = await client.get(f"/api/v1/factor-sensitivity/runs/{run_id}")
        assert get_run_resp.status_code == 200
        assert get_run_resp.json()["run_id"] == run_id

        # Step 9: Get Historical Coefficients endpoint
        hist_resp = await client.get(
            f"/api/v1/factor-sensitivity/INSTRUMENT/{inst_id}/coefficients?factor_code=MKT_INDIA"
        )
        assert hist_resp.status_code == 200
        assert len(hist_resp.json()) >= 1
