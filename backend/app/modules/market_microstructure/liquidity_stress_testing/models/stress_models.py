"""
SQLAlchemy ORM models for M09.06 Liquidity Stress Testing.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String,
    DateTime,
    Numeric,
    Boolean,
    Integer,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class LiquidityStressConfig(Base):
    """
    Versioned stress scenario configuration definition.
    """
    __tablename__ = "m09_06_liquidity_stress_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_code: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    scenario_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="COMBINED_STRESS"
    )  # BASELINE, SINGLE_FACTOR, COMBINED_STRESS, HISTORICAL_EMPIRICAL, REVERSE_STRESS, CUSTOM
    
    # Spread Transformation parameters
    spread_shock_method: Mapped[str] = mapped_column(String(50), default="MULTIPLIER")
    spread_multiplier: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1.50"))
    spread_additive_bps: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"))
    
    # Depth Reduction parameters
    depth_shock_method: Mapped[str] = mapped_column(String(50), default="UNIFORM")
    bid_depth_reduction: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.25"))
    ask_depth_reduction: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.25"))
    
    # Volume Contraction parameters
    volume_shock_method: Mapped[str] = mapped_column(String(50), default="UNIFORM")
    volume_contraction: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.20"))
    participation_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.10"))
    
    execution_horizon_intervals: Mapped[int] = mapped_column(Integer, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("scenario_code", "version", name="uq_m09_06_stress_config_ver"),
    )


class LiquidityStressScenarioRun(Base):
    """
    Executed liquidity stress test run metadata.
    """
    __tablename__ = "m09_06_liquidity_stress_scenario_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    scenario_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scenario_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    instrument_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(50), default="DEFAULT")
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY or SELL
    order_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Baseline vs Stressed Spread
    baseline_spread: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    stressed_spread: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Immediate Visible Depth
    baseline_visible_depth: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_visible_depth: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Liquidation Duration (Intervals)
    baseline_duration_intervals: Mapped[int] = mapped_column(Integer, nullable=False)
    stressed_duration_intervals: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_increase_intervals: Mapped[int] = mapped_column(Integer, nullable=False)
    liquidation_status: Mapped[str] = mapped_column(String(50), default="COMPLETED")
    
    # Executable vs Residual Quantity
    stressed_fillable_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_residual_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Cost Comparison
    baseline_total_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    stressed_total_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cost_escalation_monetary: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cost_escalation_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    cost_escalation_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_m09_06_run_inst_time", "instrument_id", "created_at"),
    )


class LiquidityStressMonitoringSnapshot(Base):
    """
    Ongoing monitoring of liquidity deterioration relative to stress thresholds.
    """
    __tablename__ = "m09_06_liquidity_stress_monitoring_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(50), default="DEFAULT")
    monitoring_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    current_spread: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    baseline_spread: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    spread_multiplier: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    
    current_depth: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_depth: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    depth_reduction_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    
    stress_status: Mapped[str] = mapped_column(String(20), default="NORMAL")  # NORMAL, WARNING, BREACH
    alert_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
