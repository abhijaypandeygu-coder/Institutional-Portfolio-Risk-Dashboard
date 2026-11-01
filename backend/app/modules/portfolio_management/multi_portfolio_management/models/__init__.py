"""
M05.08 Multi-Portfolio Management Models.
Domain models for portfolio groups, membership lifecycle, hierarchy, shared policies/overrides,
consolidation runs, consolidated holdings, contributor lineage, consolidated cash, snapshots, and audit events.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


class GroupType(str, Enum):
    STRATEGY = "STRATEGY"
    DESK = "DESK"
    MANDATE = "MANDATE"
    FUND_FAMILY = "FUND_FAMILY"
    TEAM = "TEAM"
    GEOGRAPHY = "GEOGRAPHY"
    REPORTING_GROUP = "REPORTING_GROUP"
    CUSTOM = "CUSTOM"


class GroupStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class MembershipRole(str, Enum):
    MEMBER = "MEMBER"
    PRIMARY_MEMBER = "PRIMARY_MEMBER"
    OBSERVER = "OBSERVER"
    REPORTING_ONLY = "REPORTING_ONLY"
    CONSOLIDATION_ELIGIBLE = "CONSOLIDATION_ELIGIBLE"
    EXCLUDED_FROM_CONSOLIDATION = "EXCLUDED_FROM_CONSOLIDATION"


class MembershipStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REMOVED = "REMOVED"


class ConsolidationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class PortfolioGroup(Base):
    """
    Logical container referencing one or more existing portfolios.
    """
    __tablename__ = "portfolio_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    group_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    group_type: Mapped[str] = mapped_column(String(32), default=GroupType.CUSTOM.value, nullable=False)
    parent_group_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("portfolio_groups.id"), nullable=True, index=True)
    owner_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    primary_benchmark_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    shared_risk_convention: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=GroupStatus.ACTIVE.value, nullable=False)
    
    current_version: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    parent_group: Mapped[Optional["PortfolioGroup"]] = relationship("PortfolioGroup", remote_side=[id], backref="child_groups")
    memberships: Mapped[List["PortfolioGroupMembership"]] = relationship("PortfolioGroupMembership", back_populates="group", cascade="all, delete-orphan")
    policies: Mapped[List["PortfolioGroupPolicy"]] = relationship("PortfolioGroupPolicy", back_populates="group", cascade="all, delete-orphan")
    overrides: Mapped[List["PortfolioGroupSettingOverride"]] = relationship("PortfolioGroupSettingOverride", back_populates="group", cascade="all, delete-orphan")
    consolidation_runs: Mapped[List["PortfolioGroupConsolidationRun"]] = relationship("PortfolioGroupConsolidationRun", back_populates="group", cascade="all, delete-orphan")
    snapshots: Mapped[List["PortfolioGroupSnapshot"]] = relationship("PortfolioGroupSnapshot", back_populates="group", cascade="all, delete-orphan")


class PortfolioGroupMembership(Base):
    """
    Stores historical and current relationships between groups and portfolios with bitemporal semantics.
    """
    __tablename__ = "portfolio_group_memberships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    membership_role: Mapped[str] = mapped_column(String(48), default=MembershipRole.MEMBER.value, nullable=False)
    membership_status: Mapped[str] = mapped_column(String(32), default=MembershipStatus.ACTIVE.value, nullable=False)
    
    # Consolidation eligibility flags
    include_in_positions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_in_valuation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_in_cash: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_in_contribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_in_risk_inputs: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Optional reporting weight (never mutates raw holdings)
    reporting_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    # Effective and Knowledge dates
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    recorded_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    recorded_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    membership_version: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    approval_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    group: Mapped["PortfolioGroup"] = relationship("PortfolioGroup", back_populates="memberships")

    __table_args__ = (
        Index("idx_group_port_eff", "group_id", "portfolio_id", "effective_from", "effective_to"),
    )


class PortfolioGroupMembershipEvent(Base):
    """
    Immutable audit trail of membership changes.
    """
    __tablename__ = "portfolio_group_membership_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    membership_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)  # ADD, REMOVE, SUSPEND, REACTIVATE, SCOPE_CHANGE
    previous_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    membership_version: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PortfolioGroupPolicy(Base):
    """
    Versioned shared group settings and policy references.
    """
    __tablename__ = "portfolio_group_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    benchmark_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    risk_convention_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    valuation_policy_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    calendar_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    return_convention_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    exposure_aggregation_policy: Mapped[str] = mapped_column(String(64), default="CANONICAL_INSTRUMENT", nullable=False)
    configuration_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    policy_version: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    group: Mapped["PortfolioGroup"] = relationship("PortfolioGroup", back_populates="policies")


class PortfolioGroupSettingOverride(Base):
    """
    Portfolio-specific overrides inside a group context without modifying M05.01 portfolio configuration.
    """
    __tablename__ = "portfolio_group_setting_overrides"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    setting_type: Mapped[str] = mapped_column(String(64), nullable=False)  # BENCHMARK, RISK_CONVENTION, CALENDAR
    override_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    override_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    override_version: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    group: Mapped["PortfolioGroup"] = relationship("PortfolioGroup", back_populates="overrides")


class PortfolioGroupConsolidationRun(Base):
    """
    Tracks an execution of cross-portfolio consolidation.
    """
    __tablename__ = "portfolio_group_consolidation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    group_version: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    membership_version: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    consolidation_type: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False)
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    consolidation_policy_version: Mapped[str] = mapped_column(String(64), default="CONS-POL-V1", nullable=False)
    
    included_portfolio_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    excluded_portfolio_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    distinct_instrument_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    
    total_gross_long_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_gross_short_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    run_status: Mapped[str] = mapped_column(String(32), default=ConsolidationStatus.COMPLETED.value, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    input_manifest_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    group: Mapped["PortfolioGroup"] = relationship("PortfolioGroup", back_populates="consolidation_runs")
    holdings: Mapped[List["PortfolioGroupConsolidatedHolding"]] = relationship("PortfolioGroupConsolidatedHolding", back_populates="consolidation_run", cascade="all, delete-orphan")
    cash_summaries: Mapped[List["PortfolioGroupCashSummary"]] = relationship("PortfolioGroupCashSummary", back_populates="consolidation_run", cascade="all, delete-orphan")


class PortfolioGroupConsolidatedHolding(Base):
    """
    Consolidated instrument holding summary across participating portfolios.
    """
    __tablename__ = "portfolio_group_consolidated_holdings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consolidation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_group_consolidation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    native_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    # Quantities
    gross_long_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_short_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    # Market values in reporting currency
    gross_long_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_short_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    reporting_currency_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    contributing_portfolio_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    contributing_account_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    valuation_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    consolidation_run: Mapped["PortfolioGroupConsolidationRun"] = relationship("PortfolioGroupConsolidationRun", back_populates="holdings")
    contributors: Mapped[List["PortfolioGroupHoldingContributor"]] = relationship("PortfolioGroupHoldingContributor", back_populates="consolidated_holding", cascade="all, delete-orphan")


class PortfolioGroupHoldingContributor(Base):
    """
    Source lineage record for every single contributing portfolio position.
    """
    __tablename__ = "portfolio_group_holding_contributors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consolidated_holding_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_group_consolidated_holdings.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_position_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_valuation_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_side: Mapped[str] = mapped_column(String(16), nullable=False)  # LONG / SHORT
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    market_value_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    market_value_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate_applied: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False)
    source_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    consolidated_holding: Mapped["PortfolioGroupConsolidatedHolding"] = relationship("PortfolioGroupConsolidatedHolding", back_populates="contributors")


class PortfolioGroupCashSummary(Base):
    """
    Consolidated cash summary grouped by currency.
    """
    __tablename__ = "portfolio_group_cash_summaries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consolidation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_group_consolidation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settled_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unsettled_receivables: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unsettled_payables: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    reserved_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    restricted_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    available_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reporting_currency_equivalent: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    contributing_account_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    completeness_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    consolidation_run: Mapped["PortfolioGroupConsolidationRun"] = relationship("PortfolioGroupConsolidationRun", back_populates="cash_summaries")


class PortfolioGroupSnapshot(Base):
    """
    Immutable consolidated group snapshot metadata.
    """
    __tablename__ = "portfolio_group_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    consolidation_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_version: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    membership_version: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_snapshot_references: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy_version_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    snapshot_status: Mapped[str] = mapped_column(String(32), default="FINAL", nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    supersedes_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    group: Mapped["PortfolioGroup"] = relationship("PortfolioGroup", back_populates="snapshots")


class PortfolioGroupAuditEvent(Base):
    """
    Immutable audit events for group governance.
    """
    __tablename__ = "portfolio_group_audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
