"""
SQLAlchemy ORM models for M10.07 Monte Carlo Scenarios.
Adheres strictly to SQLAlchemy 2.0 type conventions using Mapped[Optional[T]].
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import uuid

from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    JSON,
    BigInteger,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class MonteCarloScenario(Base):
    """
    Master scenario entity defining name, description, horizon, and scope.
    """
    __tablename__ = "m10_monte_carlo_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    horizon_days: Mapped[int] = mapped_column(Integer, default=20, nullable=False)  # e.g., 1, 5, 10, 20, 60, 252
    time_step_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False) # delta t (1 = daily)
    distribution_type: Mapped[str] = mapped_column(String(32), default="MULTIVARIATE_NORMAL", nullable=False) # MULTIVARIATE_NORMAL, STUDENT_T, EMPIRICAL_BOOTSTRAP
    degrees_of_freedom: Mapped[Optional[float]] = mapped_column(Float, default=5.0, nullable=True)
    expected_return_model: Mapped[str] = mapped_column(String(32), default="ZERO_DRIFT", nullable=False) # ZERO_DRIFT, HISTORICAL_MEAN, CUSTOM
    volatility_model: Mapped[str] = mapped_column(String(32), default="SAMPLE_ANNUALIZED", nullable=False) # SAMPLE_ANNUALIZED, EWMA, STRESSED_MULTIPLIER
    volatility_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    correlation_repair_method: Mapped[str] = mapped_column(String(32), default="EIGENVALUE_CLIPPING", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    runs: Mapped[List["MonteCarloSimulationRun"]] = relationship("MonteCarloSimulationRun", back_populates="scenario", cascade="all, delete-orphan")


class MonteCarloSimulationRun(Base):
    """
    Execution record of a Monte Carlo simulation.
    Includes seed, path counts, execution time, and status.
    """
    __tablename__ = "m10_monte_carlo_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("m10_monte_carlo_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    n_paths: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    n_steps: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    random_seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    generator_algorithm: Mapped[str] = mapped_column(String(32), default="PCG64", nullable=False)
    matrix_was_repaired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False) # PENDING, RUNNING, COMPLETED, FAILED
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_parameters_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    scenario: Mapped["MonteCarloScenario"] = relationship("MonteCarloScenario", back_populates="runs")
    summary: Mapped[Optional["MonteCarloSimulationSummary"]] = relationship("MonteCarloSimulationSummary", back_populates="run", uselist=False, cascade="all, delete-orphan")
    risk_metrics: Mapped[List["MonteCarloRiskMetric"]] = relationship("MonteCarloRiskMetric", back_populates="run", cascade="all, delete-orphan")
    instrument_results: Mapped[List["MonteCarloInstrumentResult"]] = relationship("MonteCarloInstrumentResult", back_populates="run", cascade="all, delete-orphan")
    audit_events: Mapped[List["MonteCarloAuditEvent"]] = relationship("MonteCarloAuditEvent", back_populates="run", cascade="all, delete-orphan")


class MonteCarloSimulationSummary(Base):
    """
    Portfolio-level outcome summary from the simulation run.
    Contains statistical moments, baseline valuation, and distribution quantiles.
    """
    __tablename__ = "m10_monte_carlo_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m10_monte_carlo_runs.id", ondelete="CASCADE"), unique=True, nullable=False)
    baseline_portfolio_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    mean_terminal_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    median_terminal_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    std_terminal_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    mean_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    median_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    std_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    skewness_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    excess_kurtosis_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    loss_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    min_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    max_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    percentiles_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False) # p1, p5, p10, p25, p50, p75, p90, p95, p99

    # Relationships
    run: Mapped["MonteCarloSimulationRun"] = relationship("MonteCarloSimulationRun", back_populates="summary")


class MonteCarloRiskMetric(Base):
    """
    Loss-positive VaR and Expected Shortfall metrics at configured confidence intervals.
    """
    __tablename__ = "m10_monte_carlo_risk_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m10_monte_carlo_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False) # 0.90, 0.95, 0.99
    var_loss_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False) # Loss is positive
    cvar_loss_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False) # Loss is positive
    var_percent: Mapped[float] = mapped_column(Float, nullable=False) # VaR / baseline value
    cvar_percent: Mapped[float] = mapped_column(Float, nullable=False) # CVaR / baseline value
    pnl_cutoff_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False) # Terminal P&L cutoff (negative)

    # Relationships
    run: Mapped["MonteCarloSimulationRun"] = relationship("MonteCarloSimulationRun", back_populates="risk_metrics")


class MonteCarloInstrumentResult(Base):
    """
    Simulated results per instrument in the portfolio.
    """
    __tablename__ = "m10_monte_carlo_instrument_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m10_monte_carlo_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    mean_terminal_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    mean_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pnl_std: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    var_95_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    annualized_volatility: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    run: Mapped["MonteCarloSimulationRun"] = relationship("MonteCarloSimulationRun", back_populates="instrument_results")


class MonteCarloAuditEvent(Base):
    """
    Audit log for simulation runs, seed settings, parameter changes, and repairs.
    """
    __tablename__ = "m10_monte_carlo_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("m10_monte_carlo_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    run: Mapped[Optional["MonteCarloSimulationRun"]] = relationship("MonteCarloSimulationRun", back_populates="audit_events")

