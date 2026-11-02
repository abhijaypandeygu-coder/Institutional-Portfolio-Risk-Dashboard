"""
M07.10 Risk Forecasting Test Suite.
Covers:
1. Pure Mathematical & Model Tests:
   - Rolling historical variance baseline (1-step and multi-step)
   - EWMA variance recursion and decay factor sensitivity
   - GARCH(1,1) maximum likelihood parameter estimation and stationarity constraints (alpha + beta < 1)
   - GARCH multi-step forecast mean-reversion toward long-run variance (V_L)
   - Out-of-sample forecast evaluation (forecast error, MAE, RMSE, QLIKE loss)
   - Calibration regression diagnostics
2. Integration & API Endpoints:
   - System health check registration of M07.10
   - POST /api/v1/market-risk/forecast/volatility (Rolling, EWMA, GARCH)
   - GET /api/v1/market-risk/forecast/volatility
   - POST /api/v1/market-risk/forecast/compare (Walk-forward multi-model comparison)
   - POST /api/v1/market-risk/forecast/{calculation_id}/evaluate
   - GET /api/v1/portfolios/{portfolio_id}/risk/forecast
   - GET /api/v1/market-risk/forecast/monitoring-events
"""
import pytest
import numpy as np
import math
from decimal import Decimal
from datetime import date, datetime, timedelta
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.market_risk.risk_forecasting.calculations.forecasting_math import (
    forecast_rolling_historical_variance,
    forecast_ewma_variance,
    fit_and_forecast_garch_1_1,
    evaluate_forecast_realized,
    compute_calibration_regression,
)
from backend.app.modules.market_risk.risk_forecasting.models import (
    ForecastModelType,
    ForecastCalculationScope,
    ForecastStatus,
    EvaluationStatus,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioTypeEnum,
    PortfolioLifecycleStatus,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.instrument_reference_data.price_reference.models import PriceReferenceObservation


# ============================================================================
# 1. PURE MATHEMATICAL & NUMERICAL TESTS
# ============================================================================

def test_rolling_historical_variance_math():
    """Verify rolling historical variance baseline."""
    returns = np.array([0.01, -0.01, 0.02, -0.02, 0.01, -0.01], dtype=np.float64)
    res = forecast_rolling_historical_variance(returns, horizon=5, annualization_factor=252.0)

    assert res["status"] == ForecastStatus.VALID
    expected_var = float(np.var(returns, ddof=1))
    expected_vol = math.sqrt(expected_var)

    assert pytest.approx(res["one_step_variance"], 1e-9) == expected_var
    assert pytest.approx(res["one_step_volatility"], 1e-9) == expected_vol
    assert len(res["horizon_variance_path"]) == 5
    assert pytest.approx(res["cumulative_horizon_variance"], 1e-9) == expected_var * 5
    assert pytest.approx(res["annualized_forecast_volatility"], 1e-9) == expected_vol * math.sqrt(252.0)


def test_ewma_recursion_and_shock_adaptation():
    """Verify EWMA variance recursive updating and reaction to volatility shock."""
    returns_calm = np.full(50, 0.001, dtype=np.float64)
    res_calm = forecast_ewma_variance(returns_calm, decay_factor=0.94)

    # Inject large shock at the end
    returns_shock = np.append(returns_calm, [0.05])
    res_shock = forecast_ewma_variance(returns_shock, decay_factor=0.94)

    assert res_calm["status"] == ForecastStatus.VALID
    assert res_shock["status"] == ForecastStatus.VALID
    # EWMA variance must react upward sharply to the return shock
    assert res_shock["one_step_variance"] > res_calm["one_step_variance"] * 2.0


def test_garch_estimation_and_mean_reversion():
    """
    Verify GARCH(1,1) parameter constraints (alpha + beta < 1)
    and multi-step mean reversion toward long-run variance V_L.
    """
    np.random.seed(42)
    # Simulate stationary GARCH(1,1) series: omega=0.0001, alpha=0.1, beta=0.8
    n_sim = 400
    true_omega = 0.0001
    true_alpha = 0.10
    true_beta = 0.80
    v_l = true_omega / (1.0 - true_alpha - true_beta)  # 0.001

    h = v_l
    returns = np.zeros(n_sim, dtype=np.float64)
    for t in range(n_sim):
        z = np.random.normal(0, 1)
        r = math.sqrt(h) * z
        returns[t] = r
        h = true_omega + true_alpha * (r**2) + true_beta * h

    garch_res = fit_and_forecast_garch_1_1(returns, horizon=20, annualization_factor=252.0)

    assert garch_res["status"] == ForecastStatus.VALID
    params = garch_res["parameters"]
    assert params["omega"] > 0.0
    assert params["alpha"] >= 0.0
    assert params["beta"] >= 0.0
    assert params["persistence"] < 1.0  # Stationarity verified

    # Verify multi-step path converges towards long-run variance
    path = garch_res["horizon_variance_path"]
    assert len(path) == 20
    long_run_var = params["long_run_variance"]
    # Later step should be closer to long-run variance than first step (if starting away from mean)
    diff_start = abs(path[0] - long_run_var)
    diff_end = abs(path[-1] - long_run_var)
    if diff_start > 1e-6:
        assert diff_end <= diff_start


def test_forecast_evaluation_qlike_and_error_metrics():
    """Verify forecast error, MAE, RMSE, and QLIKE loss calculation."""
    f_var = 0.04   # 20% volatility
    r_var = 0.0225 # 15% volatility

    eval_out = evaluate_forecast_realized(f_var, r_var)
    assert eval_out["is_overforecast"] is True
    assert pytest.approx(eval_out["forecast_volatility"], 1e-6) == 0.20
    assert pytest.approx(eval_out["realized_volatility"], 1e-6) == 0.15
    assert pytest.approx(eval_out["forecast_error_volatility"], 1e-6) == 0.05
    assert pytest.approx(eval_out["absolute_error_volatility"], 1e-6) == 0.05

    # QLIKE: (0.0225 / 0.04) - ln(0.0225 / 0.04) - 1
    expected_ratio = 0.0225 / 0.04
    expected_qlike = expected_ratio - math.log(expected_ratio) - 1.0
    assert pytest.approx(eval_out["qlike_loss"], 1e-6) == expected_qlike
    assert eval_out["qlike_loss"] > 0.0


def test_calibration_regression():
    """Verify calibration regression slope and intercept."""
    # Perfectly calibrated forecasts: RV = 0.0 + 1.0 * h
    f_vars = np.array([0.01, 0.02, 0.03, 0.04, 0.05], dtype=np.float64)
    r_vars = f_vars.copy()

    calib = compute_calibration_regression(f_vars, r_vars)
    assert pytest.approx(calib["slope"], 1e-6) == 1.0
    assert pytest.approx(calib["intercept"], 1e-6) == 0.0
    assert pytest.approx(calib["r_squared"], 1e-6) == 1.0
    assert calib["is_calibrated"] is True


# ============================================================================
# 2. INTEGRATION TESTS (FASTAPI & DATABASE LIFECYCLE)
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_includes_m07_10():
    """Verify that M07.10 is registered in the system health response."""
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "M07.10 - Risk Forecasting Engine" in data["modules"]


@pytest.mark.asyncio
async def test_end_to_end_forecasting_workflow():
    """
    End-to-end integration test:
    1. Seed portfolio, instrument, and historical price observations.
    2. Execute POST /api/v1/market-risk/forecast/volatility with EWMA.
    3. Execute POST /api/v1/market-risk/forecast/volatility with GARCH(1,1).
    4. Retrieve GET /api/v1/market-risk/forecast/volatility.
    5. Execute POST /api/v1/market-risk/forecast/compare.
    6. Execute POST /api/v1/market-risk/forecast/{calc_id}/evaluate.
    7. Query nested portfolio router /api/v1/portfolios/{portfolio_id}/risk/forecast.
    8. Query GET /api/v1/market-risk/forecast/monitoring-events.
    """
    await init_db()
    test_pid = f"PORT_FC_TEST_{datetime.utcnow().strftime('%H%M%S')}"
    inst_id = f"INST_FC_{datetime.utcnow().strftime('%H%M%S')}"

    # 1. Seed database records
    async with AsyncSessionLocal() as session:
        port = Portfolio(
            portfolio_id=test_pid,
            portfolio_code=test_pid,
            portfolio_name="Risk Forecasting Test Portfolio",
            short_name="FC_PORT",
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="INR",
            created_by="TEST_RUNNER",
        )
        session.add(port)

        inst = Instrument(
            instrument_id=inst_id,
            canonical_name="Reliance Industries Ltd",
            short_name="RELIANCE",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            country_of_issue="IND",
            issue_currency="INR",
        )
        session.add(inst)

        # Seed 45 days of realistic price series
        base_d = date.today() - timedelta(days=60)
        p_val = 2500.0
        for day in range(50):
            obs_d = base_d + timedelta(days=day)
            p_val *= 1.0 + (0.012 if day % 2 == 0 else -0.010)

            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_FC_{inst_id}_{day}",
                instrument_id=inst_id,
                exchange_code="NSE",
                trading_date=obs_d,
                reference_type="OFFICIAL_CLOSE",
                price_value=Decimal(str(round(p_val, 2))),
                currency="INR",
            ))

        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 2. POST /volatility (EWMA)
        req_ewma = {
            "scope": "INSTRUMENT",
            "entity_id": inst_id,
            "model_name": "EWMA",
            "forecast_horizon": 5,
            "lookback_days": 60,
            "ewma_decay_factor": "0.9400",
        }
        resp_ewma = await client.post("/api/v1/market-risk/forecast/volatility", json=req_ewma)
        assert resp_ewma.status_code == 200
        ewma_data = resp_ewma.json()
        assert ewma_data["status"] == "VALID"
        assert ewma_data["forecast_horizon"] == 5
        assert len(ewma_data["step_results"]) == 5
        assert float(ewma_data["one_step_forecast_volatility"]) > 0.0
        calc_id = ewma_data["calculation_id"]

        # 3. POST /volatility (GARCH(1,1))
        req_garch = {
            "scope": "INSTRUMENT",
            "entity_id": inst_id,
            "model_name": "GARCH_1_1",
            "forecast_horizon": 5,
            "lookback_days": 60,
        }
        resp_garch = await client.post("/api/v1/market-risk/forecast/volatility", json=req_garch)
        assert resp_garch.status_code == 200
        garch_data = resp_garch.json()
        assert garch_data["status"] == "VALID"
        assert garch_data["model_parameters"]["persistence"] < 1.0

        # 4. GET /volatility
        get_resp = await client.get(
            "/api/v1/market-risk/forecast/volatility",
            params={"scope": "INSTRUMENT", "entity_id": inst_id, "model_name": "EWMA"},
        )
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["calculation_id"] == calc_id

        # 5. POST /compare (multi-model comparison)
        comp_req = {
            "scope": "INSTRUMENT",
            "entity_id": inst_id,
            "models": ["ROLLING_HISTORICAL", "EWMA", "GARCH_1_1"],
            "forecast_horizon": 1,
        }
        comp_resp = await client.post("/api/v1/market-risk/forecast/compare", json=comp_req)
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert len(comp_data["models"]) == 3
        assert comp_data["comparison_code"].startswith("COMP_")

        # 6. POST /{calculation_id}/evaluate
        eval_resp = await client.post(f"/api/v1/market-risk/forecast/{calc_id}/evaluate")
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["calculation_id"] == calc_id
        assert eval_data["evaluation_status"] in ["EVALUATED", "AWAITING_REALIZED_DATA", "INSUFFICIENT_REALIZED_DATA"]

        # 7. GET nested portfolio router /api/v1/portfolios/{portfolio_id}/risk/forecast
        nest_resp = await client.get(f"/api/v1/portfolios/{test_pid}/risk/forecast")
        assert nest_resp.status_code == 200
        nest_data = nest_resp.json()
        assert nest_data["entity_id"] == test_pid

        # 8. GET /monitoring-events
        mon_resp = await client.get("/api/v1/market-risk/forecast/monitoring-events")
        assert mon_resp.status_code == 200
        assert isinstance(mon_resp.json(), list)
