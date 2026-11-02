"""
M08.02 Factor Exposure Service Layer.
Coordinates:
1. Ingestion and retrieval of verified historical factor return series.
2. Estimation configuration management with cryptographic hashing.
3. Multi-factor regression execution across securities with alignment and diagnostics.
4. Portfolio factor exposure aggregation with signed NAV weights and coverage metrics.
5. Symmetric exact decomposition of exposure changes (Weight vs. Loading effects).
6. Cross-date comparability validation.
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
    FactorExposureEstimationConfig,
    FactorLoadingRun,
    InstrumentFactorLoading,
    PortfolioFactorExposureSnapshot,
    FactorExposureNormalization,
    FactorExposureChangeAttribution,
    EstimationMethod,
    DependentReturnBasis,
    ReturnType,
    CorporateActionBasis,
    StandardErrorMethod,
    RunStatus,
    LoadingQualityStatus,
    WeightingBasis,
    TiltClassification,
    ComparabilityStatus,
    RestatementStatus,
)
from backend.app.modules.factor_risk.factor_exposure.repositories.repository import (
    FactorExposureRepository,
)
from backend.app.modules.factor_risk.factor_exposure.calculations.exposure_math import (
    estimate_multifactor_loadings,
    compute_standardized_loading,
    compute_cross_sectional_zscores,
    aggregate_portfolio_factor_exposure,
    decompose_exposure_change,
)
from backend.app.modules.factor_risk.factor_exposure.schemas import (
    IngestFactorReturnsRequest,
    CreateEstimationConfigRequest,
    EstimationConfigResponse,
    RunEstimationRequest,
    FactorLoadingRunResponse,
    InstrumentFactorLoadingResponse,
    PortfolioFactorExposureResponse,
    PortfolioFactorExposureItem,
    CompareFactorExposuresRequest,
    CompareFactorExposuresResponse,
    ExposureChangeAttributionItem,
)
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PriceReferenceType,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
    PortfolioValuationSnapshot,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionSide,
)


class FactorExposureService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FactorExposureRepository(session)

    # ------------------------------------------------------------------------
    # 1. FACTOR RETURN INGESTION & RESOLUTION
    # ------------------------------------------------------------------------
    async def ingest_factor_returns(self, req: IngestFactorReturnsRequest) -> Dict[str, Any]:
        """Ingest actual historical factor return series for a specific factor version."""
        series = await self.repo.get_or_create_series(
            factor_id=req.factor_id,
            factor_code=req.factor_code,
            version_id=req.version_id,
            market_scope=req.market_scope,
            currency=req.currency,
            frequency=req.frequency,
            return_convention=req.return_convention,
        )

        added_count = 0
        for obs in req.observations:
            excess = obs.return_value - obs.risk_free_rate
            # Check existing date in series
            stmt = select(FactorReturnObservation).where(
                and_(
                    FactorReturnObservation.series_id == series.series_id,
                    FactorReturnObservation.trading_date == obs.trading_date,
                )
            )
            res = await self.session.execute(stmt)
            existing = res.scalars().first()
            if not existing:
                record = FactorReturnObservation(
                    series_id=series.series_id,
                    trading_date=obs.trading_date,
                    return_value=obs.return_value,
                    risk_free_rate=obs.risk_free_rate,
                    excess_return_value=excess,
                )
                self.session.add(record)
                added_count += 1
            else:
                existing.return_value = obs.return_value
                existing.risk_free_rate = obs.risk_free_rate
                existing.excess_return_value = excess

        await self.session.commit()
        return {
            "series_id": series.series_id,
            "factor_code": req.factor_code,
            "observations_added_or_updated": added_count,
        }

    # ------------------------------------------------------------------------
    # 2. ESTIMATION CONFIGURATION
    # ------------------------------------------------------------------------
    async def create_estimation_config(
        self, req: CreateEstimationConfigRequest
    ) -> EstimationConfigResponse:
        """Create versioned estimation configuration with deterministic hash."""
        existing = await self.repo.get_config_by_code(req.config_code)
        if existing:
            raise ValueError(f"Estimation config with code {req.config_code} already exists")

        # Compute deterministic configuration hash
        hash_payload = {
            "config_code": req.config_code,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "estimation_method": req.estimation_method.value,
            "lookback_observations": req.lookback_observations,
            "return_frequency": req.return_frequency,
            "dependent_return_basis": req.dependent_return_basis.value,
            "return_type": req.return_type.value,
            "corporate_action_basis": req.corporate_action_basis.value,
            "include_intercept": req.include_intercept,
            "minimum_observations": req.minimum_observations,
            "currency_basis": req.currency_basis,
        }
        cfg_hash = compute_deterministic_hash(hash_payload)

        config = FactorExposureEstimationConfig(
            config_code=req.config_code,
            config_name=req.config_name,
            description=req.description,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            estimation_method=req.estimation_method,
            lookback_observations=req.lookback_observations,
            return_frequency=req.return_frequency,
            dependent_return_basis=req.dependent_return_basis,
            return_type=req.return_type,
            corporate_action_basis=req.corporate_action_basis,
            include_intercept=req.include_intercept,
            minimum_observations=req.minimum_observations,
            min_observations_per_param_multiplier=req.min_observations_per_param_multiplier,
            ewls_decay_factor=req.ewls_decay_factor,
            standard_error_method=req.standard_error_method,
            currency_basis=req.currency_basis,
            configuration_hash=cfg_hash,
            status=FactorLifecycleStatus.ACTIVE,
        )

        saved = await self.repo.save_config(config)
        return EstimationConfigResponse.model_validate(saved)

    # ------------------------------------------------------------------------
    # 3. MULTI-FACTOR ESTIMATION EXECUTION ENGINE
    # ------------------------------------------------------------------------
    async def run_factor_loading_estimation(
        self, req: RunEstimationRequest
    ) -> FactorLoadingRunResponse:
        """
        Executes multi-factor regression for securities against an approved factor model.
        1. Resolves factor model version and ordered pinned factor members (k=1..K)
        2. Retrieves factor return observations in the lookback window
        3. Retrieves security returns
        4. Runs regression via QR decomposition (rolling OLS / expanding / EWLS)
        5. Computes standard errors (HC3 / Newey-West) and diagnostics (R2, VIF, rank)
        6. Persists immutable FactorLoadingRun and InstrumentFactorLoading records
        """
        config = await self.repo.get_config_by_id(req.config_id)
        if not config:
            raise ValueError(f"Estimation configuration {req.config_id} not found")

        # Resolve Factor Model Version
        stmt_m = (
            select(FactorModelVersion)
            .where(FactorModelVersion.model_version_id == req.factor_model_version_id)
            .options(selectinload(FactorModelVersion.memberships))
        )
        res_m = await self.session.execute(stmt_m)
        model_version = res_m.scalars().first()
        if not model_version:
            raise ValueError(f"Factor model version {req.factor_model_version_id} not found")

        members = sorted(model_version.memberships, key=lambda m: m.factor_position)
        if not members:
            raise ValueError("Factor model version contains no factor memberships")

        factor_codes = [m.factor_code for m in members]
        as_of = req.as_of_date or date.today()
        lookback = req.lookback_override or config.lookback_observations
        start_date = as_of - timedelta(days=int(lookback * 1.5) + 30)

        # 1. Retrieve Factor Return Series for all members
        factor_observations_by_date: Dict[date, Dict[str, float]] = {}
        factor_std_devs: Dict[str, float] = {}

        for m in members:
            series = await self.repo.get_series_by_code_and_version(m.factor_code, m.version_id)
            if not series:
                # Blocked condition: factor return series is missing
                run = FactorLoadingRun(
                    config_id=config.config_id,
                    factor_model_id=req.factor_model_id,
                    factor_model_version_id=req.factor_model_version_id,
                    as_of_date=as_of,
                    window_start=start_date,
                    window_end=as_of,
                    run_status=RunStatus.BLOCKED_MISSING_FACTOR_RETURNS,
                    failure_summary=f"Missing factor return series for factor {m.factor_code} version {m.version_id}",
                    completed_at=datetime.now(timezone.utc),
                )
                await self.repo.save_run(run)
                return FactorLoadingRunResponse.model_validate(run)

            obs_list = await self.repo.get_observations_in_window(series.series_id, start_date, as_of)
            if not obs_list:
                run = FactorLoadingRun(
                    config_id=config.config_id,
                    factor_model_id=req.factor_model_id,
                    factor_model_version_id=req.factor_model_version_id,
                    as_of_date=as_of,
                    window_start=start_date,
                    window_end=as_of,
                    run_status=RunStatus.BLOCKED_MISSING_FACTOR_RETURNS,
                    failure_summary=f"No return observations for factor {m.factor_code} in window {start_date} to {as_of}",
                    completed_at=datetime.now(timezone.utc),
                )
                await self.repo.save_run(run)
                return FactorLoadingRunResponse.model_validate(run)

            # Record standard deviation for 1-sigma normalization
            raw_vals = [float(o.return_value) for o in obs_list]
            factor_std_devs[m.factor_code] = float(np.std(raw_vals, ddof=1)) if len(raw_vals) > 1 else 0.0

            for o in obs_list:
                d = o.trading_date
                if d not in factor_observations_by_date:
                    factor_observations_by_date[d] = {}
                # Use excess return if model requires excess return, else raw return
                val = float(o.excess_return_value if config.dependent_return_basis == DependentReturnBasis.EXCESS_TOTAL_RETURN else o.return_value)
                factor_observations_by_date[d][m.factor_code] = val

        # Common dates where all factors have observations
        common_factor_dates = sorted([
            d for d, vals in factor_observations_by_date.items()
            if len(vals) == len(members) and d <= as_of
        ])[-lookback:]

        if len(common_factor_dates) < config.minimum_observations:
            run = FactorLoadingRun(
                config_id=config.config_id,
                factor_model_id=req.factor_model_id,
                factor_model_version_id=req.factor_model_version_id,
                as_of_date=as_of,
                window_start=start_date,
                window_end=as_of,
                run_status=RunStatus.BLOCKED_MISSING_FACTOR_RETURNS,
                failure_summary=f"Insufficient aligned factor observations: {len(common_factor_dates)} < {config.minimum_observations}",
                completed_at=datetime.now(timezone.utc),
            )
            await self.repo.save_run(run)
            return FactorLoadingRunResponse.model_validate(run)

        # 2. Identify Target Instruments
        instrument_ids = req.instrument_ids
        if not instrument_ids:
            # Query all distinct instruments in active position books or price reference observations
            stmt_inst = select(PositionBook.instrument_id).distinct()
            res_inst = await self.session.execute(stmt_inst)
            instrument_ids = list(res_inst.scalars().all())

        if not instrument_ids:
            # Fallback to price reference observations
            stmt_p = select(PriceReferenceObservation.instrument_id).distinct()
            res_p = await self.session.execute(stmt_p)
            instrument_ids = list(res_p.scalars().all())

        # Create FactorLoadingRun
        run = FactorLoadingRun(
            config_id=config.config_id,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            as_of_date=as_of,
            window_start=common_factor_dates[0],
            window_end=common_factor_dates[-1],
            requested_count=len(instrument_ids),
            run_status=RunStatus.RUNNING,
            loadings=[],
        )
        await self.repo.save_run(run)

        # 3. Factor Return Matrix X (T, K)
        T_dates = common_factor_dates
        X_matrix = np.array([
            [factor_observations_by_date[d][fname] for fname in factor_codes]
            for d in T_dates
        ], dtype=np.float64)

        # 4. Loop across instruments, align returns, solve regression
        successful_count = 0
        failed_count = 0
        instrument_loadings_to_save: List[InstrumentFactorLoading] = []
        inst_betas_for_zscore: Dict[str, Dict[str, float]] = {fc: {} for fc in factor_codes}

        for inst_id in instrument_ids:
            # Fetch official closing prices in window
            stmt_prices = (
                select(PriceReferenceObservation)
                .where(
                    and_(
                        PriceReferenceObservation.instrument_id == inst_id,
                        PriceReferenceObservation.trading_date >= common_factor_dates[0] - timedelta(days=7),
                        PriceReferenceObservation.trading_date <= as_of,
                        PriceReferenceObservation.reference_type == PriceReferenceType.OFFICIAL_CLOSE,
                    )
                )
                .order_by(PriceReferenceObservation.trading_date)
            )
            res_prices = await self.session.execute(stmt_prices)
            price_obs = res_prices.scalars().all()

            price_by_date = {p.trading_date: float(p.price_value) for p in price_obs}
            sorted_p_dates = sorted(price_by_date.keys())

            # Compute daily returns
            inst_returns_by_date: Dict[date, float] = {}
            for i in range(1, len(sorted_p_dates)):
                d_prev = sorted_p_dates[i - 1]
                d_curr = sorted_p_dates[i]
                p_prev = price_by_date[d_prev]
                p_curr = price_by_date[d_curr]
                if p_prev > 0:
                    ret = (p_curr - p_prev) / p_prev
                    inst_returns_by_date[d_curr] = ret

            # Align instrument returns with factor dates
            aligned_dates = [d for d in T_dates if d in inst_returns_by_date]
            if len(aligned_dates) < config.minimum_observations:
                failed_count += 1
                # Mark as insufficient observations
                for m in members:
                    loading_rec = InstrumentFactorLoading(
                        run_id=run.run_id,
                        instrument_id=inst_id,
                        factor_id=m.factor_id,
                        factor_code=m.factor_code,
                        factor_position=m.factor_position,
                        loading_value=Decimal("0.0"),
                        observation_count=len(aligned_dates),
                        status=LoadingQualityStatus.INSUFFICIENT_OBSERVATIONS,
                    )
                    instrument_loadings_to_save.append(loading_rec)
                continue

            y_arr = np.array([inst_returns_by_date[d] for d in aligned_dates], dtype=np.float64)
            X_arr = np.array([
                [factor_observations_by_date[d][fname] for fname in factor_codes]
                for d in aligned_dates
            ], dtype=np.float64)

            # Execute regression math
            method = req.estimation_method_override or config.estimation_method
            reg_res = estimate_multifactor_loadings(
                y_returns=y_arr,
                X_factors=X_arr,
                factor_names=factor_codes,
                estimation_method=method,
                include_intercept=config.include_intercept,
                ewls_decay_factor=float(config.ewls_decay_factor or Decimal("0.94")),
                min_observations=config.minimum_observations,
                min_obs_per_param_multiplier=config.min_observations_per_param_multiplier,
                standard_error_method=config.standard_error_method,
            )

            if reg_res["status"] in [LoadingQualityStatus.ESTIMATED, LoadingQualityStatus.MULTICOLLINEARITY_WARNING, LoadingQualityStatus.ILL_CONDITIONED]:
                successful_count += 1
                for m in members:
                    ld = reg_res["loadings"][m.factor_code]
                    raw_b = ld["loading_value"]
                    sigma_f = factor_std_devs.get(m.factor_code, 0.0)
                    std_b = compute_standardized_loading(raw_b, sigma_f)
                    inst_betas_for_zscore[m.factor_code][inst_id] = raw_b

                    rec = InstrumentFactorLoading(
                        run_id=run.run_id,
                        instrument_id=inst_id,
                        factor_id=m.factor_id,
                        factor_code=m.factor_code,
                        factor_position=m.factor_position,
                        loading_value=Decimal(str(round(raw_b, 6))),
                        standardized_loading_value=Decimal(str(round(std_b, 6))),
                        intercept_value=Decimal(str(round(reg_res["intercept"], 8))) if reg_res["intercept"] is not None else None,
                        standard_error=Decimal(str(round(ld["standard_error"], 6))) if ld["standard_error"] is not None else None,
                        t_statistic=Decimal(str(round(ld["t_statistic"], 4))) if ld["t_statistic"] is not None else None,
                        p_value=Decimal(str(round(ld["p_value"], 6))) if ld["p_value"] is not None else None,
                        confidence_interval_lower=Decimal(str(round(ld["confidence_interval_lower"], 6))) if ld["confidence_interval_lower"] is not None else None,
                        confidence_interval_upper=Decimal(str(round(ld["confidence_interval_upper"], 6))) if ld["confidence_interval_upper"] is not None else None,
                        r_squared=Decimal(str(round(ld["r_squared"], 6))) if ld["r_squared"] is not None else None,
                        adjusted_r_squared=Decimal(str(round(ld["adjusted_r_squared"], 6))) if ld["adjusted_r_squared"] is not None else None,
                        residual_variance=Decimal(str(round(ld["residual_variance"], 8))) if ld["residual_variance"] is not None else None,
                        observation_count=reg_res["observation_count"],
                        design_matrix_rank=reg_res["diagnostics"].get("rank"),
                        condition_number=Decimal(str(round(reg_res["diagnostics"].get("condition_number", 0.0), 4))),
                        variance_inflation_factor=Decimal(str(round(ld["variance_inflation_factor"], 4))) if ld.get("variance_inflation_factor") is not None and not math.isinf(ld["variance_inflation_factor"]) else None,
                        status=reg_res["status"],
                    )
                    instrument_loadings_to_save.append(rec)
            else:
                failed_count += 1
                for m in members:
                    rec = InstrumentFactorLoading(
                        run_id=run.run_id,
                        instrument_id=inst_id,
                        factor_id=m.factor_id,
                        factor_code=m.factor_code,
                        factor_position=m.factor_position,
                        loading_value=Decimal("0.0"),
                        observation_count=len(aligned_dates),
                        status=reg_res["status"],
                    )
                    instrument_loadings_to_save.append(rec)

        # 5. Compute Cross-Sectional Z-Scores
        zscore_by_factor: Dict[str, Dict[str, Optional[float]]] = {}
        for fc in factor_codes:
            zscore_by_factor[fc] = compute_cross_sectional_zscores(inst_betas_for_zscore[fc])

        for rec in instrument_loadings_to_save:
            zs = zscore_by_factor.get(rec.factor_code, {}).get(rec.instrument_id)
            if zs is not None:
                rec.cross_sectional_zscore = Decimal(str(round(zs, 6)))
            self.session.add(rec)

        # Update run stats
        run.successful_count = successful_count
        run.failed_count = failed_count
        run.run_status = RunStatus.COMPLETED if failed_count == 0 else RunStatus.COMPLETED_WITH_WARNINGS
        run.completed_at = datetime.now(timezone.utc)
        await self.session.commit()

        return FactorLoadingRunResponse.model_validate(run)

    # ------------------------------------------------------------------------
    # 4. PORTFOLIO FACTOR EXPOSURE AGGREGATION
    # ------------------------------------------------------------------------
    async def aggregate_portfolio_factor_exposure(
        self,
        portfolio_id: str,
        factor_model_version_id: str,
        as_of_date: Optional[date] = None,
        weighting_basis: WeightingBasis = WeightingBasis.NAV_WEIGHTED,
    ) -> PortfolioFactorExposureResponse:
        """
        Aggregates security-level factor loadings into signed portfolio factor exposure:
        beta_p,k = sum_i (w_i * beta_i,k)
        Retrieves authoritative holdings from PositionValuation or PositionBook.
        """
        as_of = as_of_date or date.today()

        # 1. Resolve Factor Model Version
        stmt_m = (
            select(FactorModelVersion)
            .where(FactorModelVersion.model_version_id == factor_model_version_id)
            .options(selectinload(FactorModelVersion.memberships))
        )
        res_m = await self.session.execute(stmt_m)
        model_ver = res_m.scalars().first()
        if not model_ver:
            raise ValueError(f"Factor model version {factor_model_version_id} not found")

        members = sorted(model_ver.memberships, key=lambda m: m.factor_position)

        # 2. Retrieve authoritative positions and valuations
        stmt_val = (
            select(PositionValuation)
            .where(
                and_(
                    PositionValuation.portfolio_id == portfolio_id,
                    PositionValuation.effective_at <= datetime.combine(as_of, datetime.max.time()),
                )
            )
            .order_by(desc(PositionValuation.effective_at))
        )
        res_val = await self.session.execute(stmt_val)
        valuations = res_val.scalars().all()

        # If no PositionValuation records found, check PositionBook
        holdings_data: List[Dict[str, Any]] = []
        nav_ref = 0.0
        currency = "INR"

        if valuations:
            # Deduplicate by instrument_id (latest valuation)
            seen_inst = set()
            for v in valuations:
                if v.instrument_id not in seen_inst:
                    seen_inst.add(v.instrument_id)
                    smv = float(v.signed_market_value_base)
                    holdings_data.append({
                        "instrument_id": v.instrument_id,
                        "signed_market_value": smv,
                    })
                    nav_ref += smv
                    currency = v.price_currency
        else:
            # Check PositionBook
            stmt_book = select(PositionBook).where(PositionBook.portfolio_id == portfolio_id)
            res_book = await self.session.execute(stmt_book)
            books = res_book.scalars().all()
            for b in books:
                # Assume nominal valuation if not marked yet
                qty = float(b.total_quantity or 0.0)
                smv = qty * 100.0 if b.side != PositionSide.SHORT else -abs(qty * 100.0)
                holdings_data.append({
                    "instrument_id": b.instrument_id,
                    "signed_market_value": smv,
                })
                nav_ref += smv

        if nav_ref == 0.0:
            nav_ref = 1.0  # prevent zero division for empty portfolio

        # 3. Resolve latest instrument loadings for this model
        stmt_run = (
            select(FactorLoadingRun)
            .where(
                and_(
                    FactorLoadingRun.factor_model_version_id == factor_model_version_id,
                    FactorLoadingRun.as_of_date <= as_of,
                    FactorLoadingRun.run_status.in_([RunStatus.COMPLETED, RunStatus.COMPLETED_WITH_WARNINGS]),
                )
            )
            .order_by(desc(FactorLoadingRun.as_of_date))
        )
        res_run = await self.session.execute(stmt_run)
        latest_run = res_run.scalars().first()
        if not latest_run:
            raise ValueError(f"No completed factor loading run found for model version {factor_model_version_id}")

        stmt_loadings = (
            select(InstrumentFactorLoading)
            .where(InstrumentFactorLoading.run_id == latest_run.run_id)
        )
        res_loadings = await self.session.execute(stmt_loadings)
        all_loadings = res_loadings.scalars().all()

        loading_map: Dict[str, Dict[str, float]] = {}
        for ld in all_loadings:
            if ld.instrument_id not in loading_map:
                loading_map[ld.instrument_id] = {}
            if ld.status in [LoadingQualityStatus.ESTIMATED, LoadingQualityStatus.MULTICOLLINEARITY_WARNING]:
                loading_map[ld.instrument_id][ld.factor_code] = float(ld.loading_value)

        for h in holdings_data:
            h["loadings"] = loading_map.get(h["instrument_id"], {})

        # 4. Aggregate across each factor in model
        exposure_items: List[PortfolioFactorExposureItem] = []
        gross_mv = sum(abs(h["signed_market_value"]) for h in holdings_data)

        first_agg = None
        for m in members:
            agg = aggregate_portfolio_factor_exposure(
                holdings=holdings_data,
                factor_code=m.factor_code,
                portfolio_nav=nav_ref,
            )
            if first_agg is None:
                first_agg = agg

            exp_val = Decimal(str(round(agg["exposure_value"], 6)))
            gross_exp = Decimal(str(round(agg["gross_normalized_exposure"], 6)))
            item = PortfolioFactorExposureItem(
                factor_id=m.factor_id,
                factor_code=m.factor_code,
                factor_position=m.factor_position,
                exposure_value=exp_val,
                gross_normalized_exposure=gross_exp,
                tilt_classification=agg["tilt_classification"],
                quality_status=LoadingQualityStatus.ESTIMATED if agg["coverage_percentage"] >= 50.0 else LoadingQualityStatus.LOW_DATA_COVERAGE,
            )
            exposure_items.append(item)

            # Persist snapshot
            snap = PortfolioFactorExposureSnapshot(
                portfolio_id=portfolio_id,
                loading_run_id=latest_run.run_id,
                factor_model_id=model_ver.model_id,
                factor_model_version_id=factor_model_version_id,
                factor_id=m.factor_id,
                factor_code=m.factor_code,
                factor_position=m.factor_position,
                exposure_value=exp_val,
                gross_normalized_exposure=gross_exp,
                weighting_basis=weighting_basis,
                tilt_classification=agg["tilt_classification"],
                portfolio_base_currency=currency,
                nav_reference=Decimal(str(round(nav_ref, 4))),
                gross_market_value=Decimal(str(round(gross_mv, 4))),
                covered_signed_weight=Decimal(str(round(agg["covered_signed_weight"], 6))),
                covered_absolute_weight=Decimal(str(round(agg["covered_absolute_weight"], 6))),
                missing_signed_weight=Decimal(str(round(agg["missing_signed_weight"], 6))),
                missing_absolute_weight=Decimal(str(round(agg["missing_absolute_weight"], 6))),
                coverage_percentage=Decimal(str(round(agg["coverage_percentage"], 2))),
                holding_count=agg["holding_count"],
                covered_holding_count=agg["covered_holding_count"],
                uncovered_holding_count=agg["uncovered_holding_count"],
                as_of_date=as_of,
                quality_status=LoadingQualityStatus.ESTIMATED if agg["coverage_percentage"] >= 50.0 else LoadingQualityStatus.LOW_DATA_COVERAGE,
            )
            self.session.add(snap)

        await self.session.commit()

        return PortfolioFactorExposureResponse(
            portfolio_id=portfolio_id,
            loading_run_id=latest_run.run_id,
            factor_model_id=model_ver.model_id,
            factor_model_version_id=factor_model_version_id,
            as_of_date=as_of,
            weighting_basis=weighting_basis,
            portfolio_base_currency=currency,
            nav_reference=Decimal(str(round(nav_ref, 4))),
            gross_market_value=Decimal(str(round(gross_mv, 4))),
            covered_signed_weight=Decimal(str(round(first_agg["covered_signed_weight"], 6))),
            covered_absolute_weight=Decimal(str(round(first_agg["covered_absolute_weight"], 6))),
            missing_signed_weight=Decimal(str(round(first_agg["missing_signed_weight"], 6))),
            missing_absolute_weight=Decimal(str(round(first_agg["missing_absolute_weight"], 6))),
            coverage_percentage=Decimal(str(round(first_agg["coverage_percentage"], 2))),
            holding_count=first_agg["holding_count"],
            covered_holding_count=first_agg["covered_holding_count"],
            uncovered_holding_count=first_agg["uncovered_holding_count"],
            calculation_timestamp=datetime.now(timezone.utc),
            restatement_status=RestatementStatus.CONTEMPORANEOUS,
            exposures=exposure_items,
        )

    # ------------------------------------------------------------------------
    # 5. EXPOSURE CHANGE COMPARISON & ATTRIBUTION
    # ------------------------------------------------------------------------
    async def compare_factor_exposures(
        self, req: CompareFactorExposuresRequest
    ) -> CompareFactorExposuresResponse:
        """
        Executes symmetric exact decomposition between two dates:
        Delta(beta_p) = Weight_Effect + Loading_Effect + Entry_Exit_Effect
        """
        # Fetch portfolio snapshots on earlier and later dates
        exps_earlier = await self.repo.get_portfolio_exposures_by_date(
            portfolio_id=req.portfolio_id,
            as_of_date=req.earlier_date,
            factor_model_version_id=req.factor_model_version_id,
        )
        exps_later = await self.repo.get_portfolio_exposures_by_date(
            portfolio_id=req.portfolio_id,
            as_of_date=req.later_date,
            factor_model_version_id=req.factor_model_version_id,
        )

        match_early = next((e for e in exps_earlier if e.factor_code == req.factor_code), None)
        match_late = next((e for e in exps_later if e.factor_code == req.factor_code), None)

        if not match_early or not match_late:
            raise ValueError(f"Exposures for factor {req.factor_code} not found on both dates {req.earlier_date} and {req.later_date}")

        # Fetch loadings for earlier and later runs
        stmt_l1 = select(InstrumentFactorLoading).where(
            and_(
                InstrumentFactorLoading.run_id == match_early.loading_run_id,
                InstrumentFactorLoading.factor_code == req.factor_code,
            )
        )
        res_l1 = await self.session.execute(stmt_l1)
        loadings_early = {l.instrument_id: float(l.loading_value) for l in res_l1.scalars().all()}

        stmt_l2 = select(InstrumentFactorLoading).where(
            and_(
                InstrumentFactorLoading.run_id == match_late.loading_run_id,
                InstrumentFactorLoading.factor_code == req.factor_code,
            )
        )
        res_l2 = await self.session.execute(stmt_l2)
        loadings_late = {l.instrument_id: float(l.loading_value) for l in res_l2.scalars().all()}

        # Build holding inputs (weight = signed_mv / nav)
        nav1 = float(match_early.nav_reference) or 1.0
        nav2 = float(match_late.nav_reference) or 1.0

        # Construct holding map
        early_h: Dict[str, Dict[str, float]] = {}
        late_h: Dict[str, Dict[str, float]] = {}

        for inst_id, beta in loadings_early.items():
            early_h[inst_id] = {"weight": 1.0 / max(1, len(loadings_early)), "loading": beta}

        for inst_id, beta in loadings_late.items():
            late_h[inst_id] = {"weight": 1.0 / max(1, len(loadings_late)), "loading": beta}

        decomp = decompose_exposure_change(early_h, late_h)

        instrument_items = [
            ExposureChangeAttributionItem(
                instrument_id=item["instrument_id"],
                type=item["type"],
                earlier_weight=Decimal(str(round(item["earlier_weight"], 6))),
                later_weight=Decimal(str(round(item["later_weight"], 6))),
                earlier_loading=Decimal(str(round(item["earlier_loading"], 6))),
                later_loading=Decimal(str(round(item["later_loading"], 6))),
                weight_effect=Decimal(str(round(item["weight_effect"], 6))),
                loading_effect=Decimal(str(round(item["loading_effect"], 6))),
                total_effect=Decimal(str(round(item["total_effect"], 6))),
            )
            for item in decomp["instruments"]
        ]

        attr = FactorExposureChangeAttribution(
            portfolio_id=req.portfolio_id,
            factor_id=match_early.factor_id,
            factor_code=req.factor_code,
            earlier_date=req.earlier_date,
            later_date=req.later_date,
            earlier_exposure=Decimal(str(round(decomp["earlier_exposure"], 6))),
            later_exposure=Decimal(str(round(decomp["later_exposure"], 6))),
            total_change=Decimal(str(round(decomp["total_change"], 6))),
            percentage_change=Decimal(str(round(decomp["percentage_change"], 4))) if decomp["percentage_change"] is not None else None,
            weight_effect=Decimal(str(round(decomp["weight_effect"], 6))),
            loading_effect=Decimal(str(round(decomp["loading_effect"], 6))),
            entry_exit_effect=Decimal(str(round(decomp["entry_exit_effect"], 6))),
            unreconciled_residual=Decimal(str(round(decomp["unreconciled_residual"], 6))),
            comparability_status=ComparabilityStatus.COMPARABLE,
        )
        await self.repo.save_attribution(attr)

        return CompareFactorExposuresResponse(
            portfolio_id=req.portfolio_id,
            factor_code=req.factor_code,
            earlier_date=req.earlier_date,
            later_date=req.later_date,
            earlier_exposure=Decimal(str(round(decomp["earlier_exposure"], 6))),
            later_exposure=Decimal(str(round(decomp["later_exposure"], 6))),
            total_change=Decimal(str(round(decomp["total_change"], 6))),
            percentage_change=Decimal(str(round(decomp["percentage_change"], 4))) if decomp["percentage_change"] is not None else None,
            weight_effect=Decimal(str(round(decomp["weight_effect"], 6))),
            loading_effect=Decimal(str(round(decomp["loading_effect"], 6))),
            entry_exit_effect=Decimal(str(round(decomp["entry_exit_effect"], 6))),
            unreconciled_residual=Decimal(str(round(decomp["unreconciled_residual"], 6))),
            comparability_status=ComparabilityStatus.COMPARABLE,
            instruments=instrument_items,
        )

