"""
M07.10 Risk Forecasting Pydantic Schemas.
Request and response models for:
- Forecasting execution (single & multi-step)
- Rolling forecasts retrieval
- Model comparison
- Forecast evaluation
- Configuration management
- Monitoring alerts
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.market_risk.risk_forecasting.models import (
    ForecastModelType,
    ForecastCalculationScope,
    ForecastTargetMeasure,
    RealizedVarianceProxyType,
    ForecastStatus,
    EvaluationStatus,
    MonitoringEventType,
)


class ForecastStepPoint(BaseModel):
    step_number: int
    target_date: date
    step_variance: Decimal
    step_volatility: Decimal
    cumulative_variance: Decimal
    cumulative_volatility: Decimal
    annualized_volatility: Decimal
    model_config = ConfigDict(from_attributes=True)


class VolatilityForecastRequest(BaseModel):
    scope: ForecastCalculationScope = Field(
        ForecastCalculationScope.INSTRUMENT, description="INSTRUMENT or PORTFOLIO"
    )
    entity_id: str = Field(..., description="Target instrument_id or portfolio_id")
    model_name: ForecastModelType = Field(
        ForecastModelType.EWMA, description="ROLLING_HISTORICAL, EWMA, or GARCH_1_1"
    )
    forecast_origin: Optional[date] = Field(None, description="Forecast origin cutoff date (default latest)")
    forecast_horizon: int = Field(1, ge=1, le=60, description="Forecast horizon in trading sessions")
    lookback_days: int = Field(252, ge=20, le=1260, description="Estimation window in calendar days")
    ewma_decay_factor: Decimal = Field(Decimal("0.9400"), description="EWMA lambda parameter")
    annualization_factor: Decimal = Field(Decimal("252.0"), description="Annualization factor")
    model_config = ConfigDict(from_attributes=True)


class VolatilityForecastResponse(BaseModel):
    calculation_id: str
    scope: ForecastCalculationScope
    entity_id: str
    model_name: ForecastModelType
    model_version: str
    forecast_origin: date
    target_start_date: date
    target_end_date: date
    forecast_horizon: int
    annualization_factor: Decimal

    # Core predictions
    one_step_forecast_variance: Decimal
    one_step_forecast_volatility: Decimal
    cumulative_horizon_variance: Decimal
    cumulative_horizon_volatility: Decimal
    annualized_forecast_volatility: Decimal

    # Estimated model parameters & fit diagnostics
    model_parameters: Optional[Dict[str, Any]] = None
    fit_diagnostics: Optional[Dict[str, Any]] = None

    # Step-by-step path
    step_results: List[ForecastStepPoint] = []
    status: ForecastStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ForecastEvaluationItem(BaseModel):
    evaluation_id: int
    calculation_id: str
    target_start_date: date
    target_end_date: date
    realized_proxy_type: RealizedVarianceProxyType
    forecast_variance: Decimal
    realized_variance: Decimal
    forecast_volatility: Decimal
    realized_volatility: Decimal
    forecast_error_volatility: Decimal
    absolute_error_volatility: Decimal
    squared_error_volatility: Decimal
    qlike_loss: Optional[Decimal] = None
    evaluation_status: EvaluationStatus
    model_config = ConfigDict(from_attributes=True)


class ModelComparisonRequest(BaseModel):
    scope: ForecastCalculationScope = ForecastCalculationScope.INSTRUMENT
    entity_id: str
    models: List[ForecastModelType] = [
        ForecastModelType.ROLLING_HISTORICAL,
        ForecastModelType.EWMA,
        ForecastModelType.GARCH_1_1,
    ]
    forecast_horizon: int = Field(1, ge=1, le=20)
    evaluation_start_date: Optional[date] = None
    evaluation_end_date: Optional[date] = None
    model_config = ConfigDict(from_attributes=True)


class ModelComparisonSummary(BaseModel):
    model_name: ForecastModelType
    forecast_count: int
    evaluated_count: int
    mean_absolute_error: Decimal
    root_mean_squared_error: Decimal
    mean_bias: Decimal
    average_qlike_loss: Decimal
    calibration_slope: Decimal
    calibration_r_squared: Decimal
    model_config = ConfigDict(from_attributes=True)


class ModelComparisonResponse(BaseModel):
    comparison_code: str
    entity_id: str
    forecast_horizon: int
    evaluation_start_date: date
    evaluation_end_date: date
    sample_count: int
    models: List[ModelComparisonSummary]
    best_model_by_mae: Optional[str] = None
    best_model_by_qlike: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class MonitoringEventResponse(BaseModel):
    id: int
    entity_id: str
    model_name: ForecastModelType
    event_type: MonitoringEventType
    detected_at: datetime
    observed_metric: str
    observed_value: Decimal
    threshold_value: Decimal
    details: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)
