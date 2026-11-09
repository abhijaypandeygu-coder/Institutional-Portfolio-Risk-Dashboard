"""
Sector Shock Simulation SQLAlchemy Models (M10.04).
Normalized, relational database models with immutable versioning, audit logs, and diagnostic warnings.
Entities:
- SectorShockScenario
- SectorShockScenarioVersion
- SectorShockGroupDefinition
- SectorShockMembershipSnapshot
- SectorSpilloverRelationship
- SectorSpilloverRelationshipVersion
- SectorShockMappingResult
- SectorShockSimulationRun
- SectorShockPositionResult
- SectorShockGroupResult
- SectorShockAttributionResult
- SectorShockWarning
- SectorShockAuditLog
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


class SectorShockScenario(Base):
    """Scenario header metadata."""
    __tablename__ = "sector_shock_scenarios"

    id = Column(String(64), primary_key=True)
    scenario_code = Column(String(64), unique=True, nullable=False, index=True)
    scenario_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=False, default="CONCENTRATED_SECTOR") # CONCENTRATED_SECTOR, INDUSTRY_DISLOCATION, MULTI_SECTOR_CASCADE, CROSS_SECTOR_CONTAGION
    portfolio_id = Column(String(64), nullable=True, index=True)
    author_id = Column(String(64), nullable=True)
    owner_id = Column(String(64), nullable=True)
    visibility = Column(String(32), nullable=False, default="PRIVATE")
    current_version = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="ACTIVE") # ACTIVE, ARCHIVED, DRAFT
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    versions = relationship("SectorShockScenarioVersion", back_populates="scenario", cascade="all, delete-orphan")
    runs = relationship("SectorShockSimulationRun", back_populates="scenario")


class SectorShockScenarioVersion(Base):
    """Immutable versioned scenario configuration."""
    __tablename__ = "sector_shock_scenario_versions"

    id = Column(String(64), primary_key=True)
    scenario_id = Column(String(64), ForeignKey("sector_shock_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    configuration_json = Column(JSON, nullable=False)
    configuration_hash = Column(String(64), nullable=False)
    change_reason = Column(String(255), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    scenario = relationship("SectorShockScenario", back_populates="versions")
    group_definitions = relationship("SectorShockGroupDefinition", back_populates="version_rel", cascade="all, delete-orphan")


class SectorShockGroupDefinition(Base):
    """Direct sector/industry target shock definitions within a scenario version."""
    __tablename__ = "sector_shock_group_definitions"

    id = Column(String(64), primary_key=True)
    scenario_version_id = Column(String(64), ForeignKey("sector_shock_scenario_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    classification_system = Column(String(32), nullable=False, default="GICS") # GICS, ICB, NIC
    classification_version = Column(String(32), nullable=False, default="2026.1")
    group_type = Column(String(32), nullable=False, default="SECTOR") # SECTOR, INDUSTRY_GROUP, INDUSTRY, SUB_INDUSTRY
    group_identifier = Column(String(64), nullable=False, index=True) # e.g. FINANCIALS, TECHNOLOGY, SOFTWARE
    shock_method = Column(String(32), nullable=False, default="PERCENTAGE") # PERCENTAGE, TARGET_LEVEL, POINT_CHANGE
    shock_value = Column(Numeric(12, 8), nullable=False) # e.g. -0.25000000
    shock_unit = Column(String(16), nullable=False, default="RATIO")
    baseline_index_reference = Column(String(64), nullable=True)
    shock_priority = Column(Integer, nullable=False, default=1)
    application_method = Column(String(32), nullable=False, default="UNIFORM") # UNIFORM, SENSITIVITY_ADJUSTED, ANALYST_EXPLICIT
    configuration_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    version_rel = relationship("SectorShockScenarioVersion", back_populates="group_definitions")


class SectorShockMembershipSnapshot(Base):
    """Frozen membership snapshot of securities in shocked groups for an execution."""
    __tablename__ = "sector_shock_membership_snapshots"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("sector_shock_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    classification_system = Column(String(32), nullable=False, default="GICS")
    classification_version = Column(String(32), nullable=False, default="2026.1")
    group_identifier = Column(String(64), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    listing_id = Column(String(64), nullable=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    membership_source = Column(String(32), nullable=False, default="M04_SECURITY_CLASSIFICATION")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class SectorSpilloverRelationship(Base):
    """Configurable sector, industry, or factor spillover relationships."""
    __tablename__ = "sector_spillover_relationships"

    id = Column(String(64), primary_key=True)
    relationship_code = Column(String(64), unique=True, nullable=False, index=True)
    source_type = Column(String(32), nullable=False) # SECTOR, INDUSTRY
    source_identifier = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32), nullable=False) # SECTOR, INDUSTRY, FACTOR
    target_identifier = Column(String(64), nullable=False, index=True)
    relationship_method = Column(String(32), nullable=False, default="ANALYST_DEFINED") # ANALYST_DEFINED, CORRELATION_INFORMED, REGRESSION_BETA, FACTOR_SENSITIVITY
    spillover_coefficient = Column(Numeric(10, 6), nullable=False) # transmission multiplier e.g. 0.350000
    direction = Column(String(16), nullable=False, default="DIRECTED")
    calibration_source = Column(String(255), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    approval_status = Column(String(32), nullable=False, default="APPROVED")
    author_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    versions = relationship("SectorSpilloverRelationshipVersion", back_populates="relationship", cascade="all, delete-orphan")


class SectorSpilloverRelationshipVersion(Base):
    """Immutable version of a spillover relationship configuration."""
    __tablename__ = "sector_spillover_relationship_versions"

    id = Column(String(64), primary_key=True)
    relationship_id = Column(String(64), ForeignKey("sector_spillover_relationships.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    configuration_json = Column(JSON, nullable=False)
    calibration_metadata = Column(JSON, nullable=True)
    change_reason = Column(String(255), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    relationship = relationship("SectorSpilloverRelationship", back_populates="versions")


class SectorShockMappingResult(Base):
    """Resolved instrument-to-shock mapping for a simulation run."""
    __tablename__ = "sector_shock_mapping_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("sector_shock_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    listing_id = Column(String(64), nullable=True)
    sector_id = Column(String(64), nullable=True)
    industry_id = Column(String(64), nullable=True)
    mapping_method = Column(String(64), nullable=False)
    mapping_status = Column(String(32), nullable=False, default="MAPPED") # MAPPED, SPILLOVER_ONLY, UNMAPPED
    mapping_rationale = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class SectorShockSimulationRun(Base):
    """Master simulation execution record."""
    __tablename__ = "sector_shock_simulation_runs"

    id = Column(String(64), primary_key=True)
    simulation_code = Column(String(64), unique=True, nullable=False, index=True)
    scenario_id = Column(String(64), ForeignKey("sector_shock_scenarios.id", ondelete="SET NULL"), nullable=True, index=True)
    scenario_version_id = Column(String(64), nullable=True)
    portfolio_id = Column(String(64), nullable=False, index=True)
    portfolio_snapshot_id = Column(String(64), nullable=True)
    base_currency = Column(String(10), nullable=False, default="USD")
    calculation_version = Column(String(32), nullable=False, default="1.0.0")
    conflict_resolution_policy = Column(String(32), nullable=False, default="MOST_SPECIFIC_WINS") # MOST_SPECIFIC_WINS, REJECT_CONFLICT, DIRECT_SHOCK_WINS, ADDITIVE_INCREMENTAL
    missing_data_policy = Column(String(32), nullable=False, default="STRICT") # STRICT, PARTIAL, EXCLUDE_UNSUPPORTED
    composition_policy = Column(String(32), nullable=False, default="ADDITIVE") # ADDITIVE, COMPOUND
    run_status = Column(String(32), nullable=False, default="RUNNING") # RUNNING, COMPLETED, COMPLETED_WITH_WARNINGS, PARTIAL, FAILED

    baseline_nav = Column(Numeric(20, 4), nullable=False)
    scenario_nav = Column(Numeric(20, 4), nullable=False)
    scenario_pnl = Column(Numeric(20, 4), nullable=False)
    scenario_loss = Column(Numeric(20, 4), nullable=False)
    scenario_return = Column(Numeric(14, 8), nullable=False)

    direct_exposure_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)
    spillover_exposure_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)
    classification_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)
    sensitivity_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)

    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=True)

    scenario = relationship("SectorShockScenario", back_populates="runs")
    position_results = relationship("SectorShockPositionResult", back_populates="run", cascade="all, delete-orphan")
    group_results = relationship("SectorShockGroupResult", back_populates="run", cascade="all, delete-orphan")
    attribution_results = relationship("SectorShockAttributionResult", back_populates="run", cascade="all, delete-orphan")
    warnings = relationship("SectorShockWarning", back_populates="run", cascade="all, delete-orphan")


class SectorShockPositionResult(Base):
    """Position-level scenario revaluation results."""
    __tablename__ = "sector_shock_position_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("sector_shock_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    listing_id = Column(String(64), nullable=True)
    sector = Column(String(64), nullable=True)
    industry = Column(String(64), nullable=True)
    currency = Column(String(10), nullable=False, default="USD")

    signed_quantity = Column(Numeric(18, 4), nullable=False)
    baseline_price = Column(Numeric(18, 4), nullable=False)
    scenario_price = Column(Numeric(18, 4), nullable=False)
    baseline_market_value = Column(Numeric(20, 4), nullable=False)
    scenario_market_value = Column(Numeric(20, 4), nullable=False)

    direct_sector_return = Column(Numeric(14, 8), nullable=False, default=0.0)
    industry_return = Column(Numeric(14, 8), nullable=False, default=0.0)
    sensitivity_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    spillover_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    factor_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    manual_adjustment = Column(Numeric(14, 8), nullable=False, default=0.0)
    final_scenario_return = Column(Numeric(14, 8), nullable=False)

    scenario_pnl = Column(Numeric(20, 4), nullable=False)
    scenario_loss = Column(Numeric(20, 4), nullable=False)
    portfolio_contribution = Column(Numeric(14, 8), nullable=False)

    mapping_status = Column(String(32), nullable=False, default="MAPPED")
    classification_status = Column(String(32), nullable=False, default="CLASSIFIED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("SectorShockSimulationRun", back_populates="position_results")


class SectorShockGroupResult(Base):
    """Aggregated sector and industry group performance."""
    __tablename__ = "sector_shock_group_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("sector_shock_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    group_type = Column(String(32), nullable=False) # SECTOR, INDUSTRY
    group_identifier = Column(String(64), nullable=False, index=True) # e.g. FINANCIALS, TECHNOLOGY
    baseline_exposure = Column(Numeric(20, 4), nullable=False)
    direct_shock = Column(Numeric(14, 8), nullable=False, default=0.0)
    spillover_shock = Column(Numeric(14, 8), nullable=False, default=0.0)
    total_scenario_return = Column(Numeric(14, 8), nullable=False)
    scenario_pnl = Column(Numeric(20, 4), nullable=False)
    scenario_loss = Column(Numeric(20, 4), nullable=False)
    portfolio_contribution = Column(Numeric(14, 8), nullable=False)
    position_count = Column(Integer, nullable=False)
    classification_coverage = Column(Numeric(6, 4), nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("SectorShockSimulationRun", back_populates="group_results")


class SectorShockAttributionResult(Base):
    """Decomposition of portfolio losses across channels and groups."""
    __tablename__ = "sector_shock_attribution_results"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("sector_shock_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    attribution_type = Column(String(32), nullable=False) # SECTOR, INDUSTRY, IMPACT_CHANNEL (DIRECT, SPILLOVER, FACTOR, MANUAL)
    attribution_identifier = Column(String(64), nullable=False)
    direct_impact = Column(Numeric(20, 4), nullable=False, default=0.0)
    spillover_impact = Column(Numeric(20, 4), nullable=False, default=0.0)
    factor_impact = Column(Numeric(20, 4), nullable=False, default=0.0)
    manual_impact = Column(Numeric(20, 4), nullable=False, default=0.0)
    total_impact = Column(Numeric(20, 4), nullable=False)
    contribution_percentage = Column(Numeric(10, 6), nullable=False)
    reconciliation_residual = Column(Numeric(14, 8), nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("SectorShockSimulationRun", back_populates="attribution_results")


class SectorShockWarning(Base):
    """Validation diagnostics and caveat warnings."""
    __tablename__ = "sector_shock_warnings"

    id = Column(String(64), primary_key=True)
    simulation_run_id = Column(String(64), ForeignKey("sector_shock_simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=True)
    group_identifier = Column(String(64), nullable=True)
    warning_code = Column(String(64), nullable=False) # UNCLASSIFIED_HOLDING, MISSING_SENSITIVITY, OVERLAPPING_SHOCK, CYCLE_DETECTED
    severity = Column(String(16), nullable=False, default="INFO") # INFO, WARNING, HIGH, CRITICAL
    category = Column(String(32), nullable=False, default="GENERAL")
    message = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=True)
    resolution_status = Column(String(32), nullable=False, default="UNRESOLVED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("SectorShockSimulationRun", back_populates="warnings")


class SectorShockAuditLog(Base):
    """Audit log tracking configuration changes and scenario executions."""
    __tablename__ = "sector_shock_audit_logs"

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

