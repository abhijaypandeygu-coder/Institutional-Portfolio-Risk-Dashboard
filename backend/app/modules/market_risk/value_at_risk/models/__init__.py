"""
Module M07.02: Value at Risk (VaR) - SQLAlchemy 2.x Models.
Defines database entities for VaR configurations, calculation results, historical scenarios,
covariance matrices, Monte Carlo simulation metadata, risk contributions, and diagnostics.
"""
import enum
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Enum as SAEnum,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VaRMethodology(str, enum.Enum):
    HISTORICAL = "HISTORICAL"
    PARAMETRIC = "PARAMETRIC"
    MONTE_CARLO = "MONTE_CARLO"


class HistoricalVaRSubMethod(str, enum.Enum):
    PORTFOLIO_RETURNS = "PORTFOLIO_RETURNS"
    HISTORICAL_SIMULATION = "HISTORICAL_SIMULATION"


class VaRDistributionAssumption(str, enum.Enum):
    EMPIRICAL = "EMPIRICAL"
    NORMAL = "NORMAL"
    STUDENT_T = "STUDENT_T"


class VaRValuationBaseType(str, enum.Enum):
    PORTFOLIO_NAV = "PORTFOLIO_NAV"
    PORTFOLIO_GROSS_EXPOSURE = "PORTFOLIO_GROSS_EXPOSURE"
    PORTFOLIO_NET_EXPOSURE = "PORTFOLIO_NET_EXPOSURE"
    CUSTOM_AMOUNT = "CUSTOM_AMOUNT"


class VaRQuantileMethod(str, enum.Enum):
    NEAREST_RANK = "NEAREST_RANK"
    LINEAR_INTERPOLATION = "LINEAR_INTERPOLATION"
    EXACT_ORDER_STATISTIC = "EXACT_ORDER_STATISTIC"


class VaRCalculationStatus(str, enum.Enum):
    CALCULATED = "CALCULATED"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    WEAK_TAIL_SUPPORT = "WEAK_TAIL_SUPPORT"
    INVALID_COVARIANCE = "INVALID_COVARIANCE"
    SIMULATION_CONVERGENCE_WARNING = "SIMULATION_CONVERGENCE_WARNING"
    DENOMINATOR_UNAVAILABLE = "DENOMINATOR_UNAVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class VaRTrendStatus(str, enum.Enum):
    VAR_INCREASING = "VAR_INCREASING"
    VAR_DECREASING = "VAR_DECREASING"
    VAR_STABLE = "VAR_STABLE"
    VAR_ELEVATED = "VAR_ELEVATED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INCOMPARABLE_METHODOLOGY = "INCOMPARABLE_METHODOLOGY"


class VaRModelConfig(Base):
    """
    Versioned model configuration controlling VaR parameters, assumptions, and conventions.
    """
    __tablename__ = "m07_var_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VARCFG_{uuid.uuid4().hex[:12].upper()}"
    )
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    methodology: Mapped[VaRMethodology] = mapped_column(
        SAEnum(VaRMethodology, native_enum=False), default=VaRMethodology.HISTORICAL, nullable=False
    )
    historical_sub_method: Mapped[HistoricalVaRSubMethod] = mapped_column(
        SAEnum(HistoricalVaRSubMethod, native_enum=False), default=HistoricalVaRSubMethod.PORTFOLIO_RETURNS, nullable=False
    )
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.9900"), nullable=False)  # 0.95, 0.99
    holding_horizon_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1, 5, 10
    valuation_base_type: Mapped[VaRValuationBaseType] = mapped_column(
        SAEnum(VaRValuationBaseType, native_enum=False), default=VaRValuationBaseType.PORTFOLIO_NAV, nullable=False
    )
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    lookback_period_days: Mapped[int] = mapped_column(Integer, default=252, nullable=False)  # 20, 60, 252
    
    distribution_assumption: Mapped[VaRDistributionAssumption] = mapped_column(
        SAEnum(VaRDistributionAssumption, native_enum=False), default=VaRDistributionAssumption.EMPIRICAL, nullable=False
    )
    quantile_method: Mapped[VaRQuantileMethod] = mapped_column(
        SAEnum(VaRQuantileMethod, native_enum=False), default=VaRQuantileMethod.LINEAR_INTERPOLATION, nullable=False
    )
    covariance_method: Mapped[str] = mapped_column(String(64), default="SAMPLE_COVARIANCE", nullable=False)
    
    # Monte Carlo parameters
    simulation_count: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    random_seed: Mapped[Optional[int]] = mapped_column(Integer, default=42, nullable=True)
    random_generator: Mapped[str] = mapped_column(String(64), default="PCG64", nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class VaRResult(Base):
    """
    Authoritative VaR estimate record for a portfolio snapshot.
    Preserves loss quantile, monetary loss threshold, percentage loss threshold, and assumptions.
    """
    __tablename__ = "m07_var_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VAR_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    methodology: Mapped[VaRMethodology] = mapped_column(
        SAEnum(VaRMethodology, native_enum=False), nullable=False
    )
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    holding_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Valuation Base & Loss Quantiles
    valuation_base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    signed_loss_quantile: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)  # Raw statistical return quantile (-R)
    var_return_percentage: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)  # Non-negative return loss % (or 0 if gain)
    var_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # Monetary loss threshold (V0 * var_return)
    
    # Model Metadata & Sampling
    distribution_assumption: Mapped[str] = mapped_column(String(32), default="EMPIRICAL", nullable=False)
    lookback_observations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tail_observations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    portfolio_period_volatility: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    expected_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    
    simulation_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    successful_simulation_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    random_seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    calculation_status: Mapped[VaRCalculationStatus] = mapped_column(
        SAEnum(VaRCalculationStatus, native_enum=False), default=VaRCalculationStatus.CALCULATED, nullable=False
    )
    data_quality_status: Mapped[str] = mapped_column(String(32), default="PASSED", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_var_port_asof_method", "portfolio_id", "as_of_date", "methodology"),
    )


class VaRRiskContribution(Base):
    """
    Component / marginal risk attribution across instruments, sectors, or countries.
    """
    __tablename__ = "m07_var_risk_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contribution_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VARC_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m07_var_results.result_id", ondelete="CASCADE"), nullable=False, index=True
    )
    grouping_dimension: Mapped[str] = mapped_column(String(32), default="INSTRUMENT", nullable=False)  # INSTRUMENT, SECTOR, COUNTRY
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(128), nullable=False)
    
    weight_percentage: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    marginal_var: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    component_var_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    percentage_of_total_var: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    is_additive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attribution_method: Mapped[str] = mapped_column(String(64), default="EULER_MARGINAL", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class VaRHistoricalScenario(Base):
    """
    Empirical tail scenario observations contributing to Historical or Simulation VaR.
    """
    __tablename__ = "m07_var_historical_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VSCEN_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m07_var_results.result_id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    portfolio_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    portfolio_loss: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    loss_return: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    is_in_tail: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class VaRCalculationDiagnostic(Base):
    """
    Quality diagnostics ledger for VaR models (e.g. singular covariance, insufficient tail sample).
    """
    __tablename__ = "m07_var_calculation_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VARDIAG_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    diagnostic_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="WARNING", nullable=False)  # INFO, WARNING, ERROR
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

