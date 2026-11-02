"""
Module M07.03: Expected Shortfall (ES) / Conditional Value at Risk (CVaR) Models.
Provides data structures for:
1. ExpectedShortfallConfig: Reusable model configurations (confidence, horizon, methodology, tail weighting).
2. ExpectedShortfallResult: Authoritative tail loss statistics, VaR references, Tail Excess, and data quality.
3. ESTailObservation: Scenario and empirical observations in the selected tail with fractional weights.
4. ESDiagnostic: Tail sample size, effective sample count, boundary sensitivity, and dispersion.
5. ESContribution: Scenario-weighted instrument, sector, and risk factor tail risk attribution.
6. ESHistory: Point-in-time trend tracking for Expected Shortfall.
"""
from datetime import datetime, timezone, date
from decimal import Decimal
import enum
from typing import Optional, List, Dict, Any
import uuid
from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Date,
    Boolean,
    Text,
    Enum as SAEnum,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ESMethodology(str, enum.Enum):
    HISTORICAL_PORTFOLIO_RETURNS = "HISTORICAL_PORTFOLIO_RETURNS"
    HISTORICAL_SIMULATION = "HISTORICAL_SIMULATION"
    MONTE_CARLO = "MONTE_CARLO"


class ESTailWeightingMethod(str, enum.Enum):
    FRACTIONAL_BOUNDARY = "FRACTIONAL_BOUNDARY"
    STRICT_EXCESS = "STRICT_EXCESS"  # Disclosed fallback for strict boundary exclusion
    EXPONENTIAL_TAIL = "EXPONENTIAL_TAIL"


class ESQuantileMethod(str, enum.Enum):
    LINEAR_INTERPOLATION = "LINEAR_INTERPOLATION"
    NEAREST_RANK = "NEAREST_RANK"


class ESTailStabilityStatus(str, enum.Enum):
    STABLE = "STABLE"
    MODERATELY_STABLE = "MODERATELY_STABLE"
    TAIL_BOUNDARY_SENSITIVE = "TAIL_BOUNDARY_SENSITIVE"
    UNSTABLE = "UNSTABLE"
    INSUFFICIENT_TAIL_SAMPLE = "INSUFFICIENT_TAIL_SAMPLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ESCalculationStatus(str, enum.Enum):
    CALCULATED = "CALCULATED"
    CALCULATED_WITH_WARNINGS = "CALCULATED_WITH_WARNINGS"
    INSUFFICIENT_TAIL_SAMPLE = "INSUFFICIENT_TAIL_SAMPLE"
    WEAK_TAIL_SUPPORT = "WEAK_TAIL_SUPPORT"
    INCOMPLETE_HISTORICAL_DATA = "INCOMPLETE_HISTORICAL_DATA"
    INVALID_LOSS_DISTRIBUTION = "INVALID_LOSS_DISTRIBUTION"
    SIMULATION_FAILURE = "SIMULATION_FAILURE"
    FAILED = "FAILED"


class ESTrendDirection(str, enum.Enum):
    ES_INCREASING = "ES_INCREASING"
    ES_DECREASING = "ES_DECREASING"
    ES_STABLE = "ES_STABLE"
    TAIL_SEVERITY_INCREASING = "TAIL_SEVERITY_INCREASING"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class ExpectedShortfallConfig(Base):
    """
    Configuration specification for Expected Shortfall tail estimation.
    """
    __tablename__ = "m07_expected_shortfall_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ESCFG_{uuid.uuid4().hex[:12].upper()}"
    )
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    methodology: Mapped[ESMethodology] = mapped_column(
        SAEnum(ESMethodology, native_enum=False), default=ESMethodology.HISTORICAL_PORTFOLIO_RETURNS, nullable=False
    )
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.9750"), nullable=False)
    tail_probability: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0250"), nullable=False)
    holding_horizon_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valuation_base_type: Mapped[str] = mapped_column(String(64), default="PORTFOLIO_NAV", nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    lookback_period_days: Mapped[int] = mapped_column(Integer, default=252, nullable=False)

    quantile_method: Mapped[ESQuantileMethod] = mapped_column(
        SAEnum(ESQuantileMethod, native_enum=False), default=ESQuantileMethod.LINEAR_INTERPOLATION, nullable=False
    )
    tail_weighting_method: Mapped[ESTailWeightingMethod] = mapped_column(
        SAEnum(ESTailWeightingMethod, native_enum=False), default=ESTailWeightingMethod.FRACTIONAL_BOUNDARY, nullable=False
    )

    simulation_count: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    random_seed: Mapped[Optional[int]] = mapped_column(Integer, default=42, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ExpectedShortfallResult(Base):
    """
    Authoritative Expected Shortfall (CVaR) execution result.
    Captures average tail loss, corresponding VaR, Tail Excess, and data lineage.
    """
    __tablename__ = "m07_expected_shortfall_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ES_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    var_result_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    methodology: Mapped[ESMethodology] = mapped_column(
        SAEnum(ESMethodology, native_enum=False), nullable=False
    )
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    tail_probability: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    holding_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    valuation_base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Core Quantile and ES metrics
    var_return_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)  # e.g. 2.50%
    var_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    signed_var_loss_quantile: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    es_return_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)  # e.g. 3.20%
    es_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    signed_es_loss_average: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    # Tail Excess = ES - VaR
    tail_excess_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tail_excess_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    es_to_var_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    # Tail Sample Counts & Diagnostics
    total_observations_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_observations_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_tail_observations: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    full_tail_observations_count: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_tail_sample_size: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    boundary_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("1.0"), nullable=False)

    # Tail loss dispersion
    worst_tail_loss_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    tail_median_loss_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    tail_standard_deviation: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)

    quantile_method: Mapped[str] = mapped_column(String(64), default="LINEAR_INTERPOLATION", nullable=False)
    tail_weighting_method: Mapped[str] = mapped_column(String(64), default="FRACTIONAL_BOUNDARY", nullable=False)
    tail_stability_status: Mapped[ESTailStabilityStatus] = mapped_column(
        SAEnum(ESTailStabilityStatus, native_enum=False), default=ESTailStabilityStatus.STABLE, nullable=False
    )
    calculation_status: Mapped[ESCalculationStatus] = mapped_column(
        SAEnum(ESCalculationStatus, native_enum=False), default=ESCalculationStatus.CALCULATED, nullable=False
    )
    data_quality_status: Mapped[str] = mapped_column(String(64), default="PASSED", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_es_port_date", "portfolio_id", "as_of_date"),
        Index("ix_m07_es_port_method", "portfolio_id", "methodology"),
    )


class ESTailObservation(Base):
    """
    Detailed observation or scenario in the adverse tail of the loss distribution.
    Records portfolio P&L, loss, and fractional boundary weighting.
    """
    __tablename__ = "m07_es_tail_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scenario_index: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    observation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    portfolio_return: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    portfolio_loss: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    tail_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    is_boundary_observation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    loss_amount_native: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    __table_args__ = (
        Index("ix_m07_es_obs_result", "result_id"),
    )


class ESDiagnostic(Base):
    """
    Statistical diagnostics evaluating tail coverage, effective degrees of freedom,
    and boundary sensitivity for Expected Shortfall results.
    """
    __tablename__ = "m07_es_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    diagnostic_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="INFO", nullable=False)  # INFO, WARNING, ERROR
    diagnostic_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ESContribution(Base):
    """
    Scenario-weighted tail risk attribution across instruments, sectors, or factors.
    Decomposes Expected Shortfall into constituent tail contributions.
    """
    __tablename__ = "m07_es_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    grouping_dimension: Mapped[str] = mapped_column(String(64), default="INSTRUMENT", nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    weight_percentage: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    average_tail_loss_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    contribution_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    percentage_of_total_es: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    is_additive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attribution_method: Mapped[str] = mapped_column(String(64), default="SCENARIO_WEIGHTED_AVERAGE", nullable=False)

    __table_args__ = (
        Index("ix_m07_es_contrib_res", "result_id"),
    )


class ESHistory(Base):
    """
    Historical Expected Shortfall trend tracking point.
    """
    __tablename__ = "m07_es_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    result_id: Mapped[str] = mapped_column(String(64), nullable=False)
    methodology: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    holding_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    valuation_base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    es_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    es_return_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    var_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tail_excess_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tail_stability_status: Mapped[str] = mapped_column(String(64), default="STABLE", nullable=False)
    trend_direction: Mapped[ESTrendDirection] = mapped_column(
        SAEnum(ESTrendDirection, native_enum=False), default=ESTrendDirection.ES_STABLE, nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_es_hist_port_date", "portfolio_id", "as_of_date"),
    )
