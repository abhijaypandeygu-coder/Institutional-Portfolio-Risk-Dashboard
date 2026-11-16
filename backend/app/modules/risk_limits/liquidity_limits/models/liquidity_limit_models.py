"""
SQLAlchemy ORM models for M11.04 Liquidity Limits.
Adheres strictly to SQLAlchemy 2.0 conventions using Mapped[Optional[T]].
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
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class LiquidityLimitConfiguration(Base):
    """
    Configuration entity for position and portfolio-level liquidity restrictions.
    """
    __tablename__ = "m11_liquidity_limit_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    limit_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    profile_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("m11_liquidity_limit_profiles.id"), nullable=True)

    # Limit Type: MIN_LIQUIDITY_SCORE, MIN_DISPLAYED_DEPTH, MIN_DAILY_VOLUME, MIN_DAILY_TURNOVER,
    # MAX_SPREAD_BPS, MAX_LIQUIDATION_COST, MAX_LIQUIDATION_HORIZON, MAX_PARTICIPATION_RATE, etc.
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Thresholds
    minimum_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    maximum_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    warning_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_unit: Mapped[str] = mapped_column(String(32), default="POINTS", nullable=False)
    threshold_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    # Execution & Horizon Parameters
    participation_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.1000"), nullable=False)
    lookback_sessions: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    horizon_unit: Mapped[str] = mapped_column(String(16), default="TRADING_DAYS", nullable=False)
    cost_methodology: Mapped[str] = mapped_column(String(64), default="ALL_IN_SLIPPAGE", nullable=False)

    # Stress Scenario Reference
    is_stress_limit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stress_scenario_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    precedence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile: Mapped[Optional["LiquidityLimitProfile"]] = relationship("LiquidityLimitProfile", back_populates="configurations")


class LiquidityLimitProfile(Base):
    """
    Reusable liquidity limit profile grouping position and portfolio liquidity policies.
    """
    __tablename__ = "m11_liquidity_limit_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_tier: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    configurations: Mapped[List["LiquidityLimitConfiguration"]] = relationship("LiquidityLimitConfiguration", back_populates="profile", cascade="all, delete-orphan")
    assignments: Mapped[List["LiquidityLimitAssignment"]] = relationship("LiquidityLimitAssignment", back_populates="profile", cascade="all, delete-orphan")


class LiquidityLimitAssignment(Base):
    """
    Assignment linking a liquidity limit profile to a target portfolio or mandate.
    """
    __tablename__ = "m11_liquidity_limit_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("m11_liquidity_limit_profiles.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO", nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    precedence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    profile: Mapped["LiquidityLimitProfile"] = relationship("LiquidityLimitProfile", back_populates="assignments")


class LiquidityLimitEvaluation(Base):
    """
    Execution run header for position-level and portfolio-wide liquidity evaluations.
    """
    __tablename__ = "m11_liquidity_limit_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    evaluation_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO_WIDE", nullable=False)
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    portfolio_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    # Aggregates
    total_positions_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_liquidation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    max_liquidation_horizon_days: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(32), default="WITHIN_LIMIT", nullable=False)
    warning_breaches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_breaches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unavailable_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    results: Mapped[List["PositionLiquidityEvaluationResult"]] = relationship("PositionLiquidityEvaluationResult", back_populates="evaluation", cascade="all, delete-orphan")


class PositionLiquidityEvaluationResult(Base):
    """
    Granular evaluation row for a position across liquidity dimensions.
    """
    __tablename__ = "m11_position_liquidity_evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String(36), ForeignKey("m11_liquidity_limit_evaluations.id"), index=True, nullable=False)
    limit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    position_side: Mapped[str] = mapped_column(String(8), default="LONG", nullable=False)
    position_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    position_notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Observed Metrics
    actual_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    liquidity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    available_depth: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    adv: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    spread_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    estimated_liquidation_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    estimated_horizon_days: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    participation_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Thresholds
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    warning_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_unit: Mapped[str] = mapped_column(String(32), nullable=False)

    # Utilization & Headroom
    utilization_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    headroom_or_capacity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    breach_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    evaluation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    evaluation: Mapped["LiquidityLimitEvaluation"] = relationship("LiquidityLimitEvaluation", back_populates="results")


class LiquidityLimitBreachEvent(Base):
    """
    Immutable breach record feeding downstream M11.08 breach escalation.
    """
    __tablename__ = "m11_liquidity_limit_breach_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    breach_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="HIGH", nullable=False)
    actual_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    breach_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    utilization_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    cause: Mapped[str] = mapped_column(String(64), default="LIQUIDITY_DETERIORATION", nullable=False)
    detection_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LiquidityDataExceptionRecord(Base):
    """
    Records missing, stale, or invalid market/microstructure inputs.
    """
    __tablename__ = "m11_liquidity_data_exceptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exception_type: Mapped[str] = mapped_column(String(64), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(32), default="UNAVAILABLE", nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LiquidityLimitAuditLog(Base):
    """
    Append-only configuration and operational audit log.
    """
    __tablename__ = "m11_liquidity_limit_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

