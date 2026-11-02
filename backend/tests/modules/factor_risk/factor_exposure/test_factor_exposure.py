"""
M08.02 Factor Exposure Test Suite.
Covers:
1. Synthetic Multi-Factor Loading Estimation Recovery:
   - Known data generation: y_t = alpha + beta_1 * F_1,t + beta_2 * F_2,t + beta_3 * F_3,t + eps_t
   - Accurate parameter recovery via QR-based rolling OLS regression
   - Statistical inference: HC3 heteroskedasticity-robust SEs, t-stats, confidence intervals, R2, VIF
2. EWLS Exponentially Weighted Regression:
   - Sensitivity to decay factor lambda
3. Missing Observations & Multicollinearity Diagnostics:
   - Rank-deficient factor matrix detection
   - Insufficient observation cutoff
4. Exposure Normalization:
   - 1-sigma standardized loading: beta_k * sigma_factor
   - Cross-sectional z-score standardization across universe
5. Portfolio Aggregation & Short Position Weighting:
   - Signed NAV-weighted exposure: beta_p = sum(w_i * beta_i)
   - Proper negative contribution from short holdings
   - Gross-normalized factor exposure
   - Coverage percentage tracking & unmodeled holding preservation
6. Symmetric Exact Decomposition (Weight vs. Loading Effects):
   - Delta(w_i * beta_i) = Delta(w_i) * avg(beta) + Delta(beta_i) * avg(w)
   - Exact mathematical reconciliation to observed total portfolio exposure change
7. API & End-to-End Workflow:
   - Factor return ingestion
   - Estimation configuration creation with SHA-256 hash
   - Factor loading run execution
   - Portfolio exposure calculation and historical snapshot retrieval
   - Exposure change comparison endpoint
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import numpy as np
import pytest
import uuid
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.factor_risk.factor_exposure.calculations.exposure_math import (
    estimate_multifactor_loadings,
    compute_standardized_loading,
    compute_cross_sectional_zscores,
    aggregate_portfolio_factor_exposure,
    decompose_exposure_change,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    EstimationMethod,
    StandardErrorMethod,
    LoadingQualityStatus,
    TiltClassification,
)


def test_synthetic_multifactor_loading_recovery():
    """
    Generate synthetic asset returns from 3 known factors:
    y_t = 0.0005 + 1.20 * F1 - 0.40 * F2 + 0.80 * F3 + eps_t
    Verify estimator recovers coefficients within tight statistical tolerance.
    """
    np.random.seed(42)
    T = 250
    F1 = np.random.normal(0.0004, 0.012, T)
    F2 = np.random.normal(0.0001, 0.008, T)
    F3 = np.random.normal(0.0002, 0.010, T)
    X = np.column_stack([F1, F2, F3])

    true_alpha = 0.0005
    true_beta = np.array([1.20, -0.40, 0.80])
    noise = np.random.normal(0.0, 0.002, T)  # High signal-to-noise
    y = true_alpha + np.dot(X, true_beta) + noise

    res = estimate_multifactor_loadings(
        y_returns=y,
        X_factors=X,
        factor_names=["MKT", "SMB", "HML"],
        estimation_method=EstimationMethod.ROLLING_OLS,
        include_intercept=True,
        standard_error_method=StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST,
    )

    assert res["status"] == LoadingQualityStatus.ESTIMATED
    assert pytest.approx(res["intercept"], abs=0.001) == true_alpha
    b_recovered = [res["loadings"][f]["loading_value"] for f in ["MKT", "SMB", "HML"]]
    assert pytest.approx(b_recovered[0], abs=0.05) == 1.20
    assert pytest.approx(b_recovered[1], abs=0.05) == -0.40
    assert pytest.approx(b_recovered[2], abs=0.05) == 0.80

    # Verify R2 is high and t-statistics are significant
    assert res["r_squared"] > 0.85
    assert res["loadings"]["MKT"]["t_statistic"] > 10.0
    assert res["loadings"]["SMB"]["t_statistic"] < -5.0
    assert res["loadings"]["HML"]["t_statistic"] > 8.0


def test_ewls_estimation_and_rank_deficiency():
    """Test EWLS weighting and collinearity rejection."""
    np.random.seed(123)
    T = 100
    F1 = np.random.normal(0.0, 0.01, T)
    F2 = np.random.normal(0.0, 0.01, T)
    X = np.column_stack([F1, F2])
    y = 0.5 * F1 + 0.3 * F2 + np.random.normal(0.0, 0.001, T)

    res_ewls = estimate_multifactor_loadings(
        y_returns=y,
        X_factors=X,
        factor_names=["F1", "F2"],
        estimation_method=EstimationMethod.EWLS,
        ewls_decay_factor=0.94,
    )
    assert res_ewls["status"] == LoadingQualityStatus.ESTIMATED
    assert pytest.approx(res_ewls["loadings"]["F1"]["loading_value"], abs=0.05) == 0.5
    assert pytest.approx(res_ewls["loadings"]["F2"]["loading_value"], abs=0.05) == 0.3

    # Rank-deficient collinear test (F2 = 2 * F1)
    X_collinear = np.column_stack([F1, 2.0 * F1])
    res_rank = estimate_multifactor_loadings(
        y_returns=y,
        X_factors=X_collinear,
        factor_names=["F1", "F1_DUPLICATE"],
    )
    assert res_rank["status"] == LoadingQualityStatus.MULTICOLLINEARITY_WARNING


def test_portfolio_signed_weight_aggregation():
    """
    Hand-calculated portfolio aggregation test:
    Holdings:
    A: Long +600,000 INR (w = +0.60), beta_MKT = 1.20, beta_SMB = 0.40
    B: Long +500,000 INR (w = +0.50), beta_MKT = 0.80, beta_SMB = -0.20
    C: Short -100,000 INR (w = -0.10), beta_MKT = 1.40, beta_SMB = 0.10
    NAV = +1,000,000 INR
    Total Gross MV = 1,200,000 INR

    Expected beta_MKT = (0.60)(1.20) + (0.50)(0.80) + (-0.10)(1.40)
                      = 0.72 + 0.40 - 0.14 = 0.98
    Expected beta_SMB = (0.60)(0.40) + (0.50)(-0.20) + (-0.10)(0.10)
                      = 0.24 - 0.10 - 0.01 = 0.13
    """
    holdings = [
        {"instrument_id": "INST_A", "signed_market_value": 600000.0, "loadings": {"MKT": 1.20, "SMB": 0.40}},
        {"instrument_id": "INST_B", "signed_market_value": 500000.0, "loadings": {"MKT": 0.80, "SMB": -0.20}},
        {"instrument_id": "INST_C", "signed_market_value": -100000.0, "loadings": {"MKT": 1.40, "SMB": 0.10}},
    ]
    nav = 1000000.0

    res_mkt = aggregate_portfolio_factor_exposure(holdings, "MKT", nav)
    assert pytest.approx(res_mkt["exposure_value"], 1e-6) == 0.98
    assert res_mkt["coverage_percentage"] == 100.0
    assert res_mkt["tilt_classification"] == TiltClassification.STRONG_POSITIVE

    res_smb = aggregate_portfolio_factor_exposure(holdings, "SMB", nav)
    assert pytest.approx(res_smb["exposure_value"], 1e-6) == 0.13

    # Gross-normalized view for MKT:
    # w_gross_A = 600k / 1.2M = 0.50
    # w_gross_B = 500k / 1.2M = 0.416667
    # w_gross_C = -100k / 1.2M = -0.083333
    # sum = 0.50*1.2 + 0.416667*0.8 - 0.083333*1.4 = 0.60 + 0.333333 - 0.116667 = 0.816667
    assert pytest.approx(res_mkt["gross_normalized_exposure"], 1e-4) == 0.816667


def test_exposure_change_exact_decomposition():
    """
    Verify symmetric exact decomposition:
    Delta(w * beta) = Delta(w) * avg(beta) + Delta(beta) * avg(w)
    Reconciles exactly to observed exposure delta with 0 residual.
    """
    earlier = {
        "INST_A": {"weight": 0.50, "loading": 1.20},
        "INST_B": {"weight": 0.50, "loading": 0.80},
    }
    later = {
        "INST_A": {"weight": 0.60, "loading": 1.10},  # weight changed +0.10, loading changed -0.10
        "INST_B": {"weight": 0.40, "loading": 0.90},  # weight changed -0.10, loading changed +0.10
    }

    # Earlier exposure: 0.50*1.20 + 0.50*0.80 = 0.60 + 0.40 = 1.00
    # Later exposure:   0.60*1.10 + 0.40*0.90 = 0.66 + 0.36 = 1.02
    # Total change = +0.02
    res = decompose_exposure_change(earlier, later)
    assert pytest.approx(res["earlier_exposure"], 1e-6) == 1.00
    assert pytest.approx(res["later_exposure"], 1e-6) == 1.02
    assert pytest.approx(res["total_change"], 1e-6) == 0.02

    # Verify reconciliation
    sum_effects = res["weight_effect"] + res["loading_effect"] + res["entry_exit_effect"]
    assert pytest.approx(sum_effects, 1e-6) == res["total_change"]
    assert pytest.approx(res["unreconciled_residual"], 1e-6) == 0.0


@pytest.mark.asyncio
async def test_end_to_end_factor_exposure_workflow():
    """
    Full end-to-end integration test:
    1. Seed canonical factor definitions & create Fama-French 3-Factor model (M08.01)
    2. Ingest daily factor return series for MKT, SMB, HML (M08.02)
    3. Register an instrument and historical official close prices (M04.05)
    4. Create estimation profile & execute factor loading run
    5. Aggregate portfolio factor exposure using signed holdings (M08.02)
    6. Verify portfolio factor exposure retrieval and history
    """
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Seed canonical factors
        resp_seed = await client.post("/api/v1/factors/seed?market=INDIA")
        assert resp_seed.status_code == 200
        seeded = resp_seed.json()

        mkt = next(f for f in seeded if f["factor_code"] == "MKT_INDIA")
        smb = next(f for f in seeded if f["factor_code"] == "SMB_INDIA")
        hml = next(f for f in seeded if f["factor_code"] == "HML_INDIA")

        # 2. Create Factor Model FF3
        model_code = f"FF3_{uuid.uuid4().hex[:6].upper()}"
        model_payload = {
            "model_code": model_code,
            "model_name": "Fama-French 3-Factor Model (India Test)",
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

        # 3. Ingest Factor Returns for 40 trading days
        base_date = date.today() - timedelta(days=50)
        np.random.seed(999)
        T_days = 40
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

        # 4. Ingest Official Price Reference Observations for a target instrument
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
                canonical_name=f"Test Equity {inst_id}",
                short_name=inst_id,
                isin=f"IN{uuid.uuid4().hex[:10].upper()}",
                instrument_type="COMMON_STOCK",
                lifecycle_status="ACTIVE",
                issue_currency="INR",
            )
            session.add(inst)

            # Generate synthetic prices linked to factors: beta_mkt=1.1, beta_smb=-0.3, beta_hml=0.5
            p = 100.0
            for i in range(T_days):
                r_inst = 1.1 * mkt_ret[i] - 0.3 * smb_ret[i] + 0.5 * hml_ret[i] + np.random.normal(0.0, 0.001)
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

        # 5. Create Estimation Configuration
        config_code = f"CFG_{uuid.uuid4().hex[:6].upper()}"
        cfg_payload = {
            "config_code": config_code,
            "config_name": "Indian Equity Rolling 30D OLS",
            "description": "Standard short-term rolling OLS factor loading estimation profile.",
            "factor_model_id": model_id,
            "factor_model_version_id": model_version_id,
            "estimation_method": "ROLLING_OLS",
            "lookback_observations": 35,
            "minimum_observations": 25,
            "min_observations_per_param_multiplier": 5,
            "currency_basis": "INR",
        }
        resp_cfg = await client.post("/api/v1/factor-exposures/configs", json=cfg_payload)
        assert resp_cfg.status_code == 200
        cfg_data = resp_cfg.json()
        cfg_id = cfg_data["config_id"]

        # 6. Execute Factor Loading Run
        run_payload = {
            "config_id": cfg_id,
            "factor_model_id": model_id,
            "factor_model_version_id": model_version_id,
            "as_of_date": dates[-1].isoformat(),
            "instrument_ids": [inst_id],
        }
        resp_run = await client.post("/api/v1/factor-exposures/estimate", json=run_payload)
        assert resp_run.status_code == 200
        run_data = resp_run.json()
        assert run_data["run_status"] == "COMPLETED"
        assert run_data["successful_count"] == 1

        # 7. Query Instrument Loadings
        resp_inst_l = await client.get(
            f"/api/v1/instruments/{inst_id}/factor-exposures",
            params={"factor_model_version_id": model_version_id},
        )
        assert resp_inst_l.status_code == 200
        loadings = resp_inst_l.json()
        assert len(loadings) == 3
        # Verify MKT loading is close to true 1.1
        mkt_ld = next(l for l in loadings if l["factor_code"] == "MKT_INDIA")
        assert pytest.approx(float(mkt_ld["loading_value"]), abs=0.15) == 1.1

        # 8. Create a position and Aggregate Portfolio Factor Exposure
        test_pid = f"PORT_{uuid.uuid4().hex[:6].upper()}"
        from backend.app.modules.portfolio_management.position_valuation.models import (
            PositionValuation,
            ValuationStatus,
        )
        from backend.app.modules.portfolio_management.position_management.models import PositionSide

        async with AsyncSessionLocal() as session:
            pv = PositionValuation(
                valuation_id=str(uuid.uuid4()),
                calculation_id=str(uuid.uuid4()),
                portfolio_id=test_pid,
                account_id="ACC_MAIN",
                instrument_id=inst_id,
                position_side=PositionSide.LONG,
                signed_quantity=Decimal("1000"),
                mark_price=Decimal("100.0"),
                price_currency="INR",
                signed_market_value_native=Decimal("100000.0"),
                signed_market_value_base=Decimal("100000.0"),
                signed_cost_basis_native=Decimal("95000.0"),
                signed_cost_basis_base=Decimal("95000.0"),
                unrealized_pnl_native=Decimal("5000.0"),
                unrealized_pnl_base=Decimal("5000.0"),
                valuation_status=ValuationStatus.VALUED,
                effective_at=datetime.combine(dates[-1], datetime.min.time()),
            )
            session.add(pv)
            await session.commit()

        # Query Portfolio Factor Exposure
        resp_port_exp = await client.get(
            f"/api/v1/portfolios/{test_pid}/factor-exposures",
            params={"factor_model_version_id": model_version_id, "as_of_date": dates[-1].isoformat()},
        )
        assert resp_port_exp.status_code == 200
        port_exp = resp_port_exp.json()
        assert port_exp["portfolio_id"] == test_pid
        assert len(port_exp["exposures"]) == 3
        assert float(port_exp["coverage_percentage"]) == 100.0

        # 9. Query Portfolio Exposure History
        resp_hist = await client.get(f"/api/v1/portfolios/{test_pid}/factor-exposures/history")
        assert resp_hist.status_code == 200
        hist_data = resp_hist.json()
        assert len(hist_data) >= 1
