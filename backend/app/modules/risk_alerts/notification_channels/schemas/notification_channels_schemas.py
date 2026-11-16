"""
Pydantic schemas for M12.07 — Notification Channels.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# Channel Schemas
class ChannelRegisterRequest(BaseModel):
    channel_code: str = Field(..., max_length=32)
    channel_name: str = Field(..., max_length=128)
    channel_type: str = Field(..., max_length=32)  # IN_APP, EMAIL, WEBHOOK
    description: Optional[str] = None
    is_enabled: bool = True
    capabilities_json: Dict[str, Any] = Field(default_factory=dict)
    initial_config_json: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default="admin")


class ChannelUpdateRequest(BaseModel):
    channel_name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    capabilities_json: Optional[Dict[str, Any]] = None
    config_json: Optional[Dict[str, Any]] = None
    updated_by: str = Field(default="admin")


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel_code: str
    channel_name: str
    channel_type: str
    description: Optional[str] = None
    is_enabled: bool
    health_status: str
    configuration_version: int
    capabilities_json: Dict[str, Any]
    last_successful_delivery_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Preference Schemas
class UserPreferenceUpdateRequest(BaseModel):
    user_id: str
    channel_code: str
    enabled: bool = True
    email_address: Optional[str] = None
    is_email_verified: bool = False
    allowed_severities: List[str] = Field(default_factory=lambda: ["CRITICAL", "EMERGENCY"])
    allowed_categories: List[str] = Field(default_factory=lambda: ["ALL"])
    quiet_period_enabled: bool = False
    quiet_period_start: Optional[str] = "22:00"
    quiet_period_end: Optional[str] = "07:00"
    timezone: str = "UTC"
    emergency_bypass: bool = True
    digest_enabled: bool = False


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    channel_code: str
    enabled: bool
    email_address: Optional[str] = None
    is_email_verified: bool
    allowed_severities: List[str]
    allowed_categories: List[str]
    quiet_period_enabled: bool
    quiet_period_start: Optional[str] = None
    quiet_period_end: Optional[str] = None
    timezone: str
    emergency_bypass: bool
    digest_enabled: bool
    preference_version: int
    created_at: datetime
    updated_at: datetime


# Subscription Schemas
class SubscriptionCreateRequest(BaseModel):
    user_id: str
    subscription_type: str = "PORTFOLIO"  # PORTFOLIO, INSTRUMENT, ALL
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    channel_code: str = "ALL"
    min_severity: str = "WARNING"
    is_enabled: bool = True


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    subscription_type: str
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    channel_code: str
    min_severity: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


# In-App Notification Schemas
class InAppNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_alert_id: str
    recipient_user_id: str
    title: str
    summary: str
    severity: str
    priority_score: Decimal
    priority_band: str
    alert_category: str
    portfolio_id: Optional[str] = None
    portfolio_name: Optional[str] = None
    instrument_id: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    read_by_user_id: Optional[str] = None
    event_timestamp: datetime
    notification_metadata: Dict[str, Any]
    created_at: datetime


class NotificationCountsResponse(BaseModel):
    total_notifications: int
    unread_count: int
    unread_critical_count: int
    unread_emergency_count: int
    by_severity: Dict[str, int]
    by_category: Dict[str, int]


# Delivery Schemas
class DeliveryAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    delivery_id: str
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    outcome: str
    provider_response_code: Optional[str] = None
    provider_message_id: Optional[str] = None
    error_category: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[Decimal] = None
    created_at: datetime


class DeliveryStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    delivery_id: str
    previous_status: Optional[str] = None
    new_status: str
    transition_reason: str
    actor_type: str
    actor_id: str
    created_at: datetime


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_alert_id: str
    channel_id: str
    recipient_user_id: str
    recipient_address: Optional[str] = None
    idempotency_key: str
    status: str
    priority: str
    title: str
    payload_json: Dict[str, Any]
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    attempt_count: int
    max_attempts: int
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ManualRetryRequest(BaseModel):
    authorized_by: str
    retry_reason: str = Field(..., min_length=3)


class DeadLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    delivery_id: str
    channel_code: str
    recipient_user_id: str
    failure_category: str
    final_error: str
    attempt_count: int
    dead_lettered_at: datetime
    retry_authorized_by: Optional[str] = None
    retry_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None


class DeliveryMetricsResponse(BaseModel):
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    dead_lettered_count: int
    deferred_count: int
    pending_queued_count: int
    success_rate_pct: Decimal
    in_app_deliveries_count: int
    email_deliveries_count: int
    by_status: Dict[str, int]
    by_channel: Dict[str, int]


# Alert Event Ingestion Contract
class AlertNotificationIngestRequest(BaseModel):
    source_alert_id: str
    title: str
    summary: str
    severity: str  # WARNING, CRITICAL, EMERGENCY
    priority_score: Optional[Decimal] = Decimal("50.00")
    priority_band: Optional[str] = "P3_NORMAL"
    alert_category: Optional[str] = "GENERAL"  # THRESHOLD, MARKET, LIQUIDITY, PORTFOLIO
    portfolio_id: Optional[str] = None
    portfolio_name: Optional[str] = None
    instrument_id: Optional[str] = None
    metric_values: Optional[Dict[str, Any]] = Field(default_factory=dict)
    event_timestamp: Optional[datetime] = None
    target_user_ids: Optional[List[str]] = None

