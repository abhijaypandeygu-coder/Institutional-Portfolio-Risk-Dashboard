"""
SQLAlchemy ORM models for M11.05 — Dynamic Limits.

Defines database schemas for:
1. DynamicLimitPolicy: Top-level policy entity (governed, active version pointer).
2. DynamicLimitPolicyVersion: Immutable version containing rule definitions.
3. DynamicLimitCondition: Metric thresholds, operators, hysteresis bands, persistence.
4. DynamicLimitSchedule: Time-based session schedules across IN (Asia/Kolkata) and US (America/New_York).
5. DynamicLimitOverride: Time-bounded manual overrides with maker-checker approvals.
6. DynamicLimitEvaluation: Record of evaluation runs.
7. EffectiveLimitSnapshot: Immutable point-in-time calculation snapshots consumed by M11.07 & M11.08.
8. DynamicLimitAuditEvent: Complete audit trail for policy lifecycle and override actions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Text,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


class DynamicLimitPolicy(Base):
    """
    Top-level Dynamic Limit Policy.
    Maps to a specific portfolio, asset class, market, or global default.
    """
    __tablename__ = "dynamic_limit_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    market: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)  # IN, US, or GLOBAL
    asset_class: Mapped[str] = mapped_column(String(32), default="EQUITY")
    
    # State lifecycle: DRAFT, SUBMITTED, APPROVED, ACTIVE, SUSPENDED, RETIRED
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    current_version_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Audit & ownership
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    versions: Mapped[List["DynamicLimitPolicyVersion"]] = relationship(
        "DynamicLimitPolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="desc(DynamicLimitPolicyVersion.version_number)"
    )
    overrides: Mapped[List["DynamicLimitOverride"]] = relationship(
        "DynamicLimitOverride",
        back_populates="policy",
        cascade="all, delete-orphan"
    )
    snapshots: Mapped[List["EffectiveLimitSnapshot"]] = relationship(
        "EffectiveLimitSnapshot",
        back_populates="policy",
        cascade="all, delete-orphan"
    )


class DynamicLimitPolicyVersion(Base):
    """
    Immutable version of a dynamic limit policy defining rules, conditions, and schedules.
    """
    __tablename__ = "dynamic_limit_policy_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("dynamic_limit_policies.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Target limit identifier and metric being modulated
    target_limit_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # e.g., MAX_POSITION_WEIGHT, MAX_PORTFOLIO_VAR
    limit_nature: Mapped[str] = mapped_column(String(16), default="CAP")  # CAP or FLOOR
    base_limit_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    restrictive_only: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Bounds protection
    min_allowed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    max_allowed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    
    # Approval governance (Maker-Checker)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")  # DRAFT, APPROVED, SUPERSEDED
    authored_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approval_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    policy: Mapped["DynamicLimitPolicy"] = relationship("DynamicLimitPolicy", back_populates="versions")
    conditions: Mapped[List["DynamicLimitCondition"]] = relationship(
        "DynamicLimitCondition",
        back_populates="version",
        cascade="all, delete-orphan"
    )
    schedules: Mapped[List["DynamicLimitSchedule"]] = relationship(
        "DynamicLimitSchedule",
        back_populates="version",
        cascade="all, delete-orphan"
    )


class DynamicLimitCondition(Base):
    """
    Condition-based rule that adjusts limits when trigger criteria are satisfied.
    """
    __tablename__ = "dynamic_limit_conditions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(String(64), ForeignKey("dynamic_limit_policy_versions.id", ondelete="CASCADE"), index=True)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)  # Lower number = higher priority
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Metric binding (e.g. M07 VIX / Portfolio Volatility, M09 Liquidity Depth, Market Regime, Drawdown)
    metric_source: Mapped[str] = mapped_column(String(64), nullable=False)  # VOLATILITY, LIQUIDITY, REGIME, DRAWDOWN
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)    # e.g., PORTFOLIO_VOLATILITY, MARKET_REGIME
    operator: Mapped[str] = mapped_column(String(32), default="GREATER_THAN")
    
    # Thresholds & Hysteresis
    threshold_low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    hysteresis_entry: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    hysteresis_exit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    hysteresis_direction: Mapped[str] = mapped_column(String(8), default="UP")  # UP or DOWN
    persistence_minutes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Categorical match (for REGIME: NORMAL, HIGH_VOLATILITY, STRESSED)
    regime_match: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Adjustment definition
    adjustment_type: Mapped[str] = mapped_column(String(32), default="MULTIPLICATIVE") # MULTIPLICATIVE, ADDITIVE, ABSOLUTE_REPLACEMENT
    adjustment_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    version: Mapped["DynamicLimitPolicyVersion"] = relationship("DynamicLimitPolicyVersion", back_populates="conditions")


class DynamicLimitSchedule(Base):
    """
    Time-based profile adjustments mapped to exchange trading sessions.
    """
    __tablename__ = "dynamic_limit_schedules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(String(64), ForeignKey("dynamic_limit_policy_versions.id", ondelete="CASCADE"), index=True)
    session_name: Mapped[str] = mapped_column(String(32), nullable=False)  # PRE_MARKET, MARKET_OPEN, REGULAR_TRADING, MARKET_CLOSE, POST_MARKET
    market: Mapped[str] = mapped_column(String(16), default="IN")          # IN or US
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    
    # Adjustment applied during this session
    adjustment_type: Mapped[str] = mapped_column(String(32), default="MULTIPLICATIVE")
    adjustment_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    version: Mapped["DynamicLimitPolicyVersion"] = relationship("DynamicLimitPolicyVersion", back_populates="schedules")


class DynamicLimitOverride(Base):
    """
    Time-bounded manual override with strict Maker-Checker governance.
    """
    __tablename__ = "dynamic_limit_overrides"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("dynamic_limit_policies.id", ondelete="CASCADE"), index=True)
    target_limit_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Override parameters
    override_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)  # MARKET_EVENT, CLIENT_REQUEST, EMERGENCY_DERISK, etc.
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Validity timeframe
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Governance (Maker-Checker)
    status: Mapped[str] = mapped_column(String(32), default="PENDING_APPROVAL")  # PENDING_APPROVAL, APPROVED, REJECTED, REVOKED, EXPIRED
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    policy: Mapped["DynamicLimitPolicy"] = relationship("DynamicLimitPolicy", back_populates="overrides")


class EffectiveLimitSnapshot(Base):
    """
    Immutable point-in-time calculation snapshot of effective limits.
    Directly consumed by M11.07 Pre-Trade Risk & M11.08 Breach Monitoring.
    """
    __tablename__ = "effective_limit_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("dynamic_limit_policies.id", ondelete="CASCADE"), index=True)
    policy_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    target_limit_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Values
    base_limit_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    effective_limit_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    limit_nature: Mapped[str] = mapped_column(String(16), nullable=False)
    
    # Contributing factors
    active_regime: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    active_session: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    condition_adjustment_applied: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    override_applied_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Audit & Cryptographic Lineage
    as_of_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    lineage_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    policy: Mapped["DynamicLimitPolicy"] = relationship("DynamicLimitPolicy", back_populates="snapshots")


class DynamicLimitAuditEvent(Base):
    """
    Audit log for dynamic limit policy lifecycle, overrides, and administrative actions.
    """
    __tablename__ = "dynamic_limit_audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # POLICY, VERSION, OVERRIDE, SNAPSHOT
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)       # CREATE, SUBMIT, APPROVE, OVERRIDE_REQUEST, OVERRIDE_APPROVE, REVOKE
    performed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

