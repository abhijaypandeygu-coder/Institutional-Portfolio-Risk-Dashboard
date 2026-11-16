"""
Unit and integration tests for M10.07 Monte Carlo Scenarios.
Tests:
1. Matrix validation, repair, and Cholesky factorization.
2. Multivariate normal and Student-t innovation generation.
3. Geometric Brownian Motion path simulation (positive price preservation).
4. Portfolio valuation, terminal P&L distribution, and moments.
5. Monte Carlo VaR and Expected Shortfall (loss-positive convention).
6. Random seed reproducibility (PCG64).
7. FastAPI HTTP API end-to-end integration.
"""

from decimal import Decimal
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.main import app
from backend.app.modules.scenario_analysis.monte_carlo.calculations.monte_carlo_math import (
    validate_and_repair_correlation_matrix,
    compute_cholesky_factor,
    generate_correlated_innovations,
    simulate_geometric_brownian_paths,
    calculate_portfolio_outcomes,
    compute_distribution_statistics,
    compute_var_and_cvar,
)
from backend.app.modules.scenario_analysis.monte_carlo.schemas.monte_carlo_schemas import (
    MonteCarloScenarioCreate,
    SimulationExecutionRequest,
    PositionOverride,
)
from backend.app.modules.scenario_analysis.monte_carlo.services.monte_carlo_service import (
    MonteCarloService,
)


@pytest.mark.asyncio
async def test_correlation_matrix_validation_and_repair():
    # 1. Non-PSD matrix with negative eigenvalue
    non_psd = np.array([
        [1.0, 0.95, 0.95],
        [0.95, 1.0, -0.90],
        [0.95, -0.90, 1.0]
    ], dtype=np.float64)

    repaired, was_repaired = validate_and_repair_correlation_matrix(non_psd)
    assert was_repaired is True
    # Verify eigenvalues are non-negative
    eigvals = np.linalg.eigvalsh(repaired)
    assert np.all(eigvals >= 0.0)
    # Verify unit diagonal
    assert np.allclose(np.diag(repaired), 1.0)
    # Verify symmetry
    assert np.allclose(repaired, repaired.T)

    # Cholesky should succeed on repaired matrix
    L = compute_cholesky_factor(repaired)
    assert L.shape == (3, 3)
    assert np.allclose(L @ L.T, repaired, atol=1e-5)


@pytest.mark.asyncio
async def test_multivariate_innovations_and_reproducibility():
    corr = np.array([
        [1.0, 0.5],
        [0.5, 1.0]
    ], dtype=np.float64)
    L = compute_cholesky_factor(corr)

    # Normal innovations
    rng1 = np.random.default_rng(42)
    Z1 = generate_correlated_innovations(10000, 2, L, distribution_type="MULTIVARIATE_NORMAL", rng=rng1)
    
    # Exact seed reproduction
    rng2 = np.random.default_rng(42)
    Z2 = generate_correlated_innovations(10000, 2, L, distribution_type="MULTIVARIATE_NORMAL", rng=rng2)
    assert np.allclose(Z1, Z2)

    # Sample correlation check
    sample_corr = np.corrcoef(Z1, rowvar=False)
    assert np.isclose(sample_corr[0, 1], 0.5, atol=0.04)

    # Student-t innovations (df=4)
    rng_t = np.random.default_rng(123)
    Z_t = generate_correlated_innovations(20000, 2, L, distribution_type="STUDENT_T", degrees_of_freedom=4.0, rng=rng_t)
    # Check heavy tails (kurtosis > 0)
    from scipy.stats import kurtosis
    kurt = kurtosis(Z_t[:, 0])
    assert kurt > 1.0  # Heavier tails than normal


@pytest.mark.asyncio
async def test_geometric_brownian_path_simulation():
    prices = np.array([100.0, 50.0], dtype=np.float64)
    drifts = np.array([0.05, 0.10], dtype=np.float64)
    vols = np.array([0.20, 0.30], dtype=np.float64)
    L = np.eye(2, dtype=np.float64)

    rng = np.random.default_rng(999)
    terminal_prices, full_paths = simulate_geometric_brownian_paths(
        initial_prices=prices,
        drifts=drifts,
        volatilities=vols,
        cholesky_L=L,
        n_paths=5000,
        n_steps=20,
        dt=1.0/252.0,
        rng=rng,
        store_full_paths=True
    )

    # Prices must strictly remain positive
    assert np.all(terminal_prices > 0.0)
    assert np.all(full_paths > 0.0)
    assert terminal_prices.shape == (5000, 2)
    assert full_paths.shape == (5000, 21, 2)


@pytest.mark.asyncio
async def test_portfolio_valuation_and_risk_metrics():
    quantities = np.array([100.0, -50.0], dtype=np.float64) # Long stock 1, short stock 2
    baseline_prices = np.array([100.0, 100.0], dtype=np.float64)
    # Baseline: 100 * 100 - 50 * 100 + 1000 cash = 10000 - 5000 + 1000 = 6000
    cash = 1000.0

    # Synthetic simulated prices
    np.random.seed(42)
    sim_prices = np.array([
        [105.0, 95.0],   # V = 10500 - 4750 + 1000 = 6750, PnL = +750
        [90.0, 110.0],   # V = 9000 - 5500 + 1000 = 4500, PnL = -1500
        [100.0, 100.0],  # V = 6000, PnL = 0
    ], dtype=np.float64)

    outcomes = calculate_portfolio_outcomes(quantities, baseline_prices, sim_prices, cash_balance=cash)
    assert outcomes["baseline_portfolio_value"] == 6000.0
    assert np.allclose(outcomes["pnl"], [750.0, -1500.0, 0.0])

    # Test distribution stats and VaR
    # Create larger sample for VaR
    pnl_dist = np.random.normal(loc=100.0, scale=1000.0, size=5000)
    stats_res = compute_distribution_statistics(pnl_dist)
    assert "mean" in stats_res
    assert "loss_probability" in stats_res

    var_res = compute_var_and_cvar(pnl_dist, [0.95])
    # VaR loss must be positive and CVaR loss >= VaR loss
    assert var_res["95%"]["var_loss"] > 0
    assert var_res["95%"]["cvar_loss"] >= var_res["95%"]["var_loss"]


@pytest.mark.asyncio
async def test_monte_carlo_service_end_to_end():
    await init_db()

    async with AsyncSessionLocal() as session:
        service = MonteCarloService(session)

        # 1. Create Scenario with unique code
        import uuid
        scenario_code = f"MC_TEST_{uuid.uuid4().hex[:8].upper()}"
        create_payload = MonteCarloScenarioCreate(
            scenario_code=scenario_code,
            name="Tech Volatility Stress Monte Carlo",
            description="20-day horizon with Student-t innovations",
            horizon_days=20,
            time_step_days=1,
            distribution_type="STUDENT_T",
            degrees_of_freedom=4.0,
            expected_return_model="ZERO_DRIFT",
            volatility_multiplier=1.2,
            correlation_repair_method="EIGENVALUE_CLIPPING"
        )
        scenario = await service.create_scenario(create_payload)
        await session.commit()
        assert scenario.scenario_code == scenario_code

        # 2. Run Simulation with deterministic seed
        req = SimulationExecutionRequest(
            portfolio_id="PORT_TEST_01",
            n_paths=1000,
            random_seed=777,
            positions_override=[
                PositionOverride(symbol="AAPL", quantity=Decimal("100"), baseline_price=Decimal("150"), annualized_volatility=0.25),
                PositionOverride(symbol="MSFT", quantity=Decimal("50"), baseline_price=Decimal("300"), annualized_volatility=0.20),
            ]
        )
        run = await service.run_simulation(scenario_code, req)
        await session.commit()

        assert run.status == "COMPLETED"
        assert run.n_paths == 1000
        assert run.random_seed == 777
        assert run.summary is not None
        assert run.summary.baseline_portfolio_value == Decimal("30000.0000") # 100*150 + 50*300 = 30000
        assert len(run.risk_metrics) == 3 # 90%, 95%, 99%
        assert len(run.instrument_results) == 2


@pytest.mark.asyncio
async def test_fastapi_monte_carlo_endpoints():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check health endpoint includes M10.07
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert "M10.07 - Monte Carlo Scenarios Engine" in health_resp.json()["modules"]

        # Create scenario via API
        import uuid
        sc_code = f"MC_API_{uuid.uuid4().hex[:8].upper()}"
        create_data = {
            "scenario_code": sc_code,
            "name": "API Automated Monte Carlo Scenario",
            "description": "API Integration Test Scenario",
            "horizon_days": 10,
            "time_step_days": 1,
            "distribution_type": "MULTIVARIATE_NORMAL",
            "volatility_multiplier": 1.0,
            "expected_return_model": "ZERO_DRIFT",
            "correlation_repair_method": "EIGENVALUE_CLIPPING"
        }
        res_create = await client.post("/api/v1/risk/scenarios/monte-carlo/scenarios", json=create_data)
        assert res_create.status_code == 201, f"Failed create: {res_create.text}"
        assert res_create.json()["scenario_code"] == sc_code

        # Run simulation via API
        exec_payload = {
            "portfolio_id": "PORT_API_BENCHMARK",
            "n_paths": 2000,
            "random_seed": 42
        }
        res_run = await client.post(f"/api/v1/risk/scenarios/monte-carlo/scenarios/{sc_code}/run", json=exec_payload)
        assert res_run.status_code == 200, f"Run error: {res_run.text}"
        run_data = res_run.json()
        assert run_data["status"] == "COMPLETED"
        assert run_data["n_paths"] == 2000
        assert run_data["random_seed"] == 42
        assert run_data["summary"]["baseline_portfolio_value"] is not None
        assert len(run_data["risk_metrics"]) == 3
        assert len(run_data["instrument_results"]) > 0

        # Query by run_code
        run_code = run_data["run_code"]
        res_get_run = await client.get(f"/api/v1/risk/scenarios/monte-carlo/runs/{run_code}")
        assert res_get_run.status_code == 200
        assert res_get_run.json()["run_code"] == run_code

