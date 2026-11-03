"""
M09.04 Market Impact - Database Models (SQLAlchemy 2.x).
Defines institutional relational tables for:
- market_impact_configs (m09_04_market_impact_configs)
- market_impact_scenarios (m09_04_market_impact_scenarios)
- market_impact_depth_walks (m09_04_market_impact_depth_walks)
- market_impact_depth_walk_levels (m09_04_market_impact_depth_walk_levels)
- market_impact_estimates (m09_04_market_impact_estimates)
- market_impact_model_configs (m09_04_market_impact_model_configs)
- market_impact_model_validation_runs (m09_04_market_impact_model_validation_runs)
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    DateTime,
    Numeric,
    JSON,
    Boolean,
    Text,
    Index,
    UniqueConstraint,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketImpactConfig(Base):
    """
    Versioned market-impact estimation policies and assumptions.
    """
    __tablename__ = "m09_04_market_impact_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    reference_price_method: Mapped[str] = mapped_column(String(32), default="MIDPOINT", nullable=False)
    default_execution_horizon_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    default_max_participation_rate: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    default_schedule: Mapped[str] = mapped_column(String(32), default="UNIFORM", nullable=False)

    square_root_y_coefficient: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    __table_args__ = (
        UniqueConstraint("config_code", "version", name="uq_m09_04_impact_cfg_code_ver"),
    )


class MarketImpactScenario(Base):
    """
    Hypothetical or historical order scenario for impact evaluation.
    """
    __tablename__ = "m09_04_market_impact_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    order_side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY, SELL
    proposed_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    proposed_notional: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_price_method: Mapped[str] = mapped_column(String(32), default="MIDPOINT", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    execution_horizon_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_participation_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    maximum_participation_rate: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    execution_schedule: Mapped[str] = mapped_column(String(32), default="IMMEDIATE", nullable=False)
    market_regime: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_04_scen_inst_time", "instrument_id", "created_at"),
    )


class MarketImpactDepthWalk(Base):
    """
    Static displayed-book simulation record for a proposed order scenario.
    """
    __tablename__ = "m09_04_market_impact_depth_walks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    depth_walk_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_book_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    order_side: Mapped[str] = mapped_column(String(8), nullable=False)
    proposed_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    visible_fill_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    residual_unfilled_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    fill_percentage: Mapped[float] = mapped_column(Float, nullable=False)

    reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    average_execution_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    marginal_execution_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    gross_execution_value: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)

    estimated_cost_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    estimated_cost_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_crossing_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    additional_depth_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    consumed_level_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_level_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class MarketImpactDepthWalkLevel(Base):
    """
    Granular level consumption details for a depth walk.
    """
    __tablename__ = "m09_04_market_impact_depth_walk_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    depth_walk_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    level_index: Mapped[int] = mapped_column(Integer, nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    consumed_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    executed_value: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_04_walk_level", "depth_walk_id", "level_index"),
    )


class MarketImpactEstimate(Base):
    """
    Empirical or horizon-modeled impact estimate.
    """
    __tablename__ = "m09_04_market_impact_estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estimate_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # DEPTH_WALK, SQUARE_ROOT, EMPIRICAL_REGRESSION, KYLE_OFI
    model_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)

    reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    estimated_impact_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_temporary_impact_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_permanent_impact_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_cost_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)

    participation_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prediction_lower_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prediction_upper_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    standard_error_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    market_regime: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)
    estimation_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class MarketImpactModelConfig(Base):
    """
    Versioned empirical model specification and calibrated parameter values.
    """
    __tablename__ = "m09_04_market_impact_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # SQUARE_ROOT, EMPIRICAL_REGRESSION, KYLE_OFI

    parameter_values: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    calibration_sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    __table_args__ = (
        UniqueConstraint("model_code", "version", name="uq_m09_04_model_code_ver"),
    )


class MarketImpactModelValidationRun(Base):
    """
    Out-of-sample backtesting and validation metrics for an impact model.
    """
    __tablename__ = "m09_04_market_impact_model_validation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[int] = mapped_column(Integer, nullable=False)

    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mae: Mapped[float] = mapped_column(Float, nullable=False)
    rmse: Mapped[float] = mapped_column(Float, nullable=False)
    mean_bias_error: Mapped[float] = mapped_column(Float, nullable=False)
    interval_coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="PASSED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
