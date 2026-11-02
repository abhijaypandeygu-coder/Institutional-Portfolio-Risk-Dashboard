"""
M07.05 Correlation Analysis Service Layer.
Integrates with M07.01 Historical Volatility return series and M05.07 Portfolio History.
Orchestrates pairwise correlation, rolling time series, matrix calculations with PSD diagnostics,
and regime event monitoring.
"""
from datetime import datetime, date, timezone
from decimal import Decimal
import time
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.market_risk.correlation.models import (
    CorrelationConfiguration,
    CorrelationCalculationRun,
    CorrelationPairResult,
    CorrelationMatrixMetadata,
    CorrelationMatrixTransformation,
    CorrelationRegimeEvent,
    CorrelationEstimator,
    CorrelationAlignmentPolicy,
    CorrelationMissingDataPolicy,
    CorrelationScopeType,
    PSDStatus,
    CorrelationRegimeEventType,
    CorrelationRegimeStatus,
)
from backend.app.modules.market_risk.correlation.schemas import (
    PairwiseCorrelationRequest,
    PairwiseCorrelationResponse,
    MatrixCorrelationRequest,
    CorrelationMatrixResponse,
    RollingCorrelationRequest,
    RollingCorrelationResponse,
    RollingCorrelationPoint,
    CorrelationRankingsResponse,
    MultiHorizonCorrelationResponse,
)
from backend.app.modules.market_risk.correlation.calculations.correlation_math import (
    align_two_series,
    calculate_pairwise_correlation,
    compute_correlation_matrix,
    repair_psd_matrix,
    calculate_rolling_correlation,
)
from backend.app.modules.market_risk.correlation.repositories.repository import CorrelationRepository
from backend.app.modules.market_risk.historical_volatility.services.service import HistoricalVolatilityService
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.portfolio_management.position_management.models import PositionBook


from backend.app.modules.market_risk.historical_volatility.models import (
    VolatilityScopeType,
    PriceSourceType,
    ReturnType,
)
from backend.app.modules.market_risk.historical_volatility.calculations.volatility_math import (
    calculate_return,
)


class CorrelationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CorrelationRepository(session)
        self.vol_service = HistoricalVolatilityService(session)

    async def _resolve_instrument_symbol(self, instrument_id: str) -> str:
        stmt = select(Instrument.short_name).where(Instrument.instrument_id == instrument_id)
        res = await self.session.execute(stmt)
        sym = res.scalar_one_or_none()
        return sym if sym else instrument_id[:8]

    async def _get_portfolio_instruments(self, portfolio_id: str) -> List[str]:
        stmt = (
            select(PositionBook.instrument_id)
            .where(PositionBook.portfolio_id == portfolio_id)
            .distinct()
        )
        res = await self.session.execute(stmt)
        return [str(x) for x in res.scalars().all()]

    async def _resolve_returns_for_asset(
        self,
        asset_id: str,
        as_of: Optional[date] = None,
    ) -> List[Tuple[date, Decimal]]:
        """
        Fetch historical price series from authoritative M07.01 service and compute daily log returns.
        """
        # Fetch price series via M07.01 using VolatilityScopeType and PriceSourceType
        prices = await self.vol_service.resolve_price_series(
            scope_type=VolatilityScopeType.INSTRUMENT,
            instrument_id=asset_id,
            portfolio_id=None,
            price_source=PriceSourceType.OFFICIAL_CLOSE,
            as_of=as_of,
        )
        if len(prices) < 2:
            return []

        returns = []
        for i in range(1, len(prices)):
            p_prev = prices[i - 1][1]
            p_curr = prices[i][1]
            d_curr = prices[i][0]
            ret = calculate_return(p_prev, p_curr, return_type=ReturnType.LOGARITHMIC)
            d_out = d_curr.date() if isinstance(d_curr, datetime) else d_curr
            returns.append((d_out, ret))

        return returns

    async def calculate_pairwise(
        self, request: PairwiseCorrelationRequest
    ) -> PairwiseCorrelationResponse:
        start_time = time.perf_counter()
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)

        # Canonical ordering
        asset_a, asset_b = (
            (request.asset_a_id, request.asset_b_id)
            if request.asset_a_id <= request.asset_b_id
            else (request.asset_b_id, request.asset_a_id)
        )

        sym_a = await self._resolve_instrument_symbol(asset_a)
        sym_b = await self._resolve_instrument_symbol(asset_b)

        returns_a = await self._resolve_returns_for_asset(asset_a, request.as_of)
        returns_b = await self._resolve_returns_for_asset(asset_b, request.as_of)

        # Filter to lookback window
        if request.lookback_days and len(returns_a) > 0 and len(returns_b) > 0:
            returns_a = returns_a[-request.lookback_days:]
            returns_b = returns_b[-request.lookback_days:]

        aligned_dates, x, y = align_two_series(
            returns_a,
            returns_b,
            alignment_policy=request.alignment_policy,
            missing_data_policy=request.missing_data_policy,
        )

        calc = calculate_pairwise_correlation(x, y, estimator=request.estimator)

        # Record Calculation Run and Pair Result
        run_code = f"CORR_RUN_{uuid4().hex[:12].upper()}"
        run = CorrelationCalculationRun(
            run_code=run_code,
            scope_type=CorrelationScopeType.INSTRUMENT_PAIR,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of_dt,
            lookback_window_days=request.lookback_days,
            estimator_used=request.estimator,
            universe_size=2,
            pairs_calculated=1,
            execution_time_ms=int((time.perf_counter() - start_time) * 1000),
        )
        await self.repo.create_calculation_run(run)

        pair_record = CorrelationPairResult(
            run_id=run.id,
            portfolio_id=request.portfolio_id,
            asset_a_id=asset_a,
            asset_b_id=asset_b,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            estimator=request.estimator,
            correlation_coefficient=calc["correlation"],
            sample_size=calc["sample_size"],
            p_value=calc["p_value"],
            t_statistic=calc["t_statistic"],
            std_error=calc["std_error"],
            ci_lower_95=calc["ci_lower_95"],
            ci_upper_95=calc["ci_upper_95"],
            covariance=calc["covariance"],
            volatility_a=calc["volatility_a"],
            volatility_b=calc["volatility_b"],
        )
        await self.repo.save_pair_results([pair_record])

        # Evaluate regime event
        await self._check_regime_event_for_pair(
            portfolio_id=request.portfolio_id,
            asset_a_id=asset_a,
            asset_b_id=asset_b,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            correlation=calc["correlation"],
            detected_at=as_of_dt,
        )

        return PairwiseCorrelationResponse(
            asset_a_id=asset_a,
            asset_b_id=asset_b,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            estimator=request.estimator,
            correlation_coefficient=Decimal(str(round(calc["correlation"], 6))),
            sample_size=calc["sample_size"],
            p_value=Decimal(str(round(calc["p_value"], 6))) if calc["p_value"] is not None else None,
            t_statistic=Decimal(str(round(calc["t_statistic"], 4))) if calc["t_statistic"] is not None else None,
            std_error=Decimal(str(round(calc["std_error"], 6))) if calc["std_error"] is not None else None,
            ci_lower_95=Decimal(str(round(calc["ci_lower_95"], 6))) if calc["ci_lower_95"] is not None else None,
            ci_upper_95=Decimal(str(round(calc["ci_upper_95"], 6))) if calc["ci_upper_95"] is not None else None,
            covariance=Decimal(str(round(calc["covariance"], 8))) if calc["covariance"] is not None else None,
            volatility_a=Decimal(str(round(calc["volatility_a"], 6))) if calc["volatility_a"] is not None else None,
            volatility_b=Decimal(str(round(calc["volatility_b"], 6))) if calc["volatility_b"] is not None else None,
            alignment_applied=request.alignment_policy.value,
            missing_data_strategy=request.missing_data_policy.value,
        )

    async def calculate_matrix(
        self, request: MatrixCorrelationRequest
    ) -> CorrelationMatrixResponse:
        start_time = time.perf_counter()
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)

        asset_ids = request.asset_ids or []
        if request.portfolio_id and not asset_ids:
            asset_ids = await self._get_portfolio_instruments(request.portfolio_id)

        asset_ids = sorted(list(set(asset_ids)))
        if not asset_ids:
            raise ValueError("No assets provided or found in portfolio.")

        symbols = [await self._resolve_instrument_symbol(aid) for aid in asset_ids]

        returns_dict: Dict[str, List[Tuple[date, Decimal]]] = {}
        for aid in asset_ids:
            rets = await self._resolve_returns_for_asset(aid, request.as_of)
            if request.lookback_days and len(rets) > 0:
                rets = rets[-request.lookback_days:]
            returns_dict[aid] = rets

        raw_matrix, diag = compute_correlation_matrix(
            returns_dict=returns_dict,
            asset_order=asset_ids,
            estimator=request.estimator,
        )

        matrix_code = f"CORR_MAT_{uuid4().hex[:12].upper()}"
        matrix_meta = CorrelationMatrixMetadata(
            matrix_code=matrix_code,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            estimator=request.estimator,
            dimension=len(asset_ids),
            asset_ids=asset_ids,
            asset_symbols=symbols,
            raw_matrix_data=raw_matrix.tolist(),
            psd_status=diag["psd_status"],
            min_eigenvalue=diag["min_eigenvalue"],
            max_eigenvalue=diag["max_eigenvalue"],
            condition_number=diag["condition_number"],
            negative_eigenvalues_count=diag["negative_eigenvalues_count"],
            completeness_ratio=diag["completeness_ratio"],
            average_correlation=diag["average_correlation"],
            median_correlation=diag["median_correlation"],
        )
        saved_matrix = await self.repo.save_matrix(matrix_meta)

        # Also persist pairwise records for portfolio ranking lookups
        run_code = f"CORR_RUN_MAT_{uuid4().hex[:10].upper()}"
        run = CorrelationCalculationRun(
            run_code=run_code,
            scope_type=CorrelationScopeType.PORTFOLIO_CONSTITUENTS if request.portfolio_id else CorrelationScopeType.CUSTOM_UNIVERSE,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of_dt,
            lookback_window_days=request.lookback_days,
            estimator_used=request.estimator,
            universe_size=len(asset_ids),
            pairs_calculated=(len(asset_ids) * (len(asset_ids) - 1)) // 2,
            execution_time_ms=int((time.perf_counter() - start_time) * 1000),
        )
        await self.repo.create_calculation_run(run)

        pair_records = []
        n = len(asset_ids)
        for i in range(n):
            for j in range(i + 1, n):
                pair_records.append(
                    CorrelationPairResult(
                        run_id=run.id,
                        portfolio_id=request.portfolio_id,
                        asset_a_id=asset_ids[i],
                        asset_b_id=asset_ids[j],
                        asset_a_symbol=symbols[i],
                        asset_b_symbol=symbols[j],
                        as_of_date=as_of_dt,
                        lookback_days=request.lookback_days,
                        estimator=request.estimator,
                        correlation_coefficient=float(raw_matrix[i, j]),
                        sample_size=request.lookback_days,
                    )
                )
        if pair_records:
            await self.repo.save_pair_results(pair_records)

        # Transformed matrix if requested or if repair_psd is True
        transformed_mat_list = None
        transform_info_dict = None
        if request.repair_psd and diag["psd_status"] == PSDStatus.NON_PSD:
            repaired_mat, t_info = repair_psd_matrix(raw_matrix, method=request.transformation_method or "EIGENVALUE_CLIPPING")
            transformation = CorrelationMatrixTransformation(
                original_matrix_id=saved_matrix.id,
                transformation_method=request.transformation_method or "EIGENVALUE_CLIPPING",
                transformed_matrix_data=repaired_mat.tolist(),
                min_eigenvalue_after=t_info["min_eigenvalue_after"],
                frobenius_distance=t_info["frobenius_distance"],
                max_absolute_element_diff=t_info["max_absolute_element_diff"],
            )
            await self.repo.save_transformation(transformation)
            transformed_mat_list = [[Decimal(str(round(v, 6))) for v in row] for row in repaired_mat]
            transform_info_dict = t_info

        matrix_decimals = [[Decimal(str(round(v, 6))) for v in row] for row in raw_matrix]

        return CorrelationMatrixResponse(
            matrix_id=saved_matrix.id,
            matrix_code=saved_matrix.matrix_code,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            estimator=request.estimator,
            dimension=len(asset_ids),
            asset_ids=asset_ids,
            asset_symbols=symbols,
            matrix=matrix_decimals,
            psd_status=diag["psd_status"],
            min_eigenvalue=Decimal(str(round(diag["min_eigenvalue"], 6))),
            max_eigenvalue=Decimal(str(round(diag["max_eigenvalue"], 6))),
            condition_number=Decimal(str(round(diag["condition_number"], 4))) if diag["condition_number"] else None,
            negative_eigenvalues_count=diag["negative_eigenvalues_count"],
            completeness_ratio=Decimal(str(round(diag["completeness_ratio"], 4))),
            average_correlation=Decimal(str(round(diag["average_correlation"], 6))),
            median_correlation=Decimal(str(round(diag["median_correlation"], 6))),
            transformed_matrix=transformed_mat_list,
            transformation_info=transform_info_dict,
        )

    async def calculate_rolling(
        self, request: RollingCorrelationRequest
    ) -> RollingCorrelationResponse:
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)

        asset_a, asset_b = (
            (request.asset_a_id, request.asset_b_id)
            if request.asset_a_id <= request.asset_b_id
            else (request.asset_b_id, request.asset_a_id)
        )
        sym_a = await self._resolve_instrument_symbol(asset_a)
        sym_b = await self._resolve_instrument_symbol(asset_b)

        returns_a = await self._resolve_returns_for_asset(asset_a, request.as_of)
        returns_b = await self._resolve_returns_for_asset(asset_b, request.as_of)

        if len(returns_a) > request.history_lookback_days:
            returns_a = returns_a[-request.history_lookback_days:]
        if len(returns_b) > request.history_lookback_days:
            returns_b = returns_b[-request.history_lookback_days:]

        aligned_dates, x, y = align_two_series(returns_a, returns_b, alignment_policy=request.alignment_policy)

        rolling_raw = calculate_rolling_correlation(
            aligned_dates=aligned_dates,
            returns_a=x,
            returns_b=y,
            window_days=request.window_days,
            estimator=request.estimator,
        )

        full_calc = calculate_pairwise_correlation(x, y, estimator=request.estimator)
        baseline_rho = Decimal(str(round(full_calc["correlation"], 6)))

        series_points = [
            RollingCorrelationPoint(
                observation_date=item["observation_date"],
                correlation=Decimal(str(round(item["correlation"], 6))),
                delta_rho=Decimal(str(round(item["delta_rho"], 6))) if item["delta_rho"] is not None else None,
                baseline_deviation=Decimal(str(round(item["baseline_deviation"], 6))) if item["baseline_deviation"] is not None else None,
                sample_size=item["sample_size"],
            )
            for item in rolling_raw
        ]

        return RollingCorrelationResponse(
            asset_a_id=asset_a,
            asset_b_id=asset_b,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            window_days=request.window_days,
            history_lookback_days=request.history_lookback_days,
            estimator=request.estimator,
            baseline_correlation=baseline_rho,
            series=series_points,
        )

    async def get_rankings(
        self,
        portfolio_id: str,
        lookback_days: int = 60,
        as_of: Optional[date] = None,
        top_n: int = 5,
    ) -> CorrelationRankingsResponse:
        as_of_dt = datetime.combine(as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)
        pairs = await self.repo.list_pairs_for_portfolio(portfolio_id, as_of_dt, lookback_days)

        # If not found for exact date, generate matrix for portfolio
        if not pairs:
            await self.calculate_matrix(
                MatrixCorrelationRequest(
                    portfolio_id=portfolio_id,
                    lookback_days=lookback_days,
                    as_of=as_of,
                )
            )
            pairs = await self.repo.list_pairs_for_portfolio(portfolio_id, as_of_dt, lookback_days)

        # Convert to schemas
        mapped_pairs = [
            PairwiseCorrelationResponse(
                asset_a_id=p.asset_a_id,
                asset_b_id=p.asset_b_id,
                asset_a_symbol=p.asset_a_symbol,
                asset_b_symbol=p.asset_b_symbol,
                as_of_date=p.as_of_date,
                lookback_days=p.lookback_days,
                estimator=p.estimator,
                correlation_coefficient=Decimal(str(round(p.correlation_coefficient, 6))),
                sample_size=p.sample_size,
                p_value=Decimal(str(round(p.p_value, 6))) if p.p_value is not None else None,
                t_statistic=Decimal(str(round(p.t_statistic, 4))) if p.t_statistic is not None else None,
                std_error=Decimal(str(round(p.std_error, 6))) if p.std_error is not None else None,
                ci_lower_95=Decimal(str(round(p.ci_lower_95, 6))) if p.ci_lower_95 is not None else None,
                ci_upper_95=Decimal(str(round(p.ci_upper_95, 6))) if p.ci_upper_95 is not None else None,
                covariance=Decimal(str(round(p.covariance, 8))) if p.covariance is not None else None,
                volatility_a=Decimal(str(round(p.volatility_a, 6))) if p.volatility_a is not None else None,
                volatility_b=Decimal(str(round(p.volatility_b, 6))) if p.volatility_b is not None else None,
                alignment_applied="COMMON_SESSION_DATE",
                missing_data_strategy="STRICT_PAIRWISE_COMPLETE",
            )
            for p in pairs
        ]

        # Sortings
        sorted_pos = sorted(mapped_pairs, key=lambda x: x.correlation_coefficient, reverse=True)
        sorted_neg = sorted(mapped_pairs, key=lambda x: x.correlation_coefficient)
        sorted_stable = sorted(mapped_pairs, key=lambda x: abs(x.correlation_coefficient))

        return CorrelationRankingsResponse(
            portfolio_id=portfolio_id,
            as_of_date=as_of_dt,
            lookback_days=lookback_days,
            top_positive_correlations=sorted_pos[:top_n],
            top_negative_correlations=sorted_neg[:top_n],
            most_stable_correlations=sorted_stable[:top_n],
        )

    async def get_multi_horizon(
        self,
        asset_a_id: str,
        asset_b_id: str,
        as_of: Optional[date] = None,
    ) -> MultiHorizonCorrelationResponse:
        as_of_dt = datetime.combine(as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)
        sym_a = await self._resolve_instrument_symbol(asset_a_id)
        sym_b = await self._resolve_instrument_symbol(asset_b_id)

        horizons = {"20D": 20, "60D": 60, "120D": 120, "252D": 252}
        results: Dict[str, Optional[Decimal]] = {}

        returns_a = await self._resolve_returns_for_asset(asset_a_id, as_of)
        returns_b = await self._resolve_returns_for_asset(asset_b_id, as_of)

        for label, days in horizons.items():
            sub_a = returns_a[-days:] if len(returns_a) >= days else returns_a
            sub_b = returns_b[-days:] if len(returns_b) >= days else returns_b
            _, x, y = align_two_series(sub_a, sub_b)
            c = calculate_pairwise_correlation(x, y)
            results[label] = Decimal(str(round(c["correlation"], 6))) if c["is_valid"] else None

        return MultiHorizonCorrelationResponse(
            asset_a_id=asset_a_id,
            asset_b_id=asset_b_id,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            as_of_date=as_of_dt,
            horizons=results,
        )

    async def _check_regime_event_for_pair(
        self,
        portfolio_id: Optional[str],
        asset_a_id: str,
        asset_b_id: str,
        asset_a_symbol: str,
        asset_b_symbol: str,
        correlation: float,
        detected_at: datetime,
    ) -> None:
        events = []
        if correlation >= 0.70:
            events.append(
                CorrelationRegimeEvent(
                    event_code=f"REGIME_HI_POS_{uuid4().hex[:10].upper()}",
                    event_type=CorrelationRegimeEventType.HIGH_POSITIVE_CORRELATION,
                    portfolio_id=portfolio_id,
                    asset_a_id=asset_a_id,
                    asset_b_id=asset_b_id,
                    asset_a_symbol=asset_a_symbol,
                    asset_b_symbol=asset_b_symbol,
                    detected_at=detected_at,
                    status=CorrelationRegimeStatus.ACTIVE,
                    current_correlation=correlation,
                    threshold_value=0.70,
                    consecutive_periods_observed=1,
                    notes="Elevated positive co-movement above 0.70 threshold.",
                )
            )
        elif correlation <= -0.50:
            events.append(
                CorrelationRegimeEvent(
                    event_code=f"REGIME_STR_NEG_{uuid4().hex[:10].upper()}",
                    event_type=CorrelationRegimeEventType.STRONG_NEGATIVE_CORRELATION,
                    portfolio_id=portfolio_id,
                    asset_a_id=asset_a_id,
                    asset_b_id=asset_b_id,
                    asset_a_symbol=asset_a_symbol,
                    asset_b_symbol=asset_b_symbol,
                    detected_at=detected_at,
                    status=CorrelationRegimeStatus.ACTIVE,
                    current_correlation=correlation,
                    threshold_value=-0.50,
                    consecutive_periods_observed=1,
                    notes="Strong negative diversification correlation below -0.50 threshold.",
                )
            )

        if events:
            await self.repo.save_regime_events(events)
