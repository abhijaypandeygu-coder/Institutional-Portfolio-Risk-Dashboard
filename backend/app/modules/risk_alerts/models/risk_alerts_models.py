"""
SQLAlchemy ORM models for M12 — Risk Alerts & Notification Engine.

Tables:
1. `alert_rules`: Master alert rule configurations.
2. `alert_rule_versions`: Immutable versions of alert rules.
3. `alert_threshold_definitions`: Warning, critical and recovery boundaries per rule version.
4. `alert_threshold_states`: Current tracking state per rule & portfolio.
5. `alert_threshold_transitions`: State transition log with metric snapshots.
6. `alert_events`: Master alert instances (threshold, breach, feed health, liquidity, portfolio change).
7. `alert_evidence`: Detailed immutable audit evidence per alert.
8. `alert_lifecycle_events`: State transitions (OPEN, ACKNOWLEDGED, ASSIGNED, INVESTIGATING, RESOLVED, REOPENED).
9. `notification_preferences`: User channel and subscription preferences.
10. `notification_messages`: Individual notification delivery tasks across in-app, email, webhook.
11. `notification_delivery_attempts`: Delivery outcome logs and retry histories.
12. `alert_audit_logs`: Governance audit logs.
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


def utc_now() -> datetime:
    return datetime.utcnow()


class AlertRule(Base):
    """
    Master alert rule configuration entity.
    """
    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metric_category: Mapped[str] = mapped_column(String(64), nullable=False)  # VAR, VOLATILITY, EXPOSURE, DRAWDOWN, LIQUIDITY, FEED_HEALTH
    metric_identifier: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # var_95, realized_vol_20d, gross_exposure, etc.
    scope_type: Mapped[str] = mapped_column(String(32), default="ALL")  # ALL, PORTFOLIO, INSTRUMENT, SECTOR
    scope_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="MEDIUM")  # INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL, EMERGENCY
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # DRAFT, ACTIVE, SUSPENDED, RETIRED
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    versions: Mapped[List["AlertRuleVersion"]] = relationship(
        "AlertRuleVersion", back_populates="rule", cascade="all, delete-orphan", order_by="desc(AlertRuleVersion.version_number)"
    )
    states: Mapped[List["AlertThresholdState"]] = relationship(
        "AlertThresholdState", back_populates="rule", cascade="all, delete-orphan"
    )
    alerts: Mapped[List["AlertEvent"]] = relationship(
        "AlertEvent", back_populates="rule"
    )


class AlertRuleVersion(Base):
    """
    Immutable versioned definition of an alert rule.
    """
    __tablename__ = "alert_rule_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    rule: Mapped["AlertRule"] = relationship("AlertRule", back_populates="versions")
    thresholds: Mapped[List["AlertThresholdDefinition"]] = relationship(
        "AlertThresholdDefinition", back_populates="version", cascade="all, delete-orphan"
    )


class AlertThresholdDefinition(Base):
    """
    Configured warning, critical and recovery boundaries.
    """
    __tablename__ = "alert_threshold_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_rule_versions.id", ondelete="CASCADE"), index=True)
    comparison_operator: Mapped[str] = mapped_column(String(32), default="GREATER_THAN_OR_EQUAL")  # GREATER_THAN_OR_EQUAL, LESS_THAN_OR_EQUAL
    warning_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    critical_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    recovery_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    metric_unit: Mapped[str] = mapped_column(String(32), default="NAV_PERCENTAGE")  # CURRENCY, NAV_PERCENTAGE, BASIS_POINTS, RATIO
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    version: Mapped["AlertRuleVersion"] = relationship("AlertRuleVersion", back_populates="thresholds")


class AlertThresholdState(Base):
    """
    Current live threshold state per rule and portfolio.
    """
    __tablename__ = "alert_threshold_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_state: Mapped[str] = mapped_column(String(32), default="NORMAL", index=True)  # NORMAL, APPROACHING, WARNING, CRITICAL, RECOVERING, RECOVERED, STALE
    current_metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.00"))
    last_metric_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    consecutive_breaches: Mapped[int] = mapped_column(Integer, default=0)
    active_alert_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    rule: Mapped["AlertRule"] = relationship("AlertRule", back_populates="states")


class AlertThresholdTransition(Base):
    """
    State transition history for threshold monitoring.
    """
    __tablename__ = "alert_threshold_transitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    transition_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertEvent(Base):
    """
    Master alert record across all M12 alert categories.
    """
    __tablename__ = "alert_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # THRESHOLD_ALERT, EVENT_ALERT, FEED_HEALTH, LIQUIDITY_ALERT, PORTFOLIO_CHANGE
    alert_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # VAR, VOLATILITY, EXPOSURE, DRAWDOWN, BREACH, PRETRADE, SPREAD, CASH
    source_module: Mapped[str] = mapped_column(String(32), default="M12.01")
    source_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_entity_type: Mapped[str] = mapped_column(String(64), default="METRIC")
    source_entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    rule_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Text] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="MEDIUM", index=True)  # INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL, EMERGENCY
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)  # OPEN, ACKNOWLEDGED, ASSIGNED, INVESTIGATING, MITIGATED, RESOLVED, CLOSED, REOPENED
    deduplication_key: Mapped[str] = mapped_column(String(128), index=True)
    correlation_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    assigned_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    rule: Mapped[Optional["AlertRule"]] = relationship("AlertRule", back_populates="alerts")
    evidence: Mapped[List["AlertEvidence"]] = relationship(
        "AlertEvidence", back_populates="alert", cascade="all, delete-orphan"
    )
    lifecycle_events: Mapped[List["AlertLifecycleEvent"]] = relationship(
        "AlertLifecycleEvent", back_populates="alert", cascade="all, delete-orphan", order_by="desc(AlertLifecycleEvent.created_at)"
    )
    notifications: Mapped[List["NotificationMessage"]] = relationship(
        "NotificationMessage", back_populates="alert", cascade="all, delete-orphan"
    )


class AlertEvidence(Base):
    """
    Immutable audit evidence supporting each alert.
    """
    __tablename__ = "alert_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(32), default="NAV_PERCENTAGE")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    evidence_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    source_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    alert: Mapped["AlertEvent"] = relationship("AlertEvent", back_populates="evidence")


class AlertLifecycleEvent(Base):
    """
    Append-only state machine transition log for alerts.
    """
    __tablename__ = "alert_lifecycle_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)  # CREATED, ACKNOWLEDGED, ASSIGNED, INVESTIGATED, RESOLVED, REOPENED
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    alert: Mapped["AlertEvent"] = relationship("AlertEvent", back_populates="lifecycle_events")


class NotificationPreference(Base):
    """
    User notification delivery and channel preferences.
    """
    __tablename__ = "notification_preferences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    enabled_channels: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["IN_APP"])  # IN_APP, EMAIL, WEBHOOK
    min_priority: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    subscribed_categories: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["ALL"])
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # "22:00"
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)    # "06:00"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class NotificationMessage(Base):
    """
    Outbound message task across application channels.
    """
    __tablename__ = "notification_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    recipient_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="IN_APP")
    delivery_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)  # PENDING, QUEUED, SENT, DELIVERED, FAILED
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Text] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    alert: Mapped["AlertEvent"] = relationship("AlertEvent", back_populates="notifications")
    attempts: Mapped[List["NotificationDeliveryAttempt"]] = relationship(
        "NotificationDeliveryAttempt", back_populates="message", cascade="all, delete-orphan"
    )


class NotificationDeliveryAttempt(Base):
    """
    Individual delivery attempt log.
    """
    __tablename__ = "notification_delivery_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    notification_id: Mapped[str] = mapped_column(String(64), ForeignKey("notification_messages.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="DELIVERED")  # DELIVERED, FAILED
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    message: Mapped["NotificationMessage"] = relationship("NotificationMessage", back_populates="attempts")


class AlertAuditLog(Base):
    """
    Administrative and governance audit log.
    """
    __tablename__ = "alert_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # RULE_CREATED, RULE_UPDATED, ALERT_ACKNOWLEDGED, ALERT_RESOLVED
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
