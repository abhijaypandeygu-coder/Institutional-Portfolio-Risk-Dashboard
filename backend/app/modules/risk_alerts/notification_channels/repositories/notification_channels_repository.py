"""
Repository for M12.07 — Notification Channels.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
import uuid

from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from backend.app.modules.risk_alerts.notification_channels.calculations.notification_channels_math import (
    calculate_delivery_success_rate,
)


class NotificationChannelsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------
    # Channel Registry & Config
    # -------------------------------------------------------------
    async def get_channel_by_code(self, channel_code: str) -> Optional[NotificationChannelRegistry]:
        stmt = (
            select(NotificationChannelRegistry)
            .where(NotificationChannelRegistry.channel_code == channel_code.upper())
            .options(selectinload(NotificationChannelRegistry.configs))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_channel_by_id(self, channel_id: str) -> Optional[NotificationChannelRegistry]:
        stmt = (
            select(NotificationChannelRegistry)
            .where(NotificationChannelRegistry.id == channel_id)
            .options(selectinload(NotificationChannelRegistry.configs))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_channels(self, enabled_only: bool = False) -> List[NotificationChannelRegistry]:
        stmt = select(NotificationChannelRegistry).order_by(NotificationChannelRegistry.channel_code)
        if enabled_only:
            stmt = stmt.where(NotificationChannelRegistry.is_enabled == True)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_channel(
        self,
        channel_code: str,
        channel_name: str,
        channel_type: str,
        description: Optional[str],
        is_enabled: bool,
        capabilities_json: Dict[str, Any],
        initial_config_json: Dict[str, Any],
        created_by: str = "admin",
    ) -> NotificationChannelRegistry:
        channel_id = str(uuid.uuid4())
        channel = NotificationChannelRegistry(
            id=channel_id,
            channel_code=channel_code.upper(),
            channel_name=channel_name,
            channel_type=channel_type.upper(),
            description=description,
            is_enabled=is_enabled,
            health_status="HEALTHY",
            configuration_version=1,
            capabilities_json=capabilities_json,
        )
        self.session.add(channel)

        config_hist = NotificationChannelConfigHistory(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            configuration_version=1,
            configuration_json=initial_config_json,
            created_by=created_by,
        )
        self.session.add(config_hist)
        await self.session.flush()
        return channel

    async def update_channel_status(
        self,
        channel_id: str,
        is_enabled: Optional[bool] = None,
        health_status: Optional[str] = None,
        last_error: Optional[str] = None,
        mark_success: bool = False,
    ) -> Optional[NotificationChannelRegistry]:
        channel = await self.get_channel_by_id(channel_id)
        if not channel:
            return None
        if is_enabled is not None:
            channel.is_enabled = is_enabled
        if health_status is not None:
            channel.health_status = health_status
        if last_error:
            channel.last_error_at = datetime.utcnow()
            channel.last_error_message = last_error
        if mark_success:
            channel.last_successful_delivery_at = datetime.utcnow()
            channel.health_status = "HEALTHY"
        await self.session.flush()
        return channel

    # -------------------------------------------------------------
    # User Preferences & Subscriptions
    # -------------------------------------------------------------
    async def get_user_preference(self, user_id: str, channel_code: str) -> Optional[UserNotificationChannelPreference]:
        stmt = select(UserNotificationChannelPreference).where(
            and_(
                UserNotificationChannelPreference.user_id == user_id,
                UserNotificationChannelPreference.channel_code == channel_code.upper(),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_user_preferences(self, user_id: str) -> List[UserNotificationChannelPreference]:
        stmt = select(UserNotificationChannelPreference).where(
            UserNotificationChannelPreference.user_id == user_id
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def upsert_user_preference(
        self,
        user_id: str,
        channel_code: str,
        enabled: bool,
        email_address: Optional[str],
        is_email_verified: bool,
        allowed_severities: List[str],
        allowed_categories: List[str],
        quiet_period_enabled: bool,
        quiet_period_start: Optional[str],
        quiet_period_end: Optional[str],
        timezone: str,
        emergency_bypass: bool,
        digest_enabled: bool,
    ) -> UserNotificationChannelPreference:
        pref = await self.get_user_preference(user_id, channel_code)
        if pref:
            pref.enabled = enabled
            if email_address is not None:
                pref.email_address = email_address
            pref.is_email_verified = is_email_verified
            pref.allowed_severities = allowed_severities
            pref.allowed_categories = allowed_categories
            pref.quiet_period_enabled = quiet_period_enabled
            pref.quiet_period_start = quiet_period_start
            pref.quiet_period_end = quiet_period_end
            pref.timezone = timezone
            pref.emergency_bypass = emergency_bypass
            pref.digest_enabled = digest_enabled
            pref.preference_version += 1
            pref.updated_at = datetime.utcnow()
        else:
            pref = UserNotificationChannelPreference(
                id=str(uuid.uuid4()),
                user_id=user_id,
                channel_code=channel_code.upper(),
                enabled=enabled,
                email_address=email_address,
                is_email_verified=is_email_verified,
                allowed_severities=allowed_severities,
                allowed_categories=allowed_categories,
                quiet_period_enabled=quiet_period_enabled,
                quiet_period_start=quiet_period_start,
                quiet_period_end=quiet_period_end,
                timezone=timezone,
                emergency_bypass=emergency_bypass,
                digest_enabled=digest_enabled,
                preference_version=1,
            )
            self.session.add(pref)
        await self.session.flush()
        return pref

    async def get_subscriptions_for_user(self, user_id: str) -> List[NotificationPortfolioSubscription]:
        stmt = select(NotificationPortfolioSubscription).where(
            NotificationPortfolioSubscription.user_id == user_id
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_subscription(
        self,
        user_id: str,
        subscription_type: str,
        portfolio_id: Optional[str],
        instrument_id: Optional[str],
        channel_code: str,
        min_severity: str,
        is_enabled: bool,
    ) -> NotificationPortfolioSubscription:
        sub = NotificationPortfolioSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            subscription_type=subscription_type.upper(),
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            channel_code=channel_code.upper(),
            min_severity=min_severity.upper(),
            is_enabled=is_enabled,
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    # -------------------------------------------------------------
    # In-App Notifications
    # -------------------------------------------------------------
    async def create_in_app_notification(
        self,
        source_alert_id: str,
        recipient_user_id: str,
        title: str,
        summary: str,
        severity: str,
        priority_score: Decimal,
        priority_band: str,
        alert_category: str,
        portfolio_id: Optional[str],
        portfolio_name: Optional[str],
        instrument_id: Optional[str],
        event_timestamp: datetime,
        notification_metadata: Dict[str, Any],
    ) -> InAppNotification:
        item = InAppNotification(
            id=str(uuid.uuid4()),
            source_alert_id=source_alert_id,
            recipient_user_id=recipient_user_id,
            title=title,
            summary=summary,
            severity=severity.upper(),
            priority_score=priority_score,
            priority_band=priority_band,
            alert_category=alert_category.upper(),
            portfolio_id=portfolio_id,
            portfolio_name=portfolio_name,
            instrument_id=instrument_id,
            is_read=False,
            event_timestamp=event_timestamp,
            notification_metadata=notification_metadata,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_in_app_inbox(
        self,
        user_id: str,
        unread_only: bool = False,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InAppNotification]:
        stmt = (
            select(InAppNotification)
            .where(InAppNotification.recipient_user_id == user_id)
            .order_by(desc(InAppNotification.event_timestamp))
        )
        if unread_only:
            stmt = stmt.where(InAppNotification.is_read == False)
        if severity:
            stmt = stmt.where(InAppNotification.severity == severity.upper())
        if category:
            stmt = stmt.where(InAppNotification.alert_category == category.upper())
        if portfolio_id:
            stmt = stmt.where(InAppNotification.portfolio_id == portfolio_id)
        stmt = stmt.offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_in_app_counts(self, user_id: str) -> Dict[str, Any]:
        base_stmt = select(InAppNotification).where(InAppNotification.recipient_user_id == user_id)
        res = await self.session.execute(base_stmt)
        items = list(res.scalars().all())

        total = len(items)
        unread = sum(1 for i in items if not i.is_read)
        unread_critical = sum(1 for i in items if not i.is_read and i.severity == "CRITICAL")
        unread_emergency = sum(1 for i in items if not i.is_read and i.severity == "EMERGENCY")

        by_severity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        for i in items:
            by_severity[i.severity] = by_severity.get(i.severity, 0) + 1
            by_category[i.alert_category] = by_category.get(i.alert_category, 0) + 1

        return {
            "total_notifications": total,
            "unread_count": unread,
            "unread_critical_count": unread_critical,
            "unread_emergency_count": unread_emergency,
            "by_severity": by_severity,
            "by_category": by_category,
        }

    async def mark_in_app_read(
        self,
        notification_id: str,
        user_id: str,
        is_read: bool = True,
    ) -> Optional[InAppNotification]:
        stmt = select(InAppNotification).where(
            and_(
                InAppNotification.id == notification_id,
                InAppNotification.recipient_user_id == user_id,
            )
        )
        res = await self.session.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            return None
        item.is_read = is_read
        item.read_at = datetime.utcnow() if is_read else None
        item.read_by_user_id = user_id if is_read else None
        await self.session.flush()
        return item

    async def mark_all_in_app_read(self, user_id: str) -> int:
        stmt = (
            update(InAppNotification)
            .where(
                and_(
                    InAppNotification.recipient_user_id == user_id,
                    InAppNotification.is_read == False,
                )
            )
            .values(
                is_read=True,
                read_at=datetime.utcnow(),
                read_by_user_id=user_id,
            )
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount

    # -------------------------------------------------------------
    # Deliveries, Attempts & Status History
    # -------------------------------------------------------------
    async def get_delivery_by_idempotency_key(self, idempotency_key: str) -> Optional[NotificationChannelDelivery]:
        stmt = select(NotificationChannelDelivery).where(
            NotificationChannelDelivery.idempotency_key == idempotency_key
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_delivery_by_id(self, delivery_id: str) -> Optional[NotificationChannelDelivery]:
        stmt = (
            select(NotificationChannelDelivery)
            .where(NotificationChannelDelivery.id == delivery_id)
            .options(
                selectinload(NotificationChannelDelivery.attempts),
                selectinload(NotificationChannelDelivery.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_delivery(
        self,
        source_alert_id: str,
        channel_id: str,
        recipient_user_id: str,
        recipient_address: Optional[str],
        idempotency_key: str,
        status: str,
        priority: str,
        title: str,
        payload_json: Dict[str, Any],
        scheduled_at: datetime,
        max_attempts: int = 5,
    ) -> NotificationChannelDelivery:
        delivery_id = str(uuid.uuid4())
        delivery = NotificationChannelDelivery(
            id=delivery_id,
            source_alert_id=source_alert_id,
            channel_id=channel_id,
            recipient_user_id=recipient_user_id,
            recipient_address=recipient_address,
            idempotency_key=idempotency_key,
            status=status,
            priority=priority,
            title=title,
            payload_json=payload_json,
            scheduled_at=scheduled_at,
            max_attempts=max_attempts,
            attempt_count=0,
        )
        self.session.add(delivery)

        hist = NotificationChannelStatusHistory(
            id=str(uuid.uuid4()),
            delivery_id=delivery_id,
            previous_status=None,
            new_status=status,
            transition_reason="Delivery task initialized",
            actor_type="SYSTEM",
            actor_id="system",
        )
        self.session.add(hist)
        await self.session.flush()
        return delivery

    async def record_delivery_attempt(
        self,
        delivery_id: str,
        attempt_number: int,
        outcome: str,
        started_at: datetime,
        completed_at: datetime,
        provider_response_code: Optional[str] = None,
        provider_message_id: Optional[str] = None,
        error_category: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[Decimal] = None,
    ) -> NotificationChannelDeliveryAttempt:
        attempt = NotificationChannelDeliveryAttempt(
            id=str(uuid.uuid4()),
            delivery_id=delivery_id,
            attempt_number=attempt_number,
            started_at=started_at,
            completed_at=completed_at,
            outcome=outcome,
            provider_response_code=provider_response_code,
            provider_message_id=provider_message_id,
            error_category=error_category,
            error_code=error_code,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def update_delivery_status(
        self,
        delivery_id: str,
        new_status: str,
        transition_reason: str,
        actor_type: str = "SYSTEM",
        actor_id: str = "system",
        next_retry_at: Optional[datetime] = None,
        provider_message_id: Optional[str] = None,
        last_error_code: Optional[str] = None,
        last_error_message: Optional[str] = None,
    ) -> Optional[NotificationChannelDelivery]:
        delivery = await self.get_delivery_by_id(delivery_id)
        if not delivery:
            return None
        prev_status = delivery.status
        delivery.status = new_status
        delivery.updated_at = datetime.utcnow()
        if next_retry_at is not None:
            delivery.next_retry_at = next_retry_at
        if provider_message_id:
            delivery.provider_message_id = provider_message_id
        if last_error_code:
            delivery.last_error_code = last_error_code
        if last_error_message:
            delivery.last_error_message = last_error_message
        if new_status in ("SENT", "PROVIDER_ACCEPTED", "DELIVERED"):
            delivery.completed_at = datetime.utcnow()

        hist = NotificationChannelStatusHistory(
            id=str(uuid.uuid4()),
            delivery_id=delivery_id,
            previous_status=prev_status,
            new_status=new_status,
            transition_reason=transition_reason,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        self.session.add(hist)
        await self.session.flush()
        return delivery

    async def list_pending_or_scheduled_deliveries(
        self,
        as_of_utc: datetime,
        limit: int = 50,
    ) -> List[NotificationChannelDelivery]:
        stmt = (
            select(NotificationChannelDelivery)
            .where(
                or_(
                    NotificationChannelDelivery.status == "QUEUED",
                    and_(
                        NotificationChannelDelivery.status == "RETRY_SCHEDULED",
                        NotificationChannelDelivery.next_retry_at <= as_of_utc,
                    ),
                    and_(
                        NotificationChannelDelivery.status == "DEFERRED",
                        NotificationChannelDelivery.scheduled_at <= as_of_utc,
                    ),
                )
            )
            .order_by(
                desc(NotificationChannelDelivery.priority == "P1_IMMEDIATE"),
                NotificationChannelDelivery.scheduled_at,
            )
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------
    # Outbox & Dead Letters
    # -------------------------------------------------------------
    async def create_outbox_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload_json: Dict[str, Any],
        idempotency_key: str,
    ) -> NotificationChannelOutbox:
        outbox = NotificationChannelOutbox(
            id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_id=aggregate_id,
            payload_json=payload_json,
            idempotency_key=idempotency_key,
            status="PENDING",
        )
        self.session.add(outbox)
        await self.session.flush()
        return outbox

    async def mark_outbox_processed(self, outbox_id: str, error: Optional[str] = None):
        stmt = select(NotificationChannelOutbox).where(NotificationChannelOutbox.id == outbox_id)
        res = await self.session.execute(stmt)
        ev = res.scalar_one_or_none()
        if ev:
            ev.status = "FAILED" if error else "PROCESSED"
            ev.processed_at = datetime.utcnow()
            ev.processing_error = error
            await self.session.flush()

    async def create_dead_letter(
        self,
        delivery_id: str,
        channel_code: str,
        recipient_user_id: str,
        failure_category: str,
        final_error: str,
        attempt_count: int,
    ) -> NotificationDeadLetter:
        dl = NotificationDeadLetter(
            id=str(uuid.uuid4()),
            delivery_id=delivery_id,
            channel_code=channel_code,
            recipient_user_id=recipient_user_id,
            failure_category=failure_category,
            final_error=final_error,
            attempt_count=attempt_count,
        )
        self.session.add(dl)
        await self.session.flush()
        return dl

    async def list_dead_letters(self, limit: int = 50) -> List[NotificationDeadLetter]:
        stmt = select(NotificationDeadLetter).order_by(desc(NotificationDeadLetter.dead_lettered_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_delivery_metrics(self) -> Dict[str, Any]:
        stmt = select(NotificationChannelDelivery)
        res = await self.session.execute(stmt)
        all_del = list(res.scalars().all())

        total = len(all_del)
        successful = sum(1 for d in all_del if d.status in ("SENT", "PROVIDER_ACCEPTED", "DELIVERED"))
        failed = sum(1 for d in all_del if d.status == "FAILED")
        dead_lettered = sum(1 for d in all_del if d.status == "DEAD_LETTERED")
        deferred = sum(1 for d in all_del if d.status == "DEFERRED")
        pending_queued = sum(1 for d in all_del if d.status in ("CREATED", "QUEUED", "PROCESSING", "RETRY_SCHEDULED"))

        by_status: Dict[str, int] = {}
        for d in all_del:
            by_status[d.status] = by_status.get(d.status, 0) + 1

        # Channel breakdown
        by_channel: Dict[str, int] = {}
        for d in all_del:
            by_channel[d.channel_id] = by_channel.get(d.channel_id, 0) + 1

        # in-app and email
        in_app_count = sum(1 for d in all_del if "in_app" in d.idempotency_key.lower())
        email_count = sum(1 for d in all_del if "email" in d.idempotency_key.lower())

        eligible_deliveries = successful + failed + dead_lettered
        success_rate = calculate_delivery_success_rate(successful, eligible_deliveries)

        return {
            "total_deliveries": total,
            "successful_deliveries": successful,
            "failed_deliveries": failed,
            "dead_lettered_count": dead_lettered,
            "deferred_count": deferred,
            "pending_queued_count": pending_queued,
            "success_rate_pct": success_rate,
            "in_app_deliveries_count": in_app_count,
            "email_deliveries_count": email_count,
            "by_status": by_status,
            "by_channel": by_channel,
        }

