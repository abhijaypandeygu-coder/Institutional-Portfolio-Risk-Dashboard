"""
Models package for notification_channels.
"""
from backend.app.modules.risk_alerts.notification_channels.models.notification_channels_models import (
    NotificationChannelRegistry,
    NotificationChannelConfigHistory,
    UserNotificationChannelPreference,
    NotificationPortfolioSubscription,
    InAppNotification,
    NotificationChannelDelivery,
    NotificationChannelDeliveryAttempt,
    NotificationChannelStatusHistory,
    NotificationTemplate,
    NotificationChannelOutbox,
    NotificationDeadLetter,
)

__all__ = [
    "NotificationChannelRegistry",
    "NotificationChannelConfigHistory",
    "UserNotificationChannelPreference",
    "NotificationPortfolioSubscription",
    "InAppNotification",
    "NotificationChannelDelivery",
    "NotificationChannelDeliveryAttempt",
    "NotificationChannelStatusHistory",
    "NotificationTemplate",
    "NotificationChannelOutbox",
    "NotificationDeadLetter",
]

