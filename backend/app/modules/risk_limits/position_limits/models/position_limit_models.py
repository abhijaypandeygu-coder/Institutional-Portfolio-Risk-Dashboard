"""
SQLAlchemy ORM models for M11.02 Position Limits.
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
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class PositionLimitConfiguration(Base):
    """
    Core position-limit configuration rule.
    Supports portfolio-specific, instrument-specific, listing-specific, or issuer-specific limits.
    """
    __tablename__ = "m11_position_limit_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    limit_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scopes
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    issuer_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    profile_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("m11_position_limit_profiles.id"), nullable=True)

    # Limit specifications
    # MAX_POSITION_WEIGHT, MAX_ABSOLUTE_NOTIONAL, MAX_LONG_WEIGHT, MAX_SHORT_WEIGHT,
    # MAX_LONG_NOTIONAL, MAX_SHORT_NOTIONAL, MAX_ISSUER_WEIGHT, MAX_ISSUER_NOTIONAL
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="ANY", nullable=False) # LONG, SHORT, ANY, GROSS, NET
    aggregation_level: Mapped[str] = mapped_column(String(32), default="INSTRUMENT", nullable=False) # INSTRUMENT, LISTING, ISSUER

    # Thresholds
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    warning_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(32), default="PERCENT_NAV", nullable=False) # PERCENT_NAV, USD, INR, etc.
    limit_currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    comparison_operator: Mapped[str] = mapped_column(String(32), default="GREATER_THAN_OR_EQUAL", nullable=False)

    # Precedence & Lifecycle
    precedence: Mapped[int] = mapped_column(Integer, default=1, nullable=False) # 1: Override, 2: Portfolio, 3: Mandate, 4: Default
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False) # DRAFT, SUBMITTED_FOR_APPROVAL, APPROVED, ACTIVE, SUSPENDED, EXPIRED, RETIRED, REJECTED
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile: Mapped[Optional["PositionLimitProfile"]] = relationship("PositionLimitProfile", back_populates="configurations")


class PositionLimitProfile(Base):
    """
    Reusable position limit profile (e.g. CONSERVATIVE, MODERATE, AGGRESSIVE, MANDATE_SPECIFIC).
    """
    __tablename__ = "m11_position_limit_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_tier: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False) # STANDARD, CONSERVATIVE, MODERATE, AGGRESSIVE
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    configurations: Mapped[List["PositionLimitConfiguration"]] = relationship("PositionLimitConfiguration", back_populates="profile", cascade="all, delete-orphan")
    assignments: Mapped[List["PositionLimitAssignment"]] = relationship("PositionLimitAssignment", back_populates="profile", cascade="all, delete-orphan")


class PositionLimitAssignment(Base):
    """
    Assignment of a position limit profile to a portfolio, mandate, or asset scope.
    """
    __tablename__ = "m11_position_limit_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("m11_position_limit_profiles.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO", nullable=False) # PORTFOLIO, MANDATE, ISSUER
    target_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    precedence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    profile: Mapped["PositionLimitProfile"] = relationship("PositionLimitProfile", back_populates="assignments")


class PositionLimitEvaluation(Base):
    """
    Execution header for a position limit evaluation run.
    """
    __tablename__ = "m11_position_limit_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    evaluation_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO_WIDE", nullable=False) # PORTFOLIO_WIDE, INSTRUMENT, ISSUER, PROPOSED_ORDER
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    portfolio_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    overall_status: Mapped[str] = mapped_column(String(32), default="WITHIN_LIMIT", nullable=False) # WITHIN_LIMIT, WARNING, HARD_LIMIT_EXCEEDED, INVALID, UNAVAILABLE
    total_positions_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_breaches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_breaches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    results: Mapped[List["PositionLimitEvaluationResult"]] = relationship("PositionLimitEvaluationResult", back_populates="evaluation", cascade="all, delete-orphan")


class PositionLimitEvaluationResult(Base):
    """
    Individual evaluation result for a single position/instrument/issuer constraint.
    """
    __tablename__ = "m11_position_limit_evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String(36), ForeignKey("m11_position_limit_evaluations.id"), index=True, nullable=False)
    limit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    issuer_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    position_direction: Mapped[str] = mapped_column(String(16), default="LONG", nullable=False)

    # Financial Exposure & Limit metrics
    actual_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    exposure_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    warning_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(32), nullable=False)

    # Utilization
    warning_utilization_pct: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    hard_utilization_pct: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    remaining_capacity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    breach_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)

    # Status & Diagnostic details
    evaluation_status: Mapped[str] = mapped_column(String(32), nullable=False) # WITHIN_LIMIT, WARNING, HARD_LIMIT_EXCEEDED, NOT_APPLICABLE, INVALID
    reason_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    evaluation: Mapped["PositionLimitEvaluation"] = relationship("PositionLimitEvaluation", back_populates="results")


class PositionLimitBreachEvent(Base):
    """
    Audit event record for a limit breach. Feeds downstream M11.08 breach escalation.
    """
    __tablename__ = "m11_position_limit_breach_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    issuer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    breach_type: Mapped[str] = mapped_column(String(64), nullable=False) # POSITION_WEIGHT_BREACH, POSITION_NOTIONAL_BREACH, ISSUER_CONCENTRATION_BREACH
    severity: Mapped[str] = mapped_column(String(16), default="HIGH", nullable=False) # INFO, WARNING, HIGH, CRITICAL
    actual_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    breach_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    utilization_pct: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    cause: Mapped[str] = mapped_column(String(64), default="POSITION_INCREASE", nullable=False)
    detection_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PositionLimitAuditLog(Base):
    """
    Append-only configuration and operational audit log.
    """
    __tablename__ = "m11_position_limit_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False) # CONFIGURATION, PROFILE, ASSIGNMENT, EVALUATION
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False) # CREATE, APPROVE, ACTIVATE, SUSPEND, EVALUATE, BREACH
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
