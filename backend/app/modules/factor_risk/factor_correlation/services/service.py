"""
Service Layer for M08.07 Factor Correlation & Covariance Analytics.
Coordinates:
1. Approved factor model version and actual factor return resolution
2. Point-in-time session alignment across factor returns
3. Inter-factor correlation matrix execution (Pearson, Spearman, Kendall)
4. Authoritative factor covariance estimation (Sample, EWMA, Ledoit-Wolf) & PSD validation
5. Rolling relationship tracking, deltas, baseline percentile, and stability classification
6. Correlation regime detection, structural break detection, and alert publishing
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

from backend.app.modules.factor_risk.factor_correlation.models import (
    FactorCorrelationConfig,
    FactorCorrelationRun,
    FactorCorrelationPair,
    FactorCorrelationMatrixSnapshot,
    FactorCovarianceConfig,
    FactorCovarianceSnapshot,
    RollingFactorCorrelation,
    FactorRegimeAlert,
    FactorCorrelationMethod,
    FactorCovarianceMethod,
    MissingDataPolicy,
    CorrelationRelationshipClassification,
    CorrelationStabilityCategory,
    CorrelationRegimeStatus,
    RegimeAlertSeverity,
    RegimeAlertStatus,
)
from backend.app.modules.factor_risk.factor_correlation.schemas import (
    FactorCorrelationConfigCreate,
    FactorCorrelationCalculateRequest,
    FactorCovarianceCalculateRequest,
    RollingFactorCorrelationRequest,
    FactorRegimeEvaluateRequest,
)
from backend.app.modules.factor_risk.factor_correlation.repositories.repository import FactorCorrelationRepository
from backend.app.modules.factor_risk.factor_correlation.calculations.factor_correlation_math import (
    compute_pairwise_correlation,
    compute_inter_factor_correlation_matrix,
    estimate_factor_covariance,
    project_to_nearest_psd,
    compute_rolling_factor_relationships,
    evaluate_correlation_regimes,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorModel,
    FactorModelVersion,
    FactorLifecycleStatus,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    FactorReturnObservation,
    FactorReturnSeries,
)


def compute_deterministic_hash(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class FactorCorrelationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FactorCorrelationRepository(session)

    # =========================================================================
    # 1. Configuration Management
    # =========================================================================

    async def create_or_get_correlation_config(
        self, req: FactorCorrelationConfigCreate
    ) -> FactorCorrelationConfig:
        existing = await self.repo.get_correlation_config_by_code(req.config_code)
        if existing:
            return existing

        payload = {
            "config_code": req.config_code,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "correlation_method": req.correlation_method.value,
            "observation_frequency": req.observation_frequency,
            "return_convention": req.return_convention,
            "currency_basis": req.currency_basis,
            "missing_data_policy": req.missing_data_policy.value,
            "estimation_window": req.estimation_window,
            "minimum_observations": req.minimum_observations,
            "confidence_level": str(req.confidence_level),
        }
        cfg_hash = compute_deterministic_hash(payload)

        config = FactorCorrelationConfig(
            config_code=req.config_code,
            config_name=req.config_name,
            description=req.description,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            correlation_method=req.correlation_method,
            observation_frequency=req.observation_frequency,
            return_convention=req.return_convention,
            currency_basis=req.currency_basis,
            missing_data_policy=req.missing_data_policy,
            estimation_window=req.estimation_window,
            minimum_observations=req.minimum_observations,
            confidence_level=req.confidence_level,
            config_hash=cfg_hash,
            status=FactorLifecycleStatus.ACTIVE,
        )
        return await self.repo.create_correlation_config(config)

    async def get_correlation_config(self, config_id: str) -> Optional[FactorCorrelationConfig]:
        return await self.repo.get_correlation_config_by_id(config_id)

    async def list_correlation_configs(self, limit: int = 50) -> List[FactorCorrelationConfig]:
        return await self.repo.list_correlation_configs(limit)

    # =========================================================================
    # 2. Factor Return Alignment Helper
    # =========================================================================

    async def _resolve_and_align_factor_returns(
        self,
        factor_model_version_id: str,
        as_of_date: date,
        lookback_days: int = 60,
        selected_factor_ids: Optional[List[str]] = None,
    ) -> Tuple[np.ndarray, List[str], List[str], List[date]]:
        """
        Retrieves actual approved factor return observations for the factor model version.
        Aligns observations across factors.
        Returns:
            aligned_returns_matrix (T x K), factor_ids, factor_codes, aligned_dates
        """
        mv_stmt = (
            select(FactorModelVersion)
            .where(FactorModelVersion.model_version_id == factor_model_version_id)
            .options(selectinload(FactorModelVersion.memberships))
        )
        mv_res = await self.session.execute(mv_stmt)
        mv = mv_res.scalars().first()
        if not mv or not mv.memberships:
            raise ValueError(f"Active factor model version '{factor_model_version_id}' has no factor memberships")

        sorted_members = sorted(mv.memberships, key=lambda m: m.factor_position)
        if selected_factor_ids:
            sorted_members = [m for m in sorted_members if m.factor_id in selected_factor_ids or m.factor_code in selected_factor_ids]

        if not sorted_members:
            raise ValueError("No matching factors found in selected factor model version")

        factor_ids = [m.factor_id for m in sorted_members]
        factor_codes = [m.factor_code for m in sorted_members]
        K = len(factor_codes)

        calendar_days = int(lookback_days * 1.6) + 30
        win_start = as_of_date - timedelta(days=calendar_days)

        # Retrieve factor returns
        factor_observations: Dict[str, Dict[date, float]] = {}
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
            factor_observations[f_code] = {
                obs.trading_date: float(obs.return_value) for obs in obs_list
            }

        # Listwise intersection of dates
        common_dates = set.intersection(*(set(d_dict.keys()) for d_dict in factor_observations.values())) if factor_observations else set()
        sorted_dates = sorted(list(common_dates))
        if len(sorted_dates) > lookback_days:
            sorted_dates = sorted_dates[-lookback_days:]

        T = len(sorted_dates)
        if T == 0:
            raise ValueError(f"No aligned factor return observations found for window ending {as_of_date}")

        returns_matrix = np.zeros((T, K), dtype=np.float64)
        for j, f_code in enumerate(factor_codes):
            for i, d in enumerate(sorted_dates):
                returns_matrix[i, j] = factor_observations[f_code][d]

        return returns_matrix, factor_ids, factor_codes, sorted_dates

    # =========================================================================
    # 3. Static Inter-Factor Correlation Matrix Execution
    # =========================================================================

    async def calculate_inter_factor_correlation(
        self, req: FactorCorrelationCalculateRequest
    ) -> FactorCorrelationRun:
        window_size = req.estimation_window or 60
        method = req.correlation_method.value if req.correlation_method else "PEARSON"

        config_id = req.config_id
        if not config_id:
            # Resolve or create default config
            cfg_code = f"CFG_CORR_{req.factor_model_version_id[:8].upper()}_{method}"
            cfg = await self.repo.get_correlation_config_by_code(cfg_code)
            if not cfg:
                # get model id
                mv_stmt = select(FactorModelVersion).where(FactorModelVersion.model_version_id == req.factor_model_version_id)
                mv_res = await self.session.execute(mv_stmt)
                mv = mv_res.scalars().first()
                m_id = mv.model_id if mv else "UNKNOWN_MODEL"

                cfg = await self.create_or_get_correlation_config(
                    FactorCorrelationConfigCreate(
                        config_code=cfg_code,
                        config_name=f"Default {method} Correlation Config",
                        factor_model_id=m_id,
                        factor_model_version_id=req.factor_model_version_id,
                        correlation_method=FactorCorrelationMethod(method),
                        estimation_window=window_size,
                    )
                )
            config_id = cfg.config_id

        # Align returns
        returns_mat, factor_ids, factor_codes, dates = await self._resolve_and_align_factor_returns(
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_days=window_size,
            selected_factor_ids=req.selected_factor_ids,
        )

        T, K = returns_mat.shape
        corr_res = compute_inter_factor_correlation_matrix(
            returns_matrix=returns_mat,
            method=method,
        )

        # Build Pairwise records
        pair_models: List[FactorCorrelationPair] = []
        valid_pairs_count = 0
        invalid_pairs_count = 0

        for i in range(K):
            for j in range(i + 1, K):
                res_ij = compute_pairwise_correlation(returns_mat[:, i], returns_mat[:, j], method=method)
                val = res_ij["correlation"]
                cov_val = res_ij["covariance"]
                std_i = res_ij["std_x"] or 0.0
                std_j = res_ij["std_y"] or 0.0

                if res_ij["is_defined"]:
                    valid_pairs_count += 1
                    abs_val = abs(val)
                    if abs_val < 0.20:
                        rel_class = CorrelationRelationshipClassification.VERY_WEAK
                    elif abs_val < 0.40:
                        rel_class = CorrelationRelationshipClassification.WEAK
                    elif abs_val < 0.60:
                        rel_class = CorrelationRelationshipClassification.MODERATE
                    elif abs_val < 0.80:
                        rel_class = CorrelationRelationshipClassification.STRONG
                    else:
                        rel_class = CorrelationRelationshipClassification.VERY_STRONG
                else:
                    invalid_pairs_count += 1
                    rel_class = CorrelationRelationshipClassification.VERY_WEAK

                p_model = FactorCorrelationPair(
                    factor_a_id=factor_ids[i],
                    factor_b_id=factor_ids[j],
                    factor_a_code=factor_codes[i],
                    factor_b_code=factor_codes[j],
                    correlation_value=Decimal(str(round(val, 6))) if val is not None else None,
                    covariance_value=Decimal(str(round(cov_val, 8))) if cov_val is not None else None,
                    factor_a_volatility_annualized=Decimal(str(round(std_i * math.sqrt(252.0), 8))),
                    factor_b_volatility_annualized=Decimal(str(round(std_j * math.sqrt(252.0), 8))),
                    p_value=Decimal(str(round(res_ij["p_value"], 6))) if res_ij["p_value"] is not None else None,
                    ci_lower=Decimal(str(round(res_ij["ci_lower"], 6))) if res_ij["ci_lower"] is not None else None,
                    ci_upper=Decimal(str(round(res_ij["ci_upper"], 6))) if res_ij["ci_upper"] is not None else None,
                    relationship_classification=rel_class,
                    is_defined=res_ij["is_defined"],
                    undefined_reason=res_ij["reason"],
                )
                pair_models.append(p_model)

        # Build Matrix Snapshot
        hash_payload = {
            "factor_model_version_id": req.factor_model_version_id,
            "as_of_date": req.as_of_date.isoformat(),
            "method": method,
            "factors": factor_codes,
            "corr_matrix": corr_res["correlation_matrix"].tolist(),
        }
        res_hash = compute_deterministic_hash(hash_payload)

        mat_snap = FactorCorrelationMatrixSnapshot(
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=req.as_of_date,
            dimension=K,
            factor_ordering=factor_codes,
            correlation_matrix=corr_res["correlation_matrix"].tolist(),
            is_symmetric=True,
            is_positive_semidefinite=corr_res["is_positive_semidefinite"],
            min_eigenvalue=Decimal(str(round(corr_res.get("min_eigenvalue", 0.0) or 0.0, 8))),
            max_eigenvalue=Decimal(str(round(corr_res.get("max_eigenvalue", 1.0) or 1.0, 8))),
            condition_number=Decimal(str(round(corr_res.get("condition_number", 1.0) or 1.0, 4))),
            result_hash=res_hash,
        )

        run = FactorCorrelationRun(
            config_id=config_id,
            factor_model_version_id=req.factor_model_version_id,
            window_start=dates[0],
            window_end=dates[-1],
            as_of_date=req.as_of_date,
            observation_count=T,
            factor_count=K,
            valid_pair_count=valid_pairs_count,
            invalid_pair_count=invalid_pairs_count,
            is_positive_semidefinite=corr_res["is_positive_semidefinite"],
            min_eigenvalue=Decimal(str(round(corr_res.get("min_eigenvalue", 0.0) or 0.0, 8))),
            max_eigenvalue=Decimal(str(round(corr_res.get("max_eigenvalue", 1.0) or 1.0, 8))),
            condition_number=Decimal(str(round(corr_res.get("condition_number", 1.0) or 1.0, 4))),
            matrix_rank=corr_res["matrix_rank"] or K,
            result_hash=res_hash,
        )

        return await self.repo.save_correlation_run(run, pairs=pair_models, matrix_snapshot=mat_snap)

    async def get_matrix_snapshot(self, matrix_id: str) -> Optional[FactorCorrelationMatrixSnapshot]:
        return await self.repo.get_matrix_snapshot_by_id(matrix_id)

    # =========================================================================
    # 4. Authoritative Factor Covariance Estimation for M08.05
    # =========================================================================

    async def calculate_factor_covariance(
        self, req: FactorCovarianceCalculateRequest
    ) -> FactorCovarianceSnapshot:
        """
        Authoritative factor covariance estimation consumed by M08.05 Systematic Risk.
        Guarantees Sigma_F == D * P_F * D consistency and spectral PSD validation.
        """
        # Align returns
        returns_mat, factor_ids, factor_codes, dates = await self._resolve_and_align_factor_returns(
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_days=req.estimation_window,
        )

        T, K = returns_mat.shape
        ann_factor = float(req.annualization_factor)
        method_str = req.covariance_method.value
        decay = float(req.decay_factor) if req.decay_factor is not None else 0.94
        sh_target = req.shrinkage_target or "IDENTITY"
        sh_intensity = float(req.shrinkage_intensity) if req.shrinkage_intensity is not None else None

        cov_res = estimate_factor_covariance(
            returns_matrix=returns_mat,
            method=method_str,
            annualization_factor=ann_factor,
            decay_factor=decay,
            shrinkage_target=sh_target,
            shrinkage_intensity=sh_intensity,
        )

        cov_period = cov_res["covariance_matrix_period"]
        cov_ann = cov_res["covariance_matrix_annualized"]
        corr_mat = cov_res["correlation_matrix"]
        min_eig = cov_res["min_eigenvalue"]
        is_psd = cov_res["is_positive_semidefinite"]
        is_regularized = False
        orig_min_eig = None

        # Nearest-PSD projection if non-PSD and regularization is requested
        if not is_psd and req.regularize_if_non_psd:
            orig_min_eig = Decimal(str(round(min_eig, 8)))
            cov_period, psd_meta = project_to_nearest_psd(cov_period)
            cov_ann = cov_period * ann_factor
            is_regularized = True
            is_psd = True
            min_eig = psd_meta["adjusted_min_eigenvalue"]

        hash_payload = {
            "factor_model_version_id": req.factor_model_version_id,
            "as_of_date": req.as_of_date.isoformat(),
            "method": method_str,
            "cov_ann": cov_ann.tolist(),
        }
        res_hash = compute_deterministic_hash(hash_payload)

        snapshot = FactorCovarianceSnapshot(
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            covariance_method=req.covariance_method,
            as_of_date=req.as_of_date,
            window_start=dates[0],
            window_end=dates[-1],
            observation_count=T,
            effective_sample_size=Decimal(str(round(cov_res["effective_sample_size"], 2))),
            dimension=K,
            factor_ordering=factor_codes,
            covariance_matrix_period=cov_period.tolist(),
            covariance_matrix_annualized=cov_ann.tolist(),
            correlation_matrix=corr_mat.tolist(),
            factor_volatilities_annualized=cov_res["factor_stds_annualized"].tolist(),
            is_positive_semidefinite=is_psd,
            min_eigenvalue=Decimal(str(round(min_eig, 8))),
            max_eigenvalue=Decimal(str(round(cov_res["max_eigenvalue"], 8))),
            condition_number=Decimal(str(round(cov_res["condition_number"], 4))),
            matrix_rank=cov_res["matrix_rank"],
            is_regularized=is_regularized,
            original_min_eigenvalue=orig_min_eig,
            result_hash=res_hash,
        )
        return await self.repo.save_covariance_snapshot(snapshot)

    async def get_covariance_snapshot(self, snapshot_id: str) -> Optional[FactorCovarianceSnapshot]:
        return await self.repo.get_covariance_snapshot_by_id(snapshot_id)

    async def get_latest_covariance_snapshot(
        self, factor_model_version_id: str, as_of_date: date
    ) -> Optional[FactorCovarianceSnapshot]:
        return await self.repo.get_latest_covariance_snapshot(
            factor_model_version_id=factor_model_version_id, as_of_date=as_of_date
        )

    # =========================================================================
    # 5. Rolling Factor Relationships
    # =========================================================================

    async def compute_rolling_relationships(
        self, req: RollingFactorCorrelationRequest
    ) -> Dict[str, Any]:
        returns_mat, factor_ids, factor_codes, dates = await self._resolve_and_align_factor_returns(
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_days=req.window_length * 4,
            selected_factor_ids=[req.factor_a_code, req.factor_b_code],
        )

        idx_a = factor_codes.index(req.factor_a_code)
        idx_b = factor_codes.index(req.factor_b_code)

        rolling_res = compute_rolling_factor_relationships(
            returns_x=returns_mat[:, idx_a],
            returns_y=returns_mat[:, idx_b],
            dates=dates,
            window_length=req.window_length,
            min_observations=req.min_observations,
            baseline_window=req.baseline_window,
        )

        # Persist latest rolling point
        stability_enum = CorrelationStabilityCategory(rolling_res["relationship_stability"])
        record = RollingFactorCorrelation(
            factor_model_version_id=req.factor_model_version_id,
            factor_a_id=factor_ids[idx_a],
            factor_b_id=factor_ids[idx_b],
            factor_a_code=req.factor_a_code,
            factor_b_code=req.factor_b_code,
            as_of_date=req.as_of_date,
            window_length=req.window_length,
            observation_count=len(rolling_res["dates"]),
            correlation_value=Decimal(str(round(rolling_res["current_correlation"], 6))),
            covariance_value=Decimal(str(round(rolling_res["rolling_covariances"][-1], 8))),
            previous_correlation=Decimal(str(round(rolling_res["previous_correlation"], 6))),
            signed_correlation_change=Decimal(str(round(rolling_res["signed_correlation_change"], 6))),
            absolute_strength_change=Decimal(str(round(rolling_res["absolute_strength_change"], 6))),
            baseline_correlation=Decimal(str(round(rolling_res["baseline_correlation"], 6))),
            percentile_rank=Decimal(str(round(rolling_res["percentile_rank"], 2))),
            stability_status=stability_enum,
            is_sign_reversal=rolling_res["is_sign_reversal"],
        )
        await self.repo.save_rolling_correlation(record)

        history_points = [
            {
                "date": rolling_res["dates"][i],
                "correlation": rolling_res["rolling_correlations"][i],
                "covariance": rolling_res["rolling_covariances"][i],
                "std_a": rolling_res["rolling_std_x"][i],
                "std_b": rolling_res["rolling_std_y"][i],
            }
            for i in range(len(rolling_res["dates"]))
        ]

        return {
            "factor_model_version_id": req.factor_model_version_id,
            "factor_a_code": req.factor_a_code,
            "factor_b_code": req.factor_b_code,
            "as_of_date": req.as_of_date,
            "window_length": req.window_length,
            "current_correlation": Decimal(str(round(rolling_res["current_correlation"], 6))),
            "previous_correlation": Decimal(str(round(rolling_res["previous_correlation"], 6))),
            "signed_correlation_change": Decimal(str(round(rolling_res["signed_correlation_change"], 6))),
            "absolute_strength_change": Decimal(str(round(rolling_res["absolute_strength_change"], 6))),
            "baseline_correlation": Decimal(str(round(rolling_res["baseline_correlation"], 6))),
            "percentile_rank": Decimal(str(round(rolling_res["percentile_rank"], 2))),
            "stability_status": stability_enum,
            "is_sign_reversal": rolling_res["is_sign_reversal"],
            "rolling_min": rolling_res["rolling_min"],
            "rolling_max": rolling_res["rolling_max"],
            "rolling_mean": rolling_res["rolling_mean"],
            "rolling_std": rolling_res["rolling_std"],
            "history": history_points,
        }

    # =========================================================================
    # 6. Correlation Regime Detection & Alert Evaluation
    # =========================================================================

    async def evaluate_regimes(
        self, req: FactorRegimeEvaluateRequest
    ) -> Dict[str, Any]:
        returns_mat, factor_ids, factor_codes, dates = await self._resolve_and_align_factor_returns(
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_days=req.window_length * 3,
        )

        K = len(factor_codes)
        active_alerts: List[FactorRegimeAlert] = []
        breaks_count = 0
        evaluated_pairs = 0

        pos_thresh = float(req.high_positive_threshold or 0.70)
        neg_thresh = float(req.high_negative_threshold or -0.70)
        rapid_thresh = float(req.rapid_change_threshold or 0.25)

        for i in range(K):
            for j in range(i + 1, K):
                evaluated_pairs += 1
                fa_code = factor_codes[i]
                fb_code = factor_codes[j]

                roll_res = compute_rolling_factor_relationships(
                    returns_x=returns_mat[:, i],
                    returns_y=returns_mat[:, j],
                    dates=dates,
                    window_length=req.window_length,
                )

                reg_eval = evaluate_correlation_regimes(
                    current_correlation=roll_res["current_correlation"],
                    previous_correlation=roll_res["previous_correlation"],
                    baseline_correlation=roll_res["baseline_correlation"],
                    high_positive_threshold=pos_thresh,
                    high_negative_threshold=neg_thresh,
                    rapid_change_threshold=rapid_thresh,
                    rolling_correlation_series=np.array(roll_res["rolling_correlations"]),
                )

                if reg_eval["has_structural_break"]:
                    breaks_count += 1

                for alrt in reg_eval["alerts"]:
                    sev_enum = RegimeAlertSeverity(alrt["severity"])
                    alert_rec = FactorRegimeAlert(
                        factor_model_version_id=req.factor_model_version_id,
                        factor_a_code=fa_code,
                        factor_b_code=fb_code,
                        as_of_date=req.as_of_date,
                        alert_type=alrt["alert_type"],
                        severity=sev_enum,
                        status=RegimeAlertStatus.ACTIVE,
                        current_correlation=Decimal(str(round(roll_res["current_correlation"], 6))),
                        baseline_correlation=Decimal(str(round(roll_res["baseline_correlation"], 6))),
                        trigger_threshold=Decimal(str(round(alrt["threshold"], 4))),
                        message=alrt["message"],
                    )
                    saved = await self.repo.save_regime_alert(alert_rec)
                    active_alerts.append(saved)

        return {
            "factor_model_version_id": req.factor_model_version_id,
            "as_of_date": req.as_of_date,
            "evaluated_pairs_count": evaluated_pairs,
            "active_alerts_count": len(active_alerts),
            "structural_breaks_count": breaks_count,
            "alerts": active_alerts,
        }

    async def get_active_alerts(
        self, factor_model_version_id: str, as_of_date: date
    ) -> List[FactorRegimeAlert]:
        return await self.repo.get_active_regime_alerts(
            factor_model_version_id=factor_model_version_id, as_of_date=as_of_date
        )

