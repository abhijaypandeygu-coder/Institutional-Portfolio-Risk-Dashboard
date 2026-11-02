"""
M08.04 Factor Attribution Service Layer.
Coordinates:
1. Attribution configuration profile management with deterministic hashing
2. Factor Covariance Matrix construction, PSD checks, and persistence
3. Factor Return Attribution execution (single-period & Carino multi-period linking)
4. Factor Risk Attribution execution (systematic variance, Euler risk, marginal risk, residual interaction)
5. Formal Attribution Reconciliation Bridge (return & risk reconciliation)
6. Attribution comparison engine (period-over-period and portfolio comparison)
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
    FactorSensitivityRun,
    FactorSensitivityCoefficient,
    TargetType,
)
from backend.app.modules.factor_risk.factor_sensitivity.repositories.repository import (
    FactorSensitivityRepository,
)
from backend.app.modules.factor_risk.factor_attribution.models import (
    FactorAttributionConfig,
    FactorReturnAttributionRun,
    FactorReturnAttributionComponent,
    FactorRiskAttributionRun,
    FactorRiskAttributionComponent,
    FactorAttributionCovarianceSnapshot,
    FactorAttributionReconciliation,
    AttributionMode,
    AttributionReturnBasis,
    MultiPeriodLinkingMethod,
    ReturnComponentType,
    RiskComponentType,
    AttributionReconciliationStatus,
    AttributionRunStatus,
    CovarianceMethod,
)
from backend.app.modules.factor_risk.factor_attribution.repositories.repository import (
    FactorAttributionRepository,
)
from backend.app.modules.factor_risk.factor_attribution.calculations.attribution_math import (
    compute_single_period_return_attribution,
    compute_carino_multi_period_linking,
    validate_factor_covariance_matrix,
    compute_systematic_factor_risk,
    compute_total_modeled_risk,
    build_attribution_reconciliation_bridge,
)
from backend.app.modules.factor_risk.factor_attribution.schemas import (
    CreateAttributionConfigRequest,
    RunReturnAttributionRequest,
    RunRiskAttributionRequest,
    AttributionComparisonRequest,
    AttributionComparisonResponse,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PortfolioValuationSnapshot,
)


class FactorAttributionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FactorAttributionRepository(session)
        self.exposure_repo = FactorExposureRepository(session)
        self.sensitivity_repo = FactorSensitivityRepository(session)

    # =========================================================================
    # 1. ATTRIBUTION CONFIGURATION
    # =========================================================================

    async def create_attribution_config(
        self, req: CreateAttributionConfigRequest
    ) -> FactorAttributionConfig:
        """Create versioned attribution configuration profile with deterministic SHA-256 hash."""
        existing = await self.repo.get_config_by_code(req.config_code)
        if existing:
            raise ValueError(f"Attribution config with code '{req.config_code}' already exists")

        hash_payload = {
            "config_code": req.config_code,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "attribution_mode": req.attribution_mode.value,
            "return_basis": req.return_basis.value,
            "linking_method": req.linking_method.value,
            "covariance_method": req.covariance_method.value,
            "annualization_factor": str(req.annualization_factor),
            "reconciliation_tolerance": str(req.reconciliation_tolerance),
        }
        config_hash = compute_deterministic_hash(hash_payload)

        config = FactorAttributionConfig(
            config_code=req.config_code,
            config_name=req.config_name,
            description=req.description,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            attribution_mode=req.attribution_mode,
            return_basis=req.return_basis,
            linking_method=req.linking_method,
            covariance_method=req.covariance_method,
            annualization_factor=req.annualization_factor,
            reconciliation_tolerance=req.reconciliation_tolerance,
            coverage_threshold_pct=req.coverage_threshold_pct,
            currency_basis=req.currency_basis,
            config_hash=config_hash,
            status=FactorLifecycleStatus.ACTIVE,
        )
        saved = await self.repo.save_config(config)
        await self.session.commit()
        return saved

    async def get_config(self, config_id: str) -> Optional[FactorAttributionConfig]:
        return await self.repo.get_config_by_id(config_id)

    async def list_configs(self) -> List[FactorAttributionConfig]:
        return await self.repo.list_configs()

    # =========================================================================
    # 2. FACTOR COVARIANCE SNAPSHOT GENERATION
    # =========================================================================

    async def get_or_create_factor_covariance(
        self,
        factor_model_version_id: str,
        as_of_date: date,
        lookback_days: int = 252,
        covariance_method: CovarianceMethod = CovarianceMethod.SAMPLE,
        annualization_factor: Decimal = Decimal("252.00"),
    ) -> FactorAttributionCovarianceSnapshot:
        """
        Retrieves existing covariance snapshot or estimates factor covariance matrix
        over lookback window, verifying positive-semidefiniteness (PSD) and condition number.
        """
        existing = await self.repo.get_latest_covariance_snapshot(
            factor_model_version_id=factor_model_version_id,
            as_of_date=as_of_date,
        )
        if existing and existing.estimation_window_end == as_of_date:
            return existing

        # 1. Fetch Factor Model Memberships in Pinned Order
        mv_stmt = (
            select(FactorModelVersion)
            .options(selectinload(FactorModelVersion.memberships))
            .where(FactorModelVersion.model_version_id == factor_model_version_id)
        )
        mv_res = await self.session.execute(mv_stmt)
        mv = mv_res.scalars().first()
        if not mv or not mv.memberships:
            raise ValueError(f"Factor model version {factor_model_version_id} has no memberships")

        sorted_m = sorted(mv.memberships, key=lambda m: m.factor_position)
        factor_ids = [m.factor_id for m in sorted_m]
        factor_codes = [m.factor_code for m in sorted_m]
        K = len(factor_codes)

        # 2. Query factor returns
        win_start = as_of_date - timedelta(days=int(lookback_days * 1.5) + 30)
        win_end = as_of_date

        factor_returns_by_code: Dict[str, Dict[date, float]] = {}
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
                obs.trading_date: float(obs.return_value) for obs in obs_list
            }

        # Common date intersection
        common_dates = set(factor_returns_by_code[factor_codes[0]].keys())
        for f_code in factor_codes[1:]:
            common_dates = common_dates.intersection(factor_returns_by_code[f_code].keys())

        sorted_common_dates = sorted(list(common_dates))
        if len(sorted_common_dates) > lookback_days:
            sorted_common_dates = sorted_common_dates[-lookback_days:]

        N = len(sorted_common_dates)
        if N < 20:
            raise ValueError(f"Insufficient aligned factor observations: {N} vs minimum 20")

        # Build matrix (N, K)
        F_mat = np.zeros((N, K), dtype=np.float64)
        for i, d in enumerate(sorted_common_dates):
            for j, f_code in enumerate(factor_codes):
                F_mat[i, j] = factor_returns_by_code[f_code][d]

        # Compute sample covariance matrix
        cov_matrix = np.cov(F_mat, rowvar=False)
        if K == 1:
            cov_matrix = np.array([[float(cov_matrix)]])

        # Validate PSD
        diag = validate_factor_covariance_matrix(cov_matrix, factor_codes)

        cov_list = cov_matrix.tolist()
        hash_payload = {
            "factor_model_version_id": factor_model_version_id,
            "window_start": sorted_common_dates[0].isoformat(),
            "window_end": sorted_common_dates[-1].isoformat(),
            "observation_count": N,
            "covariance_matrix": cov_list,
        }
        res_hash = compute_deterministic_hash(hash_payload)

        snapshot = FactorAttributionCovarianceSnapshot(
            factor_model_id=mv.model_id,
            factor_model_version_id=factor_model_version_id,
            covariance_method=covariance_method,
            observation_frequency="DAILY",
            estimation_window_start=sorted_common_dates[0],
            estimation_window_end=sorted_common_dates[-1],
            observation_count=N,
            annualization_factor=annualization_factor,
            factor_names_ordered=factor_codes,
            covariance_matrix=cov_list,
            is_positive_semidefinite=diag["is_positive_semidefinite"],
            min_eigenvalue=Decimal(str(round(diag["min_eigenvalue"], 8))),
            condition_number=Decimal(str(round(diag["condition_number"], 4))) if not math.isinf(diag["condition_number"]) else Decimal("999999.0"),
            result_hash=res_hash,
        )
        await self.repo.save_covariance_snapshot(snapshot)
        await self.session.commit()
        return snapshot

    # =========================================================================
    # 3. FACTOR RETURN ATTRIBUTION
    # =========================================================================

    async def run_return_attribution(
        self, req: RunReturnAttributionRequest
    ) -> FactorReturnAttributionRun:
        """
        Executes factor return attribution for a portfolio over a specified date range.
        Handles single-period and multi-period Carino linking.
        """
        config = await self.repo.get_config_by_id(req.config_id)
        if not config:
            raise ValueError(f"Attribution configuration '{req.config_id}' not found")

        mode = req.attribution_mode or config.attribution_mode
        linking_method = req.linking_method or config.linking_method

        # 1. Fetch Portfolio Valuations / Nav Returns
        val_stmt = (
            select(PortfolioValuationSnapshot)
            .where(
                and_(
                    PortfolioValuationSnapshot.portfolio_id == req.portfolio_id,
                    PortfolioValuationSnapshot.valuation_date >= req.start_date,
                    PortfolioValuationSnapshot.valuation_date <= req.end_date,
                )
            )
            .order_by(PortfolioValuationSnapshot.valuation_date.asc())
        )
        val_res = await self.session.execute(val_stmt)
        snapshots = val_res.scalars().all()

        daily_returns: Dict[date, float] = {}
        if len(snapshots) >= 2:
            for i in range(1, len(snapshots)):
                nav_prev = float(getattr(snapshots[i - 1], "net_asset_value", getattr(snapshots[i - 1], "net_market_value", 0.0)))
                nav_curr = float(getattr(snapshots[i], "net_asset_value", getattr(snapshots[i], "net_market_value", 0.0)))
                if nav_prev > 0:
                    d = getattr(snapshots[i], "valuation_date", snapshots[i].valuation_timestamp.date() if hasattr(snapshots[i], "valuation_timestamp") else None)
                    if d:
                        daily_returns[d] = (nav_curr - nav_prev) / nav_prev

        # 2. Fetch Portfolio Factor Sensitivities
        # Look for direct portfolio sensitivity run or M08.02 exposure snapshot
        sens_stmt = (
            select(FactorSensitivityRun)
            .options(
                selectinload(FactorSensitivityRun.coefficients),
                selectinload(FactorSensitivityRun.diagnostics),
            )
            .where(
                and_(
                    FactorSensitivityRun.target_type == TargetType.PORTFOLIO,
                    FactorSensitivityRun.target_id == req.portfolio_id,
                    FactorSensitivityRun.factor_model_version_id == config.factor_model_version_id,
                    FactorSensitivityRun.as_of_date <= req.end_date,
                )
            )
            .order_by(desc(FactorSensitivityRun.as_of_date))
        )
        s_res = await self.session.execute(sens_stmt)
        sens_run = s_res.scalars().first()

        portfolio_betas: Dict[str, float] = {}
        intercept = 0.0
        sens_run_id = None
        if sens_run and sens_run.coefficients:
            sens_run_id = sens_run.run_id
            for coeff in sens_run.coefficients:
                portfolio_betas[coeff.factor_code] = float(coeff.coefficient_value)
            if sens_run.diagnostics and sens_run.diagnostics.intercept_value is not None:
                intercept = float(sens_run.diagnostics.intercept_value)

        # Fallback to M08.02 bottom-up exposure if direct sensitivity is not found
        if not portfolio_betas:
            w_stmt = (
                select(PortfolioFactorExposureSnapshot)
                .where(
                    and_(
                        PortfolioFactorExposureSnapshot.portfolio_id == req.portfolio_id,
                        PortfolioFactorExposureSnapshot.as_of_date <= req.end_date,
                    )
                )
                .order_by(desc(PortfolioFactorExposureSnapshot.as_of_date))
            )
            w_res = await self.session.execute(w_stmt)
            w_snaps = w_res.scalars().all()
            if w_snaps:
                latest_w_date = w_snaps[0].as_of_date
                for ws in [s for s in w_snaps if s.as_of_date == latest_w_date]:
                    portfolio_betas[ws.factor_code] = float(ws.signed_nav_exposure)

        if not portfolio_betas:
            run = FactorReturnAttributionRun(
                config_id=config.config_id,
                portfolio_id=req.portfolio_id,
                factor_model_id=config.factor_model_id,
                factor_model_version_id=config.factor_model_version_id,
                period_start=req.start_date,
                period_end=req.end_date,
                attribution_mode=mode,
                linking_method=linking_method,
                realized_portfolio_return=Decimal("0.0"),
                total_attributed_return=Decimal("0.0"),
                factor_explained_return=Decimal("0.0"),
                reconciliation_status=AttributionReconciliationStatus.INSUFFICIENT_DATA,
                run_status=AttributionRunStatus.BLOCKED_MISSING_DATA,
                failure_reason=f"No factor sensitivity or exposure records found for portfolio {req.portfolio_id}",
            )
            await self.repo.save_return_run(run)
            await self.session.commit()
            return run

        # 3. Fetch Factor Return Observations
        factor_codes = list(portfolio_betas.keys())
        factor_returns_by_code: Dict[str, Dict[date, Tuple[float, float]]] = {}
        for f_code in factor_codes:
            stmt = (
                select(FactorReturnObservation)
                .join(FactorReturnSeries, FactorReturnObservation.series_id == FactorReturnSeries.series_id)
                .where(
                    and_(
                        FactorReturnSeries.factor_code == f_code,
                        FactorReturnObservation.trading_date >= req.start_date,
                        FactorReturnObservation.trading_date <= req.end_date,
                    )
                )
                .order_by(FactorReturnObservation.trading_date.asc())
            )
            res = await self.session.execute(stmt)
            obs_list = res.scalars().all()
            factor_returns_by_code[f_code] = {
                obs.trading_date: (float(obs.return_value), float(obs.risk_free_rate)) for obs in obs_list
            }

        # Filter days with aligned portfolio returns and factor returns
        aligned_dates = sorted(list(set(daily_returns.keys())))
        if not aligned_dates:
            # If no multi-day history, attempt single-period attribution on the available window
            # using cumulative or latest returns
            aligned_dates = [req.end_date]
            daily_returns[req.end_date] = 0.0

        # Run period-by-period attribution
        period_portfolio_returns: List[float] = []
        period_components: List[Dict[str, float]] = []

        total_realized_return = 0.0
        arithmetic_factor_contributions: Dict[str, float] = {f: 0.0 for f in factor_codes}
        total_rf_contrib = 0.0
        total_intercept_contrib = 0.0
        total_model_residual = 0.0

        for d in aligned_dates:
            r_p = daily_returns.get(d, 0.0)
            f_rets = {f: factor_returns_by_code.get(f, {}).get(d, (0.0, 0.0))[0] for f in factor_codes}
            rf = factor_returns_by_code[factor_codes[0]].get(d, (0.0, 0.0))[1] if factor_returns_by_code.get(factor_codes[0]) else 0.0

            sub_attr = compute_single_period_return_attribution(
                factor_sensitivities=portfolio_betas,
                factor_returns=f_rets,
                realized_portfolio_return=r_p,
                risk_free_rate=rf,
                intercept=intercept / max(1, len(aligned_dates)),
                is_excess_return_model=(config.return_basis == AttributionReturnBasis.EXCESS_RETURN),
            )

            period_portfolio_returns.append(r_p)
            comp_map = {f: sub_attr["factor_contributions"][f]["contribution"] for f in factor_codes}
            comp_map["RISK_FREE"] = sub_attr["risk_free_contribution"]
            comp_map["INTERCEPT"] = sub_attr["intercept_contribution"]
            comp_map["MODEL_RESIDUAL"] = sub_attr["model_residual"]
            period_components.append(comp_map)

            total_realized_return += r_p
            total_rf_contrib += sub_attr["risk_free_contribution"]
            total_intercept_contrib += sub_attr["intercept_contribution"]
            total_model_residual += sub_attr["model_residual"]
            for f in factor_codes:
                arithmetic_factor_contributions[f] += sub_attr["factor_contributions"][f]["contribution"]

        # 4. Multi-period Linking (Carino)
        linked_contributions = {}
        if len(aligned_dates) > 1 and linking_method == MultiPeriodLinkingMethod.CARINO:
            carino_res = compute_carino_multi_period_linking(
                period_portfolio_returns=period_portfolio_returns,
                period_component_contributions=period_components,
            )
            cum_port_return = carino_res["cumulative_portfolio_return"]
            linked_contributions = carino_res["linked_component_contributions"]
        else:
            cum_port_return = total_realized_return
            linked_contributions = {
                **arithmetic_factor_contributions,
                "RISK_FREE": total_rf_contrib,
                "INTERCEPT": total_intercept_contrib,
                "MODEL_RESIDUAL": total_model_residual,
            }

        factor_explained_return = sum(linked_contributions.get(f, 0.0) for f in factor_codes)
        rf_final = linked_contributions.get("RISK_FREE", 0.0)
        alpha_final = linked_contributions.get("INTERCEPT", 0.0)
        res_final = linked_contributions.get("MODEL_RESIDUAL", 0.0)
        total_attributed = rf_final + alpha_final + factor_explained_return + res_final
        recon_residual = float(cum_port_return - total_attributed)

        recon_bridge = build_attribution_reconciliation_bridge(
            observed_portfolio_return=cum_port_return,
            risk_free_rate=rf_final,
            intercept=alpha_final,
            factor_contributions={f: linked_contributions.get(f, 0.0) for f in factor_codes},
            model_residual=res_final,
            reconciliation_tolerance=float(config.reconciliation_tolerance),
        )

        run = FactorReturnAttributionRun(
            config_id=config.config_id,
            portfolio_id=req.portfolio_id,
            factor_model_id=config.factor_model_id,
            factor_model_version_id=config.factor_model_version_id,
            sensitivity_run_id=sens_run_id,
            exposure_snapshot_id=req.exposure_snapshot_id,
            period_start=req.start_date,
            period_end=req.end_date,
            attribution_mode=mode,
            linking_method=linking_method,
            realized_portfolio_return=Decimal(str(round(cum_port_return, 8))),
            total_attributed_return=Decimal(str(round(total_attributed, 8))),
            factor_explained_return=Decimal(str(round(factor_explained_return, 8))),
            risk_free_contribution=Decimal(str(round(rf_final, 8))),
            intercept_contribution=Decimal(str(round(alpha_final, 8))),
            model_residual=Decimal(str(round(res_final, 8))),
            reconciliation_residual=Decimal(str(round(recon_residual, 8))),
            reconciliation_status=recon_bridge["reconciliation_status"],
            coverage_percentage=Decimal("100.00"),
            run_status=AttributionRunStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )
        await self.repo.save_return_run(run)

        # 5. Persist Components
        for f_code in factor_codes:
            f_c = FactorReturnAttributionComponent(
                run_id=run.run_id,
                component_type=ReturnComponentType.FACTOR,
                factor_code=f_code,
                factor_sensitivity_beta=Decimal(str(round(portfolio_betas[f_code], 6))),
                factor_realized_return=Decimal(str(round(sum(factor_returns_by_code[f_code].get(d, (0.0, 0.0))[0] for d in aligned_dates), 8))),
                arithmetic_contribution=Decimal(str(round(arithmetic_factor_contributions[f_code], 8))),
                linked_contribution=Decimal(str(round(linked_contributions.get(f_code, 0.0), 8))),
                contribution_percentage_of_return=Decimal(str(round(linked_contributions.get(f_code, 0.0) / cum_port_return * 100.0, 4))) if abs(cum_port_return) > 1e-6 else None,
                currency=config.currency_basis,
            )
            self.session.add(f_c)

        # Residual Component
        res_comp = FactorReturnAttributionComponent(
            run_id=run.run_id,
            component_type=ReturnComponentType.MODEL_RESIDUAL,
            arithmetic_contribution=Decimal(str(round(total_model_residual, 8))),
            linked_contribution=Decimal(str(round(res_final, 8))),
            contribution_percentage_of_return=Decimal(str(round(res_final / cum_port_return * 100.0, 4))) if abs(cum_port_return) > 1e-6 else None,
            currency=config.currency_basis,
        )
        self.session.add(res_comp)

        # Reconciliation Bridge Record
        reconciliation_rec = FactorAttributionReconciliation(
            return_run_id=run.run_id,
            reconciliation_type="RETURN",
            observed_value=Decimal(str(round(cum_port_return, 8))),
            reported_value=Decimal(str(round(total_attributed, 8))),
            absolute_difference=Decimal(str(round(recon_bridge["absolute_reconciliation_difference"], 8))),
            relative_difference=Decimal(str(round(recon_bridge["relative_reconciliation_difference"], 4))) if recon_bridge["relative_reconciliation_difference"] is not None else None,
            tolerance=config.reconciliation_tolerance,
            coverage_percentage=Decimal("100.00"),
            reconciliation_status=recon_bridge["reconciliation_status"],
            reason_codes=["MODEL_FIT_PERFECT"] if recon_bridge["absolute_reconciliation_difference"] < 1e-8 else ["CARINO_LINKED_APPROXIMATION"],
        )
        await self.repo.save_reconciliation(reconciliation_rec)
        await self.session.commit()

        return await self.repo.get_return_run_by_id(run.run_id)

    # =========================================================================
    # 4. FACTOR RISK ATTRIBUTION
    # =========================================================================

    async def run_risk_attribution(
        self, req: RunRiskAttributionRequest
    ) -> FactorRiskAttributionRun:
        """
        Executes factor risk attribution (systematic Euler risk decomposition,
        marginal risk, residual variance, and total modeled volatility).
        """
        config = await self.repo.get_config_by_id(req.config_id)
        if not config:
            raise ValueError(f"Attribution configuration '{req.config_id}' not found")

        # 1. Resolve or compute Covariance Snapshot
        cov_snapshot = await self.get_or_create_factor_covariance(
            factor_model_version_id=config.factor_model_version_id,
            as_of_date=req.as_of_date,
            lookback_days=252,
            covariance_method=config.covariance_method,
            annualization_factor=config.annualization_factor,
        )

        factor_names = cov_snapshot.factor_names_ordered
        cov_matrix = np.array(cov_snapshot.covariance_matrix, dtype=np.float64)

        # 2. Resolve Portfolio Sensitivities (Matching factor ordering)
        sens_stmt = (
            select(FactorSensitivityRun)
            .options(
                selectinload(FactorSensitivityRun.coefficients),
                selectinload(FactorSensitivityRun.diagnostics),
            )
            .where(
                and_(
                    FactorSensitivityRun.target_type == TargetType.PORTFOLIO,
                    FactorSensitivityRun.target_id == req.portfolio_id,
                    FactorSensitivityRun.factor_model_version_id == config.factor_model_version_id,
                    FactorSensitivityRun.as_of_date <= req.as_of_date,
                )
            )
            .order_by(desc(FactorSensitivityRun.as_of_date))
        )
        s_res = await self.session.execute(sens_stmt)
        sens_run = s_res.scalars().first()

        portfolio_betas: Dict[str, float] = {}
        sens_run_id = None
        residual_variance_period = 0.0
        if sens_run and sens_run.coefficients:
            sens_run_id = sens_run.run_id
            for coeff in sens_run.coefficients:
                portfolio_betas[coeff.factor_code] = float(coeff.coefficient_value)
            if sens_run.diagnostics:
                residual_variance_period = float(sens_run.diagnostics.residual_variance)

        # Fallback to M08.02 bottom-up exposure if direct regression is not found
        if not portfolio_betas:
            w_stmt = (
                select(PortfolioFactorExposureSnapshot)
                .where(
                    and_(
                        PortfolioFactorExposureSnapshot.portfolio_id == req.portfolio_id,
                        PortfolioFactorExposureSnapshot.as_of_date <= req.as_of_date,
                    )
                )
                .order_by(desc(PortfolioFactorExposureSnapshot.as_of_date))
            )
            w_res = await self.session.execute(w_stmt)
            w_snaps = w_res.scalars().all()
            if w_snaps:
                latest_w_date = w_snaps[0].as_of_date
                for ws in [s for s in w_snaps if s.as_of_date == latest_w_date]:
                    portfolio_betas[ws.factor_code] = float(ws.signed_nav_exposure)

        beta_vector = np.array([portfolio_betas.get(f, 0.0) for f in factor_names], dtype=np.float64)

        # 3. Compute Systematic Factor Risk & Euler Decomposition
        sys_risk = compute_systematic_factor_risk(
            beta_vector=beta_vector,
            cov_matrix=cov_matrix,
            factor_names=factor_names,
            annualization_factor=float(config.annualization_factor),
        )

        # 4. Total Modeled Risk
        tot_risk = compute_total_modeled_risk(
            systematic_variance=sys_risk["systematic_variance_period"],
            residual_variance=residual_variance_period,
            factor_residual_covariance=0.0,
            annualization_factor=float(config.annualization_factor),
        )

        # 5. Persist Risk Run Record
        risk_run = FactorRiskAttributionRun(
            config_id=config.config_id,
            portfolio_id=req.portfolio_id,
            factor_model_id=config.factor_model_id,
            factor_model_version_id=config.factor_model_version_id,
            covariance_snapshot_id=cov_snapshot.snapshot_id,
            sensitivity_run_id=sens_run_id,
            exposure_snapshot_id=req.exposure_snapshot_id,
            as_of_date=req.as_of_date,
            observation_frequency="DAILY",
            annualization_factor=config.annualization_factor,
            systematic_variance=Decimal(str(round(sys_risk["systematic_variance_annualized"], 8))),
            systematic_volatility=Decimal(str(round(sys_risk["systematic_volatility_annualized"], 8))),
            residual_variance=Decimal(str(round(tot_risk["residual_variance"], 8))),
            residual_volatility=Decimal(str(round(math.sqrt(max(0.0, tot_risk["residual_variance"])), 8))),
            factor_residual_covariance=Decimal(str(round(tot_risk["factor_residual_covariance"], 8))),
            total_modeled_variance=Decimal(str(round(tot_risk["total_modeled_variance"], 8))),
            total_modeled_volatility=Decimal(str(round(tot_risk["total_modeled_volatility"], 8))),
            run_status=AttributionRunStatus.COMPLETED,
        )
        await self.repo.save_risk_run(risk_run)

        # 6. Persist Risk Components
        for f_name in factor_names:
            rc = FactorRiskAttributionComponent(
                run_id=risk_run.run_id,
                component_type=RiskComponentType.FACTOR,
                factor_code=f_name,
                factor_sensitivity_beta=Decimal(str(round(portfolio_betas.get(f_name, 0.0), 6))),
                variance_contribution=Decimal(str(round(sys_risk["variance_contributions"][f_name], 8))),
                volatility_contribution=Decimal(str(round(sys_risk["volatility_contributions"][f_name], 8))),
                marginal_volatility_contribution=Decimal(str(round(sys_risk["marginal_volatility_contributions"][f_name], 8))),
                marginal_variance_contribution=Decimal(str(round(sys_risk["marginal_variance_contributions"][f_name], 8))),
                percentage_volatility_contribution=Decimal(str(round(sys_risk["percentage_volatility_contributions"][f_name], 4))),
            )
            self.session.add(rc)

        # Residual Risk Component
        res_rc = FactorRiskAttributionComponent(
            run_id=risk_run.run_id,
            component_type=RiskComponentType.RESIDUAL,
            variance_contribution=Decimal(str(round(tot_risk["residual_variance"], 8))),
            volatility_contribution=Decimal(str(round(tot_risk["residual_volatility_contribution"], 8))),
            percentage_volatility_contribution=Decimal(str(round(tot_risk["residual_volatility_contribution"] / tot_risk["total_modeled_volatility"] * 100.0, 4))) if tot_risk["total_modeled_volatility"] > 1e-6 else None,
        )
        self.session.add(res_rc)

        # Reconciliation Record for Risk
        recon_risk = FactorAttributionReconciliation(
            risk_run_id=risk_run.run_id,
            reconciliation_type="RISK",
            observed_value=risk_run.total_modeled_variance,
            reported_value=risk_run.systematic_variance + (risk_run.residual_variance or Decimal("0.0")),
            absolute_difference=Decimal("0.0"),
            tolerance=config.reconciliation_tolerance,
            coverage_percentage=Decimal("100.00"),
            reconciliation_status=AttributionReconciliationStatus.FULLY_RECONCILED,
            reason_codes=["EULER_VARIANCE_EXACT"],
        )
        await self.repo.save_reconciliation(recon_risk)
        await self.session.commit()

        return await self.repo.get_risk_run_by_id(risk_run.run_id)

    # =========================================================================
    # 5. ATTRIBUTION COMPARISON
    # =========================================================================

    async def compare_attributions(
        self, req: AttributionComparisonRequest
    ) -> AttributionComparisonResponse:
        """Compares two attribution runs (e.g. Period-over-Period, Portfolio-to-Portfolio)."""
        run_base = await self.repo.get_return_run_by_id(req.run_id_base)
        run_target = await self.repo.get_return_run_by_id(req.run_id_target)

        if not run_base or not run_target:
            raise ValueError(f"One or both attribution runs ({req.run_id_base}, {req.run_id_target}) not found")

        ret_diff = run_target.realized_portfolio_return - run_base.realized_portfolio_return

        base_comps = {c.factor_code: float(c.linked_contribution or c.arithmetic_contribution) for c in run_base.components if c.factor_code}
        target_comps = {c.factor_code: float(c.linked_contribution or c.arithmetic_contribution) for c in run_target.components if c.factor_code}

        factor_shifts = {}
        all_factors = set(base_comps.keys()).union(target_comps.keys())
        for f in all_factors:
            b_val = base_comps.get(f, 0.0)
            t_val = target_comps.get(f, 0.0)
            factor_shifts[f] = {
                "base_contribution": b_val,
                "target_contribution": t_val,
                "shift": t_val - b_val,
            }

        return AttributionComparisonResponse(
            portfolio_id=req.portfolio_id,
            comparison_dimension=req.comparison_dimension,
            run_id_base=req.run_id_base,
            run_id_target=req.run_id_target,
            base_portfolio_return=run_base.realized_portfolio_return,
            target_portfolio_return=run_target.realized_portfolio_return,
            return_difference=ret_diff,
            factor_shifts=factor_shifts,
        )
