"""
Service orchestration layer for M10.07 Monte Carlo Scenarios.
Orchestrates portfolio holdings retrieval, stochastic model calibration,
chunked path generation, portfolio valuation, VaR/ES calculation, and audit persistence.
"""

from datetime import datetime
from decimal import Decimal
import hashlib
import json
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.scenario_analysis.monte_carlo.models.monte_carlo_models import (
    MonteCarloScenario,
    MonteCarloSimulationRun,
    MonteCarloSimulationSummary,
    MonteCarloRiskMetric,
    MonteCarloInstrumentResult,
)
from backend.app.modules.scenario_analysis.monte_carlo.schemas.monte_carlo_schemas import (
    MonteCarloScenarioCreate,
    MonteCarloScenarioUpdate,
    SimulationExecutionRequest,
    PositionOverride,
)
from backend.app.modules.scenario_analysis.monte_carlo.repositories.monte_carlo_repository import (
    MonteCarloRepository,
)
from backend.app.modules.scenario_analysis.monte_carlo.calculations.monte_carlo_math import (
    validate_and_repair_correlation_matrix,
    compute_cholesky_factor,
    simulate_geometric_brownian_paths,
    calculate_portfolio_outcomes,
    compute_distribution_statistics,
    compute_var_and_cvar,
    to_decimal,
)


class MonteCarloService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MonteCarloRepository(session)

    # ---------------------------------------------------------
    # Scenario CRUD Operations
    # ---------------------------------------------------------
    async def create_scenario(self, payload: MonteCarloScenarioCreate) -> MonteCarloScenario:
        existing = await self.repo.get_scenario_by_code(payload.scenario_code)
        if existing:
            raise ValueError(f"Scenario with code '{payload.scenario_code}' already exists.")

        scenario = MonteCarloScenario(
            scenario_code=payload.scenario_code,
            name=payload.name,
            description=payload.description,
            horizon_days=payload.horizon_days,
            time_step_days=payload.time_step_days,
            distribution_type=payload.distribution_type,
            degrees_of_freedom=payload.degrees_of_freedom,
            expected_return_model=payload.expected_return_model,
            volatility_model=payload.volatility_model,
            volatility_multiplier=payload.volatility_multiplier,
            correlation_repair_method=payload.correlation_repair_method,
            is_active=True
        )
        created = await self.repo.create_scenario(scenario)
        await self.repo.log_audit_event(
            action="CREATE_SCENARIO",
            details={"scenario_code": payload.scenario_code, "name": payload.name}
        )
        return created

    async def get_scenario(self, scenario_code_or_id: str) -> Optional[MonteCarloScenario]:
        scenario = await self.repo.get_scenario_by_code(scenario_code_or_id)
        if not scenario:
            scenario = await self.repo.get_scenario_by_id(scenario_code_or_id)
        return scenario

    async def list_scenarios(self, active_only: bool = True) -> List[MonteCarloScenario]:
        return await self.repo.list_scenarios(active_only=active_only)

    async def update_scenario(
        self,
        scenario_code_or_id: str,
        payload: MonteCarloScenarioUpdate
    ) -> MonteCarloScenario:
        scenario = await self.get_scenario(scenario_code_or_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_code_or_id}' not found.")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(scenario, key, value)

        scenario.updated_at = datetime.utcnow()
        updated = await self.repo.update_scenario(scenario)
        await self.repo.log_audit_event(
            action="UPDATE_SCENARIO",
            details={"scenario_code": scenario.scenario_code, "updated_fields": list(payload.model_dump(exclude_unset=True).keys())}
        )
        return updated

    async def delete_scenario(self, scenario_code_or_id: str) -> None:
        scenario = await self.get_scenario(scenario_code_or_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_code_or_id}' not found.")
        await self.repo.delete_scenario(scenario)
        await self.repo.log_audit_event(
            action="DELETE_SCENARIO",
            details={"scenario_code": scenario.scenario_code}
        )

    # ---------------------------------------------------------
    # Portfolio Resolution Helper
    # ---------------------------------------------------------
    def _resolve_holdings(
        self,
        portfolio_id: str,
        overrides: Optional[List[PositionOverride]] = None
    ) -> Tuple[List[str], np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """
        Resolves portfolio positions: symbols, quantities, baseline prices, volatilities, drifts, cash.
        If overrides are provided, uses them directly. Otherwise provides institutional default universe.
        """
        if overrides and len(overrides) > 0:
            symbols = [p.symbol for p in overrides]
            quantities = np.array([float(p.quantity) for p in overrides], dtype=np.float64)
            prices = np.array([float(p.baseline_price or Decimal("100.0")) for p in overrides], dtype=np.float64)
            vols = np.array([float(p.annualized_volatility if p.annualized_volatility is not None else 0.20) for p in overrides], dtype=np.float64)
            drifts = np.array([float(p.annualized_drift if p.annualized_drift is not None else 0.0) for p in overrides], dtype=np.float64)
            cash = 0.0
            return symbols, quantities, prices, vols, drifts, cash

        # Standard default multi-asset equity portfolio benchmark
        symbols = ["AAPL", "MSFT", "NVDA", "AMZN", "JPM"]
        quantities = np.array([500.0, 400.0, 300.0, 450.0, 600.0], dtype=np.float64)
        prices = np.array([180.0, 420.0, 120.0, 185.0, 195.0], dtype=np.float64)
        vols = np.array([0.22, 0.20, 0.42, 0.26, 0.19], dtype=np.float64)
        drifts = np.array([0.08, 0.09, 0.15, 0.07, 0.06], dtype=np.float64)
        cash = 50000.0
        return symbols, quantities, prices, vols, drifts, cash

    def _resolve_correlation_matrix(
        self,
        n_inst: int,
        custom_matrix: Optional[List[List[float]]] = None
    ) -> np.ndarray:
        if custom_matrix is not None:
            mat = np.array(custom_matrix, dtype=np.float64)
            if mat.shape == (n_inst, n_inst):
                return mat

        # Default institutional cross-asset correlation structure
        R = np.full((n_inst, n_inst), 0.45, dtype=np.float64)
        np.fill_diagonal(R, 1.0)
        return R

    # ---------------------------------------------------------
    # Simulation Execution
    # ---------------------------------------------------------
    async def run_simulation(
        self,
        scenario_code_or_id: str,
        request: SimulationExecutionRequest
    ) -> MonteCarloSimulationRun:
        start_time = time.perf_counter()

        scenario = await self.get_scenario(scenario_code_or_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_code_or_id}' not found.")

        # Resolve portfolio holdings
        symbols, quantities, prices, vols, drifts, cash = self._resolve_holdings(
            request.portfolio_id, request.positions_override
        )
        n_inst = len(symbols)

        # Apply scenario parameter adjustments
        if scenario.expected_return_model == "ZERO_DRIFT":
            drifts = np.zeros(n_inst, dtype=np.float64)

        # Scale volatility by multiplier
        effective_vols = vols * float(scenario.volatility_multiplier)

        # Resolve and validate correlation matrix
        raw_corr = self._resolve_correlation_matrix(n_inst, request.correlation_matrix_override)
        corr_matrix, was_repaired = validate_and_repair_correlation_matrix(
            raw_corr,
            repair_method=scenario.correlation_repair_method
        )
        cholesky_L = compute_cholesky_factor(corr_matrix)

        # Deterministic seed management (PCG64)
        if request.random_seed is not None:
            seed = int(request.random_seed)
        else:
            seed = int(np.random.SeedSequence().entropy % (2**63 - 1))

        rng = np.random.default_rng(seed)

        # Simulation parameters
        dt = float(scenario.time_step_days) / 252.0
        n_steps = max(1, int(scenario.horizon_days // scenario.time_step_days))
        n_paths = request.n_paths

        # Chunked execution to manage memory overhead (chunk size e.g. 20,000)
        chunk_size = min(20000, n_paths)
        simulated_prices_list = []

        remaining_paths = n_paths
        while remaining_paths > 0:
            current_chunk = min(chunk_size, remaining_paths)
            chunk_simulated, _ = simulate_geometric_brownian_paths(
                initial_prices=prices,
                drifts=drifts,
                volatilities=effective_vols,
                cholesky_L=cholesky_L,
                n_paths=current_chunk,
                n_steps=n_steps,
                dt=dt,
                distribution_type=scenario.distribution_type,
                degrees_of_freedom=scenario.degrees_of_freedom or 5.0,
                rng=rng,
                store_full_paths=False
            )
            simulated_prices_list.append(chunk_simulated)
            remaining_paths -= current_chunk

        simulated_prices = np.vstack(simulated_prices_list)

        # Compute portfolio outcomes
        outcomes = calculate_portfolio_outcomes(
            quantities=quantities,
            baseline_prices=prices,
            simulated_prices=simulated_prices,
            cash_balance=cash
        )

        pnl_series = outcomes["pnl"]
        portfolio_stats = compute_distribution_statistics(pnl_series, loss_threshold=0.0)
        var_metrics = compute_var_and_cvar(pnl_series, confidence_levels=[0.90, 0.95, 0.99])

        # Compute instrument-level summary
        instrument_results = []
        for i, sym in enumerate(symbols):
            inst_pnl = outcomes["instrument_pnl"][:, i]
            inst_terminal_prices = simulated_prices[:, i]
            inst_losses = -inst_pnl
            inst_var95 = float(np.percentile(inst_losses, 95.0))
            
            base_mv = Decimal(str(round(quantities[i] * prices[i], 4)))
            instrument_results.append(
                MonteCarloInstrumentResult(
                    symbol=sym,
                    quantity=to_decimal(quantities[i], 4),
                    baseline_price=to_decimal(prices[i], 4),
                    baseline_market_value=base_mv,
                    mean_terminal_price=to_decimal(float(np.mean(inst_terminal_prices)), 4),
                    mean_pnl=to_decimal(float(np.mean(inst_pnl)), 4),
                    pnl_std=to_decimal(float(np.std(inst_pnl, ddof=1)), 4),
                    var_95_loss=to_decimal(inst_var95, 4),
                    annualized_volatility=float(round(effective_vols[i], 4))
                )
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Build input hash for audit
        input_dict = {
            "scenario_code": scenario.scenario_code,
            "portfolio_id": request.portfolio_id,
            "n_paths": n_paths,
            "n_steps": n_steps,
            "seed": seed,
            "distribution": scenario.distribution_type,
            "vol_mult": scenario.volatility_multiplier,
        }
        input_hash = hashlib.sha256(json.dumps(input_dict, sort_keys=True).encode()).hexdigest()
        run_code = f"MC_{scenario.scenario_code}_{int(time.time())}_{uuid.uuid4().hex[:6].upper()}"

        # Build run record
        run = MonteCarloSimulationRun(
            scenario_id=scenario.id,
            run_code=run_code,
            portfolio_id=request.portfolio_id,
            n_paths=n_paths,
            n_steps=n_steps,
            random_seed=seed,
            generator_algorithm="PCG64",
            matrix_was_repaired=was_repaired,
            status="COMPLETED",
            execution_duration_ms=duration_ms,
            input_parameters_hash=input_hash,
            executed_at=datetime.utcnow()
        )

        # Build summary
        baseline_val = outcomes["baseline_portfolio_value"]
        sim_vals = outcomes["simulated_portfolio_values"]

        percentiles_data = {
            "p1": portfolio_stats.get("p1", 0.0),
            "p5": portfolio_stats.get("p5", 0.0),
            "p10": portfolio_stats.get("p10", 0.0),
            "p25": portfolio_stats.get("p25", 0.0),
            "p50": portfolio_stats.get("p50", 0.0),
            "p75": portfolio_stats.get("p75", 0.0),
            "p90": portfolio_stats.get("p90", 0.0),
            "p95": portfolio_stats.get("p95", 0.0),
            "p99": portfolio_stats.get("p99", 0.0),
        }

        summary = MonteCarloSimulationSummary(
            baseline_portfolio_value=to_decimal(baseline_val, 4),
            mean_terminal_value=to_decimal(float(np.mean(sim_vals)), 4),
            median_terminal_value=to_decimal(float(np.median(sim_vals)), 4),
            std_terminal_value=to_decimal(float(np.std(sim_vals, ddof=1)), 4),
            mean_pnl=to_decimal(portfolio_stats["mean"], 4),
            median_pnl=to_decimal(portfolio_stats["median"], 4),
            std_pnl=to_decimal(portfolio_stats["std"], 4),
            skewness_pnl=float(round(portfolio_stats["skewness"], 4)),
            excess_kurtosis_pnl=float(round(portfolio_stats["excess_kurtosis"], 4)),
            loss_probability=float(round(portfolio_stats["loss_probability"], 4)),
            min_pnl=to_decimal(portfolio_stats["min"], 4),
            max_pnl=to_decimal(portfolio_stats["max"], 4),
            percentiles_json=percentiles_data
        )
        run.summary = summary

        # Build risk metrics
        risk_metric_objs = []
        for level_str, m in var_metrics.items():
            conf = m["confidence_level"]
            var_l = m["var_loss"]
            cvar_l = m["cvar_loss"]
            var_pct = float(var_l / abs(baseline_val)) if abs(baseline_val) > 1e-6 else 0.0
            cvar_pct = float(cvar_l / abs(baseline_val)) if abs(baseline_val) > 1e-6 else 0.0

            risk_metric_objs.append(
                MonteCarloRiskMetric(
                    confidence_level=conf,
                    var_loss_amount=to_decimal(var_l, 4),
                    cvar_loss_amount=to_decimal(cvar_l, 4),
                    var_percent=float(round(var_pct, 4)),
                    cvar_percent=float(round(cvar_pct, 4)),
                    pnl_cutoff_amount=to_decimal(m["pnl_var_cutoff"], 4)
                )
            )

        run.risk_metrics = risk_metric_objs
        run.instrument_results = instrument_results

        saved_run = await self.repo.create_simulation_run(run)
        saved_run.scenario = scenario

        # Log audit event
        await self.repo.log_audit_event(
            action="EXECUTE_MONTE_CARLO_SIMULATION",
            actor="system",
            details={
                "run_code": run_code,
                "scenario_code": scenario.scenario_code,
                "n_paths": n_paths,
                "n_steps": n_steps,
                "seed": seed,
                "matrix_repaired": was_repaired,
                "loss_prob": portfolio_stats["loss_probability"]
            },
            run_id=saved_run.id
        )

        return saved_run

    async def get_simulation_run(self, run_code_or_id: str) -> Optional[MonteCarloSimulationRun]:
        run = await self.repo.get_simulation_run_by_code(run_code_or_id)
        if not run:
            run = await self.repo.get_simulation_run_by_id(run_code_or_id)
        return run

    async def list_runs_for_scenario(self, scenario_code_or_id: str) -> List[MonteCarloSimulationRun]:
        scenario = await self.get_scenario(scenario_code_or_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_code_or_id}' not found.")
        return await self.repo.list_runs_for_scenario(scenario.id)

