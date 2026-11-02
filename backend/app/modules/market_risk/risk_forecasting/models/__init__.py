"""
M07.10 Risk Forecasting Database Models and Enums.
Defines entities for:
- Forecasting configurations (versioned models and parameters)
- Calculation runs (run metadata, estimation windows, and line of sight)
- Volatility forecast results (1-step and multi-step variance/volatility predictions)
- Model parameter histories (historical parameter tracking)
- Forecast evaluation results (loss metrics: MAE, RMSE, QLIKE, calibration)
- Model comparison results (side-by-side performance on common origins)
- Forecast monitoring events (underforecasting alerts and calibration drift)
"""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class ForecastModelType(str, Enum):
    ROLLING_HISTORICAL = "ROLLING_HISTORICAL"
    EWMA = "EWMA"
    GARCH_1_1 = "GARCH_1_1"


class ForecastCalculationScope(str, Enum):
    INSTRUMENT = "INSTRUMENT"
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_GROUP = "PORTFOLIO_GROUP"
    CUSTOM_UNIVERSE = "CUSTOM_UNIVERSE"


class ForecastTargetMeasure(str, Enum):
    PERIOD_VARIANCE = "PERIOD_VARIANCE"
    PERIOD_VOLATILITY = "PERIOD_VOLATILITY"
    CUMULATIVE_HORIZON_VARIANCE = "CUMULATIVE_HORIZON_VARIANCE"
    CUMULATIVE_HORIZON_VOLATILITY = "CUMULATIVE_HORIZON_VOLATILITY"


class RealizedVarianceProxyType(str, Enum):
    SQUARED_RETURN = "SQUARED_RETURN"
    INTRADAY_REALIZED_VARIANCE = "INTRADAY_REALIZED_VARIANCE"
    HISTORICAL_CLOSE_VARIANCE = "HISTORICAL_CLOSE_VARIANCE"


class ForecastStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    OPTIMIZER_FAILED = "OPTIMIZER_FAILED"
    NON_STATIONARY = "NON_STATIONARY"
    FAILED = "FAILED"


class EvaluationStatus(str, Enum):
    AWAITING_REALIZED_DATA = "AWAITING_REALIZED_DATA"
    EVALUATED = "EVALUATED"
    INSUFFICIENT_REALIZED_DATA = "INSUFFICIENT_REALIZED_DATA"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    SUPERSEDED = "SUPERSEDED"


class MonitoringEventType(str, Enum):
    PERSISTENT_UNDERFORECAST = "PERSISTENT_UNDERFORECAST"
    PERSISTENT_OVERFORECAST = "PERSISTENT_OVERFORECAST"
    CALIBRATION_DRIFT = "CALIBRATION_DRIFT"
    QLIKE_SPIKE = "QLIKE_SPIKE"
    CONVERGENCE_FAILURE = "CONVERGENCE_FAILURE"


class RiskForecastConfiguration(Base):
    """
    Versioned forecasting configuration defining model specifications,
    lookback windows, horizons, and decay/hyperparameters.
    """
    __tablename__ = "m07_10_forecast_configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    configuration_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_name: Mapped[ForecastModelType] = mapped_column(
        SQLEnum(ForecastModelType), default=ForecastModelType.EWMA, nullable=False
    )
    calculation_scope: Mapped[ForecastCalculationScope] = mapped_column(
        SQLEnum(ForecastCalculationScope), default=ForecastCalculationScope.INSTRUMENT, nullable=False
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Return & observation settings
    return_type: Mapped[str] = mapped_column(String(32), default="LOGARITHMIC", nullable=False)
    return_frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    estimation_window: Mapped[int] = mapped_column(Integer, default=252, nullable=False)
    forecast_horizon: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    forecast_target: Mapped[ForecastTargetMeasure] = mapped_column(
        SQLEnum(ForecastTargetMeasure), default=ForecastTargetMeasure.PERIOD_VOLATILITY, nullable=False
    )
    annualization_factor: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("252.0"), nullable=False
    )

    # Hyperparameters
    ewma_decay_factor: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 4), default=Decimal("0.9400"), nullable=True
    )
    minimum_observations: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RiskForecastCalculationRun(Base):
    """
    Execution header record capturing a point-in-time risk forecast.
    Preserves strict forecast origin, estimation boundaries, and data watermark.
    """
    __tablename__ = "m07_10_forecast_runs"

    calculation_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[ForecastCalculationScope] = mapped_column(
        SQLEnum(ForecastCalculationScope), nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # instrument_id or portfolio_id
    model_name: Mapped[ForecastModelType] = mapped_column(
        SQLEnum(ForecastModelType), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)

    # Time boundaries
    forecast_origin: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    target_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_horizon: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    # Sample statistics
    estimation_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    input_data_watermark: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Estimated model parameters (e.g. {omega, alpha, beta, persistence, long_run_var})
    model_parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fit_diagnostics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Summary 1-step forecast outputs
    one_step_forecast_variance: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    one_step_forecast_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    cumulative_horizon_variance: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    cumulative_horizon_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    annualized_forecast_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)

    status: Mapped[ForecastStatus] = mapped_column(
        SQLEnum(ForecastStatus), default=ForecastStatus.VALID, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    step_results: Mapped[List["VolatilityForecastResult"]] = relationship(
        "VolatilityForecastResult",
        back_populates="calculation_run",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[List["RiskForecastEvaluationResult"]] = relationship(
        "RiskForecastEvaluationResult",
        back_populates="calculation_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_m07_10_run_entity_origin", "entity_id", "forecast_origin"),
    )


class VolatilityForecastResult(Base):
    """
    Step-by-step forecast path for horizons h = 1, 2, ..., H.
    """
    __tablename__ = "m07_10_volatility_forecast_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calculation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("m07_10_forecast_runs.calculation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to H
    target_date: Mapped[date] = mapped_column(Date, nullable=False)

    step_variance: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    step_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    cumulative_variance: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    cumulative_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    annualized_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)

    calculation_run: Mapped["RiskForecastCalculationRun"] = relationship(
        "RiskForecastCalculationRun", back_populates="step_results"
    )

    __table_args__ = (
        Index("idx_m07_10_step_calc_step", "calculation_id", "step_number"),
    )


class RiskForecastEvaluationResult(Base):
    """
    Ex-post evaluation of a forecast against subsequently realized market outcomes.
    Captures forecast error, MAE, RMSE, QLIKE loss, and calibration slope.
    """
    __tablename__ = "m07_10_forecast_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calculation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("m07_10_forecast_runs.calculation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    realized_proxy_type: Mapped[RealizedVarianceProxyType] = mapped_column(
        SQLEnum(RealizedVarianceProxyType), default=RealizedVarianceProxyType.SQUARED_RETURN, nullable=False
    )
    target_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Quantities compared
    forecast_variance: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    realized_variance: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    forecast_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    realized_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)

    # Error metrics: Error = Forecast - Realized (+ is overforecasting, - is underforecasting)
    forecast_error_variance: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    forecast_error_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    absolute_error_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    squared_error_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    qlike_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)

    evaluation_status: Mapped[EvaluationStatus] = mapped_column(
        SQLEnum(EvaluationStatus), default=EvaluationStatus.EVALUATED, nullable=False
    )
    diagnostics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    calculation_run: Mapped["RiskForecastCalculationRun"] = relationship(
        "RiskForecastCalculationRun", back_populates="evaluations"
    )


class RiskForecastModelComparison(Base):
    """
    Comparison record tracking competing models over common origins and evaluation horizons.
    """
    __tablename__ = "m07_10_model_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comparison_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    forecast_horizon: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evaluation_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    evaluation_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Serialized comparison results (e.g. per-model MAE, RMSE, QLIKE, bias, calibration slope)
    model_summaries: Mapped[dict] = mapped_column(JSON, nullable=False)
    best_model_by_mae: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    best_model_by_qlike: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RiskForecastMonitoringEvent(Base):
    """
    Audit log of forecast risk alerts: persistent underforecasting, calibration drift, or optimizer failures.
    """
    __tablename__ = "m07_10_monitoring_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_name: Mapped[ForecastModelType] = mapped_column(SQLEnum(ForecastModelType), nullable=False)
    event_type: Mapped[MonitoringEventType] = mapped_column(SQLEnum(MonitoringEventType), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    observed_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
