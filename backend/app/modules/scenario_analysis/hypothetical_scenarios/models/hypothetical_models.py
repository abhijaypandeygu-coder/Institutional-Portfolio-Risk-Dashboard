"""
Hypothetical Scenarios SQLAlchemy Models (M10.02).

Tables:
1. hypothetical_scenario_templates: Reusable scenario templates.
2. hypothetical_scenario_template_versions: Immutable versioned configurations.
3. hypothetical_scenario_runs: Execution records of hypothetical scenarios.
4. hypothetical_scenario_position_results: Position-level valuation impacts.
5. hypothetical_scenario_risk_results: Stressed vs baseline portfolio risk metrics.
6. hypothetical_scenario_liquidity_results: Stressed vs baseline liquidity overlays.
7. hypothetical_scenario_warnings: Diagnostics, conflict resolutions, and caveats.
8. hypothetical_scenario_audit_logs: Scenario lifecycle state transitions.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Index,
    Boolean,
    Integer,
    Text
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class HypotheticalScenarioTemplate(Base):
    __tablename__ = "hypothetical_scenario_templates"

    id = Column(String(50), primary_key=True)
    template_code = Column(String(100), nullable=False, unique=True, index=True)
    template_name = Column(String(150), nullable=False)
    description = Column(String(255), nullable=True)
    category = Column(String(50), nullable=False, default="CUSTOM") # BROAD_MARKET_CRASH, SECTOR_DECLINE, FACTOR_ROTATION, VOLATILITY_EXPANSION, LIQUIDITY_DETERIORATION, COMBINED, CUSTOM
    tags = Column(String(255), nullable=True)
    author_id = Column(String(50), nullable=False, default="QUANT_ANALYST")
    owner_id = Column(String(50), nullable=False, default="QUANT_TEAM")
    visibility = Column(String(20), nullable=False, default="SHARED") # PRIVATE, SHARED, ORGANIZATION
    current_version = Column(String(20), nullable=False, default="1.0.0")
    status = Column(String(20), nullable=False, default="PUBLISHED") # DRAFT, PUBLISHED, ARCHIVED
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)

    versions = relationship("HypotheticalScenarioTemplateVersion", back_populates="template", cascade="all, delete-orphan")


class HypotheticalScenarioTemplateVersion(Base):
    __tablename__ = "hypothetical_scenario_template_versions"

    id = Column(String(50), primary_key=True)
    template_id = Column(String(50), ForeignKey("hypothetical_scenario_templates.id"), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    configuration_json = Column(Text, nullable=False) # Complete JSON serialization of shocks
    configuration_hash = Column(String(64), nullable=True)
    change_reason = Column(String(255), nullable=True)
    created_by = Column(String(50), nullable=False, default="QUANT_ANALYST")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)

    template = relationship("HypotheticalScenarioTemplate", back_populates="versions")


class HypotheticalScenarioRun(Base):
    __tablename__ = "hypothetical_scenario_runs"

    id = Column(String(50), primary_key=True)
    scenario_code = Column(String(100), nullable=False, unique=True, index=True)
    scenario_name = Column(String(150), nullable=False)
    template_id = Column(String(50), ForeignKey("hypothetical_scenario_templates.id"), nullable=True)
    template_version_id = Column(String(50), nullable=True)
    portfolio_id = Column(String(50), nullable=False, index=True)
    portfolio_snapshot_id = Column(String(50), nullable=True)
    base_currency = Column(String(10), nullable=False, default="USD")
    
    missing_data_policy = Column(String(50), nullable=False, default="STRICT") # STRICT, PARTIAL, EXCLUDE_UNSUPPORTED
    conflict_policy = Column(String(50), nullable=False, default="MOST_SPECIFIC_WINS") # MOST_SPECIFIC_WINS, REJECT_CONFLICT
    correlation_validation_policy = Column(String(50), nullable=False, default="REJECT_INVALID_MATRIX") # REJECT_INVALID_MATRIX, NEAREST_CORRELATION_MATRIX_REPAIR
    run_status = Column(String(50), nullable=False, default="COMPLETED") # PENDING, RUNNING, COMPLETED, COMPLETED_WITH_WARNINGS, PARTIAL, FAILED
    
    baseline_nav = Column(Numeric(24, 4), nullable=False)
    scenario_nav = Column(Numeric(24, 4), nullable=False)
    scenario_pnl = Column(Numeric(24, 4), nullable=False)
    scenario_return = Column(Numeric(18, 8), nullable=False)
    
    direct_coverage = Column(Numeric(5, 4), nullable=False, default=1.0)
    unmapped_coverage = Column(Numeric(5, 4), nullable=False, default=0.0)
    
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(50), nullable=False, default="ANALYST")

    positions = relationship("HypotheticalScenarioPositionResult", back_populates="run", cascade="all, delete-orphan")
    risk_results = relationship("HypotheticalScenarioRiskResult", back_populates="run", cascade="all, delete-orphan")
    liquidity_results = relationship("HypotheticalScenarioLiquidityResult", back_populates="run", cascade="all, delete-orphan")
    warnings = relationship("HypotheticalScenarioWarning", back_populates="run", cascade="all, delete-orphan")


class HypotheticalScenarioPositionResult(Base):
    __tablename__ = "hypothetical_scenario_position_results"

    id = Column(String(50), primary_key=True)
    scenario_run_id = Column(String(50), ForeignKey("hypothetical_scenario_runs.id"), nullable=False, index=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False)
    signed_quantity = Column(Numeric(24, 4), nullable=False)
    baseline_price = Column(Numeric(18, 8), nullable=False)
    scenario_price = Column(Numeric(18, 8), nullable=False)
    price_shock = Column(Numeric(18, 8), nullable=False)
    factor_return = Column(Numeric(18, 8), nullable=True)
    baseline_market_value = Column(Numeric(24, 4), nullable=False)
    scenario_market_value = Column(Numeric(24, 4), nullable=False)
    scenario_pnl = Column(Numeric(24, 4), nullable=False)
    baseline_weight = Column(Numeric(12, 8), nullable=False)
    scenario_contribution = Column(Numeric(12, 8), nullable=False)
    local_currency = Column(String(10), nullable=False, default="USD")
    base_currency_return = Column(Numeric(18, 8), nullable=False)
    exclusion_status = Column(Boolean, nullable=False, default=False)
    warning_status = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("HypotheticalScenarioRun", back_populates="positions")


class HypotheticalScenarioRiskResult(Base):
    __tablename__ = "hypothetical_scenario_risk_results"

    id = Column(String(50), primary_key=True)
    scenario_run_id = Column(String(50), ForeignKey("hypothetical_scenario_runs.id"), nullable=False, index=True)
    metric_code = Column(String(50), nullable=False) # PORTFOLIO_VOLATILITY, PARAMETRIC_VAR_95, PARAMETRIC_ES_95
    baseline_value = Column(Numeric(24, 4), nullable=False)
    scenario_value = Column(Numeric(24, 4), nullable=False)
    difference_value = Column(Numeric(24, 4), nullable=False)
    unit = Column(String(20), nullable=False, default="USD")
    horizon = Column(String(20), nullable=False, default="1D")
    confidence_level = Column(Numeric(5, 4), nullable=True)
    methodology = Column(String(50), nullable=False, default="PARAMETRIC_COVARIANCE")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("HypotheticalScenarioRun", back_populates="risk_results")


class HypotheticalScenarioLiquidityResult(Base):
    __tablename__ = "hypothetical_scenario_liquidity_results"

    id = Column(String(50), primary_key=True)
    scenario_run_id = Column(String(50), ForeignKey("hypothetical_scenario_runs.id"), nullable=False, index=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    baseline_spread = Column(Numeric(18, 8), nullable=False)
    scenario_spread = Column(Numeric(18, 8), nullable=False)
    baseline_bid_depth = Column(Numeric(24, 4), nullable=False)
    scenario_bid_depth = Column(Numeric(24, 4), nullable=False)
    baseline_ask_depth = Column(Numeric(24, 4), nullable=False)
    scenario_ask_depth = Column(Numeric(24, 4), nullable=False)
    baseline_volume = Column(Numeric(24, 4), nullable=False)
    scenario_volume = Column(Numeric(24, 4), nullable=False)
    market_impact_bps = Column(Numeric(12, 4), nullable=True)
    slippage_estimate_bps = Column(Numeric(12, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("HypotheticalScenarioRun", back_populates="liquidity_results")


class HypotheticalScenarioWarning(Base):
    __tablename__ = "hypothetical_scenario_warnings"

    id = Column(String(50), primary_key=True)
    scenario_run_id = Column(String(50), ForeignKey("hypothetical_scenario_runs.id"), nullable=False, index=True)
    shock_id = Column(String(50), nullable=True)
    instrument_id = Column(String(50), nullable=True)
    warning_code = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False) # INFO, WARNING, HIGH, CRITICAL
    category = Column(String(50), nullable=False) # CORRELATION_REPAIR, SHOCK_CONFLICT, CURRENCY, DATA_COVERAGE
    message = Column(String(255), nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("HypotheticalScenarioRun", back_populates="warnings")


class HypotheticalScenarioAuditLog(Base):
    __tablename__ = "hypothetical_scenario_audit_logs"

    id = Column(String(50), primary_key=True)
    template_id = Column(String(50), nullable=True, index=True)
    scenario_run_id = Column(String(50), nullable=True, index=True)
    actor_id = Column(String(50), nullable=False)
    action_type = Column(String(50), nullable=False) # TEMPLATE_CREATED, TEMPLATE_PUBLISHED, SCENARIO_EXECUTED
    previous_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=True)
    reason = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

