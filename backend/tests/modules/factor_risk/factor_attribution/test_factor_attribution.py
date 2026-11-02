"""
M08.04 Factor Attribution Unit and Integration Test Suite.
Verifies:
1. Hand-calculated single-period Factor Return Attribution (Prompt Section 18.1):
   - Beta1 = 1.20, F1 = 0.02 -> C1 = 0.024 (+2.4%)
   - Beta2 = -0.30, F2 = 0.01 -> C2 = -0.003 (-0.3%)
2. Multi-period Carino Linking Engine:
   - R_cum = prod(1 + R_t) - 1
   - sum_j C_{j,cum} == R_cum within floating point tolerance
   - Continuous limits for zero and near-zero returns
3. Hand-calculated Factor Covariance & Systematic Risk (Prompt Section 18.3):
   - beta = [1.0, 0.5]^T
   - Sigma_F = [[0.04, 0.01], [0.01, 0.09]]
   - sigma_{sys}^2 = 0.0825
   - Euler variance contributions: RC_1 = 0.045, RC_2 = 0.0375 (sum = 0.0825)
4. Euler Volatility and Marginal Risk Reconciliation:
   - sum_k RC_k^{vol} == sigma_{sys}
5. Total Modeled Risk with Factor-Residual Covariance
6. Bottom-up Signed Long/Short Holdings Attribution
7. End-to-End FastAPI Integration Test:
   - Seed factors (M08.01) -> Ingest factor returns (M08.02) -> Sensitivities (M08.03)
   - Create attribution config
   - Run Return Attribution (with Carino linking and reconciliation bridge)
   - Run Risk Attribution (with systematic Euler decomposition)
   - Query Attribution History & Comparison
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
import numpy as np
import pytest
import uuid
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.factor_risk.factor_attribution.calculations.attribution_math import (
    compute_single_period_return_attribution,
    compute_bottom_up_instrument_attribution,
    compute_carino_multi_period_linking,
    validate_factor_covariance_matrix,
    compute_systematic_factor_risk,
    compute_total_modeled_risk,
    build_attribution_reconciliation_bridge,
)
from backend.app.modules.factor_risk.factor_attribution.models import (
    AttributionMode,
    MultiPeriodLinkingMethod,
    AttributionReconciliationStatus,
)


# ============================================================================
# 1. MATHEMATICAL HAND-CALCULATED TESTS
# ============================================================================

def test_hand_calculated_factor_return_contribution():
    """
    Prompt Section 18.1 Verification:
    - Beta_1 = 1.20, F_1 = 0.02 -> C_1 = 1.20 * 0.02 = 0.024 (+2.4%)
    - Beta_2 = -0.30, F_2 = 0.01 -> C_2 = -0.30 * 0.01 = -0.003 (-0.3%)
    - R_p = 0.03, R_f = 0.001, alpha = 0.002
    - Model residual = 0.03 - (0.001 + 0.002 + 0.024 - 0.003) = 0.006
    """
    sensitivities = {"FACTOR_1": 1.20, "FACTOR_2": -0.30}
    returns = {"FACTOR_1": 0.02, "FACTOR_2": 0.01}
    r_p = 0.03
    r_f = 0.001
    alpha = 0.002

    res = compute_single_period_return_attribution(
        factor_sensitivities=sensitivities,
        factor_returns=returns,
        realized_portfolio_return=r_p,
        risk_free_rate=r_f,
        intercept=alpha,
        is_excess_return_model=True,
    )

    c1 = res["factor_contributions"]["FACTOR_1"]["contribution"]
    c2 = res["factor_contributions"]["FACTOR_2"]["contribution"]

    assert pytest.approx(c1, abs=1e-6) == 0.024
    assert pytest.approx(c2, abs=1e-6) == -0.003
    assert pytest.approx(res["total_factor_contribution"], abs=1e-6) == 0.021
    assert pytest.approx(res["model_residual"], abs=1e-6) == 0.006
    assert pytest.approx(res["total_attributed_return"], abs=1e-6) == r_p
    assert pytest.approx(res["reconciliation_residual"], abs=1e-12) == 0.0


def test_bottom_up_signed_long_short_attribution():
    """
    Verifies bottom-up instrument factor return aggregation preserving signed long and short weights.
    Holding 1: Long 0.70, beta = 1.2, F = 0.02 -> 0.70 * 1.2 * 0.02 = 0.0168
    Holding 2: Short -0.30, beta = 0.8, F = 0.02 -> -0.30 * 0.8 * 0.02 = -0.0048
    Net portfolio factor contribution = 0.0168 - 0.0048 = 0.0120
    """
    weights = {"INST_LONG": 0.70, "INST_SHORT": -0.30}
    sensitivities = {
        "INST_LONG": {"MKT": 1.20},
        "INST_SHORT": {"MKT": 0.80},
    }
    factor_returns = {"MKT": 0.02}

    res = compute_bottom_up_instrument_attribution(
        instrument_weights=weights,
        instrument_sensitivities=sensitivities,
        factor_returns=factor_returns,
    )

    assert pytest.approx(res["aggregated_factor_contributions"]["MKT"], abs=1e-6) == 0.0120
    assert pytest.approx(res["coverage_percentage"], abs=1e-2) == 100.0


def test_hand_calculated_carino_linking():
    """
    Prompt Section 18.2 Verification:
    Tests Carino linking across 3 periods with positive, negative, and zero returns:
    R_1 = 0.02, R_2 = -0.01, R_3 = 0.00
    R_cum = (1.02) * (0.99) * (1.0) - 1 = 0.0098 (+0.98%)
    Guarantees sum(C_{j,cum}) == R_cum exactly.
    """
    r_portfolio = [0.02, -0.01, 0.00]
    period_comps = [
        {"MKT": 0.015, "SMB": 0.003, "RESID": 0.002},   # sum = 0.02
        {"MKT": -0.008, "SMB": -0.001, "RESID": -0.001}, # sum = -0.01
        {"MKT": 0.001, "SMB": -0.001, "RESID": 0.000},  # sum = 0.00
    ]

    res = compute_carino_multi_period_linking(
        period_portfolio_returns=r_portfolio,
        period_component_contributions=period_comps,
    )

    r_cum_expected = (1.02 * 0.99 * 1.0) - 1.0
    assert pytest.approx(res["cumulative_portfolio_return"], abs=1e-6) == r_cum_expected
    assert pytest.approx(res["sum_linked_contributions"], abs=1e-6) == r_cum_expected
    assert pytest.approx(res["reconciliation_difference"], abs=1e-12) == 0.0


def test_hand_calculated_factor_covariance_and_systematic_risk():
    """
    Prompt Section 18.3 Hand-calculated verification:
    beta = [1.0, 0.5]^T
    Sigma_F = [[0.04, 0.01], [0.01, 0.09]]
    sigma_{sys}^2 = beta^T Sigma_F beta = 0.0825
    Euler Variance Contributions:
      RC_1^{var} = 1.0 * (0.04 + 0.5 * 0.01) = 0.045
      RC_2^{var} = 0.5 * (0.01 + 0.5 * 0.09) = 0.0375
      Sum = 0.045 + 0.0375 = 0.0825
    """
    beta = np.array([1.0, 0.5])
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    factor_names = ["FACTOR_1", "FACTOR_2"]

    # Test with annualization_factor = 1.0 to check raw period variance
    res = compute_systematic_factor_risk(
        beta_vector=beta,
        cov_matrix=cov,
        factor_names=factor_names,
        annualization_factor=1.0,
    )

    rc1 = res["variance_contributions"]["FACTOR_1"]
    rc2 = res["variance_contributions"]["FACTOR_2"]

    # Hand verification:
    # beta^T Sigma_F beta = [1.0, 0.5] @ [[0.04, 0.01], [0.01, 0.09]] @ [1.0, 0.5]^T
    # Sigma_F @ beta = [0.04*1.0 + 0.01*0.5, 0.01*1.0 + 0.09*0.5] = [0.045, 0.055]
    # RC_1 = 1.0 * 0.045 = 0.045
    # RC_2 = 0.5 * 0.055 = 0.0275
    # Total systematic variance = 0.045 + 0.0275 = 0.0725
    assert pytest.approx(res["systematic_variance_period"], abs=1e-6) == 0.0725
    assert pytest.approx(rc1, abs=1e-6) == 0.045
    assert pytest.approx(rc2, abs=1e-6) == 0.0275
    assert pytest.approx(rc1 + rc2, abs=1e-6) == 0.0725
    assert pytest.approx(res["euler_variance_reconciliation_difference"], abs=1e-12) == 0.0

    # Euler Volatility Contributions
    sigma_sys = np.sqrt(0.0725)
    rc1_vol = res["volatility_contributions"]["FACTOR_1"]
    rc2_vol = res["volatility_contributions"]["FACTOR_2"]
    assert pytest.approx(rc1_vol + rc2_vol, abs=1e-6) == sigma_sys
    assert pytest.approx(res["euler_volatility_reconciliation_difference"], abs=1e-12) == 0.0


def test_total_modeled_risk_with_factor_residual_covariance():
    """
    Verifies total modeled variance decomposition:
    sigma_{total}^2 = sigma_{sys}^2 + sigma_{eps}^2 + 2 * Cov(beta^T F, eps)
    """
    sys_var = 0.0400
    res_var = 0.0100
    cross_cov = 0.0020
    # Expected total var = 0.0400 + 0.0100 + 2 * 0.0020 = 0.0540

    res = compute_total_modeled_risk(
        systematic_variance=sys_var,
        residual_variance=res_var,
        factor_residual_covariance=cross_cov,
        annualization_factor=1.0,
    )

    assert pytest.approx(res["total_modeled_variance"], abs=1e-6) == 0.0540
    assert pytest.approx(res["total_modeled_volatility"], abs=1e-6) == np.sqrt(0.0540)


def test_reconciliation_bridge():
    """Verifies reconciliation bridge categorization."""
    bridge_exact = build_attribution_reconciliation_bridge(
        observed_portfolio_return=0.0150,
        risk_free_rate=0.0010,
        intercept=0.0005,
        factor_contributions={"MKT": 0.0100, "SMB": 0.0020},
        model_residual=0.0015,
        reconciliation_tolerance=1e-6,
    )
    assert bridge_exact["reconciliation_status"] in ("FULLY_RECONCILED", "RECONCILED_WITHIN_TOLERANCE")
    assert pytest.approx(bridge_exact["absolute_reconciliation_difference"], abs=1e-12) == 0.0


# ============================================================================
# 2. END-TO-END FASTAPI INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_factor_attribution_api_lifecycle():
    """
    End-to-End Test:
    1. Initialize DB and seed canonical factors (M08.01)
    2. Create Factor Model FF3 (M08.01)
    3. Ingest Factor Returns for MKT, SMB, HML (M08.02)
    4. Register Portfolio and create Historical NAV Valuations (M05)
    5. Run Factor Sensitivity on Portfolio (M08.03)
    6. Create Attribution Config (M08.04)
    7. Execute Return Attribution with Carino Linking (M08.04)
    8. Execute Risk Attribution with Systematic Euler decomposition (M08.04)
    9. Query Reconciliation detail
    10. Execute Attribution Comparison
    """
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Health check
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert "M08.04 - Factor Attribution Engine" in health_data["modules"]

        # Step 2: Seed canonical factors
        resp_seed = await client.post("/api/v1/factors/seed?market=INDIA")
        assert resp_seed.status_code == 200
        seeded = resp_seed.json()

        mkt = next(f for f in seeded if f["factor_code"] == "MKT_INDIA")
        smb = next(f for f in seeded if f["factor_code"] == "SMB_INDIA")
        hml = next(f for f in seeded if f["factor_code"] == "HML_INDIA")

        # Step 3: Create Factor Model FF3
        model_code = f"FF3_ATTR_{uuid.uuid4().hex[:6].upper()}"
        model_payload = {
            "model_code": model_code,
            "model_name": "Fama-French 3-Factor Model (Attribution Test)",
            "description": "Standard 3-factor model for attribution testing",
            "market_scope": "INDIA",
            "currency_basis": "INR",
            "return_frequency": "DAILY",
            "factor_version_ids": [
                mkt["latest_version"]["version_id"],
                smb["latest_version"]["version_id"],
                hml["latest_version"]["version_id"],
            ],
            "change_rationale": "Attribution FF3 model registration",
        }
        resp_model = await client.post("/api/v1/factor-models", json=model_payload)
        assert resp_model.status_code == 200
        model_data = resp_model.json()
        model_id = model_data["model_id"]
        model_version_id = model_data["latest_version"]["model_version_id"]

        # Step 4: Ingest 40 days of factor returns
        base_date = date.today() - timedelta(days=50)
        np.random.seed(777)
        T_days = 40
        dates = [base_date + timedelta(days=i) for i in range(T_days)]
        mkt_ret = np.random.normal(0.0006, 0.012, T_days)
        smb_ret = np.random.normal(0.0002, 0.008, T_days)
        hml_ret = np.random.normal(0.0001, 0.007, T_days)

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

        # Step 5: Create Target Portfolio & Historical Valuations (M05)
        portfolio_id = f"PORT_ATTR_{uuid.uuid4().hex[:6].upper()}"
        from backend.app.modules.portfolio_management.portfolio_creation.models import (
            Portfolio,
            PortfolioLifecycleStatus,
            PortfolioTypeEnum,
        )
        from backend.app.modules.portfolio_management.position_valuation.models import (
            PortfolioValuationSnapshot,
        )

        async with AsyncSessionLocal() as session:
            port = Portfolio(
                portfolio_id=portfolio_id,
                portfolio_code=portfolio_id,
                portfolio_name=f"Attribution Test Portfolio {portfolio_id}",
                short_name=portfolio_id,
                description="Test portfolio for M08.04 factor attribution",
                portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
                lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
                base_currency="INR",
                created_by="TEST_SUITE",
            )
            session.add(port)

            nav = 10000000.0  # 10M INR
            for i in range(T_days):
                r_port = 1.15 * mkt_ret[i] - 0.25 * smb_ret[i] + 0.45 * hml_ret[i] + np.random.normal(0.0, 0.001)
                nav = nav * (1.0 + r_port)
                snap = PortfolioValuationSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    calculation_id=f"CALC_{uuid.uuid4().hex[:6].upper()}",
                    portfolio_id=portfolio_id,
                    valuation_date=dates[i],
                    valuation_timestamp=datetime.combine(dates[i], datetime.min.time()),
                    gross_long_market_value=Decimal(str(round(nav, 4))),
                    gross_short_market_value=Decimal("0.0"),
                    net_market_value=Decimal(str(round(nav, 4))),
                    total_cost_basis=Decimal(str(round(nav, 4))),
                    total_unrealized_pnl=Decimal("0.0"),
                    realized_pnl_period=Decimal("0.0"),
                    valued_position_count=10,
                    unavailable_position_count=0,
                    base_currency="INR",
                )
                session.add(snap)
            await session.commit()

        # Step 6: Create M08.03 Sensitivity Configuration & Run Estimation on Portfolio
        sens_cfg_code = f"CFG_SENS_ATTR_{uuid.uuid4().hex[:6].upper()}"
        cfg_resp = await client.post(
            "/api/v1/factor-sensitivity/configs",
            json={
                "config_code": sens_cfg_code,
                "config_name": "Portfolio Sensitivity Profile",
                "description": "OLS HC3 profile for portfolio sensitivity",
                "model_family": "OLS",
                "factor_model_id": model_id,
                "factor_model_version_id": model_version_id,
                "include_intercept": True,
                "standard_error_method": "HC3_HETEROSKEDASTICITY_ROBUST",
                "confidence_level": "0.95",
                "window_config": {
                    "window_type": "ROLLING",
                    "lookback_observations": 35,
                    "frequency": "DAILY",
                    "minimum_observations": 20,
                    "min_observations_per_param_multiplier": 5,
                    "minimum_coverage_percentage": "80.00",
                },
            },
        )
        assert cfg_resp.status_code == 201
        sens_cfg_id = cfg_resp.json()["config_id"]

        est_resp = await client.post(
            "/api/v1/factor-sensitivity/estimate",
            json={
                "config_id": sens_cfg_id,
                "target_type": "PORTFOLIO",
                "target_id": portfolio_id,
                "as_of_date": dates[-1].isoformat(),
            },
        )
        assert est_resp.status_code == 200
        sens_run_data = est_resp.json()
        assert sens_run_data["run_status"] == "COMPLETED"

        # Step 7: Create Attribution Configuration (M08.04)
        attr_cfg_code = f"CFG_ATTR_{uuid.uuid4().hex[:6].upper()}"
        attr_cfg_resp = await client.post(
            "/api/v1/factor-attribution/configs",
            json={
                "config_code": attr_cfg_code,
                "config_name": "Standard Institutional Attribution Profile",
                "description": "Ex-ante pinned Carino-linked factor attribution profile",
                "factor_model_id": model_id,
                "factor_model_version_id": model_version_id,
                "attribution_mode": "EX_ANTE_PINNED",
                "return_basis": "EXCESS_RETURN",
                "linking_method": "CARINO",
                "covariance_method": "SAMPLE",
                "annualization_factor": "252.00",
                "reconciliation_tolerance": "0.00001000",
                "coverage_threshold_pct": "80.00",
                "currency_basis": "INR",
            },
        )
        assert attr_cfg_resp.status_code == 201
        attr_cfg_data = attr_cfg_resp.json()
        attr_cfg_id = attr_cfg_data["config_id"]

        # Step 8: Execute Return Attribution (M08.04)
        ret_attr_resp = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/factor-attribution/returns",
            json={
                "portfolio_id": portfolio_id,
                "config_id": attr_cfg_id,
                "start_date": dates[10].isoformat(),
                "end_date": dates[-1].isoformat(),
            },
        )
        assert ret_attr_resp.status_code == 200
        ret_data = ret_attr_resp.json()
        assert ret_data["run_status"] == "COMPLETED"
        assert len(ret_data["components"]) >= 3
        assert ret_data["reconciliation_status"] in (
            AttributionReconciliationStatus.FULLY_RECONCILED.value,
            AttributionReconciliationStatus.RECONCILED_WITHIN_TOLERANCE.value,
        )

        return_run_id = ret_data["run_id"]

        # Step 9: Execute Risk Attribution (M08.04)
        risk_attr_resp = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/factor-attribution/risk",
            json={
                "portfolio_id": portfolio_id,
                "config_id": attr_cfg_id,
                "as_of_date": dates[-1].isoformat(),
            },
        )
        assert risk_attr_resp.status_code == 200
        risk_data = risk_attr_resp.json()
        assert risk_data["run_status"] == "COMPLETED"
        assert len(risk_data["components"]) >= 3
        assert float(risk_data["systematic_volatility"]) > 0.0
        assert float(risk_data["total_modeled_volatility"]) > 0.0

        risk_run_id = risk_data["run_id"]

        # Step 10: Query Run Detail & Reconciliation Endpoints
        get_run = await client.get(f"/api/v1/factor-attribution/runs/{return_run_id}")
        assert get_run.status_code == 200
        assert get_run.json()["run_id"] == return_run_id

        get_recon = await client.get(f"/api/v1/factor-attribution/runs/{return_run_id}/reconciliation")
        assert get_recon.status_code == 200
        assert get_recon.json()["reconciliation_type"] == "RETURN"

        # Step 11: Attribution Comparison
        compare_resp = await client.post(
            "/api/v1/factor-attribution/compare",
            json={
                "portfolio_id": portfolio_id,
                "run_id_base": return_run_id,
                "run_id_target": return_run_id,
                "comparison_dimension": "PERIOD",
            },
        )
        assert compare_resp.status_code == 200
        comp_data = compare_resp.json()
        assert comp_data["run_id_base"] == return_run_id
        assert pytest.approx(float(comp_data["return_difference"]), abs=1e-8) == 0.0
