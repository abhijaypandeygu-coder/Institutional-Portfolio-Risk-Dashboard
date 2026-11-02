"""
M07.10 Risk Forecasting Service Layer.
Integrates with M07.01 Historical Volatility returns, M05 Portfolio Snapshots,
and M04 Trading Calendars to orchestrate forward-looking risk forecasting,
model comparisons, and ex-post evaluations.
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
import math
import uuid
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.risk_forecasting.models import (
    RiskForecastCalculationRun,
    VolatilityForecastResult,
    RiskForecastEvaluationResult,
    RiskForecastModelComparison,
    RiskForecastMonitoringEvent,
    ForecastModelType,
    ForecastCalculationScope,
    ForecastTargetMeasure,
    RealizedVarianceProxyType,
    ForecastStatus,
    EvaluationStatus,
    MonitoringEventType,
)
from backend.app.modules.market_risk.risk_forecasting.schemas import (
    VolatilityForecastRequest,
    VolatilityForecastResponse,
    ForecastStepPoint,
    ForecastEvaluationItem,
    ModelComparisonRequest,
    ModelComparisonResponse,
    ModelComparisonSummary,
    MonitoringEventResponse,
)
from backend.app.modules.market_risk.risk_forecasting.calculations.forecasting_math import (
    forecast_rolling_historical_variance,
    forecast_ewma_variance,
    fit_and_forecast_garch_1_1,
    evaluate_forecast_realized,
    compute_calibration_regression,
)
from backend.app.modules.market_risk.risk_forecasting.repositories.repository import (
    RiskForecastingRepository,
)
from backend.app.modules.market_risk.historical_volatility.services.service import (
    HistoricalVolatilityService,
)
from backend.app.modules.market_risk.historical_volatility.models import (
    VolatilityScopeType,
    PriceSourceType,
    ReturnType,
)
from backend.app.modules.market_risk.historical_volatility.calculations.volatility_math import (
    calculate_return,
)
from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
)


class RiskForecastingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RiskForecastingRepository(session)
        self.vol_service = HistoricalVolatilityService(session)

    async def _resolve_historical_returns(
        self,
        scope: ForecastCalculationScope,
        entity_id: str,
        as_of: Optional[date] = None,
        lookback_days: int = 252,
    ) -> List[Tuple[date, float]]:
        """
        Retrieve approved historical daily return series up to the forecast origin cutoff (no lookahead).
        """
        if scope == ForecastCalculationScope.INSTRUMENT:
            prices = await self.vol_service.resolve_price_series(
                scope_type=VolatilityScopeType.INSTRUMENT,
                instrument_id=entity_id,
                portfolio_id=None,
                price_source=PriceSourceType.OFFICIAL_CLOSE,
                as_of=as_of,
            )
        else:
            # Portfolio scope
            prices = await self.vol_service.resolve_price_series(
                scope_type=VolatilityScopeType.PORTFOLIO,
                instrument_id=None,
                portfolio_id=entity_id,
                price_source=PriceSourceType.OFFICIAL_CLOSE,
                as_of=as_of,
            )

        if len(prices) < 2:
            return []

        # Filter strictly up to as_of
        cutoff = as_of or date.today()
        filtered_prices = []
        for p in prices:
            p_date = p[0].date() if isinstance(p[0], datetime) else p[0]
            if p_date <= cutoff:
                filtered_prices.append((p_date, p[1]))

        if len(filtered_prices) < 2:
            return []

        # Enforce lookback calendar cutoff
        start_date = cutoff - timedelta(days=lookback_days + 15)
        bounded_prices = [p for p in filtered_prices if p[0] >= start_date]
        if len(bounded_prices) < 2:
            bounded_prices = filtered_prices

        returns = []
        for i in range(1, len(bounded_prices)):
            p_prev = bounded_prices[i - 1][1]
            p_curr = bounded_prices[i][1]
            d_curr = bounded_prices[i][0]
            ret = float(calculate_return(p_prev, p_curr, return_type=ReturnType.LOGARITHMIC))
            returns.append((d_curr, ret))

        return returns

    async def generate_forecast(
        self, request: VolatilityForecastRequest
    ) -> VolatilityForecastResponse:
        """
        Orchestrate point-in-time volatility forecasting across Rolling, EWMA, or GARCH(1,1).
        """
        as_of = request.forecast_origin or date.today()
        series = await self._resolve_historical_returns(
            scope=request.scope,
            entity_id=request.entity_id,
            as_of=as_of,
            lookback_days=request.lookback_days,
        )

        n = len(series)
        annual_factor_flt = float(request.annualization_factor)

        # Build trading day horizon dates (skipping weekends)
        target_dates = []
        cur_d = as_of + timedelta(days=1)
        while len(target_dates) < request.forecast_horizon:
            if cur_d.weekday() < 5:  # Monday to Friday
                target_dates.append(cur_d)
            cur_d += timedelta(days=1)

        target_start = target_dates[0] if target_dates else as_of
        target_end = target_dates[-1] if target_dates else as_of

        if n < 5:
            # Insufficient data fallback
            calc_id = str(uuid.uuid4())
            return VolatilityForecastResponse(
                calculation_id=calc_id,
                scope=request.scope,
                entity_id=request.entity_id,
                model_name=request.model_name,
                model_version="1.0.0",
                forecast_origin=as_of,
                target_start_date=target_start,
                target_end_date=target_end,
                forecast_horizon=request.forecast_horizon,
                annualization_factor=request.annualization_factor,
                one_step_forecast_variance=Decimal("0.0"),
                one_step_forecast_volatility=Decimal("0.0"),
                cumulative_horizon_variance=Decimal("0.0"),
                cumulative_horizon_volatility=Decimal("0.0"),
                annualized_forecast_volatility=Decimal("0.0"),
                model_parameters=None,
                fit_diagnostics={"error": "Insufficient historical return observations"},
                step_results=[],
                status=ForecastStatus.INSUFFICIENT_DATA,
                created_at=datetime.utcnow(),
            )

        returns_arr = np.array([pt[1] for pt in series], dtype=np.float64)

        # Execute statistical model
        if request.model_name == ForecastModelType.ROLLING_HISTORICAL:
            calc_out = forecast_rolling_historical_variance(
                returns=returns_arr,
                horizon=request.forecast_horizon,
                annualization_factor=annual_factor_flt,
            )
        elif request.model_name == ForecastModelType.EWMA:
            calc_out = forecast_ewma_variance(
                returns=returns_arr,
                decay_factor=float(request.ewma_decay_factor),
                horizon=request.forecast_horizon,
                annualization_factor=annual_factor_flt,
            )
        elif request.model_name == ForecastModelType.GARCH_1_1:
            calc_out = fit_and_forecast_garch_1_1(
                returns=returns_arr,
                horizon=request.forecast_horizon,
                annualization_factor=annual_factor_flt,
            )
        else:
            raise ValueError(f"Unsupported model {request.model_name}")

        # Assemble step points
        step_items: List[ForecastStepPoint] = []
        h_path = calc_out["horizon_variance_path"]
        cum_v = 0.0

        for i, step_v in enumerate(h_path):
            cum_v += step_v
            t_date = target_dates[i] if i < len(target_dates) else target_end
            s_vol = math.sqrt(max(0.0, step_v))
            c_vol = math.sqrt(max(0.0, cum_v))
            ann_v = s_vol * math.sqrt(annual_factor_flt)

            step_items.append(
                ForecastStepPoint(
                    step_number=i + 1,
                    target_date=t_date,
                    step_variance=Decimal(str(round(step_v, 10))),
                    step_volatility=Decimal(str(round(s_vol, 10))),
                    cumulative_variance=Decimal(str(round(cum_v, 10))),
                    cumulative_volatility=Decimal(str(round(c_vol, 10))),
                    annualized_volatility=Decimal(str(round(ann_v, 10))),
                )
            )

        # Database record
        calc_id = str(uuid.uuid4())
        run_record = RiskForecastCalculationRun(
            calculation_id=calc_id,
            scope=request.scope,
            entity_id=request.entity_id,
            model_name=request.model_name,
            model_version="1.0.0",
            forecast_origin=as_of,
            target_start_date=target_start,
            target_end_date=target_end,
            forecast_horizon=request.forecast_horizon,
            annualization_factor=request.annualization_factor,
            estimation_sample_size=n,
            input_data_watermark=f"N_{n}_ASOF_{as_of}",
            model_parameters=calc_out.get("parameters"),
            fit_diagnostics=calc_out.get("fit_diagnostics"),
            one_step_forecast_variance=Decimal(str(round(calc_out["one_step_variance"], 10))),
            one_step_forecast_volatility=Decimal(str(round(calc_out["one_step_volatility"], 10))),
            cumulative_horizon_variance=Decimal(str(round(calc_out["cumulative_horizon_variance"], 10))),
            cumulative_horizon_volatility=Decimal(str(round(calc_out["cumulative_horizon_volatility"], 10))),
            annualized_forecast_volatility=Decimal(str(round(calc_out["annualized_forecast_volatility"], 10))),
            status=calc_out["status"],
            created_at=datetime.utcnow(),
        )

        for sp in step_items:
            step_rec = VolatilityForecastResult(
                calculation_id=calc_id,
                step_number=sp.step_number,
                target_date=sp.target_date,
                step_variance=sp.step_variance,
                step_volatility=sp.step_volatility,
                cumulative_variance=sp.cumulative_variance,
                cumulative_volatility=sp.cumulative_volatility,
                annualized_volatility=sp.annualized_volatility,
            )
            run_record.step_results.append(step_rec)

        await self.repo.save_calculation_run(run_record)

        return VolatilityForecastResponse(
            calculation_id=calc_id,
            scope=request.scope,
            entity_id=request.entity_id,
            model_name=request.model_name,
            model_version="1.0.0",
            forecast_origin=as_of,
            target_start_date=target_start,
            target_end_date=target_end,
            forecast_horizon=request.forecast_horizon,
            annualization_factor=request.annualization_factor,
            one_step_forecast_variance=run_record.one_step_forecast_variance,
            one_step_forecast_volatility=run_record.one_step_forecast_volatility,
            cumulative_horizon_variance=run_record.cumulative_horizon_variance,
            cumulative_horizon_volatility=run_record.cumulative_horizon_volatility,
            annualized_forecast_volatility=run_record.annualized_forecast_volatility,
            model_parameters=run_record.model_parameters,
            fit_diagnostics=run_record.fit_diagnostics,
            step_results=step_items,
            status=run_record.status,
            created_at=run_record.created_at,
        )

    async def get_latest_forecast(
        self,
        scope: ForecastCalculationScope,
        entity_id: str,
        model_name: Optional[ForecastModelType] = None,
        as_of: Optional[date] = None,
    ) -> Optional[VolatilityForecastResponse]:
        """Fetch latest persisted forecast or generate on-demand."""
        run = await self.repo.get_latest_run_for_entity(
            scope=scope, entity_id=entity_id, model_name=model_name, as_of=as_of
        )
        if run:
            steps = [
                ForecastStepPoint(
                    step_number=s.step_number,
                    target_date=s.target_date,
                    step_variance=s.step_variance,
                    step_volatility=s.step_volatility,
                    cumulative_variance=s.cumulative_variance,
                    cumulative_volatility=s.cumulative_volatility,
                    annualized_volatility=s.annualized_volatility,
                )
                for s in run.step_results
            ]
            return VolatilityForecastResponse(
                calculation_id=run.calculation_id,
                scope=run.scope,
                entity_id=run.entity_id,
                model_name=run.model_name,
                model_version=run.model_version,
                forecast_origin=run.forecast_origin,
                target_start_date=run.target_start_date,
                target_end_date=run.target_end_date,
                forecast_horizon=run.forecast_horizon,
                annualization_factor=run.annualization_factor,
                one_step_forecast_variance=run.one_step_forecast_variance,
                one_step_forecast_volatility=run.one_step_forecast_volatility,
                cumulative_horizon_variance=run.cumulative_horizon_variance,
                cumulative_horizon_volatility=run.cumulative_horizon_volatility,
                annualized_forecast_volatility=run.annualized_forecast_volatility,
                model_parameters=run.model_parameters,
                fit_diagnostics=run.fit_diagnostics,
                step_results=steps,
                status=run.status,
                created_at=run.created_at,
            )

        # Generate default EWMA on demand
        req = VolatilityForecastRequest(
            scope=scope,
            entity_id=entity_id,
            model_name=model_name or ForecastModelType.EWMA,
            forecast_origin=as_of,
        )
        return await self.generate_forecast(req)

    async def evaluate_forecast(
        self,
        calculation_id: str,
        realized_proxy_type: RealizedVarianceProxyType = RealizedVarianceProxyType.SQUARED_RETURN,
    ) -> ForecastEvaluationItem:
        """
        Evaluate an existing forecast after its target horizon has completed.
        Fetches realized return observations over [target_start_date, target_end_date],
        constructs the realized variance proxy, and calculates MAE, RMSE, and QLIKE loss.
        """
        run = await self.repo.get_calculation_run(calculation_id)
        if not run:
            raise ValueError(f"Forecast run {calculation_id} not found")

        # Check target maturity
        today = date.today()
        if today < run.target_end_date:
            # Horizon has not yet passed
            return ForecastEvaluationItem(
                evaluation_id=0,
                calculation_id=run.calculation_id,
                target_start_date=run.target_start_date,
                target_end_date=run.target_end_date,
                realized_proxy_type=realized_proxy_type,
                forecast_variance=run.cumulative_horizon_variance,
                realized_variance=Decimal("0.0"),
                forecast_volatility=run.cumulative_horizon_volatility,
                realized_volatility=Decimal("0.0"),
                forecast_error_volatility=Decimal("0.0"),
                absolute_error_volatility=Decimal("0.0"),
                squared_error_volatility=Decimal("0.0"),
                qlike_loss=None,
                evaluation_status=EvaluationStatus.AWAITING_REALIZED_DATA,
            )

        # Retrieve realized returns in target window
        all_series = await self._resolve_historical_returns(
            scope=run.scope,
            entity_id=run.entity_id,
            as_of=run.target_end_date,
            lookback_days=100,
        )
        target_returns = [
            pt[1] for pt in all_series if run.target_start_date <= pt[0] <= run.target_end_date
        ]

        if not target_returns:
            return ForecastEvaluationItem(
                evaluation_id=0,
                calculation_id=run.calculation_id,
                target_start_date=run.target_start_date,
                target_end_date=run.target_end_date,
                realized_proxy_type=realized_proxy_type,
                forecast_variance=run.cumulative_horizon_variance,
                realized_variance=Decimal("0.0"),
                forecast_volatility=run.cumulative_horizon_volatility,
                realized_volatility=Decimal("0.0"),
                forecast_error_volatility=Decimal("0.0"),
                absolute_error_volatility=Decimal("0.0"),
                squared_error_volatility=Decimal("0.0"),
                qlike_loss=None,
                evaluation_status=EvaluationStatus.INSUFFICIENT_REALIZED_DATA,
            )

        # Realized variance proxy = sum(r_t^2) over the target window
        realized_var = float(np.sum(np.array(target_returns, dtype=np.float64) ** 2))
        f_var = float(run.cumulative_horizon_variance)

        eval_math = evaluate_forecast_realized(f_var, realized_var)

        eval_rec = RiskForecastEvaluationResult(
            calculation_id=run.calculation_id,
            evaluation_timestamp=datetime.utcnow(),
            realized_proxy_type=realized_proxy_type,
            target_start_date=run.target_start_date,
            target_end_date=run.target_end_date,
            forecast_variance=Decimal(str(round(eval_math["forecast_variance"], 10))),
            realized_variance=Decimal(str(round(eval_math["realized_variance"], 10))),
            forecast_volatility=Decimal(str(round(eval_math["forecast_volatility"], 10))),
            realized_volatility=Decimal(str(round(eval_math["realized_volatility"], 10))),
            forecast_error_variance=Decimal(str(round(eval_math["forecast_error_variance"], 10))),
            forecast_error_volatility=Decimal(str(round(eval_math["forecast_error_volatility"], 10))),
            absolute_error_volatility=Decimal(str(round(eval_math["absolute_error_volatility"], 10))),
            squared_error_volatility=Decimal(str(round(eval_math["squared_error_volatility"], 10))),
            qlike_loss=Decimal(str(round(eval_math["qlike_loss"], 10))),
            evaluation_status=EvaluationStatus.EVALUATED,
            diagnostics={"realized_sample_count": len(target_returns)},
        )

        await self.repo.save_evaluation(eval_rec)

        # Check monitoring trigger for persistent underforecasting
        if eval_math["forecast_error_volatility"] < -0.05:
            mon_evt = RiskForecastMonitoringEvent(
                entity_id=run.entity_id,
                model_name=run.model_name,
                event_type=MonitoringEventType.PERSISTENT_UNDERFORECAST,
                detected_at=datetime.utcnow(),
                observed_metric="forecast_error_volatility",
                observed_value=Decimal(str(round(eval_math["forecast_error_volatility"], 6))),
                threshold_value=Decimal("-0.05"),
                details={"calculation_id": run.calculation_id},
            )
            await self.repo.save_monitoring_event(mon_evt)

        return ForecastEvaluationItem(
            evaluation_id=eval_rec.id,
            calculation_id=run.calculation_id,
            target_start_date=run.target_start_date,
            target_end_date=run.target_end_date,
            realized_proxy_type=realized_proxy_type,
            forecast_variance=eval_rec.forecast_variance,
            realized_variance=eval_rec.realized_variance,
            forecast_volatility=eval_rec.forecast_volatility,
            realized_volatility=eval_rec.realized_volatility,
            forecast_error_volatility=eval_rec.forecast_error_volatility,
            absolute_error_volatility=eval_rec.absolute_error_volatility,
            squared_error_volatility=eval_rec.squared_error_volatility,
            qlike_loss=eval_rec.qlike_loss,
            evaluation_status=eval_rec.evaluation_status,
        )

    async def compare_models(
        self, request: ModelComparisonRequest
    ) -> ModelComparisonResponse:
        """
        Walk-forward side-by-side comparison of candidate models on identical historical origins.
        Ranks models by MAE, RMSE, and QLIKE loss.
        """
        end_d = request.evaluation_end_date or date.today()
        start_d = request.evaluation_start_date or (end_d - timedelta(days=60))

        # Retrieve full return series to simulate walk-forward origins
        full_series = await self._resolve_historical_returns(
            scope=request.scope,
            entity_id=request.entity_id,
            as_of=end_d,
            lookback_days=365,
        )

        dates = [pt[0] for pt in full_series]
        returns_map = {pt[0]: pt[1] for pt in full_series}

        eval_origins = [d for d in dates if start_d <= d <= (end_d - timedelta(days=request.forecast_horizon))]
        if len(eval_origins) > 30:
            eval_origins = eval_origins[-30:]  # Limit to 30 walk-forward steps for speed

        model_stats: Dict[ForecastModelType, Dict[str, Any]] = {
            m: {"mae": [], "rmse": [], "bias": [], "qlike": [], "f_vars": [], "r_vars": []}
            for m in request.models
        }

        for origin_d in eval_origins:
            # History strictly up to origin_d
            hist_returns = np.array(
                [returns_map[d] for d in dates if d <= origin_d], dtype=np.float64
            )
            if len(hist_returns) < 30:
                continue

            # Realized future returns in target window
            future_dates = [d for d in dates if origin_d < d <= (origin_d + timedelta(days=request.forecast_horizon * 2))]
            if len(future_dates) < request.forecast_horizon:
                continue
            target_dates = future_dates[: request.forecast_horizon]
            realized_v = float(np.sum(np.array([returns_map[d] for d in target_dates]) ** 2))

            for m in request.models:
                if m == ForecastModelType.ROLLING_HISTORICAL:
                    out = forecast_rolling_historical_variance(hist_returns, horizon=request.forecast_horizon)
                elif m == ForecastModelType.EWMA:
                    out = forecast_ewma_variance(hist_returns, horizon=request.forecast_horizon)
                elif m == ForecastModelType.GARCH_1_1:
                    out = fit_and_forecast_garch_1_1(hist_returns, horizon=request.forecast_horizon)
                else:
                    continue

                f_v = out["cumulative_horizon_variance"]
                eval_out = evaluate_forecast_realized(f_v, realized_v)

                model_stats[m]["mae"].append(eval_out["absolute_error_volatility"])
                model_stats[m]["rmse"].append(eval_out["squared_error_volatility"])
                model_stats[m]["bias"].append(eval_out["forecast_error_volatility"])
                model_stats[m]["qlike"].append(eval_out["qlike_loss"])
                model_stats[m]["f_vars"].append(f_v)
                model_stats[m]["r_vars"].append(realized_v)

        summaries: List[ModelComparisonSummary] = []
        for m in request.models:
            st = model_stats[m]
            cnt = len(st["mae"])
            if cnt > 0:
                mae_val = float(np.mean(st["mae"]))
                rmse_val = math.sqrt(float(np.mean(st["rmse"])))
                bias_val = float(np.mean(st["bias"]))
                qlike_val = float(np.mean(st["qlike"]))
                calib = compute_calibration_regression(np.array(st["f_vars"]), np.array(st["r_vars"]))
                slope_val = calib["slope"]
                r2_val = calib["r_squared"]
            else:
                mae_val = 0.0
                rmse_val = 0.0
                bias_val = 0.0
                qlike_val = 0.0
                slope_val = 1.0
                r2_val = 0.0

            summaries.append(
                ModelComparisonSummary(
                    model_name=m,
                    forecast_count=cnt,
                    evaluated_count=cnt,
                    mean_absolute_error=Decimal(str(round(mae_val, 6))),
                    root_mean_squared_error=Decimal(str(round(rmse_val, 6))),
                    mean_bias=Decimal(str(round(bias_val, 6))),
                    average_qlike_loss=Decimal(str(round(qlike_val, 6))),
                    calibration_slope=Decimal(str(round(slope_val, 6))),
                    calibration_r_squared=Decimal(str(round(r2_val, 6))),
                )
            )

        # Identify best models
        valid_summaries = [s for s in summaries if s.evaluated_count > 0]
        best_mae_model = min(valid_summaries, key=lambda s: s.mean_absolute_error).model_name.value if valid_summaries else None
        best_qlike_model = min(valid_summaries, key=lambda s: s.average_qlike_loss).model_name.value if valid_summaries else None

        comp_code = f"COMP_{uuid.uuid4().hex[:12].upper()}"
        comp_rec = RiskForecastModelComparison(
            comparison_code=comp_code,
            entity_id=request.entity_id,
            forecast_horizon=request.forecast_horizon,
            evaluation_start_date=start_d,
            evaluation_end_date=end_d,
            sample_count=len(eval_origins),
            model_summaries={s.model_name.value: s.model_dump(mode="json") for s in summaries},
            best_model_by_mae=best_mae_model,
            best_model_by_qlike=best_qlike_model,
            created_at=datetime.utcnow(),
        )
        await self.repo.save_comparison(comp_rec)

        return ModelComparisonResponse(
            comparison_code=comp_code,
            entity_id=request.entity_id,
            forecast_horizon=request.forecast_horizon,
            evaluation_start_date=start_d,
            evaluation_end_date=end_d,
            sample_count=len(eval_origins),
            models=summaries,
            best_model_by_mae=best_mae_model,
            best_model_by_qlike=best_qlike_model,
        )
