"""
SQLAlchemy 2.x Declarative Models for M09.07 Position Liquidation.
Includes tables for:
- position_liquidation_plans
- position_liquidation_targets
- position_liquidation_market_profiles
- position_liquidation_capacity_results
- position_liquidation_schedules
- position_liquidation_horizon_results
- position_liquidation_cost_results
- position_liquidation_plan_versions
- position_liquidation_calibration_runs
- portfolio_liquidation_results
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class PositionLiquidationPlan(Base):
    """Stores versioned liquidation-analysis plans."""

    __tablename__ = "m09_position_liquidation_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    position_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    venue_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    starting_signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    starting_absolute_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    starting_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    position_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    portfolio_base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    liquidation_side: Mapped[str] = mapped_column(String(8), nullable=False)  # SELL or BUY

    benchmark_type: Mapped[str] = mapped_column(String(32), default="MIDPOINT", nullable=False)
    benchmark_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    benchmark_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    maximum_participation_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.1000"), nullable=False)
    execution_schedule: Mapped[str] = mapped_column(String(32), default="PARTICIPATION_CAPPED", nullable=False)
    execution_start_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    maximum_horizon_sessions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    session_continuation_policy: Mapped[str] = mapped_column(String(32), default="CONTINUE_NEXT_SESSION", nullable=False)
    cost_configuration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON or text description

    stress_scenario_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    stress_scenario_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    plan_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    # Relationships
    targets: Mapped[List["PositionLiquidationTarget"]] = relationship(
        "PositionLiquidationTarget", back_populates="plan", cascade="all, delete-orphan"
    )
    schedules: Mapped[List["PositionLiquidationScheduleItem"]] = relationship(
        "PositionLiquidationScheduleItem", back_populates="plan", cascade="all, delete-orphan"
    )
    horizon_results: Mapped[List["PositionLiquidationHorizonResult"]] = relationship(
        "PositionLiquidationHorizonResult", back_populates="plan", cascade="all, delete-orphan"
    )
    cost_results: Mapped[List["PositionLiquidationCostResult"]] = relationship(
        "PositionLiquidationCostResult", back_populates="plan", cascade="all, delete-orphan"
    )


class PositionLiquidationTarget(Base):
    """Stores reduction targets associated with a liquidation plan."""

    __tablename__ = "m09_position_liquidation_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m09_position_liquidation_plans.plan_id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), default="PERCENTAGE", nullable=False)
    target_percentage: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    target_cumulative_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    target_incremental_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    target_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cumulative_target_flag: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    plan: Mapped["PositionLiquidationPlan"] = relationship("PositionLiquidationPlan", back_populates="targets")


class PositionLiquidationScheduleItem(Base):
    """Stores interval schedule allocations."""

    __tablename__ = "m09_position_liquidation_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m09_position_liquidation_plans.plan_id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schedule_type: Mapped[str] = mapped_column(String(32), default="PARTICIPATION_CAPPED", nullable=False)
    interval_index: Mapped[int] = mapped_column(Integer, nullable=False)
    session_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    interval_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    market_volume: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    planned_participation_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    expected_execution_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    estimated_interval_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    estimated_remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    plan: Mapped["PositionLiquidationPlan"] = relationship("PositionLiquidationPlan", back_populates="schedules")


class PositionLiquidationHorizonResult(Base):
    """Stores liquidation-time outcomes per target."""

    __tablename__ = "m09_position_liquidation_horizon_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m09_position_liquidation_plans.plan_id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    baseline_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stressed_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_interval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_session_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_completion_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    maximum_analysis_horizon_seconds: Mapped[int] = mapped_column(Integer, default=86400, nullable=False)
    expected_liquidated_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    completion_status: Mapped[str] = mapped_column(String(32), default="FULLY_LIQUIDATED_ESTIMATED", nullable=False)
    participation_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(32), default="PARTICIPATION_CAPPED", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    plan: Mapped["PositionLiquidationPlan"] = relationship("PositionLiquidationPlan", back_populates="horizon_results")


class PositionLiquidationCostResult(Base):
    """Stores cost breakdown and reconciliation per target."""

    __tablename__ = "m09_position_liquidation_cost_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m09_position_liquidation_plans.plan_id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    baseline_spread_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    baseline_depth_walk_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    baseline_market_impact_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    baseline_slippage_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    baseline_explicit_fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    baseline_opportunity_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)

    stressed_spread_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    stressed_depth_walk_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    stressed_market_impact_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    stressed_slippage_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    stressed_explicit_fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    stressed_opportunity_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)

    cumulative_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    incremental_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    cost_bps: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"), nullable=False)
    cost_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    cost_inclusion_map: Mapped[str] = mapped_column(String(256), default="SPREAD,DEPTH_WALK,IMPACT,SLIPPAGE,FEES,OPP_COST", nullable=False)
    reconciliation_difference: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    average_execution_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    plan: Mapped["PositionLiquidationPlan"] = relationship("PositionLiquidationPlan", back_populates="cost_results")


class PositionLiquidationCalibrationRun(Base):
    """Stores historical model calibration runs."""

    __tablename__ = "m09_position_liquidation_calibration_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calibration_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    calibration_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    calibration_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    training_sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_mae_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"), nullable=False)
    duration_rmse_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"), nullable=False)
    cost_mae_bps: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"), nullable=False)
    cost_rmse_bps: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"), nullable=False)
    prediction_bias_bps: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="VALIDATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PortfolioLiquidationSummary(Base):
    """Stores aggregated portfolio-level liquidation outcomes."""

    __tablename__ = "m09_portfolio_liquidation_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    schedule_mode: Mapped[str] = mapped_column(String(32), default="CONCURRENT", nullable=False)
    position_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    total_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    long_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    short_covering_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    critical_path_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    portfolio_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_status: Mapped[str] = mapped_column(String(32), default="FULLY_LIQUIDATED_ESTIMATED", nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

