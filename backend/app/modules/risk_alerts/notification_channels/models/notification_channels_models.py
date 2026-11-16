"""
SQLAlchemy ORM models for M12.07 — Notification Channels.

Tables:
1. `notification_channel_registry`: Registered channels (IN_APP, EMAIL, etc.) with operational health.
2. `notification_channel_config_history`: Immutable versioned configurations for notification channels.
3. `user_notification_channel_preferences`: Recipient preferences, quiet periods, severity/category filters.
4. `notification_portfolio_subscriptions`: Recipient subscriptions to specific portfolios or instruments.
5. `in_app_notifications`: Persisted in-app alerts with read/unread flags and recipient associations.
6. `notification_channel_deliveries`: Delivery tasks per notification-recipient-channel with idempotency keys.
7. `notification_channel_delivery_attempts`: Append-only attempt histories with provider diagnostics.
8. `notification_channel_status_history`: Append-only delivery status transition audit log.
9. `notification_templates`: Versioned templates for email subject, HTML and plaintext formatting.
10. `notification_channel_outbox`: Transactional outbox for durable asynchronous delivery processing.
11. `notification_dead_letters`: Dead-lettered exhausted/terminal failures requiring manual remediation.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class NotificationChannelRegistry(Base):
    """
    Channel registration entity (IN_APP, EMAIL, etc.).
    """
    __tablename__ = "notification_channel_registry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)  # IN_APP, EMAIL, WEBHOOK, SMS
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    health_status: Mapped[str] = mapped_column(String(32), default="HEALTHY")  # HEALTHY, DEGRADED, DOWN, MAINTENANCE
    configuration_version: Mapped[int] = mapped_column(Integer, default=1)
    capabilities_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    last_successful_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    configs: Mapped[List["NotificationChannelConfigHistory"]] = relationship(
        "NotificationChannelConfigHistory", back_populates="channel", cascade="all, delete-orphan", order_by="desc(NotificationChannelConfigHistory.configuration_version)"
    )
    deliveries: Mapped[List["NotificationChannelDelivery"]] = relationship(
        "NotificationChannelDelivery", back_populates="channel"
    )


class NotificationChannelConfigHistory(Base):
    """
    Immutable versioned configuration history for notification channels.
    """
    __tablename__ = "notification_channel_config_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(64), ForeignKey("notification_channel_registry.id", ondelete="CASCADE"), index=True)
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    channel: Mapped["NotificationChannelRegistry"] = relationship("NotificationChannelRegistry", back_populates="configs")


class UserNotificationChannelPreference(Base):
    """
    User/Recipient-level notification preferences per channel.
    """
    __tablename__ = "user_notification_channel_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_code", name="uq_user_channel_pref"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    channel_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_severities: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["CRITICAL", "EMERGENCY"])
    allowed_categories: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["ALL"])
    quiet_period_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_period_start: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # "22:00"
    quiet_period_end: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)    # "07:00"
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    emergency_bypass: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    preference_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class NotificationPortfolioSubscription(Base):
    """
    Explicit portfolio/instrument subscription rules for alert delivery.
    """
    __tablename__ = "notification_portfolio_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "portfolio_id", "instrument_id", "channel_code", name="uq_user_sub_scope"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    subscription_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO")  # PORTFOLIO, INSTRUMENT, ALL
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    channel_code: Mapped[str] = mapped_column(String(32), default="ALL")  # ALL, IN_APP, EMAIL
    min_severity: Mapped[str] = mapped_column(String(16), default="WARNING")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class InAppNotification(Base):
    """
    Persisted in-app dashboard notification inbox items.
    """
    __tablename__ = "in_app_notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_alert_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Text] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # WARNING, CRITICAL, EMERGENCY
    priority_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("50.00"))
    priority_band: Mapped[str] = mapped_column(String(16), default="P3_NORMAL")
    alert_category: Mapped[str] = mapped_column(String(64), index=True, default="GENERAL")
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    portfolio_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    read_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    notification_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class NotificationChannelDelivery(Base):
    """
    Delivery lifecycle task per notification, channel and recipient.
    """
    __tablename__ = "notification_channel_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notification_delivery_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_alert_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    channel_id: Mapped[str] = mapped_column(String(64), ForeignKey("notification_channel_registry.id", ondelete="CASCADE"), index=True)
    recipient_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    recipient_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CREATED", index=True)  # CREATED, QUEUED, DEFERRED, PROCESSING, SENT, PROVIDER_ACCEPTED, DELIVERED, RETRY_SCHEDULED, FAILED, DEAD_LETTERED, CANCELLED, UNKNOWN
    priority: Mapped[str] = mapped_column(String(16), default="P3_NORMAL", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    
    last_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    channel: Mapped["NotificationChannelRegistry"] = relationship("NotificationChannelRegistry", back_populates="deliveries")
    attempts: Mapped[List["NotificationChannelDeliveryAttempt"]] = relationship(
        "NotificationChannelDeliveryAttempt", back_populates="delivery", cascade="all, delete-orphan", order_by="NotificationChannelDeliveryAttempt.attempt_number"
    )
    status_history: Mapped[List["NotificationChannelStatusHistory"]] = relationship(
        "NotificationChannelStatusHistory", back_populates="delivery", cascade="all, delete-orphan", order_by="NotificationChannelStatusHistory.created_at"
    )


class NotificationChannelDeliveryAttempt(Base):
    """
    Append-only delivery attempt history.
    """
    __tablename__ = "notification_channel_delivery_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(64), ForeignKey("notification_channel_deliveries.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)  # SUCCESS, TRANSIENT_FAILURE, PERMANENT_FAILURE, TIMEOUT, RATE_LIMITED
    provider_response_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    delivery: Mapped["NotificationChannelDelivery"] = relationship("NotificationChannelDelivery", back_populates="attempts")


class NotificationChannelStatusHistory(Base):
    """
    Append-only state machine transition log for deliveries.
    """
    __tablename__ = "notification_channel_status_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(64), ForeignKey("notification_channel_deliveries.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    transition_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default="SYSTEM")  # SYSTEM, WORKER, ADMIN_USER
    actor_id: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    delivery: Mapped["NotificationChannelDelivery"] = relationship("NotificationChannelDelivery", back_populates="status_history")


class NotificationTemplate(Base):
    """
    Versioned templates for formatting notifications.
    """
    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint("template_code", "template_version", name="uq_template_code_version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    template_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    channel_code: Mapped[str] = mapped_column(String(32), default="EMAIL")
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    subject_template: Mapped[str] = mapped_column(String(255), nullable=False)
    html_body_template: Mapped[Text] = mapped_column(Text, nullable=False)
    text_body_template: Mapped[Text] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class NotificationChannelOutbox(Base):
    """
    Transactional outbox for durable asynchronous delivery processing.
    """
    __tablename__ = "notification_channel_outbox"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    payload_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)  # PENDING, PROCESSED, FAILED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NotificationDeadLetter(Base):
    """
    Dead-letter queue for terminal/exhausted delivery failures.
    """
    __tablename__ = "notification_dead_letters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    channel_code: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    failure_category: Mapped[str] = mapped_column(String(64), nullable=False)
    final_error: Mapped[Text] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    dead_lettered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    retry_authorized_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retry_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

