"""
M10.06 Liquidity Stress Testing SQLAlchemy Database Models.
Implements:
1. LiquidityStressScenario: Scenario definition & metadata
2. LiquidityStressConfiguration: Immutable versioned scenario parameters
3. LiquidityStressInstrumentOverride: Instrument-specific stress parameters
4. LiquidityStressRun: Execution runs with status and timings
5. LiquidityStressMarketSnapshot: Baseline vs. Stressed quotes, spreads, and depth
6. LiquidityStressDepthLevel: Detailed L2 book levels under baseline and stressed conditions
7. LiquidityStressPositionResult: Position-level capacity, liquidation duration, and residual exposure
8. LiquidityStressHorizonResult: Time-bucketed liquidation horizons (15m, 30m, 1h, 1d, 3d, 5d, 10d)
9. LiquidityStressCostAttribution: Cost decomposition (spread, depth-walk, impact, slippage, fees)
10. LiquidityStressExecutionSchedule: Time-sliced execution schedule per interval
11. LiquidityStressAuditEvent: Governance audit trail
"""
from datetime import datetime, timezone
import enum
from typing import Optional, Dict, Any, List
from uuid import uuid4
from decimal import Decimal

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScenarioCategory(str, enum.Enum):
    HYPOTHETICAL = "HYPOTHETICAL"
    HISTORICAL_EPISODE = "HISTORICAL_EPISODE"
    MARKET_CRASH_SIMULTANEOUS = "MARKET_CRASH_SIMULTANEOUS"
    SEVERE_LIQUIDITY_DETERIORATION = "SEVERE_LIQUIDITY_DETERIORATION"
    REGULATORY_STRESS = "REGULATORY_STRESS"
    CUSTOM = "CUSTOM"


class ScenarioStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class RunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"


# ---------------------------------------------------------
# Table 1: LiquidityStressScenario
# ---------------------------------------------------------
class LiquidityStressScenario(Base):
    """
    Parent configuration for liquidity stress testing scenarios.
    """
    __tablename__ = "m10_liquidity_stress_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scenario_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario_category: Mapped[ScenarioCategory] = mapped_column(
        Enum(ScenarioCategory, native_enum=False), default=ScenarioCategory.SEVERE_LIQUIDITY_DETERIORATION, nullable=False
    )
    status: Mapped[ScenarioStatus] = mapped_column(
        Enum(ScenarioStatus, native_enum=False), default=ScenarioStatus.ACTIVE, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_scenario_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="system", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    configurations: Mapped[List["LiquidityStressConfiguration"]] = relationship(
        "LiquidityStressConfiguration", back_populates="scenario", cascade="all, delete-orphan"
    )
    overrides: Mapped[List["LiquidityStressInstrumentOverride"]] = relationship(
        "LiquidityStressInstrumentOverride", back_populates="scenario", cascade="all, delete-orphan"
    )
    runs: Mapped[List["LiquidityStressRun"]] = relationship(
        "LiquidityStressRun", back_populates="scenario", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------
# Table 2: LiquidityStressConfiguration
# ---------------------------------------------------------
class LiquidityStressConfiguration(Base):
    """
    Immutable versioned configuration containing core stress parameters.
    """
    __tablename__ = "m10_liquidity_stress_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Spread Stress Parameters
    spread_stress_type: Mapped[str] = mapped_column(String(32), default="PERCENTAGE", nullable=False)
    spread_increase_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("2.0000"), nullable=False)  # 200%
    spread_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("3.0000"), nullable=False)
    absolute_spread_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    
    # Depth Stress Parameters
    bid_depth_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.4000"), nullable=False)  # 60% reduction -> 40% remaining
    ask_depth_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.4000"), nullable=False)
    depth_stress_profile: Mapped[str] = mapped_column(String(32), default="UNIFORM", nullable=False)
    
    # Volume & Participation Parameters
    market_volume_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.5000"), nullable=False)  # 50% reduction
    participation_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.5000"), nullable=False)  # 50% reduction in cap
    base_participation_cap: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.1000"), nullable=False)   # default 10%
    
    # Impact & Execution Horizon
    impact_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1.5000"), nullable=False)
    execution_horizon_sessions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    market_price_shock_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"), nullable=False)
    
    configuration_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    scenario: Mapped["LiquidityStressScenario"] = relationship(
        "LiquidityStressScenario", back_populates="configurations"
    )

    __table_args__ = (
        Index("ix_m10_06_config_ver_unique", "scenario_id", "version_number", unique=True),
    )


# ---------------------------------------------------------
# Table 3: LiquidityStressInstrumentOverride
# ---------------------------------------------------------
class LiquidityStressInstrumentOverride(Base):
    """
    Instrument-specific stress overrides.
    """
    __tablename__ = "m10_liquidity_stress_instrument_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    spread_widening_override_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    depth_multiplier_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    volume_multiplier_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    participation_cap_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    override_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    scenario: Mapped["LiquidityStressScenario"] = relationship(
        "LiquidityStressScenario", back_populates="overrides"
    )


# ---------------------------------------------------------
# Table 4: LiquidityStressRun
# ---------------------------------------------------------
class LiquidityStressRun(Base):
    """
    Execution run of a liquidity stress scenario against a portfolio snapshot.
    """
    __tablename__ = "m10_liquidity_stress_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_version: Mapped[int] = mapped_column(Integer, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    baseline_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False), default=RunStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    baseline_data_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), default="M10.06_V1.0", nullable=False)
    
    # Portfolio Aggregate Metrics
    baseline_portfolio_notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    stressed_portfolio_notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    baseline_total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    stressed_total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    incremental_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    baseline_cost_bps: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.0"), nullable=False)
    stressed_cost_bps: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.0"), nullable=False)
    
    baseline_duration_sessions: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.0"), nullable=False)
    stressed_duration_sessions: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.0"), nullable=False)
    portfolio_liquidation_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1.0"), nullable=False)
    residual_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    unliquidated_positions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    calculation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="system", nullable=True)

    scenario: Mapped["LiquidityStressScenario"] = relationship(
        "LiquidityStressScenario", back_populates="runs"
    )
    market_snapshots: Mapped[List["LiquidityStressMarketSnapshot"]] = relationship(
        "LiquidityStressMarketSnapshot", back_populates="run", cascade="all, delete-orphan"
    )
    position_results: Mapped[List["LiquidityStressPositionResult"]] = relationship(
        "LiquidityStressPositionResult", back_populates="run", cascade="all, delete-orphan"
    )
    horizon_results: Mapped[List["LiquidityStressHorizonResult"]] = relationship(
        "LiquidityStressHorizonResult", back_populates="run", cascade="all, delete-orphan"
    )
    cost_attributions: Mapped[List["LiquidityStressCostAttribution"]] = relationship(
        "LiquidityStressCostAttribution", back_populates="run", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["LiquidityStressAuditEvent"]] = relationship(
        "LiquidityStressAuditEvent", back_populates="run", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------
# Table 5: LiquidityStressMarketSnapshot
# ---------------------------------------------------------
class LiquidityStressMarketSnapshot(Base):
    """
    Baseline vs. Stressed quotes, spreads, and market depth summary.
    """
    __tablename__ = "m10_liquidity_stress_market_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    baseline_bid: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    baseline_ask: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    baseline_midpoint: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    stressed_bid: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    stressed_ask: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    stressed_midpoint: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    
    baseline_spread: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    stressed_spread: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    spread_widening_multiple: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    
    baseline_bid_depth: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.0"), nullable=False)
    baseline_ask_depth: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.0"), nullable=False)
    stressed_bid_depth: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.0"), nullable=False)
    stressed_ask_depth: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.0"), nullable=False)
    
    baseline_volume: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.0"), nullable=False)
    stressed_volume: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.0"), nullable=False)
    data_quality_status: Mapped[str] = mapped_column(String(32), default="OBSERVED_INPUT", nullable=False)

    run: Mapped["LiquidityStressRun"] = relationship(
        "LiquidityStressRun", back_populates="market_snapshots"
    )
    depth_levels: Mapped[List["LiquidityStressDepthLevel"]] = relationship(
        "LiquidityStressDepthLevel", back_populates="market_snapshot", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------
# Table 6: LiquidityStressDepthLevel
# ---------------------------------------------------------
class LiquidityStressDepthLevel(Base):
    """
    Individual order-book levels under baseline and stressed conditions.
    """
    __tablename__ = "m10_liquidity_stress_depth_levels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    market_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_market_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # BID or ASK
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    baseline_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    stressed_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    stressed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    depth_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    level_notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    market_snapshot: Mapped["LiquidityStressMarketSnapshot"] = relationship(
        "LiquidityStressMarketSnapshot", back_populates="depth_levels"
    )


# ---------------------------------------------------------
# Table 7: LiquidityStressPositionResult
# ---------------------------------------------------------
class LiquidityStressPositionResult(Base):
    """
    Position-level stressed liquidation capacity, time, and costs.
    """
    __tablename__ = "m10_liquidity_stress_position_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    signed_position_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    liquidation_side: Mapped[str] = mapped_column(String(4), nullable=False)  # SELL or BUY
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    baseline_capacity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_capacity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_duration_sessions: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    stressed_duration_sessions: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    
    baseline_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    incremental_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_cost_bps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stressed_cost_bps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    residual_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    residual_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    completion_status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="OBSERVED_INPUT", nullable=False)
    calculation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    run: Mapped["LiquidityStressRun"] = relationship(
        "LiquidityStressRun", back_populates="position_results"
    )


# ---------------------------------------------------------
# Table 8: LiquidityStressHorizonResult
# ---------------------------------------------------------
class LiquidityStressHorizonResult(Base):
    """
    Time-bucketed progressive liquidation and residual risk.
    """
    __tablename__ = "m10_liquidity_stress_horizon_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # Null for portfolio aggregate
    horizon_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 15_MINUTES, 1_HOUR, 1D, 5D, etc.
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    cumulative_executed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    residual_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    liquidation_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    estimated_cost_bps: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    completion_status: Mapped[str] = mapped_column(String(32), default="IN_PROGRESS", nullable=False)

    run: Mapped["LiquidityStressRun"] = relationship(
        "LiquidityStressRun", back_populates="horizon_results"
    )


# ---------------------------------------------------------
# Table 9: LiquidityStressCostAttribution
# ---------------------------------------------------------
class LiquidityStressCostAttribution(Base):
    """
    Decomposition of liquidation costs across components (spread, depth, impact, slippage, fees).
    """
    __tablename__ = "m10_liquidity_stress_cost_attributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    cost_component: Mapped[str] = mapped_column(String(32), nullable=False)  # SPREAD, DEPTH_WALK, MARKET_IMPACT, SLIPPAGE, FEES
    baseline_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    incremental_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    attribution_method: Mapped[str] = mapped_column(String(32), default="STANDALONE_FACTORIAL", nullable=False)
    attribution_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    run: Mapped["LiquidityStressRun"] = relationship(
        "LiquidityStressRun", back_populates="cost_attributions"
    )


# ---------------------------------------------------------
# Table 10: LiquidityStressAuditEvent
# ---------------------------------------------------------
class LiquidityStressAuditEvent(Base):
    """
    Governance and reproducibility audit trail for execution runs.
    """
    __tablename__ = "m10_liquidity_stress_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_liquidity_stress_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_description: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), default="system", nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    event_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    run: Mapped["LiquidityStressRun"] = relationship(
        "LiquidityStressRun", back_populates="audit_events"
    )
