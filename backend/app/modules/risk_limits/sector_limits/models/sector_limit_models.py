"""
SQLAlchemy ORM models for M11.03 Sector Limits.
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


class SectorLimitConfiguration(Base):
    """
    Configuration entity for sector, industry, or benchmark-relative active limits.
    """
    __tablename__ = "m11_sector_limit_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    limit_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    profile_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("m11_sector_limit_profiles.id"), nullable=True)

    # Classification Scope
    classification_system: Mapped[str] = mapped_column(String(32), default="GICS", nullable=False) # GICS, ICB, CUSTOM
    classification_version: Mapped[str] = mapped_column(String(32), default="2026.1", nullable=False)
    sector_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    sector_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    industry_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    industry_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Limit Type: MAX_SECTOR_WEIGHT, MAX_INDUSTRY_WEIGHT, MAX_SECTOR_NOTIONAL,
    # MAX_ACTIVE_SECTOR_OVERWEIGHT, MAX_ACTIVE_SECTOR_UNDERWEIGHT, etc.
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="GROSS", nullable=False) # GROSS, NET, LONG, SHORT

    # Thresholds
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False) # e.g. 25.0% or active cap
    warning_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False) # e.g. 20.0%
    lower_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True) # For underweight band, e.g. -5.0%
    threshold_unit: Mapped[str] = mapped_column(String(32), default="PERCENT_NAV", nullable=False) # PERCENT_NAV, ACTIVE_PERCENT, USD, INR

    # Benchmark reference (for relative limits)
    benchmark_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

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

    profile: Mapped[Optional["SectorLimitProfile"]] = relationship("SectorLimitProfile", back_populates="configurations")


class SectorLimitProfile(Base):
    """
    Reusable sector and industry limit profile.
    """
    __tablename__ = "m11_sector_limit_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_tier: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False)
    classification_system: Mapped[str] = mapped_column(String(32), default="GICS", nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    configurations: Mapped[List["SectorLimitConfiguration"]] = relationship("SectorLimitConfiguration", back_populates="profile", cascade="all, delete-orphan")
    assignments: Mapped[List["SectorLimitAssignment"]] = relationship("SectorLimitAssignment", back_populates="profile", cascade="all, delete-orphan")


class SectorLimitAssignment(Base):
    """
    Assignment of sector limit profile to a target portfolio or mandate.
    """
    __tablename__ = "m11_sector_limit_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("m11_sector_limit_profiles.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO", nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    precedence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    profile: Mapped["SectorLimitProfile"] = relationship("SectorLimitProfile", back_populates="assignments")


class SectorLimitEvaluation(Base):
    """
    Execution run header for sector & industry limit evaluations.
    """
    __tablename__ = "m11_sector_limit_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    evaluation_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO_WIDE", nullable=False)
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    portfolio_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    # Classification Coverage metrics
    total_eligible_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    classified_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unclassified_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    classification_coverage_pct: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    overall_status: Mapped[str] = mapped_column(String(32), default="WITHIN_LIMIT", nullable=False)
    total_sectors_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_industries_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_breaches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_breaches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    results: Mapped[List["SectorLimitEvaluationResult"]] = relationship("SectorLimitEvaluationResult", back_populates="evaluation", cascade="all, delete-orphan")


class SectorLimitEvaluationResult(Base):
    """
    Detailed evaluation row for a sector, industry, or benchmark-relative constraint.
    """
    __tablename__ = "m11_sector_limit_evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String(36), ForeignKey("m11_sector_limit_evaluations.id"), index=True, nullable=False)
    limit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    classification_level: Mapped[str] = mapped_column(String(16), default="SECTOR", nullable=False) # SECTOR or INDUSTRY
    sector_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    industry_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    # Exposures
    actual_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    benchmark_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    active_weight_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    # Thresholds & Limits
    warning_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(32), nullable=False)

    # Utilization & Status
    warning_utilization_pct: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    hard_utilization_pct: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    remaining_capacity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    breach_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    evaluation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    evaluation: Mapped["SectorLimitEvaluation"] = relationship("SectorLimitEvaluation", back_populates="results")


class SectorLimitBreachEvent(Base):
    """
    Immutable breach record feeding downstream M11.08 breach escalation.
    """
    __tablename__ = "m11_sector_limit_breach_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    sector_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    industry_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    breach_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="HIGH", nullable=False)
    actual_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    breach_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    utilization_pct: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    cause: Mapped[str] = mapped_column(String(64), default="SECTOR_CONCENTRATION", nullable=False)
    detection_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class SectorLimitAuditLog(Base):
    """
    Append-only configuration and operational audit log.
    """
    __tablename__ = "m11_sector_limit_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

