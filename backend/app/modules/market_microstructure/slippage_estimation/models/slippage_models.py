"""
SQLAlchemy ORM models for M09.05 Slippage Estimation.
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


class SlippageBenchmarkConfig(Base):
    """
    Configuration rules for benchmark price selection and tolerances.
    """
    __tablename__ = "m09_05_slippage_benchmark_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_code: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    benchmark_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ARRIVAL_MIDPOINT"
    )  # DECISION_PRICE, ARRIVAL_PRICE, ARRIVAL_MIDPOINT, BEST_BID, BEST_ASK, USER_CUSTOM
    max_quote_age_seconds: Mapped[int] = mapped_column(Integer, default=60)
    allow_cross_venue_benchmarking: Mapped[bool] = mapped_column(Boolean, default=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    multiplier: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("config_code", "version", name="uq_m09_05_benchmark_config_ver"),
    )


class SlippageExecutionSummary(Base):
    """
    Overall execution slippage summary for an order or parent order execution.
    """
    __tablename__ = "m09_05_slippage_execution_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY or SELL
    order_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    execution_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Quantities
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unfilled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fill_rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    
    # Prices
    benchmark_type: Mapped[str] = mapped_column(String(50), nullable=False)
    benchmark_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    benchmark_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    vwap_execution_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_executed_notional: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    
    # Realized Slippage Metrics
    slippage_price_units: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    slippage_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    slippage_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    is_favorable: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Attribution Summary
    market_movement_monetary: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0.0"))
    spread_crossing_monetary: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0.0"))
    residual_execution_monetary: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0.0"))
    attribution_reconciled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Explicit Fees and Total All-In Cost
    total_explicit_fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"))
    total_all_in_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0.0"))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_m09_05_summary_sym_time", "symbol", "order_created_at"),
    )


class SlippageFillAttribution(Base):
    """
    Granular fill-level additive attribution record.
    """
    __tablename__ = "m09_05_slippage_fill_attributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fill_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    fill_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    venue: Mapped[str] = mapped_column(String(50), default="DEFAULT")
    
    fill_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fill_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    benchmark_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Market state at fill
    bid_at_fill: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    ask_at_fill: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    midpoint_at_fill: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    
    # Total Fill Slippage
    fill_slippage_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fill_slippage_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    fill_slippage_money: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    
    # Additive Components
    market_movement_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    market_movement_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    market_movement_money: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    
    spread_crossing_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    spread_crossing_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    spread_crossing_money: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    
    residual_execution_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    residual_execution_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    residual_execution_money: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    
    reconciliation_discrepancy: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0.0"))
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_m09_05_fill_attr_order_fill", "order_id", "fill_id"),
    )


class SlippageOpportunityCost(Base):
    """
    Opportunity cost and Implementation Shortfall record for unexecuted quantities.
    """
    __tablename__ = "m09_05_slippage_opportunity_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    
    unfilled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    benchmark_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    terminal_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    terminal_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    terminal_price_source: Mapped[str] = mapped_column(String(50), default="EOD_CLOSE")
    
    opportunity_cost_price_units: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    opportunity_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    opportunity_cost_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    
    implementation_shortfall_monetary_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SlippageCalibrationObservation(Base):
    """
    Paired observation linking ex-ante estimated slippage with ex-post realized slippage.
    """
    __tablename__ = "m09_05_slippage_calibration_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    observation_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    estimated_slippage_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    realized_slippage_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    error_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    
    predicted_lower_bound_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    predicted_upper_bound_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    is_within_interval: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SlippageCalibrationRun(Base):
    """
    Summary record of calibration performance metrics across historical executions.
    """
    __tablename__ = "m09_05_slippage_calibration_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_error_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    mean_absolute_error_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    root_mean_squared_error_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    
    t_statistic: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    is_bias_significant: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_coverage_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    
    run_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

