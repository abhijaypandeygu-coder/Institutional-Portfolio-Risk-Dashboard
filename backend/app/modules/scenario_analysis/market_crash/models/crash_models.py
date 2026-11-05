"""
Market Crash Simulation SQLAlchemy ORM Models (M10.03).
Strictly typed, versioned, relational models with full auditability.
Entities:
- MarketCrashScenario
- MarketCrashScenarioVersion
- MarketCrashBenchmarkShock
- MarketCrashMappingRule
- MarketCrashMappingResult
- MarketCrashSensitivitySnapshot
- MarketCrashNonlinearParameter
- MarketCrashSimulationRun
- MarketCrashPositionResult
- MarketCrashSummaryResult
- MarketCrashAttributionResult
- MarketCrashWarning
- MarketCrashAuditLog
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Index,
    Text
)
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class MarketCrashScenario(Base):
    """Scenario header metadata."""
    __tablename__ = "market_crash_scenarios"

    id = Column(String(64), primary_key=True)
    scenario_code = Column(String(64), unique=True, nullable=False, index=True)
    scenario_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=False, default="BROAD_MARKET") # BROAD_MARKET, SECTOR_CRASH, GLOBAL_SYNCHRONIZED, HIGH_BETA, DOWNSIDE_BETA, NONLINEAR
    portfolio_id = Column(String(64), nullable=True, index=True)
    author_id = Column(String(64), nullable=True)
    owner_id = Column(String(64), nullable=True)
    visibility = Column(String(32), nullable=False, default="PRIVATE") # PRIVATE, TEAM, ORGANIZATION
    current_version = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="ACTIVE") # ACTIVE, ARCHIVED, DRAFT
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    versions = relationship("MarketCrashScenarioVersion", back_populates="scenario", cascade="all, delete-orphan")
    runs = relationship("MarketCrashSimulationRun", back_populates="scenario")


class MarketCrashScenarioVersion(Base):
    """Immutable versioned scenario configuration."""
    __tablename__ = "market_crash_scenario_versions"

    id = Column(String(64), primary_key=True)
    scenario_id = Column(String(64), ForeignKey("market_crash_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    configuration_json = Column(JSON, nullable=False)
    configuration_hash = Column(String(64), nullable=False)
    change_reason = Column(String(255), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    scenario = relationship("MarketCrashScenario", back_populates="versions")
    benchmark_shocks = relationship("MarketCrashBenchmarkShock", back_populates="version_rel", cascade="all, delete-orphan")
    nonlinear_parameters = relationship("MarketCrashNonlinearParameter", back_populates="version_rel", cascade="all, delete-orphan")


class MarketCrashBenchmarkShock(Base):
    """Configured index shocks within a scenario version."""
    __tablename__ = "market_crash_benchmark_shocks"

    id = Column(String(64), primary_key=True)
    scenario_version_id = Column(String(64), ForeignKey("market_crash_scenario_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    benchmark_id = Column(String(64), nullable=False, index=True) # e.g. NIFTY_50, SPX, NASDAQ
    benchmark_name = Column(String(255), nullable=True)
    market_region = Column(String(32), nullable=False, default="US") # INDIA, US, GLOBAL
    shock_method = Column(String(32), nullable=False, default="PERCENTAGE") # PERCENTAGE, TARGET_LEVEL, POINT_CHANGE, MULTI_STAGE
    baseline_index_level = Column(Numeric(18, 4), nullable=True)
    target_index_level = Column(Numeric(18, 4), nullable=True)
    index_point_change = Column(Numeric(18, 4), nullable=True)
    shock_return = Column(Numeric(12, 8), nullable=False) # e.g. -0.20000000
    return_definition = Column(String(32), nullable=False, default="PRICE_RETURN") # PRICE_RETURN, TOTAL_RETURN
    benchmark_currency = Column(String(10), nullable=False, default="USD")
    stage_order = Column(Integer, nullable=False, default=1)
    shock_configuration = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    version_rel = relationship("MarketCrashScenarioVersion", back_populates="benchmark_shocks")


class MarketCrashMappingRule(Base):
    """Configurable benchmark mapping rules."""
    __tablename__ = "market_crash_mapping_rules"

    id = Column(String(64), primary_key=True)
    rule_code = Column(String(64), unique=True, nullable=False, index=True)
    rule_name = Column(String(255), nullable=False)
    target_scope = Column(String(32), nullable=False) # EXCHANGE, SECTOR, REGION, EXPLICIT
    benchmark_id = Column(String(64), nullable=False)
    mapping_priority = Column(Integer, nullable=False, default=1)
    mapping_method = Column(String(64), nullable=False) # LISTING_EXCHANGE, PRIMARY_SECTOR, ANALYST_OVERRIDE
    rule_version = Column(Integer, nullable=False, default=1)
    configuration_json = Column(JSON, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MarketCrashMappingResult(Base):
    """Resolved instrument-to-benchmark mapping for a specific simulation run."""
    __tablename__ = "market_crash_mapping_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("market_crash_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    listing_id = Column(String(64), nullable=True)
    benchmark_id = Column(String(64), nullable=False)
    mapping_method = Column(String(64), nullable=False)
    mapping_priority = Column(Integer, nullable=False, default=1)
    mapping_confidence = Column(Numeric(5, 4), nullable=True) # 0.0 to 1.0
    mapping_rationale = Column(String(255), nullable=True)
    override_status = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MarketCrashSensitivitySnapshot(Base):
    """Snapshot of sensitivities (beta, downside beta) used in a simulation run."""
    __tablename__ = "market_crash_sensitivity_snapshots"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("market_crash_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    benchmark_id = Column(String(64), nullable=False)
    sensitivity_model = Column(String(64), nullable=False, default="OLS_BETA")
    beta_value = Column(Numeric(12, 6), nullable=False)
    downside_beta = Column(Numeric(12, 6), nullable=True)
    observation_count = Column(Integer, nullable=True)
    r_squared = Column(Numeric(6, 4), nullable=True)
    standard_error = Column(Numeric(10, 6), nullable=True)
    model_version = Column(String(64), nullable=True)
    quality_status = Column(String(32), nullable=False, default="VALID")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MarketCrashNonlinearParameter(Base):
    """Nonlinear parameters associated with a scenario version."""
    __tablename__ = "market_crash_nonlinear_parameters"

    id = Column(String(64), primary_key=True)
    scenario_version_id = Column(String(64), ForeignKey("market_crash_scenario_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=True, index=True)
    sector_id = Column(String(64), nullable=True, index=True)
    model_type = Column(String(32), nullable=False) # DOWNSIDE_BETA, PIECEWISE_BETA, STRESS_AMPLIFICATION, QUADRATIC, USER_DEFINED
    threshold = Column(Numeric(12, 6), nullable=True)
    stress_multiplier = Column(Numeric(12, 6), nullable=True) # lambda
    curvature_parameter = Column(Numeric(12, 6), nullable=True) # gamma
    exponent = Column(Numeric(6, 4), nullable=True) # p
    user_adjustment = Column(Numeric(12, 8), nullable=True)
    parameter_source = Column(String(32), nullable=False, default="ASSUMPTION") # ASSUMPTION, CALIBRATED, ANALYST_INPUT
    configuration_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    version_rel = relationship("MarketCrashScenarioVersion", back_populates="nonlinear_parameters")


class MarketCrashSimulationRun(Base):
    """Master simulation execution record."""
    __tablename__ = "market_crash_simulation_runs"

    id = Column(String(64), primary_key=True)
    simulation_code = Column(String(64), unique=True, nullable=False, index=True)
    scenario_id = Column(String(64), ForeignKey("market_crash_scenarios.id", ondelete="SET NULL"), nullable=True, index=True)
    scenario_version_id = Column(String(64), nullable=True)
    portfolio_id = Column(String(64), nullable=False, index=True)
    portfolio_snapshot_id = Column(String(64), nullable=True)
    base_currency = Column(String(10), nullable=False, default="USD")
    response_model = Column(String(64), nullable=False, default="LINEAR") # LINEAR, DOWNSIDE_BETA, PIECEWISE_BETA, STRESS_AMPLIFICATION, QUADRATIC, COMPOSITE
    missing_data_policy = Column(String(32), nullable=False, default="STRICT") # STRICT, PARTIAL, EXCLUDE_UNMAPPED, APPROVED_FALLBACK
    calculation_version = Column(String(32), nullable=False, default="1.0.0")
    run_status = Column(String(32), nullable=False, default="RUNNING") # RUNNING, COMPLETED, COMPLETED_WITH_WARNINGS, PARTIAL, FAILED
    
    baseline_nav = Column(Numeric(20, 4), nullable=False)
    scenario_nav = Column(Numeric(20, 4), nullable=False)
    scenario_pnl = Column(Numeric(20, 4), nullable=False)
    scenario_loss = Column(Numeric(20, 4), nullable=False)
    scenario_return = Column(Numeric(14, 8), nullable=False)

    mapped_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)
    beta_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)
    nonlinear_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)
    input_manifest_hash = Column(String(64), nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=True)

    scenario = relationship("MarketCrashScenario", back_populates="runs")
    position_results = relationship("MarketCrashPositionResult", back_populates="run", cascade="all, delete-orphan")
    summary_results = relationship("MarketCrashSummaryResult", back_populates="run", uselist=False, cascade="all, delete-orphan")
    attribution_results = relationship("MarketCrashAttributionResult", back_populates="run", cascade="all, delete-orphan")
    warnings = relationship("MarketCrashWarning", back_populates="run", cascade="all, delete-orphan")


class MarketCrashPositionResult(Base):
    """Position-level stress results."""
    __tablename__ = "market_crash_position_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("market_crash_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    listing_id = Column(String(64), nullable=True)
    sector = Column(String(64), nullable=True)
    market_region = Column(String(32), nullable=True)
    currency = Column(String(10), nullable=False, default="USD")

    signed_quantity = Column(Numeric(18, 4), nullable=False)
    baseline_price = Column(Numeric(18, 4), nullable=False)
    scenario_price = Column(Numeric(18, 4), nullable=False)
    baseline_market_value = Column(Numeric(20, 4), nullable=False)
    scenario_market_value = Column(Numeric(20, 4), nullable=False)

    benchmark_id = Column(String(64), nullable=False)
    benchmark_shock = Column(Numeric(12, 8), nullable=False)
    beta_value = Column(Numeric(12, 6), nullable=False)
    downside_beta = Column(Numeric(12, 6), nullable=True)

    linear_return = Column(Numeric(14, 8), nullable=False)
    downside_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    nonlinear_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    sector_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    user_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    final_scenario_return = Column(Numeric(14, 8), nullable=False)

    scenario_pnl = Column(Numeric(20, 4), nullable=False)
    scenario_loss = Column(Numeric(20, 4), nullable=False)
    portfolio_contribution = Column(Numeric(14, 8), nullable=False)

    mapping_status = Column(String(32), nullable=False, default="MAPPED")
    quality_status = Column(String(32), nullable=False, default="VALID")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("MarketCrashSimulationRun", back_populates="position_results")


class MarketCrashSummaryResult(Base):
    """Aggregated portfolio summary result."""
    __tablename__ = "market_crash_summary_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("market_crash_simulation_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    baseline_nav = Column(Numeric(20, 4), nullable=False)
    scenario_nav = Column(Numeric(20, 4), nullable=False)
    scenario_pnl = Column(Numeric(20, 4), nullable=False)
    scenario_loss = Column(Numeric(20, 4), nullable=False)
    scenario_return = Column(Numeric(14, 8), nullable=False)

    gross_exposure = Column(Numeric(20, 4), nullable=False)
    net_exposure = Column(Numeric(20, 4), nullable=False)
    mapped_exposure = Column(Numeric(20, 4), nullable=False)
    unmapped_exposure = Column(Numeric(20, 4), nullable=False, default=0.0)
    beta_covered_exposure = Column(Numeric(20, 4), nullable=False)
    nonlinear_covered_exposure = Column(Numeric(20, 4), nullable=False)

    affected_position_count = Column(Integer, nullable=False)
    excluded_position_count = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("MarketCrashSimulationRun", back_populates="summary_results")


class MarketCrashAttributionResult(Base):
    """Attribution breakdown (Sector, Benchmark, Instrument, Linear vs Nonlinear)."""
    __tablename__ = "market_crash_attribution_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("market_crash_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    attribution_type = Column(String(32), nullable=False) # SECTOR, BENCHMARK, REGION, LINEAR_VS_NONLINEAR
    attribution_identifier = Column(String(64), nullable=False) # e.g. TECHNOLOGY, NIFTY_50, LINEAR_IMPACT
    baseline_exposure = Column(Numeric(20, 4), nullable=False)
    scenario_pnl = Column(Numeric(20, 4), nullable=False)
    scenario_loss = Column(Numeric(20, 4), nullable=False)
    linear_impact = Column(Numeric(20, 4), nullable=False, default=0.0)
    nonlinear_impact = Column(Numeric(20, 4), nullable=False, default=0.0)
    contribution_percentage = Column(Numeric(10, 6), nullable=False)
    reconciliation_residual = Column(Numeric(14, 8), nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("MarketCrashSimulationRun", back_populates="attribution_results")


class MarketCrashWarning(Base):
    """Validation & diagnostic warnings."""
    __tablename__ = "market_crash_warnings"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("market_crash_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=True)
    benchmark_id = Column(String(64), nullable=True)
    warning_code = Column(String(64), nullable=False) # UNMAPPED_INSTRUMENT, HIGH_BETA, OUT_OF_BOUNDS, USER_ASSUMPTION
    severity = Column(String(16), nullable=False, default="INFO") # INFO, WARNING, HIGH, CRITICAL
    category = Column(String(32), nullable=False, default="GENERAL")
    message = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=True)
    resolution_status = Column(String(32), nullable=False, default="UNRESOLVED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("MarketCrashSimulationRun", back_populates="warnings")


class MarketCrashAuditLog(Base):
    """Audit log tracking configuration, lifecycle, and executions."""
    __tablename__ = "market_crash_audit_logs"

    id = Column(String(64), primary_key=True)
    scenario_id = Column(String(64), nullable=True, index=True)
    scenario_version_id = Column(String(64), nullable=True)
    simulation_run_id = Column(String(64), nullable=True, index=True)
    actor_id = Column(String(64), nullable=True)
    action_type = Column(String(64), nullable=False)
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    reason = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

