"""
M07.07 Portfolio Beta Service Layer.
Integrates M07.01 Historical Volatility return series, M05.02 PositionBook, and M05.07 PortfolioBookSnapshot NAV.
Orchestrates:
- Benchmark reference management
- Individual security OLS beta regressions
- Current-weight implied portfolio beta & risk contributions
- Direct portfolio return OLS beta regression
- Direct vs weighted beta reconciliation
"""
from datetime import datetime, date, timezone
from decimal import Decimal
import time
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.market_risk.beta.models import (
    BenchmarkReference,
    BetaConfiguration,
    BetaCalculationRun,
    SecurityBetaResult,
    PortfolioBetaResult,
    BetaModelType,
    BetaCalculationMethod,
    BetaRegressionStatus,
)
from backend.app.modules.market_risk.beta.schemas import (
    SecurityBetaRequest,
    SecurityBetaResponse,
    PortfolioBetaRequest,
    PortfolioBetaResponse,
    AssetBetaContribution,
    DirectVsWeightedBetaReconciliation,
    BenchmarkReferenceCreate,
    BenchmarkReferenceResponse,
)
from backend.app.modules.market_risk.beta.calculations.beta_math import (
    calculate_ols_beta,
    calculate_portfolio_weighted_beta,
)
from backend.app.modules.market_risk.beta.repositories.repository import BetaRepository
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


class BetaService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BetaRepository(session)
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

    async def _resolve_returns_for_portfolio(
        self,
        portfolio_id: str,
        as_of: Optional[date] = None,
    ) -> List[Tuple[date, Decimal]]:
        prices = await self.vol_service.resolve_price_series(
            scope_type=VolatilityScopeType.PORTFOLIO,
            instrument_id=None,
            portfolio_id=portfolio_id,
            price_source=PriceSourceType.PORTFOLIO_NAV,
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

    async def get_or_resolve_benchmark(
        self,
        benchmark_id: Optional[str] = None,
        benchmark_code: Optional[str] = None,
    ) -> BenchmarkReference:
        if benchmark_id:
            bench = await self.repo.get_benchmark_by_id(benchmark_id)
            if bench:
                return bench
        if benchmark_code:
            bench = await self.repo.get_benchmark_by_code(benchmark_code)
            if bench:
                return bench

        # Check default active benchmarks or create standard NIFTY_50
        active_list = await self.repo.list_active_benchmarks()
        if active_list:
            return active_list[0]

        # Auto-create standard NIFTY_50 benchmark reference
        bench = BenchmarkReference(
            benchmark_code="NIFTY_50",
            benchmark_name="Nifty 50 Index",
            provider="NSE_INDICES",
            market="INDIA",
            currency="INR",
            return_basis="TOTAL_RETURN",
        )
        return await self.repo.create_benchmark(bench)

    async def calculate_security_beta(
        self, request: SecurityBetaRequest
    ) -> SecurityBetaResponse:
        start_time = time.perf_counter()
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)

        benchmark = await self.get_or_resolve_benchmark(request.benchmark_id, request.benchmark_code)
        sym = await self._resolve_instrument_symbol(request.instrument_id)

        returns_asset = await self._resolve_returns_for_asset(request.instrument_id, request.as_of)
        # Use benchmark's linked instrument returns or fallback to same method
        bench_asset_id = benchmark.instrument_id or benchmark.benchmark_code
        returns_bench = await self._resolve_returns_for_asset(bench_asset_id, request.as_of)

        if request.lookback_days:
            if len(returns_asset) > request.lookback_days:
                returns_asset = returns_asset[-request.lookback_days:]
            if len(returns_bench) > request.lookback_days:
                returns_bench = returns_bench[-request.lookback_days:]

        aligned_dates, y, x = align_two_series(returns_asset, returns_bench)

        reg = calculate_ols_beta(
            returns_asset=y,
            returns_benchmark=x,
            model_type=request.model_type,
        )

        run_code = f"BETA_RUN_SEC_{uuid4().hex[:10].upper()}"
        run = BetaCalculationRun(
            run_code=run_code,
            calculation_type="SECURITY",
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id,
            benchmark_id=benchmark.id,
            as_of_date=as_of_dt,
            lookback_window_days=request.lookback_days,
            model_type=request.model_type,
            execution_time_ms=int((time.perf_counter() - start_time) * 1000),
        )
        await self.repo.create_calculation_run(run)

        res_record = SecurityBetaResult(
            run_id=run.id,
            instrument_id=request.instrument_id,
            instrument_symbol=sym,
            benchmark_id=benchmark.id,
            benchmark_code=benchmark.benchmark_code,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            beta_value=reg["beta"],
            alpha_value=reg["alpha"],
            r_squared=reg["r_squared"],
            adjusted_r_squared=reg["adjusted_r_squared"],
            beta_standard_error=reg["beta_std_error"],
            beta_t_statistic=reg["beta_t_stat"],
            p_value=reg["p_value"],
            ci_lower_95=reg["ci_lower"],
            ci_upper_95=reg["ci_upper"],
            residual_std_error=reg["residual_std_error"],
            sample_size=reg["sample_size"],
            regression_status=reg["status"],
        )
        await self.repo.save_security_beta(res_record)

        return SecurityBetaResponse(
            instrument_id=request.instrument_id,
            instrument_symbol=sym,
            benchmark_id=benchmark.id,
            benchmark_code=benchmark.benchmark_code,
            benchmark_name=benchmark.benchmark_name,
            as_of_date=as_of_dt,
            lookback_days=request.lookback_days,
            beta_value=Decimal(str(round(reg["beta"], 6))),
            alpha_value=Decimal(str(round(reg["alpha"], 8))),
            r_squared=Decimal(str(round(reg["r_squared"], 4))),
            adjusted_r_squared=Decimal(str(round(reg["adjusted_r_squared"], 4))) if reg["adjusted_r_squared"] is not None else None,
            beta_standard_error=Decimal(str(round(reg["beta_std_error"], 6))),
            beta_t_statistic=Decimal(str(round(reg["beta_t_stat"], 4))),
            p_value=Decimal(str(round(reg["p_value"], 6))) if reg["p_value"] is not None else None,
            ci_lower_95=Decimal(str(round(reg["ci_lower"], 6))) if reg["ci_lower"] is not None else None,
            ci_upper_95=Decimal(str(round(reg["ci_upper"], 6))) if reg["ci_upper"] is not None else None,
            residual_std_error=Decimal(str(round(reg["residual_std_error"], 6))) if reg["residual_std_error"] is not None else None,
            sample_size=reg["sample_size"],
            regression_status=reg["status"],
        )

    async def calculate_portfolio_beta(
        self, request: PortfolioBetaRequest
    ) -> PortfolioBetaResponse:
        as_of_dt = datetime.combine(request.as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)
        benchmark = await self.get_or_resolve_benchmark(request.benchmark_id, request.benchmark_code)
        bench_asset_id = benchmark.instrument_id or benchmark.benchmark_code

        calc_code = f"PORT_BETA_{uuid4().hex[:12].upper()}"

        if request.method == BetaCalculationMethod.DIRECT_PORTFOLIO_REGRESSION:
            # Direct OLS of portfolio NAV returns on benchmark returns
            port_rets = await self._resolve_returns_for_portfolio(request.portfolio_id, request.as_of)
            bench_rets = await self._resolve_returns_for_asset(bench_asset_id, request.as_of)

            if request.lookback_days:
                if len(port_rets) > request.lookback_days:
                    port_rets = port_rets[-request.lookback_days:]
                if len(bench_rets) > request.lookback_days:
                    bench_rets = bench_rets[-request.lookback_days:]

            _, y, x = align_two_series(port_rets, bench_rets)
            reg = calculate_ols_beta(y, x)

            res = PortfolioBetaResult(
                calculation_code=calc_code,
                portfolio_id=request.portfolio_id,
                benchmark_id=benchmark.id,
                benchmark_code=benchmark.benchmark_code,
                as_of_date=as_of_dt,
                lookback_days=request.lookback_days,
                method=BetaCalculationMethod.DIRECT_PORTFOLIO_REGRESSION,
                portfolio_beta=reg["beta"],
                portfolio_alpha=reg["alpha"],
                r_squared=reg["r_squared"],
                beta_standard_error=reg["beta_std_error"],
                beta_t_statistic=reg["beta_t_stat"],
                sample_size=reg["sample_size"],
                weight_basis="PORTFOLIO_NAV_RETURNS",
                regression_status=reg["status"],
            )
            await self.repo.save_portfolio_beta(res)

            return PortfolioBetaResponse(
                calculation_code=calc_code,
                portfolio_id=request.portfolio_id,
                benchmark_id=benchmark.id,
                benchmark_code=benchmark.benchmark_code,
                benchmark_name=benchmark.benchmark_name,
                as_of_date=as_of_dt,
                lookback_days=request.lookback_days,
                method=BetaCalculationMethod.DIRECT_PORTFOLIO_REGRESSION,
                portfolio_beta=Decimal(str(round(reg["beta"], 6))),
                portfolio_alpha=Decimal(str(round(reg["alpha"], 8))),
                r_squared=Decimal(str(round(reg["r_squared"], 4))),
                beta_standard_error=Decimal(str(round(reg["beta_std_error"], 6))),
                beta_t_statistic=Decimal(str(round(reg["beta_t_stat"], 4))),
                sample_size=reg["sample_size"],
                weight_basis="PORTFOLIO_NAV_RETURNS",
                regression_status=reg["status"],
            )

        else:
            # Weighted aggregation of individual constituent betas
            asset_ids = await self._get_portfolio_instruments(request.portfolio_id)
            if not asset_ids and request.user_weights:
                asset_ids = list(request.user_weights.keys())

            if not asset_ids:
                raise ValueError("No portfolio constituents or weights provided.")

            symbols = [await self._resolve_instrument_symbol(aid) for aid in asset_ids]
            n = len(asset_ids)

            # Determine weights
            if request.user_weights:
                weights = np.array([float(request.user_weights.get(aid, 0.0)) for aid in asset_ids], dtype=np.float64)
            else:
                eq_w = 1.0 / float(n)
                weights = np.full(n, eq_w, dtype=np.float64)

            # Compute individual betas
            betas_list = []
            sample_sizes = []
            for aid in asset_ids:
                sec_resp = await self.calculate_security_beta(
                    SecurityBetaRequest(
                        instrument_id=aid,
                        benchmark_id=benchmark.id,
                        lookback_days=request.lookback_days,
                        as_of=request.as_of,
                    )
                )
                betas_list.append(float(sec_resp.beta_value))
                sample_sizes.append(sec_resp.sample_size)

            betas_arr = np.array(betas_list, dtype=np.float64)
            weighted_calc = calculate_portfolio_weighted_beta(weights, betas_arr, symbols)

            contributions: List[AssetBetaContribution] = []
            p_beta = weighted_calc["portfolio_beta"]
            for i in range(n):
                w_i = Decimal(str(round(weights[i], 6)))
                b_i = Decimal(str(round(betas_list[i], 6)))
                cb_i = Decimal(str(round(weighted_calc["contributions"][i]["weighted_beta"], 6)))
                pct_contrib = (cb_i / Decimal(str(p_beta)) * Decimal("100.0")).quantize(Decimal("0.0001")) if abs(p_beta) > 1e-12 else None

                contributions.append(
                    AssetBetaContribution(
                        asset_id=asset_ids[i],
                        symbol=symbols[i],
                        weight=w_i,
                        individual_beta=b_i,
                        beta_contribution=cb_i,
                        contribution_percentage=pct_contrib,
                    )
                )

            res = PortfolioBetaResult(
                calculation_code=calc_code,
                portfolio_id=request.portfolio_id,
                benchmark_id=benchmark.id,
                benchmark_code=benchmark.benchmark_code,
                as_of_date=as_of_dt,
                lookback_days=request.lookback_days,
                method=BetaCalculationMethod.CURRENT_WEIGHT_IMPLIED,
                portfolio_beta=p_beta,
                sample_size=min(sample_sizes) if sample_sizes else 0,
                weight_basis="CURRENT_WEIGHTS",
                asset_ids=asset_ids,
                asset_symbols=symbols,
                weights=weights.tolist(),
                individual_betas=betas_list,
                beta_contributions=[float(c["weighted_beta"]) for c in weighted_calc["contributions"]],
                regression_status=BetaRegressionStatus.VALID,
            )
            await self.repo.save_portfolio_beta(res)

            return PortfolioBetaResponse(
                calculation_code=calc_code,
                portfolio_id=request.portfolio_id,
                benchmark_id=benchmark.id,
                benchmark_code=benchmark.benchmark_code,
                benchmark_name=benchmark.benchmark_name,
                as_of_date=as_of_dt,
                lookback_days=request.lookback_days,
                method=BetaCalculationMethod.CURRENT_WEIGHT_IMPLIED,
                portfolio_beta=Decimal(str(round(p_beta, 6))),
                sample_size=min(sample_sizes) if sample_sizes else 0,
                weight_basis="CURRENT_WEIGHTS",
                contributions=contributions,
                reconciliation_sum=Decimal(str(round(weighted_calc["reconciliation_sum"], 6))),
                reconciliation_discrepancy=Decimal(str(round(weighted_calc["discrepancy"], 10))),
                regression_status=BetaRegressionStatus.VALID,
            )

    async def reconcile_direct_vs_weighted(
        self,
        portfolio_id: str,
        benchmark_code: Optional[str] = None,
        lookback_days: int = 60,
        as_of: Optional[date] = None,
    ) -> DirectVsWeightedBetaReconciliation:
        as_of_dt = datetime.combine(as_of or date.today(), datetime.min.time(), tzinfo=timezone.utc)
        bench = await self.get_or_resolve_benchmark(benchmark_code=benchmark_code)

        # 1. Direct beta
        dir_res = await self.calculate_portfolio_beta(
            PortfolioBetaRequest(
                portfolio_id=portfolio_id,
                benchmark_id=bench.id,
                method=BetaCalculationMethod.DIRECT_PORTFOLIO_REGRESSION,
                lookback_days=lookback_days,
                as_of=as_of,
            )
        )

        # 2. Weighted beta
        wt_res = await self.calculate_portfolio_beta(
            PortfolioBetaRequest(
                portfolio_id=portfolio_id,
                benchmark_id=bench.id,
                method=BetaCalculationMethod.CURRENT_WEIGHT_IMPLIED,
                lookback_days=lookback_days,
                as_of=as_of,
            )
        )

        discrepancy = (dir_res.portfolio_beta - wt_res.portfolio_beta) if dir_res.portfolio_beta is not None else None

        explanation = (
            "Differences between direct portfolio beta and current-weight implied beta arise from "
            "historical rebalancing, time-varying constituent weights, cash flow timing, and fee drag."
        )

        return DirectVsWeightedBetaReconciliation(
            portfolio_id=portfolio_id,
            benchmark_code=bench.benchmark_code,
            as_of_date=as_of_dt,
            direct_beta=dir_res.portfolio_beta,
            weighted_beta=wt_res.portfolio_beta,
            beta_discrepancy=discrepancy,
            direct_r_squared=dir_res.r_squared,
            explanation=explanation,
        )
