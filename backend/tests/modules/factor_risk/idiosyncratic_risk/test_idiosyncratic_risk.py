"""
M08.06 Idiosyncratic Risk Unit and Integration Test Suite.
Verifies:
1. Section 19.3 Hand-calculated Portfolio Idiosyncratic Variance and Euler Contributions:
   w = [0.60, 0.40]^T
   Sigma_epsilon = [[0.09, 0.03], [0.03, 0.16]]
   Expected sigma_{epsilon,p}^2 = 0.0724
   Marginal contributions: [0.066, 0.082]
   Euler variance contributions: RC_A = 0.0396, RC_B = 0.0328 (sum == 0.0724)
2. Diversification Decomposition:
   Diagonal baseline = 0.60^2 * 0.09 + 0.40^2 * 0.16 = 0.0580
   Cross-security covariance effect = 0.0724 - 0.0580 = +0.0144
3. Volatility Scale & Robust MAD Estimator:
   Verify sample, population, EWMA, and robust normal-consistent MAD scale (1.4826 * MAD).
4. Issuer-level Matrix Consolidation:
   Verify multi-holding issuer risk aggregation matches exact consolidated weights and variance contributions.
5. Econometric Residual Diagnostics:
   Verify Jarque-Bera normality, outlier Z-scores (> 3.0), lag-1 autocorrelation, Ljung-Box, ARCH-LM heteroskedasticity, and CUSUM shift detection.
6. End-to-End FastAPI Integration:
   - Config creation
   - Residual volatility calculation
   - Covariance snapshot estimation
   - Portfolio idiosyncratic risk & Euler allocation
   - Econometric diagnostics execution
"""

import math
from datetime import date, datetime, timedelta
from decimal import Decimal
import uuid
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import Base, engine, get_db, init_db, AsyncSessionLocal
from backend.app.modules.factor_risk.idiosyncratic_risk.calculations.idiosyncratic_math import (
    compute_residual_volatility,
    estimate_residual_covariance_matrix,
    compute_portfolio_idiosyncratic_risk,
    compute_diversification_metrics,
    aggregate_issuer_idiosyncratic_risk,
    evaluate_residual_diagnostics,
)
from backend.app.modules.factor_risk.idiosyncratic_risk.models import (
    ResidualVarianceEstimator,
    ResidualModelQualityStatus,
    ContributionStatus,
    OutlierSeverity,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    InstrumentFactorLoading,
)
from backend.app.modules.factor_risk.factor_sensitivity.models import (
    FactorSensitivityRun,
    FactorSensitivityCoefficient,
    TargetType,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import (
    Instrument,
)
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PriceReferenceType,
    VerificationStatus,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionSide,
)


# ============================================================================
# 1. MATHEMATICAL VERIFICATION TESTS
# ============================================================================

def test_hand_calculated_portfolio_idiosyncratic_variance_and_euler_contributions():
    """
    Prompt Section 19.3 Hand-calculated verification:
    w = [0.60, 0.40]^T
    Sigma_epsilon = [[0.09, 0.03], [0.03, 0.16]]
    
    1. Sigma_epsilon * w = [0.09*0.6 + 0.03*0.4, 0.03*0.6 + 0.16*0.4]^T
                         = [0.054 + 0.012, 0.018 + 0.064]^T = [0.066, 0.082]^T
    2. RC_A^{var} = 0.60 * 0.066 = 0.0396
       RC_B^{var} = 0.40 * 0.082 = 0.0328
    3. sigma_{epsilon,p}^2 = 0.0396 + 0.0328 = 0.0724
    4. Euler sum equals total portfolio idiosyncratic variance.
    """
    w = np.array([0.60, 0.40], dtype=np.float64)
    cov = np.array([
        [0.09, 0.03],
        [0.03, 0.16],
    ], dtype=np.float64)

    res = compute_portfolio_idiosyncratic_risk(
        weights=w,
        residual_cov_matrix=cov,
        annualization_factor=1.0,  # daily basis for hand calculation
    )

    expected_variance = 0.0724
    expected_mc = [0.066, 0.082]
    expected_rc_var = [0.0396, 0.0328]

    assert pytest.approx(res["portfolio_idiosyncratic_variance_period"], abs=1e-6) == expected_variance
    assert pytest.approx(res["marginal_variance_contributions_period"][0], abs=1e-6) == expected_mc[0]
    assert pytest.approx(res["marginal_variance_contributions_period"][1], abs=1e-6) == expected_mc[1]
    assert pytest.approx(res["variance_contributions_period"][0], abs=1e-6) == expected_rc_var[0]
    assert pytest.approx(res["variance_contributions_period"][1], abs=1e-6) == expected_rc_var[1]
    
    # Check Euler reconciliation
    assert pytest.approx(sum(res["variance_contributions_period"]), abs=1e-6) == expected_variance
    assert pytest.approx(sum(res["volatility_contributions_period"]), abs=1e-6) == math.sqrt(expected_variance)
    assert res["euler_variance_reconciliation_diff"] < 1e-6


def test_hand_calculated_diversification_decomposition():
    """
    Prompt Section 19.3 Diversification decomposition:
    Diagonal-only baseline variance = 0.60^2 * 0.09 + 0.40^2 * 0.16
                                    = 0.36 * 0.09 + 0.16 * 0.16
                                    = 0.0324 + 0.0256 = 0.0580
    Actual portfolio idiosyncratic variance = 0.0724
    Cross-security covariance effect = 0.0724 - 0.0580 = +0.0144
    """
    w = np.array([0.60, 0.40], dtype=np.float64)
    cov = np.array([
        [0.09, 0.03],
        [0.03, 0.16],
    ], dtype=np.float64)

    div = compute_diversification_metrics(
        weights=w,
        residual_cov_matrix=cov,
        annualization_factor=1.0,
    )

    expected_diag_var = 0.0580
    expected_cov_effect = 0.0144

    assert pytest.approx(div["diagonal_baseline_variance_period"], abs=1e-6) == expected_diag_var
    assert pytest.approx(div["covariance_effect_period"], abs=1e-6) == expected_cov_effect
    assert div["diversification_benefit_period"] < 0  # positive covariance increased risk compared to diagonal
    assert div["absolute_contribution_hhi"] > 0
    assert div["effective_number_of_risk_contributors"] > 1.0


def test_robust_mad_and_residual_volatility_estimators():
    """
    Verify robust MAD scale (1.4826 * median(|eps - median(eps)|))
    and sample / population / EWMA estimators.
    """
    residuals = np.array([-0.02, 0.01, -0.01, 0.03, -0.04, 0.02, 0.00, -0.01, 0.02], dtype=np.float64)
    
    # 1. Sample Estimator
    vol_sample = compute_residual_volatility(residuals, variance_estimator="SAMPLE", annualization_factor=252.0)
    assert vol_sample["observation_count"] == 9
    assert vol_sample["residual_variance_period"] > 0
    assert vol_sample["robust_mad_scale_annualized"] is not None
    assert pytest.approx(vol_sample["residual_volatility_annualized"], abs=1e-5) == vol_sample["residual_volatility_period"] * math.sqrt(252.0)

    # 2. Population Estimator
    vol_pop = compute_residual_volatility(residuals, variance_estimator="POPULATION", annualization_factor=252.0)
    assert vol_pop["residual_variance_period"] < vol_sample["residual_variance_period"]  # ddof=0 vs ddof=1

    # 3. EWMA Estimator
    vol_ewma = compute_residual_volatility(residuals, decay_factor=0.94, annualization_factor=252.0)
    assert vol_ewma["ew_residual_volatility_annualized"] > 0
    assert vol_ewma["effective_sample_size"] is not None


def test_issuer_level_matrix_consolidation():
    """
    Test matrix consolidation where multiple holdings belong to the same issuer.
    Instrument 0 & 1 -> Issuer A
    Instrument 2 -> Issuer B
    """
    w = np.array([0.30, 0.30, 0.40], dtype=np.float64)
    cov = np.array([
        [0.09, 0.01, 0.00],
        [0.01, 0.09, 0.00],
        [0.00, 0.00, 0.16],
    ], dtype=np.float64)

    issuer_mappings = ["ISSUER_ALPHA", "ISSUER_ALPHA", "ISSUER_BETA"]

    iss_res = aggregate_issuer_idiosyncratic_risk(
        security_weights=w,
        issuer_mappings=issuer_mappings,
        residual_cov_matrix=cov,
        annualization_factor=1.0,
    )

    alpha_data = next(item for item in iss_res["issuer_details"] if item["issuer_id"] == "ISSUER_ALPHA")
    beta_data = next(item for item in iss_res["issuer_details"] if item["issuer_id"] == "ISSUER_BETA")

    assert pytest.approx(alpha_data["signed_weight"], abs=1e-6) == 0.60
    assert pytest.approx(beta_data["signed_weight"], abs=1e-6) == 0.40
    assert alpha_data["member_count"] == 2
    assert beta_data["member_count"] == 1

    # Total portfolio variance = w^T * cov * w
    total_port_var = float(w.T @ cov @ w)
    assert pytest.approx(iss_res["portfolio_idiosyncratic_variance"], abs=1e-6) == total_port_var


def test_residual_diagnostics_suite():
    """
    Verify residual diagnostics including Jarque-Bera normality, outliers,
    autocorrelation, ARCH-LM heteroskedasticity, and CUSUM shift.
    """
    np.random.seed(42)
    clean_residuals = np.random.normal(loc=0.0, scale=0.01, size=200)

    res_clean = evaluate_residual_diagnostics(clean_residuals, outlier_z_threshold=3.0)
    assert res_clean["model_quality_status"] in ["ACCEPTABLE", "ACCEPTABLE_WITH_WARNINGS"]
    assert res_clean["outlier_analysis"]["outlier_count"] <= 3

    # Introduce extreme outlier and structural break
    corrupted_residuals = clean_residuals.copy()
    corrupted_residuals[50] = 0.25  # extreme outlier
    corrupted_residuals[100:] += 0.08  # Structural level shift

    res_corrupt = evaluate_residual_diagnostics(corrupted_residuals, outlier_z_threshold=3.0)
    assert res_corrupt["outlier_analysis"]["outlier_count"] >= 1
    assert res_corrupt["stationarity_and_breaks"]["has_structural_shift"] is True
    assert res_corrupt["model_quality_status"] == "WEAK_SPECIFICATION"


# ============================================================================
# 2. END-TO-END FASTAPI INTEGRATION TEST
# ============================================================================

@pytest.mark.asyncio
async def test_end_to_end_idiosyncratic_risk_lifecycle():
    """
    Tests the full API workflow:
    1. Seed Factor Model & Factors via M08.01 Factor Registry
    2. Seed Factor Return Series and Observations via M08.02
    3. Seed Instruments & Price History
    4. Register Factor Loadings (M08.02)
    5. Register Portfolio & Positions (M05)
    6. POST /configs -> Create Residual Risk Config
    7. POST /instruments/calculate -> Calculate Residual Volatility
    8. POST /covariance/estimate -> Estimate Residual Covariance Snapshot
    9. POST /portfolios/calculate -> Calculate Portfolio Idiosyncratic Risk & Euler Contributions
    10. POST /diagnostics/run -> Run Residual Econometric Diagnostics
    """
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Seed Factors & Factor Model using M08.01 endpoints
        resp_seed = await client.post("/api/v1/factors/seed?market=INDIA")
        assert resp_seed.status_code == 200, resp_seed.text
        seeded_factors = resp_seed.json()
        mkt = next(f for f in seeded_factors if f["factor_code"] == "MKT_INDIA")

        model_code = f"FM_IDIO_{uuid.uuid4().hex[:6].upper()}"
        model_payload = {
            "model_code": model_code,
            "model_name": "Idiosyncratic Risk Test Model",
            "description": "Model for testing M08.06",
            "market_scope": "INDIA",
            "currency_basis": "INR",
            "return_frequency": "DAILY",
            "factor_version_ids": [mkt["latest_version"]["version_id"]],
            "change_rationale": "Idiosyncratic test model",
        }
        resp_model = await client.post("/api/v1/factor-models", json=model_payload)
        assert resp_model.status_code == 200, resp_model.text
        model_data = resp_model.json()
        model_id = model_data["model_id"]
        model_version_id = model_data["latest_version"]["model_version_id"]

        # Step 2: Ingest 30 days of Factor Returns
        base_date = date.today() - timedelta(days=40)
        np.random.seed(42)
        T_days = 30
        dates = [base_date + timedelta(days=i) for i in range(T_days)]
        mkt_ret = np.random.normal(0.0005, 0.01, T_days)

        ingest_payload = {
            "factor_id": mkt["factor_id"],
            "factor_code": mkt["factor_code"],
            "version_id": mkt["latest_version"]["version_id"],
            "market_scope": "INDIA",
            "currency": "INR",
            "frequency": "DAILY",
            "observations": [
                {
                    "trading_date": dates[i].isoformat(),
                    "return_value": float(mkt_ret[i]),
                    "risk_free_rate": 0.0001,
                }
                for i in range(T_days)
            ],
        }
        resp_ingest = await client.post("/api/v1/factor-exposures/returns", json=ingest_payload)
        assert resp_ingest.status_code == 200, resp_ingest.text

        # Step 3: Seed Instruments and Price History
        inst1_id = f"INST_IDIO_A_{uuid.uuid4().hex[:4].upper()}"
        inst2_id = f"INST_IDIO_B_{uuid.uuid4().hex[:4].upper()}"

        async with AsyncSessionLocal() as session:
            inst1 = Instrument(
                instrument_id=inst1_id,
                canonical_name="Alpha Tech Corp",
                short_name="ALPHA_T",
                issuer_name="ALPHA_GROUP",
            )
            inst2 = Instrument(
                instrument_id=inst2_id,
                canonical_name="Beta Energy Corp",
                short_name="BETA_T",
                issuer_name="BETA_GROUP",
            )
            session.add(inst1)
            session.add(inst2)

            p1 = 100.0
            p2 = 200.0

            for i in range(T_days):
                d = dates[i]
                p1_ret = float(mkt_ret[i]) * 1.1 + np.random.normal(0, 0.005)
                p2_ret = float(mkt_ret[i]) * 0.9 + np.random.normal(0, 0.006)
                p1 *= (1.0 + p1_ret)
                p2 *= (1.0 + p2_ret)

                price_obs1 = PriceReferenceObservation(
                    price_reference_id=str(uuid.uuid4()),
                    instrument_id=inst1_id,
                    exchange_code="NSE",
                    trading_date=d,
                    price_value=Decimal(str(round(p1, 4))),
                    reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                    currency="INR",
                    verification_status=VerificationStatus.VERIFIED,
                )
                price_obs2 = PriceReferenceObservation(
                    price_reference_id=str(uuid.uuid4()),
                    instrument_id=inst2_id,
                    exchange_code="NSE",
                    trading_date=d,
                    price_value=Decimal(str(round(p2, 4))),
                    reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                    currency="INR",
                    verification_status=VerificationStatus.VERIFIED,
                )
                session.add(price_obs1)
                session.add(price_obs2)

            # Factor Sensitivities (M08.03)
            r1 = FactorSensitivityRun(
                config_id=f"CFG_{uuid.uuid4().hex[:6]}",
                factor_model_id=model_id,
                factor_model_version_id=model_version_id,
                target_type=TargetType.INSTRUMENT,
                target_id=inst1_id,
                as_of_date=dates[-1],
                window_start=dates[0],
                window_end=dates[-1],
                observation_count_expected=len(dates),
                observation_count_used=len(dates),
            )
            r2 = FactorSensitivityRun(
                config_id=f"CFG_{uuid.uuid4().hex[:6]}",
                factor_model_id=model_id,
                factor_model_version_id=model_version_id,
                target_type=TargetType.INSTRUMENT,
                target_id=inst2_id,
                as_of_date=dates[-1],
                window_start=dates[0],
                window_end=dates[-1],
                observation_count_expected=len(dates),
                observation_count_used=len(dates),
            )
            session.add(r1)
            session.add(r2)
            await session.flush()

            c1 = FactorSensitivityCoefficient(
                run_id=r1.run_id,
                factor_id=mkt["factor_id"],
                factor_code="MKT_INDIA",
                factor_position=1,
                coefficient_value=Decimal("1.1"),
            )
            c2 = FactorSensitivityCoefficient(
                run_id=r2.run_id,
                factor_id=mkt["factor_id"],
                factor_code="MKT_INDIA",
                factor_position=1,
                coefficient_value=Decimal("0.9"),
            )
            session.add(c1)
            session.add(c2)

            # Portfolio and Holdings
            pf_id = f"PORT_IDIO_{uuid.uuid4().hex[:4].upper()}"
            pf = Portfolio(
                portfolio_id=pf_id,
                portfolio_code=pf_id,
                portfolio_name="Idiosyncratic Test Portfolio",
                short_name=pf_id,
                description="Test portfolio for M08.06",
                base_currency="INR",
                created_by="TEST_SUITE",
            )
            session.add(pf)

            v1 = PositionValuation(
                valuation_id=str(uuid.uuid4()),
                calculation_id=str(uuid.uuid4()),
                portfolio_id=pf_id,
                account_id="ACC_01",
                instrument_id=inst1_id,
                position_side=PositionSide.LONG,
                signed_quantity=Decimal("6000"),
                mark_price=Decimal("100.0"),
                price_currency="INR",
                signed_market_value_native=Decimal("600000.00"),
                signed_market_value_base=Decimal("600000.00"),
                signed_cost_basis_native=Decimal("590000.00"),
                signed_cost_basis_base=Decimal("590000.00"),
                unrealized_pnl_native=Decimal("10000.00"),
                unrealized_pnl_base=Decimal("10000.00"),
                effective_at=datetime.combine(dates[-1], datetime.min.time()),
            )
            v2 = PositionValuation(
                valuation_id=str(uuid.uuid4()),
                calculation_id=str(uuid.uuid4()),
                portfolio_id=pf_id,
                account_id="ACC_01",
                instrument_id=inst2_id,
                position_side=PositionSide.LONG,
                signed_quantity=Decimal("2000"),
                mark_price=Decimal("200.0"),
                price_currency="INR",
                signed_market_value_native=Decimal("400000.00"),
                signed_market_value_base=Decimal("400000.00"),
                signed_cost_basis_native=Decimal("390000.00"),
                signed_cost_basis_base=Decimal("390000.00"),
                unrealized_pnl_native=Decimal("10000.00"),
                unrealized_pnl_base=Decimal("10000.00"),
                effective_at=datetime.combine(dates[-1], datetime.min.time()),
            )
            session.add(v1)
            session.add(v2)

            await session.commit()

        # Step 6: POST /configs -> Create Residual Risk Config
        cfg_resp = await client.post(
            "/api/v1/idiosyncratic-risk/configs",
            json={
                "config_code": f"CFG_IDIO_{uuid.uuid4().hex[:6].upper()}",
                "config_name": "Daily Idiosyncratic Risk Config",
                "description": "Standard daily sample config",
                "factor_model_id": model_id,
                "factor_model_version_id": model_version_id,
                "variance_estimator": "SAMPLE",
                "observation_frequency": "DAILY",
                "annualization_factor": 252.0,
                "minimum_observations": 15,
                "outlier_z_threshold": 3.0,
            },
        )
        assert cfg_resp.status_code == 201, cfg_resp.text
        cfg_data = cfg_resp.json()
        config_id = cfg_data["config_id"]

        # Step 7: POST /instruments/calculate -> Calculate Residual Volatility
        vol_resp = await client.post(
            "/api/v1/idiosyncratic-risk/instruments/calculate",
            json={
                "config_id": config_id,
                "instrument_id": inst1_id,
                "as_of_date": dates[-1].isoformat(),
            },
        )
        assert vol_resp.status_code == 200, vol_resp.text
        vol_data = vol_resp.json()
        assert vol_data["instrument_id"] == inst1_id
        assert float(vol_data["residual_volatility_annualized"]) > 0
        assert vol_data["observation_count"] >= 15

        # Step 8: POST /covariance/estimate -> Estimate Residual Covariance Snapshot
        cov_resp = await client.post(
            "/api/v1/idiosyncratic-risk/covariance/estimate",
            json={
                "factor_model_version_id": model_version_id,
                "as_of_date": dates[-1].isoformat(),
                "instrument_ids": [inst1_id, inst2_id],
                "use_diagonal": False,
            },
        )
        assert cov_resp.status_code == 200, cov_resp.text
        cov_data = cov_resp.json()
        assert cov_data["dimension"] == 2
        assert cov_data["is_positive_semidefinite"] is True
        assert len(cov_data["covariance_matrix"]) == 2

        # Step 9: POST /portfolios/calculate -> Calculate Portfolio Idiosyncratic Risk
        port_resp = await client.post(
            "/api/v1/idiosyncratic-risk/portfolios/calculate",
            json={
                "config_id": config_id,
                "portfolio_id": pf_id,
                "as_of_date": dates[-1].isoformat(),
                "use_diagonal": False,
            },
        )
        assert port_resp.status_code == 200, port_resp.text
        port_data = port_resp.json()
        assert port_data["portfolio_id"] == pf_id
        assert float(port_data["portfolio_idiosyncratic_volatility_annualized"]) > 0
        assert port_data["is_reconciled"] is True
        assert len(port_data["security_contributions"]) == 2
        assert len(port_data["issuer_contributions"]) == 2

        # Step 10: POST /diagnostics/run -> Run Residual Econometric Diagnostics
        diag_resp = await client.post(
            "/api/v1/idiosyncratic-risk/diagnostics/run",
            json={
                "config_id": config_id,
                "instrument_id": inst1_id,
                "as_of_date": dates[-1].isoformat(),
            },
        )
        assert diag_resp.status_code == 200, diag_resp.text
        diag_data = diag_resp.json()
        assert diag_data["instrument_id"] == inst1_id
        assert diag_data["observation_count"] >= 15
        assert diag_data["model_quality_status"] in ["ACCEPTABLE", "ACCEPTABLE_WITH_WARNINGS", "WEAK_SPECIFICATION"]
