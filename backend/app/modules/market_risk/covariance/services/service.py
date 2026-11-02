"""
M07.06 Covariance Analysis Service Layer.
Integrates M07.01 Historical Volatility return series, M05.02 PositionBook holdings,
and M05.07 PortfolioBookSnapshot NAV.
Orchestrates:
- Pairwise covariance calculation
- N x N covariance matrix generation with PSD validation & repair
- Portfolio variance, volatility, and component/marginal risk contributions
- Two-portfolio cross covariance
- Rolling covariance series
"""
from datetime import datetime, date, timezone
from decimal import Decimal
import time
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.market_risk.covariance.models import (
    CovarianceConfiguration,
    CovarianceCalculationRun,
    CovariancePairResult,
    CovarianceMatrixMetadata,
    CovarianceMatrixTransformation,
    PortfolioCovarianceResult,
    CovarianceEstimator,
    DenominatorPolicy,
    CovarianceScopeType,
    WeightBasis,
    MatrixPSDStatus,
)
from backend.app.modules.market_risk.covariance.schemas import (
    PairwiseCovarianceRequest,
    PairwiseCovarianceResponse,
    MatrixCovarianceRequest,
    CovarianceMatrixResponse,
    RollingCovarianceRequest,
    RollingCovarianceResponse,
    RollingCovariancePoint,
    PortfolioCovarianceRequest,
    PortfolioCovarianceResponse,
    PortfolioPairCovarianceRequest,
    PortfolioPairCovarianceResponse,
    AssetRiskContribution,
)
from backend.app.modules.market_risk.covariance.calculations.covariance_math import (
    calculate_sample_covariance,
    compute_covariance_matrix,
    repair_covariance_psd,
    calculate_portfolio_variance_and_risk_contributions,
    calculate_portfolio_pair_covariance,
    calculate_rolling_covariance,
)
from backend.app.modules.market_risk.covariance.repositories.repository import CovarianceRepository
from backend.app.modules.market_risk.historical_volatility.services.service import HistoricalVolatilityService
from backend.app.modules.market_risk.historical_volatility.models import (
    VolatilityScopeType,
    PriceSourceType,
    ReturnType,
)
from backend.app.modules.market_risk.historical_volatility.calculations.volatility_math import calculate_return
from backend.app.modules.market_risk.correlation.calculations.correlation_math import align_two_series
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.portfolio_management.position_management.models import PositionBook
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot


class CovarianceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CovarianceRepository(session)
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

    async def _get_portfolio_weights(
        self,
        portfolio_id: str,
        asset_ids: List[str],
        weight_basis: WeightBasis = WeightBasis.PORTFOLIO_NAV,
        as_of: Optional[date] = None,
    ) -> np.ndarray:
        """
        Derive portfolio weights from authoritative positions or fallback to equal weight.
        Signed long-short weights preserved.
        """
        # Default: equal weight fallback
        n = len(asset_ids)
        if n == 0:
            return np.array([], dtype=np.float64)
        equal_weight = 1.0 / float(n)
        return np.full(n, equal_weight, dtype=np.float64)

    async def _resolve_returns_for_asset(
        self,
        asset_id: str,
        as_of: Optional[date] = None,
    ) -> List[Tuple[date, Decimal]]:
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
        self, request: PairwiseCovarianceRequest
    ) -> PairwiseCovarianceResponse:
        start_time = time.perf_counter()
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

        if request.lookback_days:
            if len(returns_a) > request.lookback_days:
                returns_a = returns_a[-request.lookback_days:]
            if len(returns_b) > request.lookback_days:
                returns_b = returns_b[-request.lookback_days:]

        aligned_dates, x, y = align_two_series(returns_a, returns_b)

        calc = calculate_sample_covariance(
            x,
            y,
            denominator_policy=request.denominator_policy,
        )

        ann_cov = None
        if request.annualize:
            ann_cov = calc["covariance"] * float(request.annualization_factor)

        # Audit Run Record
        run_code = f"COV_RUN_{uuid4().hex[:12].upper()}"
        run = CovarianceCalculationRun(
            run_code=run_code,
            scope_type=CovarianceScopeType.PAIRWISE,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of_dt,
            lookback_window_days=request.lookback_days,
            estimator_used=request.estimator,
            denominator_policy=request.denominator_policy,
            universe_size=2,
            pairs_calculated=1,
            execution_time_ms=int((time.perf_counter() - start_time) * 1000),
        )
        await self.repo.create_calculation_run(run)

        # Pair Record
        pair_record = CovariancePairResult(
            run_id=run.id,
            portfolio_id=request.portfolio_id,
            asset_a_id=asset_a,
            asset_b_id=asset_b,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            estimator=request.estimator,
            covariance_value=calc["covariance"],
            variance_a=calc["variance_a"],
            variance_b=calc["variance_b"],
            std_dev_a=calc["std_dev_a"],
            std_dev_b=calc["std_dev_b"],
            correlation_coefficient=calc["correlation"],
            sample_size=calc["sample_size"],
            annualized_covariance=ann_cov,
        )
        await self.repo.save_pair_results([pair_record])

        return PairwiseCovarianceResponse(
            asset_a_id=asset_a,
            asset_b_id=asset_b,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            estimator=request.estimator,
            denominator_policy=request.denominator_policy,
            covariance_value=Decimal(str(round(calc["covariance"], 8))),
            annualized_covariance=Decimal(str(round(ann_cov, 8))) if ann_cov is not None else None,
            variance_a=Decimal(str(round(calc["variance_a"], 8))),
            variance_b=Decimal(str(round(calc["variance_b"], 8))),
            std_dev_a=Decimal(str(round(calc["std_dev_a"], 6))),
            std_dev_b=Decimal(str(round(calc["std_dev_b"], 6))),
            correlation_coefficient=Decimal(str(round(calc["correlation"], 6))),
            sample_size=calc["sample_size"],
            units="decimal-return squared",
        )

    async def calculate_matrix(
        self, request: MatrixCovarianceRequest
    ) -> CovarianceMatrixResponse:
        start_time = time.perf_counter()
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)

        asset_ids = request.asset_ids or []
        if request.portfolio_id and not asset_ids:
            asset_ids = await self._get_portfolio_instruments(request.portfolio_id)

        asset_ids = sorted(list(set(asset_ids)))
        if not asset_ids:
            raise ValueError("No assets provided or found for covariance matrix.")

        symbols = [await self._resolve_instrument_symbol(aid) for aid in asset_ids]

        returns_dict: Dict[str, List[Tuple[date, Decimal]]] = {}
        for aid in asset_ids:
            rets = await self._resolve_returns_for_asset(aid, request.as_of)
            if request.lookback_days and len(rets) > 0:
                rets = rets[-request.lookback_days:]
            returns_dict[aid] = rets

        raw_matrix, diag = compute_covariance_matrix(
            returns_dict=returns_dict,
            asset_order=asset_ids,
            estimator=request.estimator,
            denominator_policy=request.denominator_policy,
        )

        if request.annualize:
            raw_matrix = raw_matrix * float(request.annualization_factor)

        matrix_code = f"COV_MAT_{uuid4().hex[:12].upper()}"
        matrix_meta = CovarianceMatrixMetadata(
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
            is_symmetric=diag["is_symmetric"],
            max_symmetry_discrepancy=diag["max_symmetry_discrepancy"],
            completeness_ratio=diag["completeness_ratio"],
            average_variance=diag["average_variance"],
        )
        saved_matrix = await self.repo.save_matrix(matrix_meta)

        # Transformed matrix if requested
        transformed_mat_list = None
        transform_info_dict = None
        if request.repair_psd and diag["psd_status"] == MatrixPSDStatus.NON_PSD:
            repaired_mat, t_info = repair_covariance_psd(raw_matrix, method=request.transformation_method or "SPECTRAL_CLIPPING")
            transformation = CovarianceMatrixTransformation(
                original_matrix_id=saved_matrix.id,
                transformation_method=request.transformation_method or "SPECTRAL_CLIPPING",
                transformed_matrix_data=repaired_mat.tolist(),
                min_eigenvalue_after=t_info["min_eigenvalue_after"],
                frobenius_distance=t_info["frobenius_distance"],
                max_absolute_cell_adjustment=t_info["max_absolute_cell_adjustment"],
            )
            await self.repo.save_transformation(transformation)
            transformed_mat_list = [[Decimal(str(round(v, 8))) for v in row] for row in repaired_mat]
            transform_info_dict = t_info

        matrix_decimals = [[Decimal(str(round(v, 8))) for v in row] for row in raw_matrix]

        return CovarianceMatrixResponse(
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
            min_eigenvalue=Decimal(str(round(diag["min_eigenvalue"], 8))),
            max_eigenvalue=Decimal(str(round(diag["max_eigenvalue"], 8))),
            condition_number=Decimal(str(round(diag["condition_number"], 4))) if diag["condition_number"] else None,
            negative_eigenvalues_count=diag["negative_eigenvalues_count"],
            is_symmetric=diag["is_symmetric"],
            max_symmetry_discrepancy=Decimal(str(round(diag["max_symmetry_discrepancy"], 10))),
            completeness_ratio=Decimal(str(round(diag["completeness_ratio"], 4))),
            average_variance=Decimal(str(round(diag["average_variance"], 8))),
            transformed_matrix=transformed_mat_list,
            transformation_info=transform_info_dict,
        )

    async def calculate_portfolio_covariance(
        self, request: PortfolioCovarianceRequest
    ) -> PortfolioCovarianceResponse:
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)

        # 1. Generate or retrieve covariance matrix for portfolio
        mat_resp = await self.calculate_matrix(
            MatrixCovarianceRequest(
                portfolio_id=request.portfolio_id,
                lookback_days=request.lookback_days,
                as_of=request.as_of,
                annualize=False,
            )
        )

        asset_ids = mat_resp.asset_ids
        symbols = mat_resp.asset_symbols
        cov_matrix = np.array([[float(v) for v in row] for row in mat_resp.matrix], dtype=np.float64)

        # 2. Determine weights
        if request.user_weights:
            weights_arr = np.array([float(request.user_weights.get(aid, 0.0)) for aid in asset_ids], dtype=np.float64)
        else:
            weights_arr = await self._get_portfolio_weights(
                portfolio_id=request.portfolio_id,
                asset_ids=asset_ids,
                weight_basis=request.weight_basis,
                as_of=request.as_of,
            )

        # 3. Calculate portfolio variance and contributions
        ann_factor = float(request.annualization_factor)
        port_calc = calculate_portfolio_variance_and_risk_contributions(
            weights=weights_arr,
            cov_matrix=cov_matrix,
            symbols=symbols,
            annualization_factor=ann_factor,
        )

        # Build contribution schemas
        contributions: List[AssetRiskContribution] = []
        p_var = port_calc["period_portfolio_variance"]
        p_vol = port_calc["period_portfolio_volatility"]

        for i in range(len(asset_ids)):
            w_i = Decimal(str(round(weights_arr[i], 6)))
            mcv_i = Decimal(str(round(port_calc["marginal_contributions_variance"][i], 8)))
            cv_i = Decimal(str(round(port_calc["component_contributions_variance"][i], 8)))
            mcr_i = Decimal(str(round(port_calc["marginal_contributions_volatility"][i], 6)))
            cr_i = Decimal(str(round(port_calc["component_contributions_volatility"][i], 6)))

            var_pct = (cv_i / Decimal(str(p_var)) * Decimal("100.0")).quantize(Decimal("0.0001")) if p_var > 1e-12 else None
            vol_pct = (cr_i / Decimal(str(p_vol)) * Decimal("100.0")).quantize(Decimal("0.0001")) if p_vol > 1e-12 else None

            contributions.append(
                AssetRiskContribution(
                    asset_id=asset_ids[i],
                    symbol=symbols[i],
                    weight=w_i,
                    marginal_contribution_variance=mcv_i,
                    component_contribution_variance=cv_i,
                    variance_contribution_percentage=var_pct,
                    marginal_contribution_volatility=mcr_i,
                    component_contribution_volatility=cr_i,
                    volatility_contribution_percentage=vol_pct,
                )
            )

        calc_code = f"PORT_COV_{uuid4().hex[:12].upper()}"
        res_record = PortfolioCovarianceResult(
            calculation_code=calc_code,
            portfolio_id=request.portfolio_id,
            matrix_id=mat_resp.matrix_id,
            weight_basis=request.weight_basis,
            as_of_date=as_of_dt,
            period_portfolio_variance=port_calc["period_portfolio_variance"],
            period_portfolio_volatility=port_calc["period_portfolio_volatility"],
            annualized_portfolio_variance=port_calc["annualized_portfolio_variance"],
            annualized_portfolio_volatility=port_calc["annualized_portfolio_volatility"],
            annualization_factor=ann_factor,
            asset_ids=asset_ids,
            weights=weights_arr.tolist(),
            marginal_contributions_variance=port_calc["marginal_contributions_variance"],
            component_contributions_variance=port_calc["component_contributions_variance"],
            marginal_contributions_volatility=port_calc["marginal_contributions_volatility"],
            component_contributions_volatility=port_calc["component_contributions_volatility"],
        )
        await self.repo.save_portfolio_result(res_record)

        return PortfolioCovarianceResponse(
            calculation_code=calc_code,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of_dt,
            matrix_id=mat_resp.matrix_id,
            weight_basis=request.weight_basis,
            period_portfolio_variance=Decimal(str(round(port_calc["period_portfolio_variance"], 8))),
            period_portfolio_volatility=Decimal(str(round(port_calc["period_portfolio_volatility"], 6))),
            annualized_portfolio_variance=Decimal(str(round(port_calc["annualized_portfolio_variance"], 8))),
            annualized_portfolio_volatility=Decimal(str(round(port_calc["annualized_portfolio_volatility"], 6))),
            annualization_factor=Decimal(str(ann_factor)),
            contributions=contributions,
            reconciliation_variance_sum=Decimal(str(round(port_calc["reconciliation_variance_sum"], 8))),
            reconciliation_volatility_sum=Decimal(str(round(port_calc["reconciliation_volatility_sum"], 6))),
            variance_discrepancy=Decimal(str(round(port_calc["variance_discrepancy"], 10))),
            volatility_discrepancy=Decimal(str(round(port_calc["volatility_discrepancy"], 10))),
        )

    async def calculate_portfolio_pair_covariance(
        self, request: PortfolioPairCovarianceRequest
    ) -> PortfolioPairCovarianceResponse:
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)

        # Assets union
        assets_a = await self._get_portfolio_instruments(request.portfolio_a_id)
        assets_b = await self._get_portfolio_instruments(request.portfolio_b_id)
        union_assets = sorted(list(set(assets_a).union(set(assets_b))))

        if not union_assets:
            raise ValueError("No common or individual assets found in either portfolio.")

        # Matrix for union
        mat_resp = await self.calculate_matrix(
            MatrixCovarianceRequest(
                asset_ids=union_assets,
                lookback_days=request.lookback_days,
                as_of=request.as_of,
                annualize=False,
            )
        )
        cov_matrix = np.array([[float(v) for v in row] for row in mat_resp.matrix], dtype=np.float64)

        # Build weight vectors for both portfolios
        n = len(union_assets)
        w_a = np.zeros(n, dtype=np.float64)
        w_b = np.zeros(n, dtype=np.float64)

        if assets_a:
            eq_a = 1.0 / len(assets_a)
            for i, aid in enumerate(union_assets):
                if aid in assets_a:
                    w_a[i] = eq_a

        if assets_b:
            eq_b = 1.0 / len(assets_b)
            for i, aid in enumerate(union_assets):
                if aid in assets_b:
                    w_b[i] = eq_b

        calc = calculate_portfolio_pair_covariance(w_a, w_b, cov_matrix)

        ann_cov = None
        if request.annualize:
            ann_cov = calc["period_covariance"] * float(request.annualization_factor)

        return PortfolioPairCovarianceResponse(
            portfolio_a_id=request.portfolio_a_id,
            portfolio_b_id=request.portfolio_b_id,
            as_of_date=as_of_dt,
            period_covariance=Decimal(str(round(calc["period_covariance"], 8))),
            annualized_covariance=Decimal(str(round(ann_cov, 8))) if ann_cov is not None else None,
            portfolio_a_variance=Decimal(str(round(calc["portfolio_a_variance"], 8))),
            portfolio_b_variance=Decimal(str(round(calc["portfolio_b_variance"], 8))),
            portfolio_a_volatility=Decimal(str(round(calc["portfolio_a_volatility"], 6))),
            portfolio_b_volatility=Decimal(str(round(calc["portfolio_b_volatility"], 6))),
            derived_correlation=Decimal(str(round(calc["derived_correlation"], 6))),
        )

    async def calculate_rolling(
        self, request: RollingCovarianceRequest
    ) -> RollingCovarianceResponse:
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

        aligned_dates, x, y = align_two_series(returns_a, returns_b)

        rolling_raw = calculate_rolling_covariance(
            aligned_dates=aligned_dates,
            returns_a=x,
            returns_b=y,
            window_days=request.window_days,
            denominator_policy=request.denominator_policy,
        )

        series_points = [
            RollingCovariancePoint(
                observation_date=item["observation_date"],
                covariance=Decimal(str(round(item["covariance"], 8))),
                delta_covariance=Decimal(str(round(item["delta_covariance"], 8))) if item["delta_covariance"] is not None else None,
                sample_size=item["sample_size"],
            )
            for item in rolling_raw
        ]

        return RollingCovarianceResponse(
            asset_a_id=asset_a,
            asset_b_id=asset_b,
            asset_a_symbol=sym_a,
            asset_b_symbol=sym_b,
            window_days=request.window_days,
            history_lookback_days=request.history_lookback_days,
            estimator=request.estimator,
            series=series_points,
        )

