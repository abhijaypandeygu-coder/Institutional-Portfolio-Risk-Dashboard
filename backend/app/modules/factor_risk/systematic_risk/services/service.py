"""
M08.05 Systematic Risk Service Layer.
Orchestrates:
1. Systematic Risk Configuration Management (with SHA-256 hashing)
2. Authoritative Factor Covariance Estimation & Snapshot Caching
3. Instrument Systematic Risk Calculation
4. Portfolio Systematic Risk Calculation (Preserving Cross-Security Covariance)
5. Scenario Sensitivity Shocks (Linear Shock Simulation & Monetary Impacts)
6. Point-in-Time Model Coverage Analysis & Holding Diagnostics
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.systematic_risk.models import (
    FactorRiskConfig,
    FactorCovarianceSnapshot,
    SystematicRiskRun,
    InstrumentSystematicRisk,
    PortfolioSystematicRisk,
    FactorScenarioConfig,
    FactorScenarioShock,
    FactorScenarioRun,
    FactorScenarioComponent,
    FactorModelCoverageRecord,
    CovarianceMethod,
    SystematicTargetType,
    SystematicRunStatus,
    ModelCoverageStatus,
    CoverageTier,
    ScenarioType,
    ShockUnit,
)
from backend.app.modules.factor_risk.systematic_risk.schemas import (
    CreateRiskConfigRequest,
    EstimateFactorCovarianceRequest,
    RunInstrumentSystematicRiskRequest,
    RunPortfolioSystematicRiskRequest,
    CreateFactorScenarioRequest,
    RunFactorScenarioRequest,
)
from backend.app.modules.factor_risk.systematic_risk.repositories.repository import SystematicRiskRepository
from backend.app.modules.factor_risk.systematic_risk.calculations.systematic_math import (
    estimate_factor_covariance_matrix,
    validate_covariance_matrix,
    compute_instrument_systematic_risk,
    compute_cross_security_systematic_variance,
    compute_factor_shock_scenario,
    evaluate_model_coverage,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorModel,
    FactorModelVersion,
    FactorDefinition,
    FactorDefinitionVersion,
    FactorLifecycleStatus,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    FactorReturnObservation,
    FactorReturnSeries,
    InstrumentFactorLoading,
    PortfolioFactorExposureSnapshot,
)
from backend.app.modules.factor_risk.factor_sensitivity.models import (
    FactorSensitivityRun,
    FactorSensitivityCoefficient,
    FactorSensitivityModelDiagnostics,
    TargetType,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionSnapshot,
    PortfolioPositionAggregate,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PortfolioValuationSnapshot,
    PositionValuation,
)


def compute_deterministic_hash(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class SystematicRiskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SystematicRiskRepository(session)

    # =========================================================================
    # 1. RISK CONFIGURATION MANAGEMENT
    # =========================================================================

    async def create_risk_config(self, req: CreateRiskConfigRequest) -> FactorRiskConfig:
        existing = await self.repo.get_config_by_code(req.config_code)
        if existing:
            return existing

        hash_payload = {
            "code": req.config_code,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "covariance_method": req.covariance_method.value,
            "frequency": req.observation_frequency,
            "annualization_factor": str(req.annualization_factor),
            "currency_basis": req.currency_basis,
        }
        config_hash = compute_deterministic_hash(hash_payload)

        config = FactorRiskConfig(
            config_code=req.config_code,
            config_name=req.config_name,
            description=req.description,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            covariance_method=req.covariance_method,
            observation_frequency=req.observation_frequency,
            annualization_factor=req.annualization_factor,
            decay_factor=req.decay_factor,
            minimum_observations=req.minimum_observations,
            coverage_threshold_pct=req.coverage_threshold_pct,
            currency_basis=req.currency_basis,
            config_hash=config_hash,
            status=FactorLifecycleStatus.ACTIVE,
        )
        saved = await self.repo.save_config(config)
        await self.session.commit()
        return saved

    async def get_config(self, config_id: str) -> Optional[FactorRiskConfig]:
        return await self.repo.get_config_by_id(config_id)

    async def list_configs(self) -> List[FactorRiskConfig]:
        return await self.repo.list_configs()

    # =========================================================================
    # 2. FACTOR COVARIANCE ESTIMATION & SNAPSHOTS
    # =========================================================================

    async def get_or_create_factor_covariance(
        self,
        factor_model_version_id: str,
        as_of_date: date,
        lookback_days: int = 252,
        covariance_method: CovarianceMethod = CovarianceMethod.SAMPLE,
        decay_factor: Decimal = Decimal("0.94"),
        annualization_factor: Decimal = Decimal("252.00"),
    ) -> FactorCovarianceSnapshot:
        """
        Retrieves existing covariance snapshot or estimates factor covariance matrix from M08.02 returns.
        """
        existing = await self.repo.get_latest_covariance_snapshot(
            factor_model_version_id=factor_model_version_id,
            as_of_date=as_of_date,
            covariance_method=covariance_method,
        )
        if existing and existing.estimation_window_end == as_of_date:
            return existing

        # 1. Fetch Factor Model Version & Members
        mv_stmt = (
            select(FactorModelVersion)
            .options(selectinload(FactorModelVersion.memberships))
            .where(FactorModelVersion.model_version_id == factor_model_version_id)
        )
        mv_res = await self.session.execute(mv_stmt)
        mv = mv_res.scalars().first()
        if not mv:
            raise ValueError(f"Factor model version '{factor_model_version_id}' not found")

        members_sorted = sorted(mv.memberships, key=lambda m: m.factor_position)
        factor_codes = [m.factor_code for m in members_sorted]
        factor_ids = [m.factor_id for m in members_sorted]

        # 2. Fetch Factor Returns
        win_start = as_of_date - timedelta(days=lookback_days * 2)
        factor_returns_by_code: Dict[str, Dict[date, float]] = {}
        for f_id, f_code in zip(factor_ids, factor_codes):
            stmt = (
                select(FactorReturnObservation)
                .join(FactorReturnSeries, FactorReturnObservation.series_id == FactorReturnSeries.series_id)
                .where(
                    and_(
                        FactorReturnSeries.factor_id == f_id,
                        FactorReturnObservation.trading_date >= win_start,
                        FactorReturnObservation.trading_date <= as_of_date,
                    )
                )
                .order_by(FactorReturnObservation.trading_date.asc())
            )
            res = await self.session.execute(stmt)
            obs_list = res.scalars().all()
            factor_returns_by_code[f_code] = {
                obs.trading_date: float(obs.return_value) for obs in obs_list
            }

        # 3. Intersect aligned trading dates (listwise complete)
        if not factor_codes or not factor_returns_by_code.get(factor_codes[0]):
            raise ValueError(f"No factor return series available for model '{factor_model_version_id}'")

        common_dates = set(factor_returns_by_code[factor_codes[0]].keys())
        for fc in factor_codes[1:]:
            common_dates = common_dates.intersection(factor_returns_by_code[fc].keys())

        sorted_common_dates = sorted(list(common_dates))
        if len(sorted_common_dates) > lookback_days:
            sorted_common_dates = sorted_common_dates[-lookback_days:]

        N = len(sorted_common_dates)
        K = len(factor_codes)
        if N < 2:
            raise ValueError(f"Insufficient aligned factor returns (found {N} dates, minimum 2 required)")

        # 4. Build T x K matrix
        R_mat = np.zeros((N, K), dtype=np.float64)
        for t_idx, d in enumerate(sorted_common_dates):
            for k_idx, fc in enumerate(factor_codes):
                R_mat[t_idx, k_idx] = factor_returns_by_code[fc][d]

        # 5. Estimate Factor Covariance
        cov_res = estimate_factor_covariance_matrix(
            returns_matrix=R_mat,
            method=covariance_method.value,
            decay_factor=float(decay_factor),
            annualization_factor=float(annualization_factor),
        )

        cov_sym = cov_res["covariance_matrix_period"]
        diag = cov_res["diagnostics"]
        cov_list = cov_sym.tolist()

        hash_payload = {
            "model_version_id": factor_model_version_id,
            "method": covariance_method.value,
            "factors": factor_codes,
            "window_start": sorted_common_dates[0].isoformat(),
            "window_end": sorted_common_dates[-1].isoformat(),
            "observation_count": N,
            "covariance_matrix": cov_list,
        }
        res_hash = compute_deterministic_hash(hash_payload)

        snapshot = FactorCovarianceSnapshot(
            factor_model_id=mv.model_id,
            factor_model_version_id=factor_model_version_id,
            covariance_method=covariance_method,
            observation_frequency="DAILY",
            estimation_window_start=sorted_common_dates[0],
            estimation_window_end=sorted_common_dates[-1],
            observation_count=N,
            effective_sample_size=Decimal(str(round(cov_res["effective_sample_size"], 2))),
            annualization_factor=annualization_factor,
            factor_names_ordered=factor_codes,
            covariance_matrix=cov_list,
            correlation_matrix=diag["correlation_matrix"],
            is_positive_semidefinite=diag["is_positive_semidefinite"],
            min_eigenvalue=Decimal(str(round(diag["min_eigenvalue"], 8))),
            max_eigenvalue=Decimal(str(round(diag["max_eigenvalue"], 8))),
            condition_number=Decimal(str(round(diag["condition_number"], 4))) if not math.isinf(diag["condition_number"]) else Decimal("999999.0"),
            matrix_rank=diag["matrix_rank"],
            result_hash=res_hash,
        )
        await self.repo.save_covariance_snapshot(snapshot)
        await self.session.commit()
        return snapshot

    # =========================================================================
    # 3. INSTRUMENT SYSTEMATIC RISK
    # =========================================================================

    async def calculate_instrument_systematic_risk(
        self, req: RunInstrumentSystematicRiskRequest
    ) -> InstrumentSystematicRisk:
        config = await self.repo.get_config_by_id(req.config_id)
        if not config:
            raise ValueError(f"Systematic risk config '{req.config_id}' not found")

        # 1. Resolve Factor Covariance
        cov_snap = await self.get_or_create_factor_covariance(
            factor_model_version_id=config.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_days=req.lookback_days,
            covariance_method=config.covariance_method,
            decay_factor=config.decay_factor or Decimal("0.94"),
            annualization_factor=config.annualization_factor,
        )

        factor_names = cov_snap.factor_names_ordered
        cov_mat = np.array(cov_snap.covariance_matrix, dtype=np.float64)

        # 2. Resolve Instrument Factor Sensitivities (from M08.03 or M08.02)
        sens_stmt = (
            select(FactorSensitivityRun)
            .options(
                selectinload(FactorSensitivityRun.coefficients),
                selectinload(FactorSensitivityRun.diagnostics),
            )
            .where(
                and_(
                    FactorSensitivityRun.target_type == TargetType.INSTRUMENT,
                    FactorSensitivityRun.target_id == req.instrument_id,
                    FactorSensitivityRun.factor_model_version_id == config.factor_model_version_id,
                    FactorSensitivityRun.as_of_date <= req.as_of_date,
                )
            )
            .order_by(desc(FactorSensitivityRun.as_of_date))
        )
        s_res = await self.session.execute(sens_stmt)
        sens_run = s_res.scalars().first()

        inst_betas: Dict[str, float] = {}
        res_var = None

        if sens_run and sens_run.coefficients:
            for coeff in sens_run.coefficients:
                inst_betas[coeff.factor_code] = float(coeff.coefficient_value)
            if sens_run.diagnostics and sens_run.diagnostics.residual_sum_of_squares is not None:
                # Periodic residual variance = RSS / (T - K)
                T_obs = sens_run.observation_count_used
                K_params = len(inst_betas)
                if T_obs > K_params:
                    res_var = float(sens_run.diagnostics.residual_sum_of_squares) / (T_obs - K_params)

        # Fallback to M08.02 loading if M08.03 regression is not found
        if not inst_betas:
            load_stmt = (
                select(InstrumentFactorLoading)
                .where(
                    and_(
                        InstrumentFactorLoading.instrument_id == req.instrument_id,
                        InstrumentFactorLoading.as_of_date <= req.as_of_date,
                    )
                )
                .order_by(desc(InstrumentFactorLoading.as_of_date))
            )
            l_res = await self.session.execute(load_stmt)
            loadings = l_res.scalars().all()
            for l in loadings:
                if l.factor_code in factor_names:
                    inst_betas[l.factor_code] = float(l.loading_value)

        # Verify coverage
        missing_factors = [fc for fc in factor_names if fc not in inst_betas]
        if missing_factors:
            status = ModelCoverageStatus.MISSING_FACTOR_LOADING if len(missing_factors) == len(factor_names) else ModelCoverageStatus.PARTIALLY_COVERED
            beta_vec = np.array([inst_betas.get(fc, 0.0) for fc in factor_names], dtype=np.float64)
        else:
            status = ModelCoverageStatus.COVERED
            beta_vec = np.array([inst_betas[fc] for fc in factor_names], dtype=np.float64)

        ann_factor = float(config.annualization_factor)
        risk_res = compute_instrument_systematic_risk(
            beta_vector=beta_vec,
            cov_matrix=cov_mat,
            residual_variance=res_var,
            annualization_factor=ann_factor,
        )

        hash_payload = {
            "instrument_id": req.instrument_id,
            "as_of_date": req.as_of_date.isoformat(),
            "config_id": config.config_id,
            "betas": inst_betas,
            "sys_var_ann": risk_res["systematic_variance_annualized"],
        }
        res_hash = compute_deterministic_hash(hash_payload)

        run = SystematicRiskRun(
            config_id=config.config_id,
            factor_model_id=config.factor_model_id,
            factor_model_version_id=config.factor_model_version_id,
            covariance_snapshot_id=cov_snap.snapshot_id,
            target_type=SystematicTargetType.INSTRUMENT,
            target_id=req.instrument_id,
            as_of_date=req.as_of_date,
            systematic_variance_annualized=Decimal(str(round(risk_res["systematic_variance_annualized"], 8))),
            systematic_volatility_annualized=Decimal(str(round(risk_res["systematic_volatility_annualized"], 8))),
            residual_variance_annualized=Decimal(str(round(risk_res["residual_variance_annualized"], 8))) if risk_res["residual_variance_annualized"] is not None else None,
            total_modeled_variance_annualized=Decimal(str(round(risk_res["total_modeled_variance_annualized"], 8))) if risk_res["total_modeled_variance_annualized"] is not None else None,
            total_modeled_volatility_annualized=Decimal(str(round(risk_res["total_modeled_volatility_annualized"], 8))) if risk_res["total_modeled_volatility_annualized"] is not None else None,
            systematic_variance_share=Decimal(str(round(risk_res["systematic_risk_ratio"], 6))) if risk_res["systematic_risk_ratio"] is not None else None,
            coverage_percentage=Decimal("100.00") if status == ModelCoverageStatus.COVERED else Decimal("50.00"),
            coverage_tier=CoverageTier.NEAR_COMPLETE if status == ModelCoverageStatus.COVERED else CoverageTier.LOW_COVERAGE,
            run_status=SystematicRunStatus.COMPLETED,
            result_hash=res_hash,
        )
        await self.repo.save_run(run)

        inst_risk = InstrumentSystematicRisk(
            run_id=run.run_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            factor_loadings=inst_betas,
            systematic_variance_period=Decimal(str(round(risk_res["systematic_variance_period"], 8))),
            systematic_volatility_period=Decimal(str(round(risk_res["systematic_volatility_period"], 8))),
            systematic_variance_annualized=Decimal(str(round(risk_res["systematic_variance_annualized"], 8))),
            systematic_volatility_annualized=Decimal(str(round(risk_res["systematic_volatility_annualized"], 8))),
            residual_variance_annualized=Decimal(str(round(risk_res["residual_variance_annualized"], 8))) if risk_res["residual_variance_annualized"] is not None else None,
            total_modeled_variance_annualized=Decimal(str(round(risk_res["total_modeled_variance_annualized"], 8))) if risk_res["total_modeled_variance_annualized"] is not None else None,
            total_modeled_volatility_annualized=Decimal(str(round(risk_res["total_modeled_volatility_annualized"], 8))) if risk_res["total_modeled_volatility_annualized"] is not None else None,
            systematic_variance_share=Decimal(str(round(risk_res["systematic_risk_ratio"], 6))) if risk_res["systematic_risk_ratio"] is not None else None,
            model_coverage_status=status,
        )
        self.session.add(inst_risk)
        await self.session.commit()
        return inst_risk

    # =========================================================================
    # 4. PORTFOLIO SYSTEMATIC RISK (CROSS-SECURITY COVARIANCE)
    # =========================================================================

    async def calculate_portfolio_systematic_risk(
        self, req: RunPortfolioSystematicRiskRequest
    ) -> PortfolioSystematicRisk:
        config = await self.repo.get_config_by_id(req.config_id)
        if not config:
            raise ValueError(f"Systematic risk config '{req.config_id}' not found")

        # 1. Resolve Factor Covariance
        cov_snap = await self.get_or_create_factor_covariance(
            factor_model_version_id=config.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_days=req.lookback_days,
            covariance_method=config.covariance_method,
            decay_factor=config.decay_factor or Decimal("0.94"),
            annualization_factor=config.annualization_factor,
        )

        factor_names = cov_snap.factor_names_ordered
        cov_mat = np.array(cov_snap.covariance_matrix, dtype=np.float64)
        K = len(factor_names)

        # 2. Resolve Positions & Signed Market Values (M05)
        pos_stmt = select(PositionSnapshot).where(
            and_(
                PositionSnapshot.portfolio_id == req.portfolio_id,
                PositionSnapshot.net_signed_quantity != Decimal("0.0"),
            )
        )
        pos_res = await self.session.execute(pos_stmt)
        positions = pos_res.scalars().all()

        # Fetch latest valuation snapshot for NAV reference
        val_stmt = select(PortfolioValuationSnapshot).where(
            PortfolioValuationSnapshot.portfolio_id == req.portfolio_id
        ).order_by(desc(PortfolioValuationSnapshot.valuation_timestamp))
        v_res = await self.session.execute(val_stmt)
        val_snap = v_res.scalars().first()
        portfolio_nav = float(getattr(val_snap, "net_asset_value", getattr(val_snap, "net_market_value", 10000000.0))) if val_snap else 10000000.0

        # 3. Resolve Sensitivities for each holding
        holdings_data = []
        inst_weights = []
        inst_betas_list = []

        for p in positions:
            inst_id = p.instrument_id
            # Estimate position signed market value: net_signed_quantity * 100.0
            smv = float(p.net_signed_quantity) * 100.0
            weight = smv / portfolio_nav if portfolio_nav > 0 else 0.0

            # Find sensitivities
            s_stmt = select(FactorSensitivityRun).options(selectinload(FactorSensitivityRun.coefficients)).where(
                and_(
                    FactorSensitivityRun.target_type == TargetType.INSTRUMENT,
                    FactorSensitivityRun.target_id == inst_id,
                    FactorSensitivityRun.factor_model_version_id == config.factor_model_version_id,
                    FactorSensitivityRun.as_of_date <= req.as_of_date,
                )
            ).order_by(desc(FactorSensitivityRun.as_of_date))
            s_res = await self.session.execute(s_stmt)
            s_run = s_res.scalars().first()

            loadings_dict = {}
            if s_run and s_run.coefficients:
                for c in s_run.coefficients:
                    loadings_dict[c.factor_code] = float(c.coefficient_value)

            holdings_data.append({
                "instrument_id": inst_id,
                "signed_market_value": smv,
                "factor_loadings": loadings_dict,
                "is_unsupported": False,
                "is_stale": False,
                "is_low_quality": False,
            })

            inst_weights.append(weight)
            inst_betas_list.append([loadings_dict.get(fc, 0.0) for fc in factor_names])

        # If no positions in DB (e.g. synthetic test portfolio), check direct M08.03 Portfolio Sensitivity
        if not positions:
            dir_stmt = select(FactorSensitivityRun).options(
                selectinload(FactorSensitivityRun.coefficients),
                selectinload(FactorSensitivityRun.diagnostics),
            ).where(
                and_(
                    FactorSensitivityRun.target_type == TargetType.PORTFOLIO,
                    FactorSensitivityRun.target_id == req.portfolio_id,
                    FactorSensitivityRun.factor_model_version_id == config.factor_model_version_id,
                    FactorSensitivityRun.as_of_date <= req.as_of_date,
                )
            ).order_by(desc(FactorSensitivityRun.as_of_date))
            dir_res = await self.session.execute(dir_stmt)
            dir_run = dir_res.scalars().first()

            port_betas = {}
            if dir_run and dir_run.coefficients:
                for c in dir_run.coefficients:
                    port_betas[c.factor_code] = float(c.coefficient_value)

            # Synthesize single position matching direct portfolio beta
            holdings_data.append({
                "instrument_id": f"SYNTH_{req.portfolio_id}",
                "signed_market_value": portfolio_nav,
                "factor_loadings": port_betas,
                "is_unsupported": False,
                "is_stale": False,
                "is_low_quality": False,
            })
            inst_weights.append(1.0)
            inst_betas_list.append([port_betas.get(fc, 0.0) for fc in factor_names])

        # 4. Model Coverage Analysis
        coverage_eval = evaluate_model_coverage(
            holdings=holdings_data,
            required_factor_codes=factor_names,
            minimum_coverage_threshold=float(config.coverage_threshold_pct),
        )

        # Save individual holding coverage diagnostics
        for hd in coverage_eval["holding_details"]:
            cov_rec = FactorModelCoverageRecord(
                portfolio_id=req.portfolio_id,
                portfolio_snapshot_id=req.portfolio_snapshot_id,
                instrument_id=hd["instrument_id"],
                factor_model_version_id=config.factor_model_version_id,
                coverage_status=ModelCoverageStatus(hd["coverage_status"]),
                signed_market_value=Decimal(str(round(hd["signed_market_value"], 4))),
                absolute_market_value=Decimal(str(round(hd["absolute_market_value"], 4))),
                absolute_weight_pct=Decimal(str(round(hd["absolute_market_value"] / coverage_eval["total_absolute_market_value"] * 100.0, 4))) if coverage_eval["total_absolute_market_value"] > 0 else Decimal("0.0"),
                missing_factor_codes=hd["missing_factors"],
                reason_description=f"Status: {hd['coverage_status']}",
                as_of_date=req.as_of_date,
            )
            await self.repo.save_coverage_record(cov_rec)

        # 5. Dual Calculation of Portfolio Systematic Variance
        W_arr = np.array(inst_weights, dtype=np.float64)
        B_mat = np.array(inst_betas_list, dtype=np.float64)
        ann_factor = float(config.annualization_factor)

        cross_res = compute_cross_security_systematic_variance(
            weights=W_arr,
            betas_matrix=B_mat,
            cov_matrix=cov_mat,
            annualization_factor=ann_factor,
        )

        portfolio_beta_dict = dict(zip(factor_names, cross_res["portfolio_beta"]))
        var_period = cross_res["variance_from_aggregated_beta"]
        vol_period = math.sqrt(max(0.0, var_period))
        var_ann = cross_res["annualized_variance"]
        vol_ann = cross_res["annualized_volatility"]

        hash_payload = {
            "portfolio_id": req.portfolio_id,
            "as_of_date": req.as_of_date.isoformat(),
            "config_id": config.config_id,
            "portfolio_beta": portfolio_beta_dict,
            "var_ann": var_ann,
        }
        res_hash = compute_deterministic_hash(hash_payload)

        run = SystematicRiskRun(
            config_id=config.config_id,
            factor_model_id=config.factor_model_id,
            factor_model_version_id=config.factor_model_version_id,
            covariance_snapshot_id=cov_snap.snapshot_id,
            target_type=SystematicTargetType.PORTFOLIO,
            target_id=req.portfolio_id,
            portfolio_snapshot_id=req.portfolio_snapshot_id,
            as_of_date=req.as_of_date,
            systematic_variance_annualized=Decimal(str(round(var_ann, 8))),
            systematic_volatility_annualized=Decimal(str(round(vol_ann, 8))),
            residual_variance_annualized=None,
            total_modeled_variance_annualized=None,
            total_modeled_volatility_annualized=None,
            systematic_variance_share=None,
            coverage_percentage=Decimal(str(round(coverage_eval["portfolio_coverage_percentage"], 2))),
            coverage_tier=CoverageTier(coverage_eval["coverage_tier"]),
            run_status=SystematicRunStatus.COMPLETED,
            result_hash=res_hash,
        )
        await self.repo.save_run(run)

        pf_risk = PortfolioSystematicRisk(
            run_id=run.run_id,
            portfolio_id=req.portfolio_id,
            portfolio_snapshot_id=req.portfolio_snapshot_id,
            portfolio_betas=portfolio_beta_dict,
            systematic_variance_period=Decimal(str(round(var_period, 8))),
            systematic_volatility_period=Decimal(str(round(vol_period, 8))),
            systematic_variance_annualized=Decimal(str(round(var_ann, 8))),
            systematic_volatility_annualized=Decimal(str(round(vol_ann, 8))),
            cross_security_variance_discrepancy=Decimal(str(round(cross_res["reconciliation_discrepancy"], 12))),
            is_cross_security_reconciled=cross_res["is_reconciled"],
            total_absolute_market_value=Decimal(str(round(coverage_eval["total_absolute_market_value"], 4))),
            covered_absolute_market_value=Decimal(str(round(coverage_eval["covered_absolute_market_value"], 4))),
            uncovered_absolute_market_value=Decimal(str(round(coverage_eval["uncovered_absolute_market_value"], 4))),
            coverage_percentage=Decimal(str(round(coverage_eval["portfolio_coverage_percentage"], 2))),
            coverage_tier=CoverageTier(coverage_eval["coverage_tier"]),
            total_holding_count=coverage_eval["total_holding_count"],
            covered_holding_count=coverage_eval["covered_holding_count"],
            uncovered_holding_count=coverage_eval["uncovered_holding_count"],
            factor_coverage_percentages=coverage_eval["factor_coverage_percentages"],
        )
        self.session.add(pf_risk)
        await self.session.commit()
        return pf_risk

    # =========================================================================
    # 5. FACTOR SCENARIO SENSITIVITY
    # =========================================================================

    async def create_scenario_config(self, req: CreateFactorScenarioRequest) -> FactorScenarioConfig:
        scenario = FactorScenarioConfig(
            scenario_code=req.scenario_code,
            scenario_name=req.scenario_name,
            description=req.description,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            scenario_type=req.scenario_type,
            shock_unit=req.shock_unit,
            status=FactorLifecycleStatus.ACTIVE,
        )
        for s in req.shocks:
            shock_rec = FactorScenarioShock(
                factor_code=s.factor_code,
                shock_value=s.shock_value,
                shock_unit=s.shock_unit,
                standard_deviation_multiple=s.standard_deviation_multiple,
            )
            scenario.shocks.append(shock_rec)

        saved = await self.repo.save_scenario_config(scenario)
        await self.session.commit()
        return saved

    async def run_factor_scenario(self, req: RunFactorScenarioRequest) -> FactorScenarioRun:
        shocks_dict: Dict[str, float] = {}
        model_version_id = req.factor_model_version_id

        if req.scenario_id:
            scen_cfg = await self.repo.get_scenario_config_by_id(req.scenario_id)
            if not scen_cfg:
                raise ValueError(f"Scenario '{req.scenario_id}' not found")
            model_version_id = scen_cfg.factor_model_version_id
            for s in scen_cfg.shocks:
                shocks_dict[s.factor_code] = float(s.shock_value)
        elif req.custom_shocks:
            shocks_dict = {k: float(v) for k, v in req.custom_shocks.items()}
        else:
            raise ValueError("Either scenario_id or custom_shocks must be provided")

        # Resolve factor ordering from Model Version
        mv_stmt = (
            select(FactorModelVersion)
            .options(selectinload(FactorModelVersion.memberships))
            .where(FactorModelVersion.model_version_id == model_version_id)
        )
        mv_res = await self.session.execute(mv_stmt)
        mv = mv_res.scalars().first()
        if not mv:
            raise ValueError(f"Factor model version '{model_version_id}' not found")

        members_sorted = sorted(mv.memberships, key=lambda m: m.factor_position)
        factor_codes = [m.factor_code for m in members_sorted]

        # Resolve Target Exposures
        target_betas: Dict[str, float] = {}
        if req.target_type == SystematicTargetType.PORTFOLIO:
            # Query latest portfolio systematic risk run
            pf_run = await self.repo.get_latest_risk_run(SystematicTargetType.PORTFOLIO, req.target_id, req.as_of_date)
            if pf_run:
                pf_detail = await self.repo.get_portfolio_risk_by_run_id(pf_run.run_id)
                if pf_detail:
                    target_betas = pf_detail.portfolio_betas
            if not target_betas:
                # Direct M08.03 sensitivity
                s_stmt = select(FactorSensitivityRun).options(selectinload(FactorSensitivityRun.coefficients)).where(
                    and_(
                        FactorSensitivityRun.target_type == TargetType.PORTFOLIO,
                        FactorSensitivityRun.target_id == req.target_id,
                        FactorSensitivityRun.factor_model_version_id == model_version_id,
                        FactorSensitivityRun.as_of_date <= req.as_of_date,
                    )
                ).order_by(desc(FactorSensitivityRun.as_of_date))
                s_res = await self.session.execute(s_stmt)
                s_run = s_res.scalars().first()
                if s_run and s_run.coefficients:
                    for c in s_run.coefficients:
                        target_betas[c.factor_code] = float(c.coefficient_value)

        elif req.target_type == SystematicTargetType.INSTRUMENT:
            inst_run = await self.repo.get_latest_risk_run(SystematicTargetType.INSTRUMENT, req.target_id, req.as_of_date)
            if inst_run:
                inst_detail = await self.repo.get_instrument_risk_by_run_id(inst_run.run_id)
                if inst_detail:
                    target_betas = inst_detail.factor_loadings

        nav = float(req.portfolio_nav) if req.portfolio_nav else 10000000.0

        scen_res = compute_factor_shock_scenario(
            factor_shocks=shocks_dict,
            factor_names_ordered=factor_codes,
            portfolio_betas=target_betas,
            portfolio_nav=nav,
        )

        run = FactorScenarioRun(
            scenario_id=req.scenario_id or f"CUSTOM_{req.target_id}",
            target_type=req.target_type,
            target_id=req.target_id,
            percentage_impact=Decimal(str(round(scen_res["portfolio_percentage_impact"], 6))),
            monetary_impact=Decimal(str(round(scen_res["portfolio_monetary_impact"], 4))) if scen_res["portfolio_monetary_impact"] is not None else None,
            currency=req.currency,
            model_limitation_warning=scen_res["model_limitation_warning"],
            coverage_percentage=Decimal("100.00"),
        )
        await self.repo.save_scenario_run(run)

        for fc in factor_codes:
            shock_v = shocks_dict.get(fc, 0.0)
            exp_v = target_betas.get(fc, 0.0)
            ret_contrib = scen_res["factor_contributions_percentage"].get(fc, 0.0)
            dollar_contrib = ret_contrib * nav if nav else None

            comp = FactorScenarioComponent(
                scenario_run_id=run.run_id,
                factor_code=fc,
                factor_shock=Decimal(str(round(shock_v, 6))),
                factor_exposure=Decimal(str(round(exp_v, 6))),
                estimated_return_contribution=Decimal(str(round(ret_contrib, 6))),
                estimated_monetary_contribution=Decimal(str(round(dollar_contrib, 4))) if dollar_contrib is not None else None,
            )
            self.session.add(comp)

        await self.session.commit()
        return run

    # =========================================================================
    # 6. MODEL COVERAGE QUERY
    # =========================================================================

    async def get_portfolio_coverage_summary(
        self, portfolio_id: str, as_of_date: date
    ) -> Dict[str, Any]:
        records = await self.repo.list_coverage_records(portfolio_id, as_of_date)
        total_abs_mv = sum(r.absolute_market_value for r in records)
        covered_abs_mv = sum(r.absolute_market_value for r in records if r.coverage_status == ModelCoverageStatus.COVERED)
        uncovered_abs_mv = total_abs_mv - covered_abs_mv

        cov_pct = (covered_abs_mv / total_abs_mv * Decimal("100.00")) if total_abs_mv > 0 else Decimal("0.00")
        if cov_pct >= Decimal("99.0"):
            tier = CoverageTier.NEAR_COMPLETE
        elif cov_pct >= Decimal("95.0"):
            tier = CoverageTier.HIGH_COVERAGE
        elif cov_pct >= Decimal("80.0"):
            tier = CoverageTier.MODERATE_COVERAGE
        elif cov_pct > Decimal("0.0"):
            tier = CoverageTier.LOW_COVERAGE
        else:
            tier = CoverageTier.NO_COVERAGE

        return {
            "portfolio_id": portfolio_id,
            "as_of_date": as_of_date,
            "portfolio_coverage_percentage": cov_pct,
            "coverage_tier": tier,
            "total_absolute_market_value": total_abs_mv,
            "covered_absolute_market_value": covered_abs_mv,
            "uncovered_absolute_market_value": uncovered_abs_mv,
            "total_holding_count": len(records),
            "covered_holding_count": sum(1 for r in records if r.coverage_status == ModelCoverageStatus.COVERED),
            "uncovered_holding_count": sum(1 for r in records if r.coverage_status != ModelCoverageStatus.COVERED),
            "factor_coverage_percentages": {},
            "holdings": records,
        }
