"""
Service Layer for M08.06 Idiosyncratic Risk.
Coordinates:
1. Residual Risk Configuration Management
2. Instrument Residual Volatility Estimation (Sample, Population, EWMA, MAD Scale)
3. Residual Covariance Matrix Generation and Snapshot Caching
4. Portfolio Idiosyncratic Risk & Euler Risk Allocation (Marginal, Component, %)
5. Diversification decomposition (diagonal baseline vs cross-security covariance effect)
6. Issuer-level risk consolidation
7. Residual Diagnostics (Moments, Jarque-Bera, Outliers, Ljung-Box, ARCH-LM, CUSUM)
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

from backend.app.modules.factor_risk.idiosyncratic_risk.models import (
    ResidualRiskConfig,
    ResidualVolatilityRun,
    ResidualCovarianceSnapshot,
    PortfolioIdiosyncraticRiskRun,
    SecurityResidualRiskContribution,
    IssuerResidualRiskContribution,
    ResidualDiagnosticRun,
    ResidualOutlierRecord,
    ResidualVarianceEstimator,
    ResidualModelQualityStatus,
    ContributionStatus,
    OutlierSeverity,
)
from backend.app.modules.factor_risk.idiosyncratic_risk.schemas import (
    ResidualConfigCreate,
    InstrumentResidualVolRequest,
    ResidualCovarianceRequest,
    PortfolioIdiosyncraticRiskRequest,
    ResidualDiagnosticRequest,
)
from backend.app.modules.factor_risk.idiosyncratic_risk.repositories.repository import IdiosyncraticRiskRepository
from backend.app.modules.factor_risk.idiosyncratic_risk.calculations.idiosyncratic_math import (
    compute_residual_volatility,
    estimate_residual_covariance_matrix,
    compute_portfolio_idiosyncratic_risk,
    compute_diversification_metrics,
    aggregate_issuer_idiosyncratic_risk,
    evaluate_residual_diagnostics,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorModel,
    FactorModelVersion,
    FactorLifecycleStatus,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    FactorReturnObservation,
    FactorReturnSeries,
    InstrumentFactorLoading,
)
from backend.app.modules.factor_risk.factor_sensitivity.models import (
    FactorSensitivityRun,
    FactorSensitivityCoefficient,
    FactorSensitivityModelDiagnostics,
    TargetType,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import (
    Instrument,
)
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PriceReferenceType,
)


def compute_deterministic_hash(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class IdiosyncraticRiskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IdiosyncraticRiskRepository(session)

    # =========================================================================
    # 1. Configuration Management
    # =========================================================================

    async def create_or_get_config(self, req: ResidualConfigCreate) -> ResidualRiskConfig:
        existing = await self.repo.get_config_by_code(req.config_code)
        if existing:
            return existing

        payload = {
            "config_code": req.config_code,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "variance_estimator": req.variance_estimator.value,
            "observation_frequency": req.observation_frequency,
            "annualization_factor": str(req.annualization_factor),
            "decay_factor": str(req.decay_factor) if req.decay_factor is not None else None,
            "minimum_observations": req.minimum_observations,
            "outlier_z_threshold": str(req.outlier_z_threshold),
        }
        cfg_hash = compute_deterministic_hash(payload)

        config = ResidualRiskConfig(
            config_code=req.config_code,
            config_name=req.config_name,
            description=req.description,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            variance_estimator=req.variance_estimator,
            observation_frequency=req.observation_frequency,
            annualization_factor=req.annualization_factor,
            decay_factor=req.decay_factor,
            minimum_observations=req.minimum_observations,
            outlier_z_threshold=req.outlier_z_threshold,
            config_hash=cfg_hash,
            status=FactorLifecycleStatus.ACTIVE,
        )
        return await self.repo.create_config(config)

    async def get_config(self, config_id: str) -> Optional[ResidualRiskConfig]:
        return await self.repo.get_config_by_id(config_id)

    async def list_configs(self, limit: int = 50) -> List[ResidualRiskConfig]:
        return await self.repo.list_configs(limit)

    # =========================================================================
    # 2. Residual Time Series Extraction Helper
    # =========================================================================

    async def _extract_residual_series(
        self,
        instrument_id: str,
        factor_model_version_id: str,
        as_of_date: date,
        lookback_obs: int = 252,
    ) -> Tuple[np.ndarray, List[date], Dict[str, Any]]:
        """
        Extracts aligned residual series epsilon_t = R_t - alpha - beta^T F_t.
        Returns:
            residuals array, dates list, metadata dictionary (alpha, betas, r_squared, total_vol)
        """
        mv_stmt = (
            select(FactorModelVersion)
            .where(FactorModelVersion.model_version_id == factor_model_version_id)
            .options(selectinload(FactorModelVersion.memberships))
        )
        mv_res = await self.session.execute(mv_stmt)
        mv = mv_res.scalars().first()
        if not mv or not mv.memberships:
            raise ValueError(f"No active factor model version found for {factor_model_version_id}")

        sorted_members = sorted(mv.memberships, key=lambda m: m.factor_position)
        factor_ids = [m.factor_id for m in sorted_members]
        factor_codes = [m.factor_code for m in sorted_members]

        # Fetch Betas and Intercept from M08.03 FactorSensitivityRun if available
        sens_stmt = (
            select(FactorSensitivityRun)
            .where(
                and_(
                    FactorSensitivityRun.target_id == instrument_id,
                    FactorSensitivityRun.factor_model_version_id == factor_model_version_id,
                    FactorSensitivityRun.as_of_date <= as_of_date,
                )
            )
            .options(
                selectinload(FactorSensitivityRun.coefficients),
                selectinload(FactorSensitivityRun.diagnostics),
            )
            .order_by(desc(FactorSensitivityRun.as_of_date))
        )
        s_res = await self.session.execute(sens_stmt)
        sens_run = s_res.scalars().first()

        betas: Dict[str, float] = {}
        alpha: float = 0.0
        r_squared: Optional[float] = None

        if sens_run and sens_run.coefficients:
            for coeff in sens_run.coefficients:
                betas[coeff.factor_code] = float(coeff.coefficient_value)
            if sens_run.diagnostics:
                if sens_run.diagnostics.intercept_value is not None:
                    alpha = float(sens_run.diagnostics.intercept_value)
                if sens_run.diagnostics.r_squared is not None:
                    r_squared = float(sens_run.diagnostics.r_squared)

        # Fallback to M08.02 loadings if M08.03 not present
        if not betas:
            load_stmt = (
                select(InstrumentFactorLoading)
                .where(
                    and_(
                        InstrumentFactorLoading.instrument_id == instrument_id,
                        InstrumentFactorLoading.as_of_date <= as_of_date,
                    )
                )
                .order_by(desc(InstrumentFactorLoading.as_of_date))
            )
            l_res = await self.session.execute(load_stmt)
            for l in l_res.scalars().all():
                if l.factor_code in factor_codes and l.factor_code not in betas:
                    betas[l.factor_code] = float(l.loading_value)

        # Lookback window
        calendar_days = int(lookback_obs * 1.6) + 30
        win_start = as_of_date - timedelta(days=calendar_days)

        # Fetch Factor Returns
        factor_rets: Dict[str, Dict[date, float]] = {}
        for f_id, f_code in zip(factor_ids, factor_codes):
            obs_stmt = (
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
            obs_res = await self.session.execute(obs_stmt)
            factor_rets[f_code] = {
                obs.trading_date: float(obs.return_value) for obs in obs_res.scalars().all()
            }

        # Fetch Instrument Price History & compute returns
        price_stmt = (
            select(PriceReferenceObservation)
            .where(
                and_(
                    PriceReferenceObservation.instrument_id == instrument_id,
                    PriceReferenceObservation.trading_date >= win_start,
                    PriceReferenceObservation.trading_date <= as_of_date,
                    PriceReferenceObservation.reference_type == PriceReferenceType.OFFICIAL_CLOSE,
                )
            )
            .order_by(PriceReferenceObservation.trading_date.asc())
        )
        p_res = await self.session.execute(price_stmt)
        prices = p_res.scalars().all()

        inst_rets: Dict[date, float] = {}
        if len(prices) >= 2:
            for i in range(1, len(prices)):
                p0 = float(prices[i - 1].price_value)
                p1 = float(prices[i].price_value)
                if p0 > 0:
                    inst_rets[prices[i].trading_date] = (p1 - p0) / p0

        common_dates = set(inst_rets.keys())
        for f_code in factor_codes:
            if f_code in factor_rets:
                common_dates = common_dates.intersection(set(factor_rets[f_code].keys()))

        sorted_dates = sorted(list(common_dates))
        if len(sorted_dates) > lookback_obs:
            sorted_dates = sorted_dates[-lookback_obs:]

        if not sorted_dates:
            return np.array([]), [], {"alpha": alpha, "betas": betas, "r_squared": r_squared}

        res_list = []
        tot_rets = []
        for d in sorted_dates:
            r_i = inst_rets[d]
            tot_rets.append(r_i)
            sys_ret = sum(betas.get(fc, 0.0) * factor_rets[fc].get(d, 0.0) for fc in factor_codes)
            eps = r_i - alpha - sys_ret
            res_list.append(eps)

        residuals = np.array(res_list, dtype=np.float64)
        total_vol = float(np.std(tot_rets, ddof=1)) if len(tot_rets) > 1 else None

        meta = {
            "alpha": alpha,
            "betas": betas,
            "r_squared": r_squared,
            "total_volatility": total_vol,
        }
        return residuals, sorted_dates, meta

    # =========================================================================
    # 3. Instrument Residual Volatility
    # =========================================================================

    async def calculate_instrument_residual_volatility(
        self, req: InstrumentResidualVolRequest
    ) -> ResidualVolatilityRun:
        cfg = await self.repo.get_config_by_id(req.config_id)
        if not cfg:
            raise ValueError(f"ResidualRiskConfig '{req.config_id}' not found")

        ann_factor = float(cfg.annualization_factor)
        estimator_type = "EWMA" if cfg.variance_estimator == ResidualVarianceEstimator.EXPONENTIALLY_WEIGHTED else cfg.variance_estimator.value
        decay_factor = float(cfg.decay_factor) if cfg.decay_factor is not None else 0.94

        residuals, dates, meta = await self._extract_residual_series(
            instrument_id=req.instrument_id,
            factor_model_version_id=cfg.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_obs=252,
        )

        if len(residuals) < cfg.minimum_observations:
            raise ValueError(
                f"Insufficient residual observations ({len(residuals)} < {cfg.minimum_observations}) for instrument {req.instrument_id}"
            )

        vol_metrics = compute_residual_volatility(
            residuals=residuals,
            variance_estimator=estimator_type,
            annualization_factor=ann_factor,
            decay_factor=decay_factor,
        )

        hash_payload = {
            "config_id": cfg.config_id,
            "instrument_id": req.instrument_id,
            "as_of_date": req.as_of_date.isoformat(),
            "vol_ann": vol_metrics["residual_volatility_annualized"],
        }
        result_hash = compute_deterministic_hash(hash_payload)

        run = ResidualVolatilityRun(
            config_id=cfg.config_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            as_of_date=req.as_of_date,
            observation_count=vol_metrics["observation_count"],
            residual_mean=Decimal(str(round(vol_metrics["residual_mean"], 8))),
            residual_variance_period=Decimal(str(round(vol_metrics["residual_variance_period"], 8))),
            residual_volatility_period=Decimal(str(round(vol_metrics["residual_volatility_period"], 8))),
            residual_variance_annualized=Decimal(str(round(vol_metrics["residual_variance_annualized"], 8))),
            residual_volatility_annualized=Decimal(str(round(vol_metrics["residual_volatility_annualized"], 8))),
            robust_mad_scale_annualized=Decimal(str(round(vol_metrics["robust_mad_scale_annualized"], 8))) if vol_metrics.get("robust_mad_scale_annualized") is not None else None,
            ew_residual_volatility_annualized=Decimal(str(round(vol_metrics["ew_residual_volatility_annualized"], 8))) if estimator_type == "EWMA" else None,
            effective_sample_size=Decimal(str(round(vol_metrics["effective_sample_size"], 2))) if vol_metrics.get("effective_sample_size") is not None else None,
            result_hash=result_hash,
        )
        return await self.repo.save_residual_volatility_run(run)

    # =========================================================================
    # 4. Residual Covariance Matrix Snapshot
    # =========================================================================

    async def get_or_create_residual_covariance(
        self, req: ResidualCovarianceRequest
    ) -> ResidualCovarianceSnapshot:
        existing = await self.repo.get_covariance_snapshot(
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=req.as_of_date,
            dimension=len(req.instrument_ids),
        )
        if existing and sorted(existing.instrument_ids_ordered) == sorted(req.instrument_ids):
            return existing

        residual_series_dict: Dict[str, Dict[date, float]] = {}
        for inst_id in req.instrument_ids:
            res_arr, dates, _ = await self._extract_residual_series(
                instrument_id=inst_id,
                factor_model_version_id=req.factor_model_version_id,
                as_of_date=req.as_of_date,
            )
            residual_series_dict[inst_id] = {d: float(res_arr[i]) for i, d in enumerate(dates)}

        common_dates = set.intersection(*(set(d_dict.keys()) for d_dict in residual_series_dict.values())) if residual_series_dict else set()
        sorted_dates = sorted(list(common_dates))
        T = len(sorted_dates)
        N = len(req.instrument_ids)

        if T < 2:
            raise ValueError(f"Insufficient aligned residual observations across {N} instruments (got {T})")

        matrix_residuals = np.zeros((T, N), dtype=np.float64)
        for j, inst_id in enumerate(req.instrument_ids):
            for i, d in enumerate(sorted_dates):
                matrix_residuals[i, j] = residual_series_dict[inst_id][d]

        cov_res = estimate_residual_covariance_matrix(
            residual_matrix=matrix_residuals,
        )

        hash_payload = {
            "factor_model_version_id": req.factor_model_version_id,
            "as_of_date": req.as_of_date.isoformat(),
            "dimension": N,
            "is_diagonal": req.use_diagonal,
        }
        res_hash = compute_deterministic_hash(hash_payload)

        cov_mat_to_store = cov_res["covariance_matrix_period"]
        if req.use_diagonal:
            cov_mat_to_store = np.diag(np.diag(cov_mat_to_store))

        snapshot = ResidualCovarianceSnapshot(
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=req.as_of_date,
            observation_count=T,
            dimension=N,
            instrument_ids_ordered=req.instrument_ids,
            covariance_matrix=cov_mat_to_store.tolist(),
            correlation_matrix=cov_res["correlation_matrix"].tolist(),
            is_positive_semidefinite=cov_res["is_positive_semidefinite"],
            min_eigenvalue=Decimal(str(round(cov_res.get("min_eigenvalue", 0.0), 8))),
            condition_number=Decimal(str(round(cov_res.get("condition_number", 1.0), 4))),
            matrix_rank=N,
            result_hash=res_hash,
        )
        return await self.repo.save_covariance_snapshot(snapshot)

    # =========================================================================
    # 5. Portfolio Idiosyncratic Risk & Risk Contributions
    # =========================================================================

    async def calculate_portfolio_idiosyncratic_risk(
        self, req: PortfolioIdiosyncraticRiskRequest
    ) -> PortfolioIdiosyncraticRiskRun:
        cfg = await self.repo.get_config_by_id(req.config_id)
        if not cfg:
            raise ValueError(f"ResidualRiskConfig '{req.config_id}' not found")

        ann_factor = float(cfg.annualization_factor)

        # 1. Fetch portfolio holdings via PositionValuation
        pos_stmt = (
            select(PositionValuation)
            .where(
                and_(
                    PositionValuation.portfolio_id == req.portfolio_id,
                    PositionValuation.effective_at <= datetime.combine(req.as_of_date, datetime.max.time()),
                )
            )
            .order_by(desc(PositionValuation.effective_at))
        )
        p_res = await self.session.execute(pos_stmt)
        valuations = p_res.scalars().all()

        if not valuations:
            raise ValueError(f"No holdings found for portfolio {req.portfolio_id} on {req.as_of_date}")

        weights_dict: Dict[str, float] = {}
        for v in valuations:
            if v.instrument_id not in weights_dict:
                mv = float(v.signed_market_value_base or 0.0)
                weights_dict[v.instrument_id] = mv

        tot_w = sum(weights_dict.values())
        if abs(tot_w) > 1e-6:
            weights_dict = {k: v / tot_w for k, v in weights_dict.items()}

        instrument_ids = list(weights_dict.keys())
        N_holdings = len(instrument_ids)

        # 2. Get covariance snapshot
        cov_snapshot = await self.get_or_create_residual_covariance(
            ResidualCovarianceRequest(
                factor_model_version_id=cfg.factor_model_version_id,
                instrument_ids=instrument_ids,
                as_of_date=req.as_of_date,
                use_diagonal=req.use_diagonal,
            )
        )

        cov_matrix = np.array(cov_snapshot.covariance_matrix, dtype=np.float64)
        weights_vector = np.array([weights_dict[inst_id] for inst_id in instrument_ids], dtype=np.float64)

        # 3. Compute portfolio idiosyncratic risk and Euler contributions
        risk_res = compute_portfolio_idiosyncratic_risk(
            weights=weights_vector,
            residual_cov_matrix=cov_matrix,
            annualization_factor=ann_factor,
        )

        # 4. Compute diversification metrics
        div_res = compute_diversification_metrics(
            weights=weights_vector,
            residual_cov_matrix=cov_matrix,
            annualization_factor=ann_factor,
        )

        # 5. Build SecurityResidualRiskContribution models
        inst_stmt = select(Instrument).where(Instrument.instrument_id.in_(instrument_ids))
        inst_res = await self.session.execute(inst_stmt)
        inst_map = {inst.instrument_id: inst for inst in inst_res.scalars().all()}

        sec_contrib_models: List[SecurityResidualRiskContribution] = []
        issuer_instruments_map: Dict[str, List[int]] = {}

        for idx, inst_id in enumerate(instrument_ids):
            inst_obj = inst_map.get(inst_id)
            iss_id = inst_obj.issuer_name if (inst_obj and inst_obj.issuer_name) else inst_id
            issuer_instruments_map.setdefault(iss_id, []).append(idx)

            var_i = cov_matrix[idx, idx]
            vol_i = math.sqrt(var_i)
            ann_vol_i = vol_i * math.sqrt(ann_factor)

            rc_var_ann = float(risk_res["variance_contributions_annualized"][idx])
            rc_vol_ann = float(risk_res["volatility_contributions_annualized"][idx])
            mrc_vol_ann = float(risk_res["marginal_volatility_contributions_annualized"][idx])
            pct_contrib = float(risk_res["percentage_contributions"][idx])
            is_div = bool(rc_var_ann < -1e-12)
            status_enum = ContributionStatus.NEGATIVE_RISK_DIVERSIFIER if is_div else (
                ContributionStatus.ZERO_CONTRIBUTION if abs(weights_vector[idx]) < 1e-9 else ContributionStatus.POSITIVE_RISK_CONTRIBUTOR
            )

            sc = SecurityResidualRiskContribution(
                instrument_id=inst_id,
                issuer_id=iss_id,
                signed_weight=Decimal(str(round(weights_vector[idx], 6))),
                absolute_weight=Decimal(str(round(abs(weights_vector[idx]), 6))),
                standalone_residual_volatility_annualized=Decimal(str(round(ann_vol_i, 8))),
                marginal_volatility_contribution_annualized=Decimal(str(round(mrc_vol_ann, 8))),
                volatility_contribution_annualized=Decimal(str(round(rc_vol_ann, 8))),
                variance_contribution_annualized=Decimal(str(round(rc_var_ann, 8))),
                percentage_contribution=Decimal(str(round(pct_contrib, 4))),
                contribution_status=status_enum,
            )
            sec_contrib_models.append(sc)

        # 6. Issuer Risk Aggregation
        issuer_mappings_list = [inst_map.get(inst_id).issuer_name if (inst_map.get(inst_id) and inst_map.get(inst_id).issuer_name) else inst_id for inst_id in instrument_ids]
        iss_agg_res = aggregate_issuer_idiosyncratic_risk(
            security_weights=weights_vector,
            issuer_mappings=issuer_mappings_list,
            residual_cov_matrix=cov_matrix,
            annualization_factor=ann_factor,
        )

        issuer_contrib_models: List[IssuerResidualRiskContribution] = []
        for iss_data in iss_agg_res["issuer_details"]:
            ann_iss_vol = iss_data["issuer_residual_volatility_annualized"]
            ic = IssuerResidualRiskContribution(
                issuer_id=iss_data["issuer_id"],
                member_instrument_count=iss_data["member_count"],
                signed_issuer_weight=Decimal(str(round(iss_data["signed_weight"], 6))),
                absolute_issuer_weight=Decimal(str(round(iss_data["absolute_weight"], 6))),
                issuer_residual_volatility_annualized=Decimal(str(round(ann_iss_vol, 8))),
                variance_contribution_annualized=Decimal(str(round(iss_data["variance_contribution_period"] * ann_factor, 8))),
                volatility_contribution_annualized=Decimal(str(round(iss_data["volatility_contribution_annualized"], 8))),
                percentage_contribution=Decimal(str(round(iss_data["percentage_contribution"], 4))),
            )
            issuer_contrib_models.append(ic)

        # 7. PortfolioIdiosyncraticRiskRun
        port_idio_var_ann = float(risk_res["portfolio_idiosyncratic_variance_annualized"])
        port_idio_vol_ann = float(risk_res["portfolio_idiosyncratic_volatility_annualized"])

        hash_payload = {
            "portfolio_id": req.portfolio_id,
            "as_of_date": req.as_of_date.isoformat(),
            "config_id": cfg.config_id,
            "port_idio_var_ann": port_idio_var_ann,
        }
        res_hash = compute_deterministic_hash(hash_payload)

        port_run = PortfolioIdiosyncraticRiskRun(
            config_id=cfg.config_id,
            portfolio_id=req.portfolio_id,
            as_of_date=req.as_of_date,
            portfolio_idiosyncratic_variance_annualized=Decimal(str(round(port_idio_var_ann, 8))),
            portfolio_idiosyncratic_volatility_annualized=Decimal(str(round(port_idio_vol_ann, 8))),
            diagonal_baseline_variance_annualized=Decimal(str(round(div_res["diagonal_baseline_variance_period"] * ann_factor, 8))),
            covariance_effect_annualized=Decimal(str(round(div_res["covariance_effect_annualized"], 8))),
            diversification_benefit_annualized=Decimal(str(round(div_res["diversification_benefit_annualized"], 8))),
            absolute_contribution_hhi=Decimal(str(round(div_res["absolute_contribution_hhi"], 6))),
            effective_number_of_risk_contributors=Decimal(str(round(div_res["effective_number_of_risk_contributors"], 4))),
            coverage_percentage=Decimal("100.00"),
            is_reconciled=bool(risk_res["is_reconciled"]),
            result_hash=res_hash,
        )

        return await self.repo.save_portfolio_run(
            port_run,
            security_contribs=sec_contrib_models,
            issuer_contribs=issuer_contrib_models,
        )

    # =========================================================================
    # 6. Residual Diagnostics
    # =========================================================================

    async def run_residual_diagnostics(
        self, req: ResidualDiagnosticRequest
    ) -> ResidualDiagnosticRun:
        cfg = await self.repo.get_config_by_id(req.config_id)
        if not cfg:
            raise ValueError(f"ResidualRiskConfig '{req.config_id}' not found")

        outlier_z = float(cfg.outlier_z_threshold)

        residuals, dates, _ = await self._extract_residual_series(
            instrument_id=req.instrument_id,
            factor_model_version_id=cfg.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_obs=252,
        )

        if len(residuals) < cfg.minimum_observations:
            raise ValueError(f"Insufficient observations ({len(residuals)} < {cfg.minimum_observations}) for diagnostics on {req.instrument_id}")

        diag_res = evaluate_residual_diagnostics(
            residuals=residuals,
            outlier_z_threshold=outlier_z,
            alpha_significance=0.05,
        )

        outlier_records: List[ResidualOutlierRecord] = []
        for out_idx in diag_res["outlier_analysis"]["outlier_indices"]:
            out_date = dates[out_idx] if out_idx < len(dates) else req.as_of_date
            z = abs(float((residuals[out_idx] - diag_res["moments"]["mean"]) / diag_res["moments"]["std_dev"])) if diag_res["moments"]["std_dev"] > 0 else 0.0
            severity = OutlierSeverity.CRITICAL if z > 4.0 else OutlierSeverity.HIGH
            ro = ResidualOutlierRecord(
                instrument_id=req.instrument_id,
                observation_date=out_date,
                residual_value=Decimal(str(round(residuals[out_idx], 8))),
                standardized_z_score=Decimal(str(round(z, 4))),
                severity=severity,
                detection_method="STANDARDIZED_Z",
            )
            outlier_records.append(ro)

        status_mapping = {
            "ACCEPTABLE": ResidualModelQualityStatus.ACCEPTABLE,
            "ACCEPTABLE_WITH_WARNINGS": ResidualModelQualityStatus.ACCEPTABLE_WITH_WARNINGS,
            "WEAK_SPECIFICATION": ResidualModelQualityStatus.WEAK_SPECIFICATION,
        }
        quality_status = status_mapping.get(diag_res["model_quality_status"], ResidualModelQualityStatus.ACCEPTABLE)

        diag_run = ResidualDiagnosticRun(
            instrument_id=req.instrument_id,
            factor_model_version_id=cfg.factor_model_version_id,
            as_of_date=req.as_of_date,
            observation_count=diag_res["observation_count"],
            skewness=Decimal(str(round(diag_res["moments"]["skewness"], 4))),
            excess_kurtosis=Decimal(str(round(diag_res["moments"]["excess_kurtosis"], 4))),
            jarque_bera_p_value=Decimal(str(round(diag_res["moments"]["jarque_bera_p_value"], 6))),
            lag1_autocorrelation=Decimal(str(round(diag_res["autocorrelation"]["lag1_acf"], 4))),
            ljung_box_p_value=Decimal(str(round(diag_res["autocorrelation"]["ljung_box_p_value"], 6))),
            arch_lm_p_value=Decimal(str(round(diag_res["heteroskedasticity"]["arch_lm_p_value"], 6))),
            has_structural_shift=diag_res["stationarity_and_breaks"]["has_structural_shift"],
            model_quality_status=quality_status,
            warning_messages=diag_res["warnings"],
        )

        return await self.repo.save_diagnostic_run(diag_run, outliers=outlier_records)
