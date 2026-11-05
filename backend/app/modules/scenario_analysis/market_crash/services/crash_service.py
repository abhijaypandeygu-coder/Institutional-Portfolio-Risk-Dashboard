"""
Market Crash Orchestration Service (M10.03).
Coordinates end-to-end execution pipeline:
1. Scenario creation & immutable versioning
2. Benchmark shock resolution & multi-stage compounding
3. Instrument-to-benchmark mapping
4. Authoritative sensitivity retrieval & beta validation
5. Linear and nonlinear downside response computation
6. Position revaluation & portfolio loss aggregation
7. Attribution breakdown (Sector, Benchmark, Linear vs Nonlinear)
8. Diagnostics, coverage metrics, and caveats auditing
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..calculations.crash_math import (
    calculate_index_shock_return,
    calculate_linear_beta_response,
    calculate_downside_response,
    calculate_base_currency_return,
    revalue_position,
    compute_portfolio_revaluation,
    compute_coverage_metrics,
    decompose_linear_nonlinear_impact
)
from ..models.crash_models import (
    MarketCrashScenario,
    MarketCrashScenarioVersion,
    MarketCrashBenchmarkShock,
    MarketCrashMappingResult,
    MarketCrashSensitivitySnapshot,
    MarketCrashNonlinearParameter,
    MarketCrashSimulationRun,
    MarketCrashPositionResult,
    MarketCrashSummaryResult,
    MarketCrashAttributionResult,
    MarketCrashWarning,
    MarketCrashAuditLog
)
from ..schemas.crash_schemas import (
    MarketCrashScenarioCreate,
    MarketCrashScenarioResponse,
    BenchmarkShockConfig,
    NonlinearParameterConfig,
    SimulationExecutionRequest,
    SimulationSummaryResponse,
    PositionResultResponse,
    AttributionResultResponse,
    WarningResponse
)
from ..repositories.crash_repository import MarketCrashRepository


class MarketCrashService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MarketCrashRepository(db)

    # -------------------------------------------------------------------------
    # Scenario Creation & Versioning
    # -------------------------------------------------------------------------
    async def create_scenario(self, req: MarketCrashScenarioCreate) -> MarketCrashScenarioResponse:
        scenario_id = f"mcsc_{uuid.uuid4().hex[:12]}"
        version_id = f"mcsv_{uuid.uuid4().hex[:12]}"

        # Calculate configuration hash
        config_dict = req.model_dump(mode="json")
        config_str = json.dumps(config_dict, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode("utf-8")).hexdigest()

        scenario = MarketCrashScenario(
            id=scenario_id,
            scenario_code=req.scenario_code,
            scenario_name=req.scenario_name,
            description=req.description,
            category=req.category,
            portfolio_id=req.portfolio_id,
            visibility=req.visibility,
            author_id=req.author_id,
            owner_id=req.owner_id,
            current_version=1,
            status="ACTIVE"
        )
        await self.repo.create_scenario(scenario)

        version = MarketCrashScenarioVersion(
            id=version_id,
            scenario_id=scenario_id,
            version=1,
            configuration_json=config_dict,
            configuration_hash=config_hash,
            change_reason="Initial creation",
            created_by=req.author_id
        )
        await self.repo.create_scenario_version(version)

        # Benchmark shocks
        for b_shock in req.benchmark_shocks:
            shock_r, i_s = calculate_index_shock_return(
                shock_method=b_shock.shock_method,
                baseline_index_level=b_shock.baseline_index_level,
                target_index_level=b_shock.target_index_level,
                index_point_change=b_shock.index_point_change,
                percentage_shock=b_shock.percentage_shock,
                multi_stage_returns=b_shock.multi_stage_returns
            )
            shock_model = MarketCrashBenchmarkShock(
                id=f"mcbs_{uuid.uuid4().hex[:12]}",
                scenario_version_id=version_id,
                benchmark_id=b_shock.benchmark_id,
                benchmark_name=b_shock.benchmark_name,
                market_region=b_shock.market_region,
                shock_method=b_shock.shock_method,
                baseline_index_level=b_shock.baseline_index_level,
                target_index_level=b_shock.target_index_level or i_s,
                index_point_change=b_shock.index_point_change,
                shock_return=shock_r,
                return_definition=b_shock.return_definition,
                benchmark_currency=b_shock.benchmark_currency,
                stage_order=b_shock.stage_order,
                shock_configuration=b_shock.model_dump(mode="json")
            )
            self.db.add(shock_model)

        # Nonlinear parameters
        if req.nonlinear_parameters:
            for nl in req.nonlinear_parameters:
                nl_model = MarketCrashNonlinearParameter(
                    id=f"mcnl_{uuid.uuid4().hex[:12]}",
                    scenario_version_id=version_id,
                    instrument_id=nl.instrument_id,
                    sector_id=nl.sector_id,
                    model_type=nl.model_type,
                    threshold=nl.threshold,
                    stress_multiplier=nl.stress_multiplier,
                    curvature_parameter=nl.curvature_parameter,
                    exponent=nl.exponent,
                    user_adjustment=nl.user_adjustment,
                    parameter_source=nl.parameter_source,
                    configuration_json=nl.model_dump(mode="json")
                )
                self.db.add(nl_model)

        await self.db.commit()

        # Build response
        saved = await self.repo.get_scenario(scenario_id)
        resp = MarketCrashScenarioResponse.model_validate(saved)
        resp.benchmark_shocks = req.benchmark_shocks
        resp.nonlinear_parameters = req.nonlinear_parameters
        return resp

    # -------------------------------------------------------------------------
    # Simulation Execution
    # -------------------------------------------------------------------------
    async def execute_simulation(self, req: SimulationExecutionRequest) -> SimulationSummaryResponse:
        run_id = f"mcrun_{uuid.uuid4().hex[:12]}"
        sim_code = f"SIM_{uuid.uuid4().hex[:8].upper()}"

        warnings: List[MarketCrashWarning] = []
        mapping_models: List[MarketCrashMappingResult] = []
        sensitivity_models: List[MarketCrashSensitivitySnapshot] = []
        position_models: List[MarketCrashPositionResult] = []
        positions_reval: List[Dict[str, Decimal]] = []
        positions_coverage_data: List[Dict[str, Any]] = []

        # 1. Resolve Benchmark Shocks
        benchmark_shock_map: Dict[str, Decimal] = {}
        for b in req.benchmark_shocks:
            shock_r, _ = calculate_index_shock_return(
                shock_method=b.shock_method,
                baseline_index_level=b.baseline_index_level,
                target_index_level=b.target_index_level,
                index_point_change=b.index_point_change,
                percentage_shock=b.percentage_shock,
                multi_stage_returns=b.multi_stage_returns
            )
            benchmark_shock_map[b.benchmark_id] = shock_r

        # 2. Map Nonlinear Parameters
        nl_map_inst: Dict[str, NonlinearParameterConfig] = {}
        nl_map_sector: Dict[str, NonlinearParameterConfig] = {}
        if req.nonlinear_parameters:
            for nl in req.nonlinear_parameters:
                if nl.instrument_id:
                    nl_map_inst[nl.instrument_id] = nl
                if nl.sector_id:
                    nl_map_sector[nl.sector_id] = nl

        # 3. Process Positions
        for pos in req.positions:
            is_mapped = False
            is_beta_valid = False
            is_nl_eligible = False

            # Resolve benchmark
            target_benchmark = pos.benchmark_id
            mapping_method = "EXPLICIT" if target_benchmark else "DEFAULT_REGIONAL"
            
            if not target_benchmark:
                if pos.market_region == "INDIA":
                    target_benchmark = "NIFTY_50"
                else:
                    target_benchmark = "SPX"

            if target_benchmark in benchmark_shock_map:
                is_mapped = True
                b_shock = benchmark_shock_map[target_benchmark]
            else:
                b_shock = list(benchmark_shock_map.values())[0] if benchmark_shock_map else Decimal("-0.20")
                warnings.append(MarketCrashWarning(
                    id=f"mcwrn_{uuid.uuid4().hex[:12]}",
                    simulation_run_id=run_id,
                    instrument_id=pos.instrument_id,
                    benchmark_id=target_benchmark,
                    warning_code="UNMAPPED_FALLBACK_APPLIED",
                    severity="WARNING",
                    category="MAPPING",
                    message=f"Instrument {pos.instrument_id} assigned benchmark {target_benchmark} with shock {b_shock}"
                ))

            # Resolve Beta
            beta = pos.beta_value if pos.beta_value is not None else Decimal("1.00")
            if pos.beta_value is not None:
                is_beta_valid = True
            else:
                warnings.append(MarketCrashWarning(
                    id=f"mcwrn_{uuid.uuid4().hex[:12]}",
                    simulation_run_id=run_id,
                    instrument_id=pos.instrument_id,
                    warning_code="BETA_ASSUMPTION_APPLIED",
                    severity="INFO",
                    category="SENSITIVITY",
                    message=f"Instrument {pos.instrument_id} missing beta; assumed standard beta 1.00"
                ))

            downside_b = pos.downside_beta

            # Linear market response
            linear_r = calculate_linear_beta_response(beta, b_shock)

            # Check nonlinear configuration
            nl_cfg = nl_map_inst.get(pos.instrument_id) or (nl_map_sector.get(pos.sector) if pos.sector else None)
            model_type = req.response_model
            nl_thresh = None
            nl_lam = None
            nl_gam = None
            nl_exp = None
            nl_user = pos.user_adjustment

            # If position has a specific nonlinear config (e.g. for its sector or instrument), use that model type
            # Otherwise, if the portfolio-level response_model is LINEAR or instrument has no nl_cfg, default to LINEAR
            if nl_cfg:
                is_nl_eligible = True
                model_type = nl_cfg.model_type
                nl_thresh = nl_cfg.threshold
                nl_lam = nl_cfg.stress_multiplier
                nl_gam = nl_cfg.curvature_parameter
                nl_exp = nl_cfg.exponent
                if nl_cfg.user_adjustment:
                    nl_user = (nl_user or Decimal("0")) + nl_cfg.user_adjustment
            else:
                model_type = "LINEAR"

            downside_resp = calculate_downside_response(
                linear_return=linear_r,
                benchmark_shock=b_shock,
                response_model=model_type,
                unconditional_beta=beta,
                downside_beta=downside_b,
                threshold=nl_thresh,
                stress_multiplier=nl_lam,
                exponent=nl_exp,
                curvature=nl_gam,
                sector_adjustment=pos.sector_adjustment,
                user_adjustment=nl_user
            )

            # Currency conversion
            final_local_r = downside_resp["final_scenario_return"]
            final_base_r = calculate_base_currency_return(final_local_r, pos.fx_return)

            # Revalue position
            reval = revalue_position(
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                final_return=final_base_r,
                baseline_nav=req.baseline_nav
            )

            positions_reval.append(reval)
            positions_coverage_data.append({
                "baseline_market_value": reval["baseline_market_value"],
                "is_mapped": is_mapped,
                "is_beta_valid": is_beta_valid,
                "is_nonlinear_eligible": is_nl_eligible
            })

            # Record mapping & sensitivity snapshots
            mapping_models.append(MarketCrashMappingResult(
                id=f"mcmp_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id,
                benchmark_id=target_benchmark,
                mapping_method=mapping_method,
                mapping_priority=1,
                mapping_confidence=Decimal("1.0"),
                override_status=pos.benchmark_id is not None
            ))

            sensitivity_models.append(MarketCrashSensitivitySnapshot(
                id=f"mcss_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                instrument_id=pos.instrument_id,
                benchmark_id=target_benchmark,
                sensitivity_model="OLS_BETA",
                beta_value=beta,
                downside_beta=downside_b,
                quality_status="VALID" if is_beta_valid else "ASSUMED"
            ))

            pos_res = MarketCrashPositionResult(
                id=f"mcpos_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id,
                sector=pos.sector or "UNCLASSIFIED",
                market_region=pos.market_region or "US",
                currency=pos.currency,
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                scenario_price=reval["scenario_price"],
                baseline_market_value=reval["baseline_market_value"],
                scenario_market_value=reval["scenario_market_value"],
                benchmark_id=target_benchmark,
                benchmark_shock=b_shock,
                beta_value=beta,
                downside_beta=downside_b,
                linear_return=downside_resp["linear_return"],
                downside_adjustment=downside_resp["downside_adjustment"],
                nonlinear_adjustment=downside_resp["nonlinear_adjustment"],
                sector_adjustment=downside_resp["sector_adjustment"],
                user_adjustment=downside_resp["user_adjustment"],
                final_scenario_return=final_base_r,
                scenario_pnl=reval["scenario_pnl"],
                scenario_loss=reval["scenario_loss"],
                portfolio_contribution=reval["portfolio_contribution"],
                mapping_status="MAPPED" if is_mapped else "UNMAPPED",
                quality_status="VALID" if is_beta_valid else "ASSUMED"
            )
            position_models.append(pos_res)

        # 4. Aggregate Portfolio Revaluation
        port_reval = compute_portfolio_revaluation(req.baseline_nav, positions_reval)
        cov_metrics = compute_coverage_metrics(positions_coverage_data)

        # 5. Attributions (Sector, Benchmark, Linear vs Nonlinear)
        attribution_models: List[MarketCrashAttributionResult] = []

        # A. Sector Attribution
        sector_agg: Dict[str, Dict[str, Decimal]] = {}
        for p in position_models:
            sec = p.sector or "UNCLASSIFIED"
            if sec not in sector_agg:
                sector_agg[sec] = {"exposure": Decimal("0"), "pnl": Decimal("0"), "loss": Decimal("0"), "lin": Decimal("0"), "nl": Decimal("0")}
            p_lin, p_nl = decompose_linear_nonlinear_impact(p.baseline_market_value, p.linear_return, p.final_scenario_return)
            sector_agg[sec]["exposure"] += abs(p.baseline_market_value)
            sector_agg[sec]["pnl"] += p.scenario_pnl
            sector_agg[sec]["loss"] += p.scenario_loss
            sector_agg[sec]["lin"] += p_lin
            sector_agg[sec]["nl"] += p_nl

        for sec, sdata in sector_agg.items():
            contrib_pct = (sdata["pnl"] / req.baseline_nav) if req.baseline_nav > Decimal("0") else Decimal("0")
            attribution_models.append(MarketCrashAttributionResult(
                id=f"mcat_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                attribution_type="SECTOR",
                attribution_identifier=sec,
                baseline_exposure=sdata["exposure"],
                scenario_pnl=sdata["pnl"],
                scenario_loss=sdata["loss"],
                linear_impact=sdata["lin"],
                nonlinear_impact=sdata["nl"],
                contribution_percentage=contrib_pct.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                reconciliation_residual=Decimal("0")
            ))

        # B. Benchmark Attribution
        bench_agg: Dict[str, Dict[str, Decimal]] = {}
        for p in position_models:
            b_id = p.benchmark_id
            if b_id not in bench_agg:
                bench_agg[b_id] = {"exposure": Decimal("0"), "pnl": Decimal("0"), "loss": Decimal("0"), "lin": Decimal("0"), "nl": Decimal("0")}
            p_lin, p_nl = decompose_linear_nonlinear_impact(p.baseline_market_value, p.linear_return, p.final_scenario_return)
            bench_agg[b_id]["exposure"] += abs(p.baseline_market_value)
            bench_agg[b_id]["pnl"] += p.scenario_pnl
            bench_agg[b_id]["loss"] += p.scenario_loss
            bench_agg[b_id]["lin"] += p_lin
            bench_agg[b_id]["nl"] += p_nl

        for b_id, bdata in bench_agg.items():
            contrib_pct = (bdata["pnl"] / req.baseline_nav) if req.baseline_nav > Decimal("0") else Decimal("0")
            attribution_models.append(MarketCrashAttributionResult(
                id=f"mcat_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                attribution_type="BENCHMARK",
                attribution_identifier=b_id,
                baseline_exposure=bdata["exposure"],
                scenario_pnl=bdata["pnl"],
                scenario_loss=bdata["loss"],
                linear_impact=bdata["lin"],
                nonlinear_impact=bdata["nl"],
                contribution_percentage=contrib_pct.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                reconciliation_residual=Decimal("0")
            ))

        # C. Linear vs Nonlinear Overall Decomposition
        total_lin_pnl = sum([decompose_linear_nonlinear_impact(p.baseline_market_value, p.linear_return, p.final_scenario_return)[0] for p in position_models], Decimal("0"))
        total_nl_pnl = sum([decompose_linear_nonlinear_impact(p.baseline_market_value, p.linear_return, p.final_scenario_return)[1] for p in position_models], Decimal("0"))

        attribution_models.append(MarketCrashAttributionResult(
            id=f"mcat_{uuid.uuid4().hex[:12]}",
            simulation_run_id=run_id,
            attribution_type="LINEAR_VS_NONLINEAR",
            attribution_identifier="LINEAR_BETA_IMPACT",
            baseline_exposure=port_reval["gross_exposure"],
            scenario_pnl=total_lin_pnl,
            scenario_loss=Decimal("0") if total_lin_pnl >= Decimal("0") else -total_lin_pnl,
            linear_impact=total_lin_pnl,
            nonlinear_impact=Decimal("0"),
            contribution_percentage=(total_lin_pnl / req.baseline_nav).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
            reconciliation_residual=Decimal("0")
        ))
        attribution_models.append(MarketCrashAttributionResult(
            id=f"mcat_{uuid.uuid4().hex[:12]}",
            simulation_run_id=run_id,
            attribution_type="LINEAR_VS_NONLINEAR",
            attribution_identifier="NONLINEAR_STRESS_IMPACT",
            baseline_exposure=port_reval["gross_exposure"],
            scenario_pnl=total_nl_pnl,
            scenario_loss=Decimal("0") if total_nl_pnl >= Decimal("0") else -total_nl_pnl,
            linear_impact=Decimal("0"),
            nonlinear_impact=total_nl_pnl,
            contribution_percentage=(total_nl_pnl / req.baseline_nav).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
            reconciliation_residual=Decimal("0")
        ))

        # 6. Master Run Record
        now = datetime.now(timezone.utc)
        run_record = MarketCrashSimulationRun(
            id=run_id,
            simulation_code=sim_code,
            scenario_id=req.scenario_id,
            portfolio_id=req.portfolio_id,
            portfolio_snapshot_id=req.portfolio_snapshot_id,
            base_currency=req.base_currency,
            response_model=req.response_model,
            missing_data_policy=req.missing_data_policy,
            calculation_version="1.0.0",
            run_status="COMPLETED" if not warnings else "COMPLETED_WITH_WARNINGS",
            baseline_nav=port_reval["baseline_nav"],
            scenario_nav=port_reval["scenario_nav"],
            scenario_pnl=port_reval["scenario_pnl"],
            scenario_loss=port_reval["scenario_loss"],
            scenario_return=port_reval["scenario_return"],
            mapped_coverage=cov_metrics["mapped_coverage"],
            beta_coverage=cov_metrics["beta_coverage"],
            nonlinear_coverage=cov_metrics["nonlinear_coverage"],
            started_at=now,
            completed_at=now
        )
        await self.repo.create_simulation_run(run_record)

        summary_result = MarketCrashSummaryResult(
            id=f"mcsum_{uuid.uuid4().hex[:12]}",
            simulation_run_id=run_id,
            baseline_nav=port_reval["baseline_nav"],
            scenario_nav=port_reval["scenario_nav"],
            scenario_pnl=port_reval["scenario_pnl"],
            scenario_loss=port_reval["scenario_loss"],
            scenario_return=port_reval["scenario_return"],
            gross_exposure=port_reval["gross_exposure"],
            net_exposure=port_reval["net_exposure"],
            mapped_exposure=port_reval["gross_exposure"] * cov_metrics["mapped_coverage"],
            beta_covered_exposure=port_reval["gross_exposure"] * cov_metrics["beta_coverage"],
            nonlinear_covered_exposure=port_reval["gross_exposure"] * cov_metrics["nonlinear_coverage"],
            affected_position_count=len(position_models),
            warning_count=len(warnings)
        )

        audit_log = MarketCrashAuditLog(
            id=f"mcaud_{uuid.uuid4().hex[:12]}",
            scenario_id=req.scenario_id,
            simulation_run_id=run_id,
            action_type="EXECUTE_CRASH_SIMULATION",
            reason=f"Executed crash simulation under {req.response_model} model"
        )

        await self.repo.save_run_details(
            mappings=mapping_models,
            sensitivities=sensitivity_models,
            positions=position_models,
            summary=summary_result,
            attributions=attribution_models,
            warnings=warnings,
            audit_log=audit_log
        )

        return SimulationSummaryResponse(
            simulation_id=run_id,
            simulation_code=sim_code,
            scenario_id=req.scenario_id,
            portfolio_id=req.portfolio_id,
            base_currency=req.base_currency,
            response_model=req.response_model,
            run_status=run_record.run_status,
            baseline_nav=port_reval["baseline_nav"],
            scenario_nav=port_reval["scenario_nav"],
            scenario_pnl=port_reval["scenario_pnl"],
            scenario_loss=port_reval["scenario_loss"],
            scenario_return=port_reval["scenario_return"],
            gross_exposure=port_reval["gross_exposure"],
            net_exposure=port_reval["net_exposure"],
            mapped_coverage=cov_metrics["mapped_coverage"],
            beta_coverage=cov_metrics["beta_coverage"],
            nonlinear_coverage=cov_metrics["nonlinear_coverage"],
            affected_positions=len(position_models),
            started_at=now,
            completed_at=now,
            position_results=[PositionResultResponse.model_validate(p) for p in position_models],
            attribution_results=[AttributionResultResponse.model_validate(a) for a in attribution_models],
            warnings=[WarningResponse.model_validate(w) for w in warnings]
        )
