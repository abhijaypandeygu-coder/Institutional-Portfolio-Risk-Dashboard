"""
M08.03 Factor Sensitivity Service Layer.
Coordinates:
1. Versioned Factor Sensitivity Model and Window Configuration management.
2. Direct regression estimation runs for both individual securities and direct portfolio return series.
3. Coefficient extraction, hypothesis testing (Student's t, p-values, HC3/HAC SEs, Benjamini-Hochberg FDR).
4. Goodness-of-fit and residual diagnostics (R2, Condition Number, VIF, Durbin-Watson, Jarque-Bera).
5. Coefficient stability tracking across historical runs and formal structural break tests (Chow F-test).
6. Reconciliation comparing direct portfolio regression sensitivity against M08.02 holdings-weighted exposure.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
import math
import numpy as np
import uuid
import json

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_definition.definitions.canonical_recipes import (
    compute_deterministic_hash,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorModel,
    FactorModelVersion,
    FactorModelMembership,
    FactorDefinition,
    FactorDefinitionVersion,
    FactorLifecycleStatus,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    FactorReturnSeries,
    FactorReturnObservation,
    PortfolioFactorExposureSnapshot,
)
from backend.app.modules.factor_risk.factor_exposure.repositories.repository import (
    FactorExposureRepository,
)
from backend.app.modules.factor_risk.factor_sensitivity.models import (
    FactorSensitivityModelConfig,
    FactorSensitivityWindowConfig,
    FactorSensitivityRun,
    FactorSensitivityCoefficient,
    FactorSensitivityModelDiagnostics,
    FactorSensitivityStability,
    FactorSensitivityBreakTest,
    TargetType,
    ModelFamily,
    SensitivityWindowType,
    MissingDataPolicy,
    StandardErrorMethod,
    StatisticalSignificanceCategory,
    CoefficientStabilityStatus,
    StructuralBreakTestType,
    StructuralBreakResultStatus,
    SensitivityRunStatus,
)
from backend.app.modules.factor_risk.factor_sensitivity.repositories.repository import (
    FactorSensitivityRepository,
)
from backend.app.modules.factor_risk.factor_sensitivity.calculations.sensitivity_math import (
    fit_factor_sensitivity_regression,
    analyze_coefficient_stability,
    compute_chow_break_test,
)
from backend.app.modules.factor_risk.factor_sensitivity.schemas import (
    CreateModelConfigRequest,
    ModelConfigResponse,
    RunSensitivityRequest,
    SensitivityRunResponse,
    SensitivityCoefficientResponse,
    ModelDiagnosticsResponse,
    SensitivityStabilityResponse,
    StructuralBreakTestResponse,
    RunBreakTestRequest,
    PortfolioSensitivityReconciliationResponse,
    FactorSensitivityComparisonItem,
)
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PriceReferenceType,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
    PortfolioValuationSnapshot,
)


class FactorSensitivityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FactorSensitivityRepository(session)
        self.exposure_repo = FactorExposureRepository(session)

    # =========================================================================
    # 1. MODEL CONFIGURATION
    # =========================================================================

    async def create_model_config(self, req: CreateModelConfigRequest) -> FactorSensitivityModelConfig:
        """Create versioned sensitivity model configuration with deterministic hash."""
        existing = await self.repo.get_config_by_code(req.config_code)
        if existing:
            raise ValueError(f"Sensitivity model config with code {req.config_code} already exists")

        hash_payload = {
            "config_code": req.config_code,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "model_family": req.model_family.value,
            "include_intercept": req.include_intercept,
            "standard_error_method": req.standard_error_method.value,
            "confidence_level": str(req.confidence_level),
            "lookback_observations": req.window_config.lookback_observations,
            "frequency": req.window_config.frequency,
            "missing_data_policy": req.window_config.missing_data_policy.value,
        }
        config_hash = compute_deterministic_hash(hash_payload)

        config = FactorSensitivityModelConfig(
            config_code=req.config_code,
            config_name=req.config_name,
            description=req.description,
            model_family=req.model_family,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            include_intercept=req.include_intercept,
            standard_error_method=req.standard_error_method,
            confidence_level=req.confidence_level,
            ewls_decay_factor=req.ewls_decay_factor,
            ridge_lambda=req.ridge_lambda,
            quantile_tau=req.quantile_tau,
            dependent_return_basis=req.dependent_return_basis,
            return_type=req.return_type,
            currency_basis=req.currency_basis,
            config_hash=config_hash,
            status=FactorLifecycleStatus.ACTIVE,
        )
        await self.repo.save_config(config)

        # Window config
        wc = req.window_config
        window = FactorSensitivityWindowConfig(
            config_id=config.config_id,
            window_type=wc.window_type,
            lookback_observations=wc.lookback_observations,
            frequency=wc.frequency,
            missing_data_policy=wc.missing_data_policy,
            minimum_observations=wc.minimum_observations,
            min_observations_per_param_multiplier=wc.min_observations_per_param_multiplier,
            minimum_coverage_percentage=wc.minimum_coverage_percentage,
        )
        self.session.add(window)
        await self.session.flush()

        saved = await self.repo.get_config_by_id(config.config_id)
        return saved

    async def get_config(self, config_id: str) -> Optional[FactorSensitivityModelConfig]:
        return await self.repo.get_config_by_id(config_id)

    async def list_configs(self) -> List[FactorSensitivityModelConfig]:
        return await self.repo.list_configs()

    # =========================================================================
    # 2. RUN SENSITIVITY ESTIMATION
    # =========================================================================

    async def run_sensitivity_estimation(self, req: RunSensitivityRequest) -> FactorSensitivityRun:
        """
        Execute statistical regression estimation for an individual instrument or direct portfolio.
        """
        config = await self.repo.get_config_by_id(req.config_id)
        if not config:
            raise ValueError(f"Config with ID {req.config_id} not found")

        window_cfg = config.window_configs[0] if config.window_configs else None
        if not window_cfg:
            raise ValueError(f"No window configuration associated with config {req.config_id}")

        # 1. Fetch Factor Model Memberships & Factor Codes
        model_version_stmt = (
            select(FactorModelVersion)
            .options(
                selectinload(FactorModelVersion.memberships)
            )
            .where(FactorModelVersion.model_version_id == config.factor_model_version_id)
        )
        mv_res = await self.session.execute(model_version_stmt)
        mv = mv_res.scalars().first()
        if not mv or not mv.memberships:
            raise ValueError(f"Active factor model version {config.factor_model_version_id} has no factors")

        # Pinned factor order by factor_position
        sorted_memberships = sorted(mv.memberships, key=lambda m: m.factor_position)
        factor_ids = [m.factor_id for m in sorted_memberships]
        factor_codes = [m.factor_code for m in sorted_memberships]
        K = len(factor_codes)

        # 2. Window determination
        as_of = req.as_of_date
        N_lookback = window_cfg.lookback_observations
        if req.custom_window_start and req.custom_window_end:
            win_start = req.custom_window_start
            win_end = req.custom_window_end
        else:
            win_end = as_of
            calendar_days = int(N_lookback * 1.5) + 30
            win_start = as_of - timedelta(days=calendar_days)

        # 3. Fetch Factor Returns
        factor_returns_by_code: Dict[str, Dict[date, Tuple[Decimal, Decimal]]] = {}
        for f_id, f_code in zip(factor_ids, factor_codes):
            stmt = (
                select(FactorReturnObservation)
                .join(FactorReturnSeries, FactorReturnObservation.series_id == FactorReturnSeries.series_id)
                .where(
                    and_(
                        FactorReturnSeries.factor_id == f_id,
                        FactorReturnObservation.trading_date >= win_start,
                        FactorReturnObservation.trading_date <= win_end,
                    )
                )
                .order_by(FactorReturnObservation.trading_date.asc())
            )
            res = await self.session.execute(stmt)
            obs_list = res.scalars().all()
            factor_returns_by_code[f_code] = {
                obs.trading_date: (obs.return_value, obs.risk_free_rate) for obs in obs_list
            }

        # Verify all factors have at least some observations
        for f_code in factor_codes:
            if not factor_returns_by_code.get(f_code):
                run = FactorSensitivityRun(
                    config_id=config.config_id,
                    factor_model_id=config.factor_model_id,
                    factor_model_version_id=config.factor_model_version_id,
                    target_type=req.target_type,
                    target_id=req.target_id,
                    target_listing_id=req.target_listing_id,
                    as_of_date=as_of,
                    window_start=win_start,
                    window_end=win_end,
                    observation_count_expected=N_lookback,
                    observation_count_used=0,
                    run_status=SensitivityRunStatus.BLOCKED_MISSING_FACTOR_RETURNS,
                    failure_reason=f"No factor return series available for factor '{f_code}' in window",
                )
                await self.repo.save_run(run)
                return run

        # 4. Fetch Dependent Target Returns (Security or Direct Portfolio)
        target_returns: Dict[date, Decimal] = {}
        risk_free_rates: Dict[date, Decimal] = {}

        if req.target_type == TargetType.INSTRUMENT:
            # Fetch price history from PriceReferenceObservation
            price_stmt = (
                select(PriceReferenceObservation)
                .where(
                    and_(
                        PriceReferenceObservation.instrument_id == req.target_id,
                        PriceReferenceObservation.trading_date >= win_start,
                        PriceReferenceObservation.trading_date <= win_end,
                        PriceReferenceObservation.reference_type == PriceReferenceType.OFFICIAL_CLOSE,
                    )
                )
                .order_by(PriceReferenceObservation.trading_date.asc())
            )
            price_res = await self.session.execute(price_stmt)
            prices = price_res.scalars().all()

            if len(prices) >= 2:
                for i in range(1, len(prices)):
                    p_curr = prices[i].price_value
                    p_prev = prices[i - 1].price_value
                    if p_prev > 0:
                        ret = (p_curr - p_prev) / p_prev
                        d = prices[i].trading_date
                        target_returns[d] = ret

        elif req.target_type == TargetType.PORTFOLIO:
            # Fetch direct portfolio returns from PortfolioValuationSnapshot
            snap_stmt = (
                select(PortfolioValuationSnapshot)
                .where(
                    and_(
                        PortfolioValuationSnapshot.portfolio_id == req.target_id,
                        PortfolioValuationSnapshot.valuation_date >= win_start,
                        PortfolioValuationSnapshot.valuation_date <= win_end,
                    )
                )
                .order_by(PortfolioValuationSnapshot.valuation_date.asc())
            )
            snap_res = await self.session.execute(snap_stmt)
            snapshots = snap_res.scalars().all()

            if len(snapshots) >= 2:
                for i in range(1, len(snapshots)):
                    nav_curr = snapshots[i].net_asset_value
                    nav_prev = snapshots[i - 1].net_asset_value
                    if nav_prev > 0:
                        ret = (nav_curr - nav_prev) / nav_prev
                        d = snapshots[i].valuation_date
                        target_returns[d] = ret

        # Intersect dates (LISTWISE_COMPLETE)
        common_dates = set(target_returns.keys())
        for f_code in factor_codes:
            common_dates = common_dates.intersection(factor_returns_by_code[f_code].keys())

        sorted_common_dates = sorted(list(common_dates))
        if len(sorted_common_dates) > N_lookback:
            sorted_common_dates = sorted_common_dates[-N_lookback:]

        T = len(sorted_common_dates)
        P = K + (1 if config.include_intercept else 0)

        if T < window_cfg.minimum_observations or T < (window_cfg.min_observations_per_param_multiplier * P):
            run = FactorSensitivityRun(
                config_id=config.config_id,
                factor_model_id=config.factor_model_id,
                factor_model_version_id=config.factor_model_version_id,
                target_type=req.target_type,
                target_id=req.target_id,
                target_listing_id=req.target_listing_id,
                as_of_date=as_of,
                window_start=win_start,
                window_end=win_end,
                observation_count_expected=N_lookback,
                observation_count_used=T,
                run_status=SensitivityRunStatus.BLOCKED_MISSING_SECURITY_RETURNS,
                failure_reason=f"Insufficient aligned returns: {T} observations vs minimum {max(window_cfg.minimum_observations, window_cfg.min_observations_per_param_multiplier * P)}",
            )
            await self.repo.save_run(run)
            return run

        # Construct Design Matrices
        y_list: List[float] = []
        X_rows: List[List[float]] = []

        for d in sorted_common_dates:
            rf = factor_returns_by_code[factor_codes[0]][d][1]
            raw_y = target_returns[d]
            if config.dependent_return_basis == "EXCESS_TOTAL_RETURN":
                y_val = float(raw_y - rf)
            else:
                y_val = float(raw_y)
            y_list.append(y_val)

            row = []
            for f_code in factor_codes:
                f_ret, f_rf = factor_returns_by_code[f_code][d]
                row.append(float(f_ret))
            X_rows.append(row)

        y_arr = np.array(y_list, dtype=float)
        X_arr = np.array(X_rows, dtype=float)

        # 5. Fit Regression Engine
        fit_res = fit_factor_sensitivity_regression(
            y_returns=y_arr,
            X_factors=X_arr,
            factor_names=factor_codes,
            model_family=config.model_family,
            include_intercept=config.include_intercept,
            ewls_decay_factor=float(config.ewls_decay_factor) if config.ewls_decay_factor else 0.94,
            ridge_lambda=float(config.ridge_lambda) if config.ridge_lambda else 0.01,
            quantile_tau=float(config.quantile_tau) if config.quantile_tau else 0.50,
            standard_error_method=config.standard_error_method,
            confidence_level=float(config.confidence_level),
        )

        # 6. Build and Persist Run Record
        actual_win_start = sorted_common_dates[0]
        actual_win_end = sorted_common_dates[-1]

        run = FactorSensitivityRun(
            config_id=config.config_id,
            factor_model_id=config.factor_model_id,
            factor_model_version_id=config.factor_model_version_id,
            target_type=req.target_type,
            target_id=req.target_id,
            target_listing_id=req.target_listing_id,
            as_of_date=as_of,
            window_start=actual_win_start,
            window_end=actual_win_end,
            observation_count_expected=N_lookback,
            observation_count_used=T,
            effective_sample_size=Decimal(str(fit_res.get("effective_sample_size", T))),
            run_status=SensitivityRunStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )
        await self.repo.save_run(run)

        # Save Coefficients
        for f_pos, (f_id, f_code) in enumerate(zip(factor_ids, factor_codes), start=1):
            c_info = fit_res["coefficients"].get(f_code, {})
            coeff = FactorSensitivityCoefficient(
                run_id=run.run_id,
                factor_id=f_id,
                factor_code=f_code,
                factor_position=f_pos,
                coefficient_value=Decimal(str(round(c_info.get("coefficient_value", 0.0), 6))),
                coefficient_standard_error=Decimal(str(round(c_info["standard_error"], 6))) if c_info.get("standard_error") is not None else None,
                t_statistic=Decimal(str(round(c_info["t_statistic"], 4))) if c_info.get("t_statistic") is not None else None,
                p_value=Decimal(str(round(c_info["p_value"], 6))) if c_info.get("p_value") is not None else None,
                adjusted_p_value=Decimal(str(round(c_info["adjusted_p_value"], 6))) if c_info.get("adjusted_p_value") is not None else None,
                confidence_interval_lower=Decimal(str(round(c_info["confidence_interval_lower"], 6))) if c_info.get("confidence_interval_lower") is not None else None,
                confidence_interval_upper=Decimal(str(round(c_info["confidence_interval_upper"], 6))) if c_info.get("confidence_interval_upper") is not None else None,
                confidence_level=config.confidence_level,
                significance_status=c_info.get("significance_status", StatisticalSignificanceCategory.INFERENCE_UNAVAILABLE),
                economic_contribution_1sigma=Decimal(str(round(c_info["economic_contribution_1sigma"], 6))) if c_info.get("economic_contribution_1sigma") is not None else None,
            )
            self.session.add(coeff)

        # Save Diagnostics
        diag_data = fit_res["diagnostics"]
        diag = FactorSensitivityModelDiagnostics(
            run_id=run.run_id,
            intercept_value=Decimal(str(round(diag_data["intercept"], 8))) if diag_data.get("intercept") is not None else None,
            intercept_standard_error=Decimal(str(round(diag_data["intercept_std_error"], 8))) if diag_data.get("intercept_std_error") is not None else None,
            intercept_t_statistic=Decimal(str(round(diag_data["intercept_t_stat"], 4))) if diag_data.get("intercept_t_stat") is not None else None,
            intercept_p_value=Decimal(str(round(diag_data["intercept_p_value"], 6))) if diag_data.get("intercept_p_value") is not None else None,
            r_squared=Decimal(str(round(diag_data.get("r_squared", 0.0), 6))),
            adjusted_r_squared=Decimal(str(round(diag_data.get("adj_r_squared", 0.0), 6))),
            residual_sum_of_squares=Decimal(str(round(diag_data.get("residual_sum_of_squares", 0.0), 8))),
            total_sum_of_squares=Decimal(str(round(diag_data.get("total_sum_of_squares", 0.0), 8))),
            residual_variance=Decimal(str(round(diag_data.get("residual_variance", 0.0), 8))),
            residual_standard_error=Decimal(str(round(diag_data.get("residual_standard_error", 0.0), 8))),
            rmse=Decimal(str(round(diag_data.get("rmse", 0.0), 8))),
            mae=Decimal(str(round(diag_data.get("mae", 0.0), 8))),
            degrees_of_freedom=diag_data.get("degrees_of_freedom", 0),
            design_matrix_rank=diag_data.get("design_matrix_rank", 0),
            condition_number=Decimal(str(round(diag_data.get("condition_number", 1.0), 4))),
            variance_inflation_factors=diag_data.get("variance_inflation_factors", {}),
            durbin_watson_stat=Decimal(str(round(diag_data["durbin_watson_stat"], 4))) if diag_data.get("durbin_watson_stat") is not None else None,
            jarque_bera_stat=Decimal(str(round(diag_data["jarque_bera_stat"], 4))) if diag_data.get("jarque_bera_stat") is not None else None,
            jarque_bera_p_value=Decimal(str(round(diag_data["jarque_bera_p_value"], 6))) if diag_data.get("jarque_bera_p_value") is not None else None,
        )
        self.session.add(diag)
        await self.session.commit()

        # Reload with relationships
        saved_run = await self.repo.get_run_by_id(run.run_id)
        return saved_run

    async def get_run(self, run_id: str) -> Optional[FactorSensitivityRun]:
        return await self.repo.get_run_by_id(run_id)

    # =========================================================================
    # 3. COEFFICIENT STABILITY & STRUCTURAL BREAKS
    # =========================================================================

    async def compute_target_stability(
        self,
        target_type: TargetType,
        target_id: str,
        factor_code: str,
        min_runs: int = 5,
    ) -> Optional[FactorSensitivityStability]:
        """
        Analyze rolling coefficient history for a given target and factor to detect drift and instability.
        """
        coeffs = await self.repo.get_coefficients_history(
            target_type=target_type,
            target_id=target_id,
            factor_code=factor_code,
        )
        if not coeffs:
            return None

        # Sort chronologically
        history_values = [float(c.coefficient_value) for c in coeffs]
        if len(history_values) < 2:
            return None

        analysis_metrics = analyze_coefficient_stability(history_values)

        # Dates from the runs
        # Use first and last coefficient creation/date
        first_date = coeffs[0].run.as_of_date if coeffs[0].run else date.today()
        last_date = coeffs[-1].run.as_of_date if coeffs[-1].run else date.today()

        stability = FactorSensitivityStability(
            target_type=target_type,
            target_id=target_id,
            factor_id=coeffs[-1].factor_id,
            factor_code=factor_code,
            analysis_start=first_date,
            analysis_end=last_date,
            observations_analyzed=len(history_values),
            rolling_coefficient_mean=Decimal(str(analysis_metrics["rolling_coefficient_mean"])),
            rolling_coefficient_std=Decimal(str(analysis_metrics["rolling_coefficient_std"])),
            rolling_coefficient_min=Decimal(str(analysis_metrics["rolling_coefficient_min"])),
            rolling_coefficient_max=Decimal(str(analysis_metrics["rolling_coefficient_max"])),
            latest_coefficient=Decimal(str(analysis_metrics["latest_coefficient"])),
            previous_coefficient=Decimal(str(analysis_metrics["previous_coefficient"])),
            absolute_change=Decimal(str(analysis_metrics["absolute_change"])),
            relative_change=Decimal(str(analysis_metrics["relative_change"])) if analysis_metrics["relative_change"] is not None else None,
            sign_change_count=analysis_metrics["sign_change_count"],
            stability_status=analysis_metrics["stability_status"],
        )
        await self.repo.save_stability(stability)
        await self.session.commit()

        return await self.repo.get_stability_by_id(stability.stability_id)

    async def run_break_test(self, req: RunBreakTestRequest) -> FactorSensitivityBreakTest:
        """
        Execute formal structural break test (Chow F-test) around candidate date.
        """
        stability = await self.repo.get_stability_by_id(req.stability_id)
        if not stability:
            raise ValueError(f"Stability record {req.stability_id} not found")

        # Fetch runs before and after candidate break date
        all_coeffs = await self.repo.get_coefficients_history(
            target_type=stability.target_type,
            target_id=stability.target_id,
            factor_code=stability.factor_code,
        )

        pre_coeffs = [c for c in all_coeffs if c.run and c.run.as_of_date < req.candidate_break_date]
        post_coeffs = [c for c in all_coeffs if c.run and c.run.as_of_date >= req.candidate_break_date]

        if len(pre_coeffs) < 3 or len(post_coeffs) < 3:
            # Insufficient observations for Chow test
            test_record = FactorSensitivityBreakTest(
                stability_id=stability.stability_id,
                test_type=req.test_type,
                candidate_break_date=req.candidate_break_date,
                pre_break_count=len(pre_coeffs),
                post_break_count=len(post_coeffs),
                test_statistic=Decimal("0.0"),
                p_value=Decimal("1.0"),
                critical_value_95=Decimal("3.0"),
                result_status=StructuralBreakResultStatus.INSUFFICIENT_OBSERVATIONS,
            )
            await self.repo.save_break_test(test_record)
            await self.session.commit()
            return test_record

        # For structural break on regression, gather the underlying returns if latest run available
        latest_run = await self.repo.get_latest_run_for_target(
            target_type=stability.target_type,
            target_id=stability.target_id,
        )
        if not latest_run:
            raise ValueError("No valid estimation run found for target")

        # Approximate Chow F-test using pre and post split variance
        pre_vals = np.array([float(c.coefficient_value) for c in pre_coeffs])
        post_vals = np.array([float(c.coefficient_value) for c in post_coeffs])
        pooled = np.concatenate([pre_vals, post_vals])

        rss_pooled = float(np.sum((pooled - np.mean(pooled)) ** 2))
        rss_pre = float(np.sum((pre_vals - np.mean(pre_vals)) ** 2))
        rss_post = float(np.sum((post_vals - np.mean(post_vals)) ** 2))

        chow_res = compute_chow_break_test(
            rss_pooled=max(rss_pooled, 1e-12),
            rss_sub1=max(rss_pre, 1e-12),
            rss_sub2=max(rss_post, 1e-12),
            k_params=1,
            n_obs1=len(pre_vals),
            n_obs2=len(post_vals),
        )

        test_record = FactorSensitivityBreakTest(
            stability_id=stability.stability_id,
            test_type=req.test_type,
            candidate_break_date=req.candidate_break_date,
            pre_break_count=len(pre_coeffs),
            post_break_count=len(post_coeffs),
            test_statistic=Decimal(str(chow_res["f_stat"])),
            p_value=Decimal(str(chow_res["p_value"])),
            critical_value_95=Decimal(str(chow_res["critical_val_95"])),
            result_status=chow_res["result_status"],
        )
        await self.repo.save_break_test(test_record)
        await self.session.commit()
        return test_record

    # =========================================================================
    # 4. DIRECT SENSITIVITY VS. WEIGHTED EXPOSURE RECONCILIATION
    # =========================================================================

    async def reconcile_portfolio_sensitivity(
        self,
        portfolio_id: str,
        as_of_date: Optional[date] = None,
        config_id: Optional[str] = None,
    ) -> PortfolioSensitivityReconciliationResponse:
        """
        Compare direct time-series regression sensitivity (R_p,t = alpha + sum beta * F + eps)
        against holdings-weighted bottom-up factor exposure (sum w_i * beta_i,k) from M08.02.
        Identifies discrepancies due to active rebalancing, cash drag, or idiosyncratic non-linearities.
        """
        # 1. Fetch Latest Direct Portfolio Sensitivity Run
        direct_run = await self.repo.get_latest_run_for_target(
            target_type=TargetType.PORTFOLIO,
            target_id=portfolio_id,
            as_of_date=as_of_date,
            config_id=config_id,
        )
        if not direct_run:
            raise ValueError(f"No direct factor sensitivity run found for portfolio {portfolio_id}")

        # 2. Fetch Latest Holdings-Weighted Factor Exposure from M08.02
        weighted_stmt = (
            select(PortfolioFactorExposureSnapshot)
            .where(
                and_(
                    PortfolioFactorExposureSnapshot.portfolio_id == portfolio_id,
                    PortfolioFactorExposureSnapshot.as_of_date <= direct_run.as_of_date,
                )
            )
            .order_by(desc(PortfolioFactorExposureSnapshot.as_of_date))
        )
        w_res = await self.session.execute(weighted_stmt)
        weighted_snapshots = w_res.scalars().all()

        weighted_map: Dict[str, Decimal] = {}
        if weighted_snapshots:
            # Use most recent snapshot matching as_of_date
            latest_snap_date = weighted_snapshots[0].as_of_date
            matching_snaps = [s for s in weighted_snapshots if s.as_of_date == latest_snap_date]
            for s in matching_snaps:
                weighted_map[s.factor_code] = s.signed_nav_exposure

        # 3. Compare factor-by-factor
        comparison_items: List[FactorSensitivityComparisonItem] = []
        max_discrepancy = Decimal("0.0")

        for coeff in direct_run.coefficients:
            f_code = coeff.factor_code
            w_exp = weighted_map.get(f_code, Decimal("0.0"))
            dir_beta = coeff.coefficient_value
            diff = abs(dir_beta - w_exp)

            if diff > max_discrepancy:
                max_discrepancy = diff

            # Reason description
            if diff < Decimal("0.05"):
                exp_text = "Strong concordance: direct time-series beta aligns closely with current bottom-up holdings weight."
            elif diff < Decimal("0.15"):
                exp_text = "Moderate divergence: typical of intra-period rebalancing or varying cash buffer."
            else:
                exp_text = "Significant divergence: indicates substantial recent portfolio turnover, structural shifts, or non-linear exposures."

            comparison_items.append(
                FactorSensitivityComparisonItem(
                    factor_id=coeff.factor_id,
                    factor_code=f_code,
                    direct_sensitivity_beta=dir_beta,
                    direct_p_value=coeff.p_value,
                    direct_significance=coeff.significance_status,
                    holdings_weighted_exposure=w_exp,
                    absolute_discrepancy=diff,
                    discrepancy_explanation=exp_text,
                )
            )

        overall_status = "ALIGNED" if max_discrepancy <= Decimal("0.10") else "DIVERGENT"

        return PortfolioSensitivityReconciliationResponse(
            portfolio_id=portfolio_id,
            as_of_date=direct_run.as_of_date,
            direct_run_id=direct_run.run_id,
            model_config_id=direct_run.config_id,
            factor_model_id=direct_run.factor_model_id,
            factor_model_name="Canonical Equity Factor Model",
            direct_portfolio_r2=direct_run.diagnostics.r_squared if direct_run.diagnostics else Decimal("0.0"),
            comparison_items=comparison_items,
            overall_alignment_status=overall_status,
        )
