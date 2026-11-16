"""
SQLAlchemy ORM models for M11.01 Portfolio Risk Limits.
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
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class RiskLimitProfile(Base):
    """
    Risk Limit Profile master entity defining identity, category, mandate, and status.
    """
    __tablename__ = "m11_risk_limit_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_category: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False) # STANDARD, CONSERVATIVE, MODERATE, AGGRESSIVE, MANDATE_SPECIFIC
    mandate_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    portfolio_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    base_currency_policy: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False) # DRAFT, APPROVED, ACTIVE, SUSPENDED, EXPIRED, RETIRED
    owner_id: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    versions: Mapped[List["RiskLimitProfileVersion"]] = relationship(
        "RiskLimitProfileVersion", back_populates="profile", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["PortfolioLimitAssignment"]] = relationship(
        "PortfolioLimitAssignment", back_populates="profile", cascade="all, delete-orphan"
    )


class RiskLimitProfileVersion(Base):
    """
    Immutable versioned snapshot of a profile's risk-limit definitions.
    """
    __tablename__ = "m11_risk_limit_profile_versions"
    __table_args__ = (
        UniqueConstraint("profile_id", "version_number", name="uq_profile_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m11_risk_limit_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    version_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False) # DRAFT, SUBMITTED, APPROVED, ACTIVE, REJECTED
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    configuration_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    profile: Mapped["RiskLimitProfile"] = relationship("RiskLimitProfile", back_populates="versions")
    limits: Mapped[List["PortfolioRiskLimit"]] = relationship(
        "PortfolioRiskLimit", back_populates="profile_version", cascade="all, delete-orphan"
    )


class PortfolioRiskLimit(Base):
    """
    Individual risk-limit rule definition (VaR, Volatility, Drawdown).
    """
    __tablename__ = "m11_portfolio_risk_limits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m11_risk_limit_profile_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    limit_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_category: Mapped[str] = mapped_column(String(32), nullable=False) # VAR, VOLATILITY, DRAWDOWN
    metric_identifier: Mapped[str] = mapped_column(String(64), nullable=False) # VAR_95_1D, REALIZED_VOL_30D, DRAWDOWN_MAX
    limit_type: Mapped[str] = mapped_column(String(32), default="ABSOLUTE", nullable=False) # ABSOLUTE, NAV_RELATIVE, PERCENTAGE
    warning_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(16), default="USD", nullable=False) # USD, INR, PERCENT, RATIO
    comparison_operator: Mapped[str] = mapped_column(String(32), default="GREATER_THAN_OR_EQUAL", nullable=False)
    confidence_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 0.95, 0.99
    risk_horizon_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # 1, 10, 20
    risk_methodology: Mapped[Optional[str]] = mapped_column(String(64), nullable=True) # HISTORICAL, PARAMETRIC, MONTE_CARLO
    volatility_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True) # REALIZED, FORECAST
    return_frequency: Mapped[Optional[str]] = mapped_column(String(32), default="DAILY", nullable=True)
    annualization_factor: Mapped[Optional[float]] = mapped_column(Float, default=252.0, nullable=True)
    estimation_window_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # e.g. 30, 90, 252
    drawdown_methodology: Mapped[Optional[str]] = mapped_column(String(64), default="PEAK_TO_TROUGH", nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    profile_version: Mapped["RiskLimitProfileVersion"] = relationship("RiskLimitProfileVersion", back_populates="limits")


class PortfolioLimitAssignment(Base):
    """
    Assignment of an approved limit profile to a target portfolio or mandate.
    """
    __tablename__ = "m11_portfolio_limit_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m11_risk_limit_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO", nullable=False) # PORTFOLIO, MANDATE, PORTFOLIO_GROUP
    target_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False) # portfolio_id or mandate code
    assignment_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False) # ACTIVE, EXPIRED, SUPERSEDED
    precedence: Mapped[int] = mapped_column(Integer, default=1, nullable=False) # 1 = Specific Portfolio (highest), 2 = Mandate, 3 = Org Default
    assigned_by: Mapped[str] = mapped_column(String(64), default="risk_admin", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    profile: Mapped["RiskLimitProfile"] = relationship("RiskLimitProfile", back_populates="assignments")


class RiskLimitUtilizationSnapshot(Base):
    """
    Persisted evaluation snapshot of risk limits against observed measurements.
    """
    __tablename__ = "m11_risk_limit_utilizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_id: Mapped[str] = mapped_column(String(36), nullable=False)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_category: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    warning_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    warning_utilization_pct: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    hard_utilization_pct: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    headroom: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="USD", nullable=False)
    evaluation_status: Mapped[str] = mapped_column(String(32), nullable=False) # WITHIN_LIMIT, WARNING, HARD_LIMIT_EXCEEDED, UNAVAILABLE, STALE, INVALID
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RiskLimitAuditLog(Base):
    """
    Audit log of limit configurations, approvals, assignments, and activations.
    """
    __tablename__ = "m11_risk_limit_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    limit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
