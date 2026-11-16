"""
SQLAlchemy ORM models for M11.06 — Breach Detection.

Tables:
1. `breach_evaluations`: Comprehensive record of every metric-to-limit comparison.
2. `breach_events`: Immutable structured breach event records (WARNING, HARD_BREACH, RECOVERED, etc.).
3. `breach_episodes`: State-tracking parent entity grouping related observations and events into an episode.
4. `breach_observations`: Time-series log of all individual evaluation observations within an episode.
5. `breach_detection_rules`: Governed rules configuring persistence modes, windows, hysteresis, and timeouts.
6. `breach_detection_rule_versions`: Version-controlled snapshots of detection rule parameters.
7. `breach_event_links`: Directed graph linking related events (RECOVERY_OF, REOPENING_OF, DUPLICATE_OF, etc.).
8. `breach_audit_events`: Full audit trail of administrative, governance, and detection state transitions.
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


class BreachEvaluation(Base):
    """
    Detailed log of every limit evaluation run against incoming metrics.
    """
    __tablename__ = "breach_evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO")  # PORTFOLIO, POSITION, SECTOR, ISSUER
    target_entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Metric Evidence
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(32), default="PERCENT")
    metric_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    metric_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    processing_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    input_quality_status: Mapped[str] = mapped_column(String(32), default="VALID")  # VALID, STALE, MISSING, INVALID

    # Threshold Evidence & Effective Snapshot Binding
    active_limit_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    effective_limit_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    warning_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    applied_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    comparison_operator: Mapped[str] = mapped_column(String(32), default="GREATER_THAN")

    # Evaluation Output
    evaluation_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # WITHIN_LIMIT, WARNING, HARD_BREACH, STALE_INPUT, etc.
    severity: Mapped[str] = mapped_column(String(16), default="LOW")  # LOW, MEDIUM, HIGH, CRITICAL
    breach_magnitude: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    utilization: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    detection_rule_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    observations: Mapped[List["BreachObservation"]] = relationship(
        "BreachObservation", back_populates="evaluation", cascade="all, delete-orphan"
    )
    events: Mapped[List["BreachEvent"]] = relationship(
        "BreachEvent", back_populates="evaluation", cascade="all, delete-orphan"
    )


class BreachEpisode(Base):
    """
    Aggregated stateful episode tracking a breach lifecycle from first violation through recovery.
    """
    __tablename__ = "breach_episodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_limit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO")
    target_entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    limit_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Status: ACTIVE_WARNING, ACTIVE_HARD_BREACH, PERSISTENT_BREACH, RECOVERING, RECOVERED, CLOSED
    episode_status: Mapped[str] = mapped_column(String(32), default="ACTIVE_WARNING", index=True)
    
    # Lifecycle Timestamps
    first_violation_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    breach_detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recovery_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Peak metrics
    maximum_breach_magnitude: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    maximum_observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    first_evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    latest_evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    observations: Mapped[List["BreachObservation"]] = relationship(
        "BreachObservation", back_populates="episode", cascade="all, delete-orphan", order_by="BreachObservation.observation_sequence"
    )
    events: Mapped[List["BreachEvent"]] = relationship(
        "BreachEvent", back_populates="episode", cascade="all, delete-orphan", order_by="desc(BreachEvent.detected_at)"
    )


class BreachObservation(Base):
    """
    Time-series observation records linking evaluations into an episode.
    """
    __tablename__ = "breach_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_episodes.id", ondelete="CASCADE"), index=True)
    evaluation_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_evaluations.id", ondelete="CASCADE"), index=True)
    
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    warning_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    comparison_result: Mapped[str] = mapped_column(String(32), nullable=False)  # VIOLATING, COMPLIANT, WARNING
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID")
    metric_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processing_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    observation_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    episode: Mapped["BreachEpisode"] = relationship("BreachEpisode", back_populates="observations")
    evaluation: Mapped["BreachEvaluation"] = relationship("BreachEvaluation", back_populates="observations")


class BreachEvent(Base):
    """
    Immutable, structured risk breach event published downstream to M11.08 and M11.07.
    """
    __tablename__ = "breach_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    breach_episode_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_episodes.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO")
    target_entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_limit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Event Classification
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # WARNING_ENTERED, HARD_BREACH_ENTERED, PERSISTENT_BREACH, BREACH_RECOVERED, etc.
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)    # LOW, MEDIUM, HIGH, CRITICAL
    
    # Financial Evidence
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    warning_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    hard_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(32), default="PERCENT")
    metric_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    breach_magnitude: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    utilization: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Timestamps & Lineage
    metric_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    persistence_status: Mapped[str] = mapped_column(String(32), default="TRANSIENT")  # TRANSIENT, PERSISTENT

    evaluation_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_evaluations.id", ondelete="CASCADE"), index=True)
    effective_limit_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_event_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    episode: Mapped["BreachEpisode"] = relationship("BreachEpisode", back_populates="events")
    evaluation: Mapped["BreachEvaluation"] = relationship("BreachEvaluation", back_populates="events")


class BreachDetectionRule(Base):
    """
    Configurable detection rules governing persistence, windows, and hysteresis.
    """
    __tablename__ = "breach_detection_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    applicable_scope: Mapped[str] = mapped_column(String(32), default="ALL")  # ALL, PORTFOLIO, ASSET_CLASS
    
    # Persistence Configuration
    persistence_mode: Mapped[str] = mapped_column(String(32), default="DURATION")  # DURATION, CONSECUTIVE, WINDOW, IMMEDIATE
    required_duration_seconds: Mapped[int] = mapped_column(Integer, default=300)
    required_consecutive_observations: Mapped[int] = mapped_column(Integer, default=3)
    observation_window_seconds: Mapped[int] = mapped_column(Integer, default=600)
    required_observation_count: Mapped[int] = mapped_column(Integer, default=3)
    permitted_gap_seconds: Mapped[int] = mapped_column(Integer, default=120)
    recovery_duration_seconds: Mapped[int] = mapped_column(Integer, default=180)
    immediate_breach: Mapped[bool] = mapped_column(Boolean, default=False)
    
    hysteresis_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    missing_data_behavior: Mapped[str] = mapped_column(String(32), default="SUPPRESS_PASS")
    rule_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")  # DRAFT, ACTIVE, SUSPENDED, RETIRED
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    versions: Mapped[List["BreachDetectionRuleVersion"]] = relationship(
        "BreachDetectionRuleVersion", back_populates="rule", cascade="all, delete-orphan"
    )


class BreachDetectionRuleVersion(Base):
    """
    Version history for detection rules.
    """
    __tablename__ = "breach_detection_rule_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_detection_rules.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rule: Mapped["BreachDetectionRule"] = relationship("BreachDetectionRule", back_populates="versions")


class BreachEventLink(Base):
    """
    Directed relational links between breach events.
    """
    __tablename__ = "breach_event_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_events.id", ondelete="CASCADE"), index=True)
    related_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_events.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)  # RECOVERY_OF, REOPENING_OF, DUPLICATE_OF, RELATED_TO, SUPERSEDES
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BreachAuditEvent(Base):
    """
    Audit log for breach detection actions, governance changes, and overrides.
    """
    __tablename__ = "breach_audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # RULE, EPISODE, EVENT, EVALUATION
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)   # RULE_ACTIVATED, BREACH_CREATED, BREACH_RECOVERED, etc.
    previous_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
