"""
M10.05 Correlation Shock Orchestration & Calculation Services.
Integrates:
- Baseline matrix retrieval from M07.05 without mutation
- Baseline covariance retrieval from M07.06
- Authoritative portfolio weights & exposures from M05
- Transformation engines (Increase, Convergence, Convergence-to-one, Pairwise, Group-level)
- Mathematical matrix validation & PSD condition diagnostics
- Controlled matrix repair & transformation audits
- Stressed covariance construction (Sigma_stress = D_sigma * R_stress * D_sigma)
- Stressed portfolio risk recalculation & Euler risk contribution decomposition
- Baseline vs. Stressed risk comparison & narrative generation
- Versioning and immutable execution history persistence
"""
from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Tuple, Any
import uuid
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.market_risk.correlation.models import CorrelationMatrixMetadata
from backend.app.modules.market_risk.covariance.models import CovarianceMatrixMetadata
from backend.app.modules.portfolio_management.position_valuation.models import PositionValuation

from backend.app.modules.scenario_analysis.correlation_shock.models import (
    CorrelationShockScenario,
    CorrelationShockScenarioVersion,
    CorrelationShockScopeMember,
    CorrelationShockPairRule,
    CorrelationShockExecution,
    CorrelationShockMatrixDiagnostic,
    CorrelationShockRepair,
    CorrelationShockRiskResult,
    CorrelationShockRiskContribution,
    ScenarioScope,
    ScenarioStatus,
    VolatilityMode,
    ExecutionStatus,
)
from backend.app.modules.scenario_analysis.correlation_shock.schemas import (
    CorrelationShockScenarioCreate,
    PairRuleCreate,
    ScopeMemberCreate,
    ExecuteScenarioRequest,
    ExecutionResponse,
    MatrixValidateResponse,
    RiskResultSummary,
    RiskContributionItem,
)
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
from backend.app.modules.scenario_analysis.correlation_shock.repositories import (
    CorrelationShockRepository,
)


class CorrelationShockService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CorrelationShockRepository(session)

    # ---------------------------------------------------------
    # 1. Scenario Lifecycle & Versioning
    # ---------------------------------------------------------
    async def create_scenario(self, payload: CorrelationShockScenarioCreate) -> CorrelationShockScenario:
        # Create parent scenario
        scenario = CorrelationShockScenario(
            scenario_code=payload.scenario_code,
            name=payload.name,
            description=payload.description,
            scenario_scope=payload.scenario_scope,
            portfolio_id=payload.portfolio_id,
            scenario_category=payload.scenario_category,
            status=ScenarioStatus.ACTIVE,
            created_by=payload.created_by,
        )
        scenario = await self.repo.create_scenario(scenario)

        # Create immutable version 1
        version = CorrelationShockScenarioVersion(
            scenario_id=scenario.id,
            version_number=1,
            transformation_method=payload.transformation_method.value,
            stress_target=payload.stress_target,
            stress_intensity=payload.stress_intensity,
            volatility_mode=payload.volatility_mode,
            matrix_repair_method=payload.matrix_repair_method.value,
            repair_parameters=payload.repair_parameters or {},
            risk_model_configuration={"method": "ANALYTIC_EULER"},
            configuration_json=payload.model_dump(mode="json"),
            created_by=payload.created_by,
        )
        version = await self.repo.create_scenario_version(version)

        # Add scope members if any
        if payload.scope_members:
            for sm in payload.scope_members:
                member = CorrelationShockScopeMember(
                    scenario_version_id=version.id,
                    scope_type=sm.scope_type,
                    instrument_id=sm.instrument_id,
                    factor_id=sm.factor_id,
                    group_id=sm.group_id,
                    membership_source=sm.membership_source,
                )
                self.session.add(member)

        # Add pair rules if any
        if payload.pair_rules:
            for pr in payload.pair_rules:
                # Canonicalize pair order entity_a <= entity_b
                ent_a, ent_b = (
                    (pr.entity_a_id, pr.entity_b_id)
                    if pr.entity_a_id <= pr.entity_b_id
                    else (pr.entity_b_id, pr.entity_a_id)
                )
                pair_rule = CorrelationShockPairRule(
                    scenario_version_id=version.id,
                    entity_a_id=ent_a,
                    entity_b_id=ent_b,
                    entity_type=pr.entity_type,
                    baseline_correlation=pr.baseline_correlation,
                    target_correlation=pr.target_correlation,
                    stress_intensity=pr.stress_intensity,
                    transformation_method=pr.transformation_method.value,
                )
                self.session.add(pair_rule)

        await self.session.commit()
        return await self.repo.get_scenario_by_id(scenario.id)

    async def list_scenarios(self, portfolio_id: Optional[str] = None) -> List[CorrelationShockScenario]:
        return await self.repo.list_scenarios(portfolio_id=portfolio_id)

    async def get_scenario(self, scenario_id: str) -> Optional[CorrelationShockScenario]:
        return await self.repo.get_scenario_by_id(scenario_id)

    # ---------------------------------------------------------
    # 2. Standalone Matrix Validation Engine
    # ---------------------------------------------------------
    def validate_matrix(
        self,
        matrix_data: List[List[float]],
        symmetry_tol: float = 1e-6,
        psd_tol: float = 1e-7,
    ) -> MatrixValidateResponse:
        mat = np.array(matrix_data, dtype=np.float64)
        diag = validate_correlation_matrix(mat, symmetry_tol=symmetry_tol, psd_tol=psd_tol)
        return MatrixValidateResponse(
            status=diag["status"],
            is_symmetric=diag["is_symmetric"],
            diagonal_valid=diag["diagonal_valid"],
            bounds_valid=diag["bounds_valid"],
            is_psd=diag["is_psd"],
            minimum_eigenvalue=diag["minimum_eigenvalue"],
            maximum_eigenvalue=diag["maximum_eigenvalue"],
            matrix_rank=diag["matrix_rank"],
            condition_number=diag["condition_number"],
            negative_eigenvalue_count=diag["negative_eigenvalue_count"],
            warnings=diag["warnings"],
        )

    # ---------------------------------------------------------
    # 3. Execution Pipeline Orchestration
    # ---------------------------------------------------------
    async def execute_scenario(
        self,
        scenario_id: str,
        request: ExecuteScenarioRequest,
    ) -> ExecutionResponse:
        start_time = time.time()
        scenario = await self.repo.get_scenario_by_id(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        version = await self.repo.get_latest_version(scenario_id)
        if not version:
            raise ValueError(f"No version found for scenario {scenario_id}")

        execution_code = f"EXEC_CORR_{uuid.uuid4().hex[:10].upper()}"
        execution = CorrelationShockExecution(
            execution_code=execution_code,
            scenario_version_id=version.id,
            portfolio_id=request.portfolio_id or scenario.portfolio_id,
            portfolio_snapshot_id=request.portfolio_snapshot_id,
            baseline_matrix_id=request.baseline_matrix_id,
            execution_status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            executed_by=request.executed_by or "analyst",
        )
        execution = await self.repo.create_execution(execution)

        try:
            # 1. Resolve Universe, Baseline Matrix, Volatilities, and Portfolio Weights
            (
                asset_ids,
                asset_symbols,
                weights_vec,
                base_corr_mat,
                vols_vec,
            ) = await self._resolve_execution_universe_and_inputs(
                scenario=scenario, version=version, request=request
            )

            n_assets = len(asset_ids)
            if n_assets == 0:
                raise ValueError("Portfolio or universe contains 0 assets")

            execution.matrix_asset_ids = asset_ids
            execution.matrix_asset_symbols = asset_symbols
            execution.baseline_matrix_data = base_corr_mat.tolist()

            # 2. Baseline Matrix Diagnostics
            base_diag = validate_correlation_matrix(base_corr_mat)
            diag_base_db = CorrelationShockMatrixDiagnostic(
                execution_id=execution.id,
                matrix_stage="BASELINE",
                is_symmetric=base_diag["is_symmetric"],
                diagonal_valid=base_diag["diagonal_valid"],
                bounds_valid=base_diag["bounds_valid"],
                is_psd=base_diag["is_psd"],
                minimum_eigenvalue=base_diag["minimum_eigenvalue"],
                maximum_eigenvalue=base_diag["maximum_eigenvalue"],
                matrix_rank=base_diag["matrix_rank"],
                condition_number=base_diag["condition_number"],
                negative_eigenvalue_count=base_diag["negative_eigenvalue_count"],
                validation_status=base_diag["status"].value,
                diagnostics_json=base_diag,
            )
            self.session.add(diag_base_db)

            # 3. Apply Configured Correlation Transformations (Raw Shocked Matrix)
            raw_stressed_mat = self._apply_correlation_transformations(
                base_mat=base_corr_mat,
                asset_ids=asset_ids,
                version=version,
            )
            execution.stressed_matrix_data = raw_stressed_mat.tolist()

            # 4. Raw Stressed Matrix Diagnostics
            raw_diag = validate_correlation_matrix(raw_stressed_mat)
            diag_raw_db = CorrelationShockMatrixDiagnostic(
                execution_id=execution.id,
                matrix_stage="RAW_STRESSED",
                is_symmetric=raw_diag["is_symmetric"],
                diagonal_valid=raw_diag["diagonal_valid"],
                bounds_valid=raw_diag["bounds_valid"],
                is_psd=raw_diag["is_psd"],
                minimum_eigenvalue=raw_diag["minimum_eigenvalue"],
                maximum_eigenvalue=raw_diag["maximum_eigenvalue"],
                matrix_rank=raw_diag["matrix_rank"],
                condition_number=raw_diag["condition_number"],
                negative_eigenvalue_count=raw_diag["negative_eigenvalue_count"],
                validation_status=raw_diag["status"].value,
                diagnostics_json=raw_diag,
            )
            self.session.add(diag_raw_db)

            # 5. Controlled Matrix Repair (if requested & needed)
            repair_method_enum = MatrixRepairMethod(version.matrix_repair_method)
            repaired_mat, repair_audit = repair_correlation_matrix(
                raw_matrix=raw_stressed_mat,
                method=repair_method_enum,
                eigenvalue_floor=1e-7,
                shrinkage_alpha=0.1,
            )

            repair_db = CorrelationShockRepair(
                execution_id=execution.id,
                repair_method=repair_audit["method"],
                repair_parameters=repair_audit["parameters"],
                pre_repair_status=repair_audit["pre_repair_status"],
                post_repair_status=repair_audit["post_repair_status"],
                maximum_adjustment=repair_audit["maximum_adjustment"],
                frobenius_adjustment=repair_audit["frobenius_adjustment"],
                convergence_status=repair_audit["convergence_status"],
                iterations=repair_audit["iterations"],
            )
            self.session.add(repair_db)

            execution.repaired_matrix_data = repaired_mat.tolist()

            # 6. Repaired Matrix Diagnostics
            repaired_diag = validate_correlation_matrix(repaired_mat)
            diag_repaired_db = CorrelationShockMatrixDiagnostic(
                execution_id=execution.id,
                matrix_stage="REPAIRED",
                is_symmetric=repaired_diag["is_symmetric"],
                diagonal_valid=repaired_diag["diagonal_valid"],
                bounds_valid=repaired_diag["bounds_valid"],
                is_psd=repaired_diag["is_psd"],
                minimum_eigenvalue=repaired_diag["minimum_eigenvalue"],
                maximum_eigenvalue=repaired_diag["maximum_eigenvalue"],
                matrix_rank=repaired_diag["matrix_rank"],
                condition_number=repaired_diag["condition_number"],
                negative_eigenvalue_count=repaired_diag["negative_eigenvalue_count"],
                validation_status=repaired_diag["status"].value,
                diagnostics_json=repaired_diag,
            )
            self.session.add(diag_repaired_db)

            # 7. Construct Covariance Matrices (Baseline and Final Stressed)
            # Baseline Covariance
            base_cov = construct_stressed_covariance(base_corr_mat, vols_vec)
            # Final Stressed Covariance using Repaired Matrix
            final_cov = construct_stressed_covariance(repaired_mat, vols_vec)

            # 8. Recalculate Portfolio Risk & Euler Risk Contributions
            base_risk = calculate_portfolio_risk_and_contributions(
                weights=weights_vec,
                cov_matrix=base_cov,
                asset_ids=asset_ids,
                asset_symbols=asset_symbols,
                volatilities=vols_vec,
            )
            stressed_risk = calculate_portfolio_risk_and_contributions(
                weights=weights_vec,
                cov_matrix=final_cov,
                asset_ids=asset_ids,
                asset_symbols=asset_symbols,
                volatilities=vols_vec,
            )

            # 9. Compute Diversification Diagnostics
            base_div = calculate_diversification_metrics(
                weights=weights_vec,
                volatilities=vols_vec,
                portfolio_volatility=base_risk["portfolio_volatility"],
                correlation_matrix=base_corr_mat,
            )
            stressed_div = calculate_diversification_metrics(
                weights=weights_vec,
                volatilities=vols_vec,
                portfolio_volatility=stressed_risk["portfolio_volatility"],
                correlation_matrix=repaired_mat,
            )

            # 10. Baseline vs. Stressed Comparison & Narrative
            comparison = compare_baseline_vs_stressed(
                base_risk=base_risk,
                stress_risk=stressed_risk,
                base_div=base_div,
                stress_div=stressed_div,
            )

            # 11. Persist Risk Results
            for m_name, b_val, s_val, d_val, pct_d, unit in [
                ("PORTFOLIO_VOLATILITY", comparison["baseline_volatility"], comparison["stressed_volatility"], comparison["absolute_volatility_change"], comparison["percentage_volatility_change"], "VOL_ANNUAL"),
                ("PORTFOLIO_VARIANCE", comparison["baseline_variance"], comparison["stressed_variance"], comparison["absolute_variance_change"], comparison["percentage_variance_change"], "VAR_ANNUAL"),
                ("AVERAGE_CORRELATION", comparison["baseline_average_correlation"], comparison["stressed_average_correlation"], comparison["average_correlation_change"], None, "RATIO"),
                ("DIVERSIFICATION_BENEFIT", comparison["baseline_diversification_benefit"], comparison["stressed_diversification_benefit"], comparison["diversification_benefit_change"], None, "VOL_ANNUAL"),
            ]:
                res_db = CorrelationShockRiskResult(
                    execution_id=execution.id,
                    metric_name=m_name,
                    baseline_value=b_val,
                    stressed_value=s_val,
                    absolute_change=d_val,
                    percentage_change=pct_d,
                    unit=unit,
                    calculation_method="EULER_ANALYTIC",
                )
                self.session.add(res_db)

            # 12. Persist Risk Contributions
            base_c_dict = {c["asset_id"]: c for c in base_risk["contributions"]}
            response_contribs: List[RiskContributionItem] = []

            for s_c in stressed_risk["contributions"]:
                aid = s_c["asset_id"]
                sym = s_c["symbol"]
                b_c = base_c_dict.get(aid, {})

                b_contrib = b_c.get("component_risk_contribution")
                s_contrib = s_c["component_risk_contribution"]
                d_contrib = s_contrib - b_contrib if b_contrib is not None else None
                pct_d_contrib = (
                    (d_contrib / abs(b_contrib) * 100.0)
                    if (b_contrib is not None and abs(b_contrib) > 1e-12)
                    else None
                )

                rc_db = CorrelationShockRiskContribution(
                    execution_id=execution.id,
                    entity_type="INSTRUMENT",
                    entity_id=aid,
                    symbol=sym,
                    weight=s_c["weight"],
                    baseline_contribution=b_contrib,
                    stressed_contribution=s_contrib,
                    absolute_change=d_contrib,
                    percentage_change=pct_d_contrib,
                    baseline_contribution_share=b_c.get("percentage_risk_contribution"),
                    stressed_contribution_share=s_c["percentage_risk_contribution"],
                )
                self.session.add(rc_db)

                response_contribs.append(
                    RiskContributionItem(
                        entity_id=aid,
                        symbol=sym,
                        weight=s_c["weight"],
                        standalone_volatility=s_c["standalone_volatility"],
                        baseline_contribution=b_contrib,
                        stressed_contribution=s_contrib,
                        absolute_change=d_contrib,
                        percentage_change=pct_d_contrib,
                        baseline_contribution_share=b_c.get("percentage_risk_contribution"),
                        stressed_contribution_share=s_c["percentage_risk_contribution"],
                    )
                )

            # 13. Audit Log
            await self.repo.log_audit_event(
                execution_id=execution.id,
                event_type="EXECUTION_COMPLETED",
                payload={"execution_code": execution.execution_code, "n_assets": n_assets},
                actor_id=request.executed_by or "analyst",
            )

            # Finalize Execution
            duration_ms = int((time.time() - start_time) * 1000)
            execution.execution_status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            execution.execution_duration_ms = duration_ms
            await self.session.commit()

            return ExecutionResponse(
                execution_id=execution.id,
                execution_code=execution.execution_code,
                scenario_id=scenario.id,
                version_number=version.version_number,
                portfolio_id=execution.portfolio_id,
                execution_status=execution.execution_status,
                execution_duration_ms=duration_ms,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
                asset_ids=asset_ids,
                asset_symbols=asset_symbols,
                baseline_matrix=base_corr_mat.tolist(),
                stressed_matrix=raw_stressed_mat.tolist(),
                repaired_matrix=repaired_mat.tolist(),
                baseline_diagnostics=MatrixValidateResponse(
                    status=base_diag["status"],
                    is_symmetric=base_diag["is_symmetric"],
                    diagonal_valid=base_diag["diagonal_valid"],
                    bounds_valid=base_diag["bounds_valid"],
                    is_psd=base_diag["is_psd"],
                    minimum_eigenvalue=base_diag["minimum_eigenvalue"],
                    maximum_eigenvalue=base_diag["maximum_eigenvalue"],
                    matrix_rank=base_diag["matrix_rank"],
                    condition_number=base_diag["condition_number"],
                    negative_eigenvalue_count=base_diag["negative_eigenvalue_count"],
                    warnings=base_diag["warnings"],
                ),
                stressed_diagnostics=MatrixValidateResponse(
                    status=raw_diag["status"],
                    is_symmetric=raw_diag["is_symmetric"],
                    diagonal_valid=raw_diag["diagonal_valid"],
                    bounds_valid=raw_diag["bounds_valid"],
                    is_psd=raw_diag["is_psd"],
                    minimum_eigenvalue=raw_diag["minimum_eigenvalue"],
                    maximum_eigenvalue=raw_diag["maximum_eigenvalue"],
                    matrix_rank=raw_diag["matrix_rank"],
                    condition_number=raw_diag["condition_number"],
                    negative_eigenvalue_count=raw_diag["negative_eigenvalue_count"],
                    warnings=raw_diag["warnings"],
                ),
                repaired_diagnostics=MatrixValidateResponse(
                    status=repaired_diag["status"],
                    is_symmetric=repaired_diag["is_symmetric"],
                    diagonal_valid=repaired_diag["diagonal_valid"],
                    bounds_valid=repaired_diag["bounds_valid"],
                    is_psd=repaired_diag["is_psd"],
                    minimum_eigenvalue=repaired_diag["minimum_eigenvalue"],
                    maximum_eigenvalue=repaired_diag["maximum_eigenvalue"],
                    matrix_rank=repaired_diag["matrix_rank"],
                    condition_number=repaired_diag["condition_number"],
                    negative_eigenvalue_count=repaired_diag["negative_eigenvalue_count"],
                    warnings=repaired_diag["warnings"],
                ),
                repair_summary=repair_audit,
                risk_summary=RiskResultSummary(
                    baseline_volatility=comparison["baseline_volatility"],
                    stressed_volatility=comparison["stressed_volatility"],
                    absolute_volatility_change=comparison["absolute_volatility_change"],
                    percentage_volatility_change=comparison["percentage_volatility_change"],
                    baseline_variance=comparison["baseline_variance"],
                    stressed_variance=comparison["stressed_variance"],
                    absolute_variance_change=comparison["absolute_variance_change"],
                    percentage_variance_change=comparison["percentage_variance_change"],
                    baseline_average_correlation=comparison["baseline_average_correlation"],
                    stressed_average_correlation=comparison["stressed_average_correlation"],
                    average_correlation_change=comparison["average_correlation_change"],
                    baseline_diversification_benefit=comparison["baseline_diversification_benefit"],
                    stressed_diversification_benefit=comparison["stressed_diversification_benefit"],
                    diversification_benefit_change=comparison["diversification_benefit_change"],
                    baseline_diversification_ratio=comparison["baseline_diversification_ratio"],
                    stressed_diversification_ratio=comparison["stressed_diversification_ratio"],
                    top_contributor=comparison["top_contributor"],
                    narrative=comparison["narrative"],
                ),
                contributions=response_contribs,
            )

        except Exception as e:
            await self.session.rollback()
            execution.execution_status = ExecutionStatus.FAILED
            execution.error_code = type(e).__name__
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            self.session.add(execution)
            await self.session.commit()
            raise

    # ---------------------------------------------------------
    # Internal Helpers
    # ---------------------------------------------------------
    async def _resolve_execution_universe_and_inputs(
        self,
        scenario: CorrelationShockScenario,
        version: CorrelationShockScenarioVersion,
        request: ExecuteScenarioRequest,
    ) -> Tuple[List[str], List[str], np.ndarray, np.ndarray, np.ndarray]:
        """
        Resolves asset ordering, portfolio weights, baseline correlation matrix, and volatilities.
        First checks custom inputs from request.
        If not supplied, attempts to load authoritative M07.05 baseline matrix and M05 positions.
        """
        # Case A: Custom inputs provided directly in execution request
        if (
            request.custom_asset_ids
            and request.custom_matrix_data
            and request.custom_weights
            and request.custom_volatilities
        ):
            asset_ids = request.custom_asset_ids
            asset_symbols = request.custom_asset_symbols or asset_ids
            n = len(asset_ids)
            weights = np.array([request.custom_weights.get(aid, 0.0) for aid in asset_ids], dtype=np.float64)
            vols = np.array([request.custom_volatilities.get(aid, 0.20) for aid in asset_ids], dtype=np.float64)
            base_mat = np.array(request.custom_matrix_data, dtype=np.float64)
            return asset_ids, asset_symbols, weights, base_mat, vols

        # Case B: Resolve from Portfolio and M07 database
        portfolio_id = request.portfolio_id or scenario.portfolio_id
        if not portfolio_id:
            raise ValueError("No portfolio ID specified for execution")

        # 1. Fetch positions from M05 Position Valuations
        stmt_pos = select(PositionValuation).where(PositionValuation.portfolio_id == portfolio_id)
        res_pos = await self.session.execute(stmt_pos)
        positions = list(res_pos.scalars().all())

        if not positions:
            raise ValueError(f"No positions found for portfolio {portfolio_id}")

        asset_ids = [p.instrument_id for p in positions]
        asset_symbols = [p.instrument_id for p in positions]
        
        # Calculate signed NAV weights
        total_market_value = sum(float(p.signed_market_value_base) for p in positions)
        if abs(total_market_value) > 1e-6:
            weights = np.array([float(p.signed_market_value_base) / total_market_value for p in positions], dtype=np.float64)
        else:
            weights = np.array([1.0 / len(positions)] * len(positions), dtype=np.float64)

        # 2. Fetch baseline matrix from M07.05
        stmt_m07 = select(CorrelationMatrixMetadata).where(
            CorrelationMatrixMetadata.portfolio_id == portfolio_id
        ).order_by(CorrelationMatrixMetadata.created_at.desc())
        res_m07 = await self.session.execute(stmt_m07)
        matrix_rec = res_m07.scalars().first()

        n = len(asset_ids)
        if matrix_rec and set(asset_ids).issubset(set(matrix_rec.asset_ids)):
            # Align matrix to current asset ordering
            m_dict = {aid: idx for idx, aid in enumerate(matrix_rec.asset_ids)}
            full_mat = np.array(matrix_rec.raw_matrix_data, dtype=np.float64)
            base_mat = np.zeros((n, n), dtype=np.float64)
            for i, a_i in enumerate(asset_ids):
                for j, a_j in enumerate(asset_ids):
                    base_mat[i, j] = full_mat[m_dict[a_i], m_dict[a_j]]
        else:
            # Fallback: Default identity baseline matrix if no M07 matrix calculated yet
            base_mat = np.eye(n, dtype=np.float64)

        # Default standard equity volatility of 20% annualized if not separately specified
        vols = np.array([0.20] * n, dtype=np.float64)

        return asset_ids, asset_symbols, weights, base_mat, vols

    def _apply_correlation_transformations(
        self,
        base_mat: np.ndarray,
        asset_ids: List[str],
        version: CorrelationShockScenarioVersion,
    ) -> np.ndarray:
        """
        Applies scenario transformations:
        1. General method across scope (Full Universe or Scope Members)
        2. Pair-level overrides from pair_rules
        """
        n = len(asset_ids)
        stressed = base_mat.copy()

        method_enum = CorrelationTransformationMethod(version.transformation_method)
        lam = float(version.stress_intensity)
        target = float(version.stress_target) if version.stress_target is not None else None

        # Build scope set
        scope_instrument_ids = set()
        if version.scope_members:
            for m in version.scope_members:
                if m.scope_type == "INSTRUMENT" and m.instrument_id:
                    scope_instrument_ids.add(m.instrument_id)

        # 1. Apply scenario-wide transformation
        for i in range(n):
            for j in range(i + 1, n):
                aid_i = asset_ids[i]
                aid_j = asset_ids[j]

                # Check if pair is within scope
                in_scope = True
                if scope_instrument_ids:
                    # Both must be in scope for scope-targeted shocks
                    in_scope = (aid_i in scope_instrument_ids) and (aid_j in scope_instrument_ids)

                if in_scope:
                    rho = stressed[i, j]
                    rho_new = transform_correlation_pair(
                        rho=rho,
                        method=method_enum,
                        stress_intensity=lam,
                        target_correlation=target,
                    )
                    stressed[i, j] = rho_new
                    stressed[j, i] = rho_new

        # 2. Apply pair-level rules (overrides)
        if version.pair_rules:
            asset_idx_map = {aid: idx for idx, aid in enumerate(asset_ids)}
            for pr in version.pair_rules:
                if pr.entity_a_id in asset_idx_map and pr.entity_b_id in asset_idx_map:
                    idx_a = asset_idx_map[pr.entity_a_id]
                    idx_b = asset_idx_map[pr.entity_b_id]
                    if idx_a != idx_b:
                        pr_method = CorrelationTransformationMethod(pr.transformation_method)
                        pr_lam = float(pr.stress_intensity)
                        pr_target = float(pr.target_correlation) if pr.target_correlation is not None else None
                        rho_pair = stressed[idx_a, idx_b]
                        new_pair_rho = transform_correlation_pair(
                            rho=rho_pair,
                            method=pr_method,
                            stress_intensity=pr_lam,
                            target_correlation=pr_target,
                        )
                        stressed[idx_a, idx_b] = new_pair_rho
                        stressed[idx_b, idx_a] = new_pair_rho

        # Ensure diagonal remains 1.0 and bounds are enforced
        np.fill_diagonal(stressed, 1.0)
        stressed = np.clip(stressed, -1.0, 1.0)
        stressed = 0.5 * (stressed + stressed.T)

        return stressed
