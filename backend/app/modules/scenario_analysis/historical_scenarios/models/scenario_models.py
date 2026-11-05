"""
Historical Scenarios SQLAlchemy Models (M10.01).

Tables:
1. historical_scenario_events: Library of named historical market episodes.
2. historical_scenario_event_versions: Immutable configuration versions.
3. historical_scenario_observations: Normalized historical asset/factor returns.
4. historical_shock_mapping_rules: Configurable shock mapping hierarchy & rules.
5. historical_shock_mapping_results: Per-position mapping decisions and shock provenance.
6. historical_scenario_replay_runs: Portfolio scenario replay executions.
7. historical_scenario_replay_positions: Position-level revaluation outcomes.
8. historical_scenario_replay_summaries: Aggregated portfolio results and reconciliations.
9. historical_scenario_replay_warnings: Granular caveats, warnings, and limitations.
10. historical_scenario_replay_paths: Daily path revaluation series across event duration.
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


class HistoricalScenarioEvent(Base):
    __tablename__ = "historical_scenario_events"

    id = Column(String(50), primary_key=True)
    event_code = Column(String(100), nullable=False, unique=True, index=True)
    event_name = Column(String(150), nullable=False)
    description = Column(String(255), nullable=True)
    category = Column(String(50), nullable=False) # CRISIS, CRASH, CORRECTION, RECOVERY, VOLATILITY_SHOCK, RATE_SHOCK, CUSTOM
    tags = Column(String(255), nullable=True) # Comma-separated or tag list
    global_scope = Column(Boolean, nullable=False, default=True)
    affected_regions = Column(String(100), nullable=False, default="GLOBAL") # INDIA, US, GLOBAL
    affected_markets = Column(String(100), nullable=False, default="ALL") # NSE, BSE, NYSE, NASDAQ
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    reference_timezone = Column(String(50), nullable=False, default="UTC")
    primary_reference_index = Column(String(50), nullable=True)
    event_narrative = Column(Text, nullable=True)
    data_coverage_status = Column(String(50), nullable=False, default="ADEQUATE") # ADEQUATE, PARTIAL, INSUFFICIENT
    event_status = Column(String(50), nullable=False, default="ACTIVE") # DRAFT, ACTIVE, INACTIVE, ARCHIVED
    current_version = Column(String(20), nullable=False, default="1.0.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(50), nullable=False, default="SYSTEM")

    versions = relationship("HistoricalScenarioEventVersion", back_populates="event", cascade="all, delete-orphan")
    observations = relationship("HistoricalScenarioObservation", back_populates="event", cascade="all, delete-orphan")


class HistoricalScenarioEventVersion(Base):
    __tablename__ = "historical_scenario_event_versions"

    id = Column(String(50), primary_key=True)
    event_id = Column(String(50), ForeignKey("historical_scenario_events.id"), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    configuration_json = Column(Text, nullable=True)
    date_boundary_policy = Column(String(50), nullable=False, default="INCLUSIVE")
    return_definition = Column(String(50), nullable=False, default="TOTAL_RETURN") # TOTAL_RETURN, PRICE_RETURN
    observation_frequency = Column(String(50), nullable=False, default="DAILY") # DAILY, INTRADAY
    mapping_policy_version = Column(String(20), nullable=False, default="1.0.0")
    source_manifest = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(50), nullable=False, default="SYSTEM")
    change_reason = Column(String(255), nullable=True)

    event = relationship("HistoricalScenarioEvent", back_populates="versions")


class HistoricalScenarioObservation(Base):
    __tablename__ = "historical_scenario_observations"

    id = Column(String(50), primary_key=True)
    event_id = Column(String(50), ForeignKey("historical_scenario_events.id"), nullable=False, index=True)
    event_version_id = Column(String(50), nullable=True)
    instrument_id = Column(String(50), nullable=True, index=True)
    listing_id = Column(String(50), nullable=True, index=True)
    factor_id = Column(String(50), nullable=True, index=True)
    observation_date = Column(DateTime(timezone=True), nullable=False, index=True)
    observation_timestamp = Column(DateTime(timezone=True), nullable=False)
    source_id = Column(String(50), nullable=False, default="HISTORICAL_ARCHIVE")
    source_record_id = Column(String(100), nullable=True)
    reference_price = Column(Numeric(18, 8), nullable=True)
    adjusted_price = Column(Numeric(18, 8), nullable=True)
    return_value = Column(Numeric(18, 8), nullable=False)
    return_type = Column(String(50), nullable=False, default="TOTAL_RETURN") # TOTAL_RETURN, PRICE_RETURN
    currency = Column(String(10), nullable=False, default="USD")
    quality_status = Column(String(50), nullable=False, default="VALID")
    calculation_version = Column(String(20), nullable=False, default="1.0.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    event = relationship("HistoricalScenarioEvent", back_populates="observations")


class HistoricalShockMappingRule(Base):
    __tablename__ = "historical_shock_mapping_rules"

    id = Column(String(50), primary_key=True)
    rule_code = Column(String(100), nullable=False, unique=True)
    rule_name = Column(String(150), nullable=False)
    target_scope = Column(String(50), nullable=False, default="ALL")
    mapping_method = Column(String(50), nullable=False) # EXACT_DIRECT, ALTERNATE_LISTING, APPROVED_PROXY, SECTOR_PROXY, MARKET_INDEX_PROXY, FACTOR_MODEL, UNMAPPED
    priority = Column(Integer, nullable=False, default=1)
    source_scope = Column(String(50), nullable=False, default="ALL")
    confidence_level = Column(String(20), nullable=False, default="HIGH") # HIGH, MEDIUM, LOW
    approval_required = Column(Boolean, nullable=False, default=False)
    effective_from = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    effective_to = Column(DateTime(timezone=True), nullable=True)
    configuration_json = Column(Text, nullable=True)
    rule_version = Column(String(20), nullable=False, default="1.0.0")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class HistoricalScenarioReplayRun(Base):
    __tablename__ = "historical_scenario_replay_runs"

    id = Column(String(50), primary_key=True)
    replay_code = Column(String(100), nullable=False, unique=True, index=True)
    portfolio_id = Column(String(50), nullable=False, index=True)
    scenario_event_id = Column(String(50), ForeignKey("historical_scenario_events.id"), nullable=False, index=True)
    scenario_event_version_id = Column(String(50), nullable=True)
    portfolio_snapshot_id = Column(String(50), nullable=True)
    replay_mode = Column(String(50), nullable=False, default="CURRENT_PORTFOLIO") # CURRENT_PORTFOLIO, HISTORICAL_SNAPSHOT, ACTUAL_HISTORICAL_PERIOD
    return_definition = Column(String(50), nullable=False, default="TOTAL_RETURN")
    base_currency = Column(String(10), nullable=False, default="USD")
    mapping_policy_version = Column(String(20), nullable=False, default="1.0.0")
    missing_data_policy = Column(String(50), nullable=False, default="STRICT") # STRICT, EXCLUDE_UNMAPPED, APPROVED_PROXY_ONLY, PARTIAL
    valuation_baseline = Column(String(50), nullable=False, default="PRE_EVENT_CLOSE")
    calculation_version = Column(String(20), nullable=False, default="1.0.0")
    replay_status = Column(String(50), nullable=False, default="COMPLETED") # PENDING, RUNNING, COMPLETED, COMPLETED_WITH_WARNINGS, PARTIAL, FAILED
    
    baseline_nav = Column(Numeric(24, 4), nullable=False)
    scenario_nav = Column(Numeric(24, 4), nullable=False)
    scenario_pnl = Column(Numeric(24, 4), nullable=False)
    scenario_return = Column(Numeric(18, 8), nullable=False)
    
    direct_coverage = Column(Numeric(5, 4), nullable=False, default=0.0)
    proxy_coverage = Column(Numeric(5, 4), nullable=False, default=0.0)
    factor_coverage = Column(Numeric(5, 4), nullable=False, default=0.0)
    unmapped_coverage = Column(Numeric(5, 4), nullable=False, default=0.0)
    
    input_manifest_hash = Column(String(64), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(50), nullable=False, default="ANALYST")

    positions = relationship("HistoricalScenarioReplayPosition", back_populates="replay_run", cascade="all, delete-orphan")
    warnings = relationship("HistoricalScenarioReplayWarning", back_populates="replay_run", cascade="all, delete-orphan")
    paths = relationship("HistoricalScenarioReplayPath", back_populates="replay_run", cascade="all, delete-orphan")
    mappings = relationship("HistoricalShockMappingResult", back_populates="replay_run", cascade="all, delete-orphan")


class HistoricalShockMappingResult(Base):
    __tablename__ = "historical_shock_mapping_results"

    id = Column(String(50), primary_key=True)
    replay_id = Column(String(50), ForeignKey("historical_scenario_replay_runs.id"), nullable=False, index=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False)
    mapping_method = Column(String(50), nullable=False) # EXACT_DIRECT, ALTERNATE_LISTING, APPROVED_PROXY, SECTOR_PROXY, MARKET_INDEX_PROXY, FACTOR_MODEL, UNMAPPED
    source_instrument_id = Column(String(50), nullable=True)
    source_factor_id = Column(String(50), nullable=True)
    source_observation_id = Column(String(50), nullable=True)
    historical_shock = Column(Numeric(18, 8), nullable=False)
    fx_shock = Column(Numeric(18, 8), nullable=False, default=0)
    base_currency_shock = Column(Numeric(18, 8), nullable=False)
    confidence_level = Column(String(20), nullable=False, default="HIGH")
    quality_status = Column(String(50), nullable=False, default="VALID")
    mapping_rationale = Column(String(255), nullable=True)
    override_status = Column(Boolean, nullable=False, default=False)
    override_reason = Column(String(255), nullable=True)
    mapping_rule_version = Column(String(20), nullable=False, default="1.0.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    replay_run = relationship("HistoricalScenarioReplayRun", back_populates="mappings")


class HistoricalScenarioReplayPosition(Base):
    __tablename__ = "historical_scenario_replay_positions"

    id = Column(String(50), primary_key=True)
    replay_id = Column(String(50), ForeignKey("historical_scenario_replay_runs.id"), nullable=False, index=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False)
    signed_quantity = Column(Numeric(24, 4), nullable=False)
    baseline_price = Column(Numeric(18, 8), nullable=False)
    baseline_market_value = Column(Numeric(24, 4), nullable=False)
    local_currency = Column(String(10), nullable=False, default="USD")
    local_return = Column(Numeric(18, 8), nullable=False)
    fx_return = Column(Numeric(18, 8), nullable=False, default=0)
    base_currency_return = Column(Numeric(18, 8), nullable=False)
    scenario_price = Column(Numeric(18, 8), nullable=False)
    scenario_market_value = Column(Numeric(24, 4), nullable=False)
    scenario_pnl = Column(Numeric(24, 4), nullable=False)
    portfolio_weight = Column(Numeric(12, 8), nullable=False)
    portfolio_contribution = Column(Numeric(12, 8), nullable=False)
    mapping_method = Column(String(50), nullable=False)
    mapping_status = Column(String(50), nullable=False, default="SUCCESS")
    quality_status = Column(String(50), nullable=False, default="VALID")
    is_excluded = Column(Boolean, nullable=False, default=False)
    exclusion_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    replay_run = relationship("HistoricalScenarioReplayRun", back_populates="positions")


class HistoricalScenarioReplayWarning(Base):
    __tablename__ = "historical_scenario_replay_warnings"

    id = Column(String(50), primary_key=True)
    replay_id = Column(String(50), ForeignKey("historical_scenario_replay_runs.id"), nullable=False, index=True)
    instrument_id = Column(String(50), nullable=True)
    warning_code = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False) # INFO, WARNING, HIGH, CRITICAL
    warning_category = Column(String(50), nullable=False) # DATA_COVERAGE, PROXY_BIAS, CURRENCY, MAPPING_FALLBACK, LOOK_AHEAD
    message = Column(String(255), nullable=False)
    details_json = Column(Text, nullable=True)
    resolution_status = Column(String(50), nullable=False, default="DISCLOSED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    replay_run = relationship("HistoricalScenarioReplayRun", back_populates="warnings")


class HistoricalScenarioReplayPath(Base):
    __tablename__ = "historical_scenario_replay_paths"

    id = Column(String(50), primary_key=True)
    replay_id = Column(String(50), ForeignKey("historical_scenario_replay_runs.id"), nullable=False, index=True)
    observation_date = Column(DateTime(timezone=True), nullable=False, index=True)
    observation_timestamp = Column(DateTime(timezone=True), nullable=False)
    baseline_nav = Column(Numeric(24, 4), nullable=False)
    scenario_nav = Column(Numeric(24, 4), nullable=False)
    scenario_pnl = Column(Numeric(24, 4), nullable=False)
    scenario_return = Column(Numeric(18, 8), nullable=False)
    coverage_ratio = Column(Numeric(5, 4), nullable=False, default=1.0)
    quality_status = Column(String(50), nullable=False, default="VALID")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    replay_run = relationship("HistoricalScenarioReplayRun", back_populates="paths")

