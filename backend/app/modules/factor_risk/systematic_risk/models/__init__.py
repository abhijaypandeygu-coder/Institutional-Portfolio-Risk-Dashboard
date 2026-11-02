"""
SQLAlchemy 2.x Database Models for M08.05 Systematic Risk Analytics.
Establishes tables for:
1. m08_05_risk_configs: Versioned systematic risk & covariance estimation settings
2. m08_05_factor_covariance_snapshots: Validated factor covariance matrices & diagnostics
3. m08_05_systematic_risk_runs: Execution header for instrument & portfolio systematic risk runs
4. m08_05_instrument_systematic_risk: Security-level common-factor variance, volatility, and residual stats
5. m08_05_portfolio_systematic_risk: Portfolio-level systematic risk, cross-security variance & coverage metrics
6. m08_05_factor_scenario_configs: User-defined factor shock scenarios & stress assumptions
7. m08_05_factor_scenario_shocks: Exact factor-by-factor shock values
8. m08_05_factor_scenario_runs: Scenario simulation run results (percentage & monetary impact)
9. m08_05_factor_scenario_components: Factor-by-factor return and dollar impact contributions
10. m08_05_model_coverage_records: Point-in-time holding-level coverage diagnostics and reasons
"""
from datetime import datetime, date, timezone
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.modules.factor_risk.factor_definition.models import (
    MarketScope,
    FactorLifecycleStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# 1. ENUMERATIONS
# ============================================================================

class CovarianceMethod(str, Enum):
    SAMPLE = "SAMPLE"
    EXPONENTIALLY_WEIGHTED = "EXPONENTIALLY_WEIGHTED"
    SHRINKAGE = "SHRINKAGE"
    REGIME_SPECIFIC = "REGIME_SPECIFIC"


class SystematicTargetType(str, Enum):
    INSTRUMENT = "INSTRUMENT"
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_GROUP = "PORTFOLIO_GROUP"


class SystematicRunStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED_MISSING_EXPOSURE = "BLOCKED_MISSING_EXPOSURE"
    BLOCKED_MISSING_COVARIANCE = "BLOCKED_MISSING_COVARIANCE"
    DEGRADED_LOW_COVERAGE = "DEGRADED_LOW_COVERAGE"


class ModelCoverageStatus(str, Enum):
    COVERED = "COVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    MISSING_FACTOR_LOADING = "MISSING_FACTOR_LOADING"
    MISSING_FACTOR_RETURN_HISTORY = "MISSING_FACTOR_RETURN_HISTORY"
    INSUFFICIENT_ESTIMATION_SAMPLE = "INSUFFICIENT_ESTIMATION_SAMPLE"
    MODEL_VERSION_MISMATCH = "MODEL_VERSION_MISMATCH"
    UNSUPPORTED_INSTRUMENT = "UNSUPPORTED_INSTRUMENT"
    UNCLASSIFIED_INSTRUMENT = "UNCLASSIFIED_INSTRUMENT"
    STALE_SENSITIVITY = "STALE_SENSITIVITY"
    INVALID_CURRENCY = "INVALID_CURRENCY"
    LOW_QUALITY_LOADING = "LOW_QUALITY_LOADING"
    NOT_MODELED = "NOT_MODELED"
    BLOCKED = "BLOCKED"


class CoverageTier(str, Enum):
    NEAR_COMPLETE = "NEAR_COMPLETE"        # 99 - 100%
    HIGH_COVERAGE = "HIGH_COVERAGE"        # 95 - 99%
    MODERATE_COVERAGE = "MODERATE_COVERAGE"# 80 - 95%
    LOW_COVERAGE = "LOW_COVERAGE"          # < 80%
    NO_COVERAGE = "NO_COVERAGE"            # 0%


class ScenarioType(str, Enum):
    SINGLE_FACTOR = "SINGLE_FACTOR"
    MULTI_FACTOR = "MULTI_FACTOR"
    STANDARDIZED = "STANDARDIZED"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    CUSTOM_STRESS = "CUSTOM_STRESS"


class ShockUnit(str, Enum):
    PERCENTAGE = "PERCENTAGE"                  # e.g. -0.05 for -5%
    BASIS_POINTS = "BASIS_POINTS"              # e.g. -500 for -5%
    STANDARD_DEVIATION = "STANDARD_DEVIATION"  # e.g. -2.0 for -2 sigma


# ============================================================================
# 2. DATABASE MODELS
# ============================================================================

class FactorRiskConfig(Base):
    """Immutable, version-controlled systematic risk calculation configuration."""
    __tablename__ = "m08_05_risk_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"SYS_CFG_{uuid.uuid4().hex[:12].upper()}")
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)

    covariance_method: Mapped[CovarianceMethod] = mapped_column(SQLEnum(CovarianceMethod, native_enum=False), default=CovarianceMethod.SAMPLE, nullable=False)
    observation_frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("252.00"), nullable=False)
    decay_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), default=Decimal("0.94"), nullable=True)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    coverage_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("80.00"), nullable=False)
    currency_basis: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus, native_enum=False), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class FactorCovarianceSnapshot(Base):
    """Pinned, validated factor covariance matrix snapshot."""
    __tablename__ = "m08_05_factor_covariance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"SYS_COV_{uuid.uuid4().hex[:12].upper()}")
    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)

    covariance_method: Mapped[CovarianceMethod] = mapped_column(SQLEnum(CovarianceMethod, native_enum=False), nullable=False)
    observation_frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    estimation_window_start: Mapped[date] = mapped_column(Date, nullable=False)
    estimation_window_end: Mapped[date] = mapped_column(Date, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_sample_size: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("252.00"), nullable=False)

    factor_names_ordered: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    covariance_matrix: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    correlation_matrix: Mapped[Optional[List[List[float]]]] = mapped_column(JSON, nullable=True)

    is_positive_semidefinite: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    max_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    condition_number: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    matrix_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SystematicRiskRun(Base):
    """Audit header for an executed systematic risk evaluation run."""
    __tablename__ = "m08_05_systematic_risk_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"SYS_RUN_{uuid.uuid4().hex[:12].upper()}")
    config_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_05_risk_configs.config_id"), nullable=False, index=True)
    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)
    covariance_snapshot_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_05_factor_covariance_snapshots.snapshot_id"), nullable=False, index=True)

    target_type: Mapped[SystematicTargetType] = mapped_column(SQLEnum(SystematicTargetType, native_enum=False), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    systematic_variance_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    systematic_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    residual_variance_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    total_modeled_variance_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    total_modeled_volatility_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    systematic_variance_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)

    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("100.00"), nullable=False)
    coverage_tier: Mapped[CoverageTier] = mapped_column(SQLEnum(CoverageTier, native_enum=False), default=CoverageTier.NEAR_COMPLETE, nullable=False)
    run_status: Mapped[SystematicRunStatus] = mapped_column(SQLEnum(SystematicRunStatus, native_enum=False), default=SystematicRunStatus.COMPLETED, nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InstrumentSystematicRisk(Base):
    """Detailed instrument-level systematic risk decomposition."""
    __tablename__ = "m08_05_instrument_systematic_risk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_05_systematic_risk_runs.run_id"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    factor_loadings: Mapped[Dict[str, float]] = mapped_column(JSON, nullable=False)
    systematic_variance_period: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    systematic_volatility_period: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    systematic_variance_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    systematic_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    residual_variance_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    total_modeled_variance_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    total_modeled_volatility_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    systematic_variance_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)

    model_coverage_status: Mapped[ModelCoverageStatus] = mapped_column(SQLEnum(ModelCoverageStatus, native_enum=False), default=ModelCoverageStatus.COVERED, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PortfolioSystematicRisk(Base):
    """Detailed portfolio-level systematic risk decomposition and coverage aggregates."""
    __tablename__ = "m08_05_portfolio_systematic_risk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_05_systematic_risk_runs.run_id"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    portfolio_betas: Mapped[Dict[str, float]] = mapped_column(JSON, nullable=False)
    systematic_variance_period: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    systematic_volatility_period: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    systematic_variance_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    systematic_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    cross_security_variance_discrepancy: Mapped[Decimal] = mapped_column(Numeric(18, 12), default=Decimal("0.0"), nullable=False)
    is_cross_security_reconciled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    residual_variance_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    total_modeled_variance_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    total_modeled_volatility_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    systematic_variance_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)

    total_absolute_market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    covered_absolute_market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    uncovered_absolute_market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    coverage_tier: Mapped[CoverageTier] = mapped_column(SQLEnum(CoverageTier, native_enum=False), nullable=False)

    total_holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    covered_holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uncovered_holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_coverage_percentages: Mapped[Dict[str, float]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# ============================================================================
# 3. FACTOR SCENARIO MODELS
# ============================================================================

class FactorScenarioConfig(Base):
    """User-defined or benchmark factor shock scenario specifications."""
    __tablename__ = "m08_05_factor_scenario_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"SYS_SCEN_{uuid.uuid4().hex[:12].upper()}")
    scenario_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)
    scenario_type: Mapped[ScenarioType] = mapped_column(SQLEnum(ScenarioType, native_enum=False), default=ScenarioType.MULTI_FACTOR, nullable=False)
    shock_unit: Mapped[ShockUnit] = mapped_column(SQLEnum(ShockUnit, native_enum=False), default=ShockUnit.PERCENTAGE, nullable=False)

    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus, native_enum=False), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    shocks: Mapped[List["FactorScenarioShock"]] = relationship("FactorScenarioShock", back_populates="scenario", cascade="all, delete-orphan")


class FactorScenarioShock(Base):
    """Factor-by-factor shock values for a scenario."""
    __tablename__ = "m08_05_factor_scenario_shocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_05_factor_scenario_configs.scenario_id"), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    shock_value: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    shock_unit: Mapped[ShockUnit] = mapped_column(SQLEnum(ShockUnit, native_enum=False), default=ShockUnit.PERCENTAGE, nullable=False)
    standard_deviation_multiple: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    scenario: Mapped["FactorScenarioConfig"] = relationship("FactorScenarioConfig", back_populates="shocks")


class FactorScenarioRun(Base):
    """Execution results for a factor shock scenario simulation."""
    __tablename__ = "m08_05_factor_scenario_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"SYS_SCEN_RUN_{uuid.uuid4().hex[:12].upper()}")
    scenario_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_05_factor_scenario_configs.scenario_id"), nullable=False, index=True)
    target_type: Mapped[SystematicTargetType] = mapped_column(SQLEnum(SystematicTargetType, native_enum=False), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    percentage_impact: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    monetary_impact: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    model_limitation_warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("100.00"), nullable=False)
    calculation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    components: Mapped[List["FactorScenarioComponent"]] = relationship("FactorScenarioComponent", back_populates="run", cascade="all, delete-orphan")


class FactorScenarioComponent(Base):
    """Component factor return and monetary contribution under a scenario."""
    __tablename__ = "m08_05_factor_scenario_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_05_factor_scenario_runs.run_id"), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_shock: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    factor_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    estimated_return_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    estimated_monetary_contribution: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)

    run: Mapped["FactorScenarioRun"] = relationship("FactorScenarioRun", back_populates="components")


class FactorModelCoverageRecord(Base):
    """Holding-level coverage diagnostics and exclusion reasoning."""
    __tablename__ = "m08_05_model_coverage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    coverage_status: Mapped[ModelCoverageStatus] = mapped_column(SQLEnum(ModelCoverageStatus, native_enum=False), nullable=False)
    signed_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    absolute_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    absolute_weight_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)

    missing_factor_codes: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    reason_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
