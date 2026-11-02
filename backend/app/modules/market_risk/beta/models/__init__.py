"""
M07.07 Portfolio Beta Database Models.
"""
from datetime import datetime, timezone
import enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import (
    String,
    DateTime,
    Numeric,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
    Enum,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BetaModelType(str, enum.Enum):
    OLS_WITH_INTERCEPT = "OLS_WITH_INTERCEPT"
    OLS_WITHOUT_INTERCEPT = "OLS_WITHOUT_INTERCEPT"
    EXCESS_RETURN_CAPM = "EXCESS_RETURN_CAPM"


class BetaCalculationMethod(str, enum.Enum):
    DIRECT_PORTFOLIO_REGRESSION = "DIRECT_PORTFOLIO_REGRESSION"
    CURRENT_WEIGHT_IMPLIED = "CURRENT_WEIGHT_IMPLIED"
    HISTORICAL_WEIGHT_RECONSTRUCTION = "HISTORICAL_WEIGHT_RECONSTRUCTION"


class StandardErrorMethod(str, enum.Enum):
    OLS_CONVENTIONAL = "OLS_CONVENTIONAL"
    HC3_HETEROSKEDASTICITY_ROBUST = "HC3_HETEROSKEDASTICITY_ROBUST"
    HAC_NEWEY_WEST = "HAC_NEWEY_WEST"


class BetaRegressionStatus(str, enum.Enum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    ZERO_BENCHMARK_VARIANCE = "ZERO_BENCHMARK_VARIANCE"
    ZERO_SECURITY_VARIANCE = "ZERO_SECURITY_VARIANCE"
    DEGENERATE_REGRESSION = "DEGENERATE_REGRESSION"
    ALIGNMENT_FAILED = "ALIGNMENT_FAILED"


class BenchmarkReference(Base):
    """
    Authoritative benchmark registry for market indices and reference assets.
    """
    __tablename__ = "m07_benchmark_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    benchmark_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), default="NSE_INDICES", nullable=False)
    market: Mapped[str] = mapped_column(String(32), default="INDIA", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    return_basis: Mapped[str] = mapped_column(String(32), default="TOTAL_RETURN", nullable=False)  # or PRICE_RETURN
    time_zone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class BetaConfiguration(Base):
    """
    Configuration profile for beta regressions.
    """
    __tablename__ = "m07_beta_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    config_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    default_benchmark_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("m07_benchmark_references.id", ondelete="SET NULL"), nullable=True
    )
    model_type: Mapped[BetaModelType] = mapped_column(
        Enum(BetaModelType, native_enum=False), default=BetaModelType.OLS_WITH_INTERCEPT, nullable=False
    )
    standard_error_method: Mapped[StandardErrorMethod] = mapped_column(
        Enum(StandardErrorMethod, native_enum=False), default=StandardErrorMethod.OLS_CONVENTIONAL, nullable=False
    )
    default_lookback_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    min_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    confidence_level: Mapped[float] = mapped_column(Numeric(5, 4), default=0.9500, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class BetaCalculationRun(Base):
    """
    Execution run metadata audit trail for beta calculations.
    """
    __tablename__ = "m07_beta_calculation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    calculation_type: Mapped[str] = mapped_column(String(32), nullable=False)  # SECURITY, PORTFOLIO_DIRECT, PORTFOLIO_WEIGHTED
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    benchmark_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_benchmark_references.id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    model_type: Mapped[BetaModelType] = mapped_column(
        Enum(BetaModelType, native_enum=False), nullable=False
    )
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SecurityBetaResult(Base):
    """
    Individual security beta against a benchmark.
    """
    __tablename__ = "m07_security_beta_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_beta_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    benchmark_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    benchmark_code: Mapped[str] = mapped_column(String(64), nullable=False)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Regression outputs
    beta_value: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    alpha_value: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    r_squared: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    adjusted_r_squared: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    beta_standard_error: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    beta_t_statistic: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    p_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 8), nullable=True)
    ci_lower_95: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    ci_upper_95: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    residual_std_error: Mapped[Optional[float]] = mapped_column(Numeric(12, 8), nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    
    regression_status: Mapped[BetaRegressionStatus] = mapped_column(
        Enum(BetaRegressionStatus, native_enum=False), default=BetaRegressionStatus.VALID, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_sec_beta_lookup", "instrument_id", "benchmark_id", "as_of_date"),
    )


class PortfolioBetaResult(Base):
    """
    Portfolio beta results (direct regression or weighted aggregation).
    """
    __tablename__ = "m07_portfolio_beta_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    calculation_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    benchmark_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    benchmark_code: Mapped[str] = mapped_column(String(64), nullable=False)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[BetaCalculationMethod] = mapped_column(
        Enum(BetaCalculationMethod, native_enum=False), nullable=False
    )
    portfolio_beta: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    portfolio_alpha: Mapped[Optional[float]] = mapped_column(Numeric(12, 8), nullable=True)
    r_squared: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    beta_standard_error: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    beta_t_statistic: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_basis: Mapped[str] = mapped_column(String(32), default="PORTFOLIO_NAV", nullable=False)
    
    # Constituent details for weighted aggregation
    asset_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    asset_symbols: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    weights: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)
    individual_betas: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)
    beta_contributions: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)
    
    regression_status: Mapped[BetaRegressionStatus] = mapped_column(
        Enum(BetaRegressionStatus, native_enum=False), default=BetaRegressionStatus.VALID, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_port_beta_lookup", "portfolio_id", "benchmark_id", "as_of_date"),
    )
