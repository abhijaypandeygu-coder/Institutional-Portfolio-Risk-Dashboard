"""
SQLAlchemy ORM models for M12.05 — Alert Prioritization.

Tables:
1. `alert_priority_policies`: Governed, versioned policies for severity, urgency, and composite weighting.
2. `alert_priority_evaluations`: Immutable calculation records of priority scores and dimensions per alert.
3. `alert_priority_history`: Historical log of priority changes and recalculation events.
4. `alert_deduplication_records`: Audit log of deduplication assessments and duplicate occurrences.
5. `alert_groups`: Navigable clusters of correlated alerts (parent-child hierarchy).
6. `alert_group_members`: Memberships linking alerts to groups with correlation metadata.
7. `alert_occurrences`: Immutable log of repeated alert occurrences.
8. `alert_escalation_events`: Formal escalation transitions when severity or priority jumps.
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
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class AlertPriorityPolicy(Base):
    """
    Governed, versioned policy configuring severity rules, urgency scoring,
    impact weighting, and priority floor constraints.
    """
    __tablename__ = "alert_priority_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    policy_type: Mapped[str] = mapped_column(String(64), default="DEFAULT")  # DEFAULT, CATEGORY_SPECIFIC, PORTFOLIO_SPECIFIC
    alert_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_module: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    severity_rules: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    urgency_rules: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    impact_weights: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # {"F": 0.45, "R": 0.40, "B": 0.15}
    priority_weights: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # {"S": 0.35, "U": 0.30, "I": 0.25, "P": 0.10}
    priority_band_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    priority_floor_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # e.g., {"EMERGENCY": 90.0, "CRITICAL": 50.0}

    effective_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    updated_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class AlertGroup(Base):
    """
    Cluster of correlated or repeated alerts (Parent group entity).
    """
    __tablename__ = "alert_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    group_type: Mapped[str] = mapped_column(String(64), default="CORRELATED_CONDITION")  # DEDUPE_GROUP, CORRELATED_CONDITION, PORTFOLIO_STRESS
    parent_group_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("alert_groups.id", ondelete="SET NULL"), nullable=True)
    primary_alert_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    current_priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    current_priority_band: Mapped[str] = mapped_column(String(32), default="P5_LOW", index=True)
    maximum_severity: Mapped[str] = mapped_column(String(32), default="WARNING")
    maximum_priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    active_child_count: Mapped[int] = mapped_column(Integer, default=0)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    group_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # ACTIVE, RESOLVED, SUPPRESSED

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    members: Mapped[List["AlertGroupMember"]] = relationship(
        "AlertGroupMember", back_populates="group", cascade="all, delete-orphan"
    )
    occurrences: Mapped[List["AlertOccurrence"]] = relationship(
        "AlertOccurrence", back_populates="group", cascade="all, delete-orphan"
    )
    escalations: Mapped[List["AlertEscalationEvent"]] = relationship(
        "AlertEscalationEvent", back_populates="group", cascade="all, delete-orphan"
    )


class AlertGroupMember(Base):
    """
    Membership linking individual alerts to a parent group.
    """
    __tablename__ = "alert_group_members"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_groups.id", ondelete="CASCADE"), index=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), default="IDENTICAL_CONDITION")  # IDENTICAL_CONDITION, PORTFOLIO_COINCIDENT, CAUSAL_CHAIN
    correlation_method: Mapped[str] = mapped_column(String(64), default="EXACT_KEY")  # EXACT_KEY, HEURISTIC, SHARED_ENTITY
    correlation_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    group: Mapped["AlertGroup"] = relationship("AlertGroup", back_populates="members")


class AlertPriorityEvaluation(Base):
    """
    Detailed, transparent priority calculation record for an alert.
    """
    __tablename__ = "alert_priority_evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    severity: Mapped[str] = mapped_column(String(32), default="WARNING")  # WARNING, CRITICAL, EMERGENCY
    severity_score: Mapped[float] = mapped_column(Float, default=30.0)
    is_authoritative_severity: Mapped[bool] = mapped_column(Boolean, default=False)
    severity_source: Mapped[str] = mapped_column(String(64), default="M12.05_POLICY")

    urgency: Mapped[str] = mapped_column(String(32), default="U3_NORMAL")  # U1_IMMEDIATE, U2_HIGH, U3_NORMAL, U4_LOW
    urgency_score: Mapped[float] = mapped_column(Float, default=45.0)
    time_to_action_label: Mapped[str] = mapped_column(String(64), default="WITHIN_CURRENT_SESSION")
    recommended_action_window_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    affected_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    affected_currency: Mapped[str] = mapped_column(String(8), default="USD")
    affected_value_pct_nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    financial_impact_score: Mapped[float] = mapped_column(Float, default=0.0)

    risk_impact_score: Mapped[float] = mapped_column(Float, default=0.0)
    breadth_impact_score: Mapped[float] = mapped_column(Float, default=0.0)
    composite_impact_score: Mapped[float] = mapped_column(Float, default=0.0)

    persistence_score: Mapped[float] = mapped_column(Float, default=10.0)
    priority_score: Mapped[float] = mapped_column(Float, default=25.0)
    priority_band: Mapped[str] = mapped_column(String(32), default="P4_NORMAL", index=True)  # P1_IMMEDIATE to P5_LOW
    priority_floor_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_floor_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    confidence: Mapped[str] = mapped_column(String(32), default="HIGH")  # HIGH, MEDIUM, LOW, UNKNOWN
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID")  # VALID, PARTIAL_VALUATION, MISSING_NAV
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    scoring_model_version: Mapped[str] = mapped_column(String(32), default="1.0.0")

    explanation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertPriorityHistory(Base):
    """
    Audit log of priority transitions and recalculations.
    """
    __tablename__ = "alert_priority_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)
    previous_priority_score: Mapped[float] = mapped_column(Float)
    new_priority_score: Mapped[float] = mapped_column(Float)
    previous_priority_band: Mapped[str] = mapped_column(String(32))
    new_priority_band: Mapped[str] = mapped_column(String(32))
    previous_severity: Mapped[str] = mapped_column(String(32))
    new_severity: Mapped[str] = mapped_column(String(32))
    previous_urgency: Mapped[str] = mapped_column(String(32))
    new_urgency: Mapped[str] = mapped_column(String(32))

    trigger_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    change_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertDeduplicationRecord(Base):
    """
    Audit record tracking deduplication evaluations and keys.
    """
    __tablename__ = "alert_deduplication_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incoming_event_id: Mapped[str] = mapped_column(String(64), index=True)
    existing_alert_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    deduplication_key: Mapped[str] = mapped_column(String(128), index=True)
    deduplication_result: Mapped[str] = mapped_column(String(32))  # NEW_ALERT, DUPLICATE_OCCURRENCE, ESCALATED_OCCURRENCE, SUPPRESSED
    matching_dimensions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertOccurrence(Base):
    """
    Immutable log of every repeated occurrence for an alert / group.
    """
    __tablename__ = "alert_occurrences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)
    evaluation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("alert_groups.id", ondelete="CASCADE"), nullable=True, index=True)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)

    observed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    severity: Mapped[str] = mapped_column(String(32))
    urgency: Mapped[str] = mapped_column(String(32))
    priority_score: Mapped[float] = mapped_column(Float)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    evidence_reference: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    group: Mapped[Optional["AlertGroup"]] = relationship("AlertGroup", back_populates="occurrences")


class AlertEscalationEvent(Base):
    """
    Formal record created when an alert worsens (e.g., WARNING -> CRITICAL or priority score jump).
    """
    __tablename__ = "alert_escalation_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("alert_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    previous_severity: Mapped[str] = mapped_column(String(32))
    new_severity: Mapped[str] = mapped_column(String(32))
    previous_priority_score: Mapped[float] = mapped_column(Float)
    new_priority_score: Mapped[float] = mapped_column(Float)
    previous_urgency: Mapped[str] = mapped_column(String(32))
    new_urgency: Mapped[str] = mapped_column(String(32))

    escalation_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    group: Mapped[Optional["AlertGroup"]] = relationship("AlertGroup", back_populates="escalations")

