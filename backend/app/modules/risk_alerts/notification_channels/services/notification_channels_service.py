"""
Core business services for M12.07 — Notification Channels.
"""

from datetime import datetime
from decimal import Decimal
import html
from typing import Optional, List, Dict, Any, Tuple
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

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
from backend.app.modules.risk_alerts.notification_channels.repositories.notification_channels_repository import (
    NotificationChannelsRepository,
)
from backend.app.modules.risk_alerts.notification_channels.calculations.notification_channels_math import (
    calculate_retry_delay,
    is_in_quiet_period,
    generate_delivery_idempotency_key,
    evaluate_severity_eligibility,
    evaluate_category_eligibility,
    calculate_delivery_latency_ms,
)
from backend.app.modules.risk_alerts.notification_channels.services.email_provider_adapter import (
    EmailProviderAdapter,
    MockEmailProvider,
    SMTPEmailProvider,
)
from backend.app.modules.risk_alerts.notification_channels.schemas.notification_channels_schemas import (
    AlertNotificationIngestRequest,
)


class NotificationChannelsService:
    def __init__(
        self,
        session: AsyncSession,
        email_provider: Optional[EmailProviderAdapter] = None,
    ):
        self.session = session
        self.repo = NotificationChannelsRepository(session)
        self.email_provider = email_provider or MockEmailProvider()

    # -------------------------------------------------------------
    # Channel Initialization & Registry
    # -------------------------------------------------------------
    async def ensure_default_channels(self):
        """
        Ensures default IN_APP and EMAIL channels exist in the database.
        """
        in_app = await self.repo.get_channel_by_code("IN_APP")
        if not in_app:
            await self.repo.create_channel(
                channel_code="IN_APP",
                channel_name="Dashboard In-App Inbox",
                channel_type="IN_APP",
                description="Real-time dashboard notifications for risk alerts and limit events",
                is_enabled=True,
                capabilities_json={
                    "supports_realtime": True,
                    "supports_read_receipt": True,
                    "supported_severities": ["WARNING", "CRITICAL", "EMERGENCY"],
                    "supported_categories": ["ALL"],
                },
                initial_config_json={"delivery_mode": "IMMEDIATE", "max_unread_limit": 1000},
                created_by="system",
            )

        email = await self.repo.get_channel_by_code("EMAIL")
        if not email:
            await self.repo.create_channel(
                channel_code="EMAIL",
                channel_name="Institutional Alert Email Dispatcher",
                channel_type="EMAIL",
                description="Secure email notifications for critical and emergency risk events",
                is_enabled=True,
                capabilities_json={
                    "supports_realtime": False,
                    "supports_read_receipt": False,
                    "supported_severities": ["CRITICAL", "EMERGENCY"],
                    "supported_categories": ["ALL"],
                },
                initial_config_json={"delivery_mode": "ASYNC_QUEUE", "max_batch_size": 20},
                created_by="system",
            )

    # -------------------------------------------------------------
    # Alert Ingestion Pipeline (Step 1 -> Step 7)
    # -------------------------------------------------------------
    async def ingest_alert_notification(
        self,
        request: AlertNotificationIngestRequest,
    ) -> Dict[str, Any]:
        """
        Consumes an alert event from M12.01-M12.06, resolves eligible recipients,
        evaluates preferences/quiet periods, creates in-app notifications and queues email deliveries.
        """
        await self.ensure_default_channels()
        event_time = request.event_timestamp or datetime.utcnow()

        # Step 1: Target Users Resolution
        # If target_user_ids specified, use them; otherwise, default to standard admin/risk users
        target_users = request.target_user_ids or ["risk_manager_1", "head_of_risk"]

        created_in_app: List[InAppNotification] = []
        queued_deliveries: List[NotificationChannelDelivery] = []

        # Get registered channels
        ch_in_app = await self.repo.get_channel_by_code("IN_APP")
        ch_email = await self.repo.get_channel_by_code("EMAIL")

        for user_id in target_users:
            # -----------------------------------------
            # Channel 1: IN_APP Delivery
            # -----------------------------------------
            if ch_in_app and ch_in_app.is_enabled:
                pref_in_app = await self.repo.get_user_preference(user_id, "IN_APP")
                in_app_enabled = pref_in_app.enabled if pref_in_app else True
                allowed_sevs = pref_in_app.allowed_severities if pref_in_app else ["WARNING", "CRITICAL", "EMERGENCY"]
                allowed_cats = pref_in_app.allowed_categories if pref_in_app else ["ALL"]

                if in_app_enabled and evaluate_severity_eligibility(
                    ch_in_app.capabilities_json.get("supported_severities", ["WARNING", "CRITICAL", "EMERGENCY"]),
                    allowed_sevs,
                    request.severity,
                ) and evaluate_category_eligibility(
                    ch_in_app.capabilities_json.get("supported_categories", ["ALL"]),
                    allowed_cats,
                    request.alert_category or "GENERAL",
                ):
                    in_app_item = await self.repo.create_in_app_notification(
                        source_alert_id=request.source_alert_id,
                        recipient_user_id=user_id,
                        title=request.title,
                        summary=request.summary,
                        severity=request.severity,
                        priority_score=request.priority_score or Decimal("50.00"),
                        priority_band=request.priority_band or "P3_NORMAL",
                        alert_category=request.alert_category or "GENERAL",
                        portfolio_id=request.portfolio_id,
                        portfolio_name=request.portfolio_name,
                        instrument_id=request.instrument_id,
                        event_timestamp=event_time,
                        notification_metadata=request.metric_values or {},
                    )
                    created_in_app.append(in_app_item)

                    # Persist delivery task record for audit tracking
                    idemp_key = generate_delivery_idempotency_key(
                        in_app_item.id, "IN_APP", user_id
                    )
                    deliv = await self.repo.create_delivery(
                        source_alert_id=request.source_alert_id,
                        channel_id=ch_in_app.id,
                        recipient_user_id=user_id,
                        recipient_address=None,
                        idempotency_key=idemp_key,
                        status="DELIVERED",
                        priority=request.priority_band or "P3_NORMAL",
                        title=request.title,
                        payload_json={"in_app_id": in_app_item.id, "severity": request.severity},
                        scheduled_at=event_time,
                    )
                    await self.repo.record_delivery_attempt(
                        delivery_id=deliv.id,
                        attempt_number=1,
                        outcome="SUCCESS",
                        started_at=event_time,
                        completed_at=datetime.utcnow(),
                        provider_response_code="PERSISTED_IN_APP",
                        provider_message_id=in_app_item.id,
                        duration_ms=Decimal("1.50"),
                    )

            # -----------------------------------------
            # Channel 2: EMAIL Delivery
            # -----------------------------------------
            if ch_email and ch_email.is_enabled:
                pref_email = await self.repo.get_user_preference(user_id, "EMAIL")
                email_enabled = pref_email.enabled if pref_email else (request.severity in ("CRITICAL", "EMERGENCY"))
                recipient_email = pref_email.email_address if (pref_email and pref_email.email_address) else f"{user_id}@institutional.internal"
                allowed_sevs = pref_email.allowed_severities if pref_email else ["CRITICAL", "EMERGENCY"]
                allowed_cats = pref_email.allowed_categories if pref_email else ["ALL"]

                if email_enabled and evaluate_severity_eligibility(
                    ch_email.capabilities_json.get("supported_severities", ["CRITICAL", "EMERGENCY"]),
                    allowed_sevs,
                    request.severity,
                ) and evaluate_category_eligibility(
                    ch_email.capabilities_json.get("supported_categories", ["ALL"]),
                    allowed_cats,
                    request.alert_category or "GENERAL",
                ):
                    # Check quiet period & emergency bypass
                    is_quiet = False
                    defer_until = None
                    if pref_email and pref_email.quiet_period_enabled:
                        in_quiet, exit_time = is_in_quiet_period(
                            now_utc=datetime.utcnow(),
                            quiet_start_time_str=pref_email.quiet_period_start or "22:00",
                            quiet_end_time_str=pref_email.quiet_period_end or "07:00",
                            recipient_timezone_str=pref_email.timezone or "UTC",
                        )
                        if in_quiet:
                            # Check emergency bypass
                            if request.severity.upper() == "EMERGENCY" and pref_email.emergency_bypass:
                                is_quiet = False
                            else:
                                is_quiet = True
                                defer_until = exit_time

                    deliv_status = "DEFERRED" if is_quiet else "QUEUED"
                    scheduled_time = defer_until if is_quiet and defer_until else datetime.utcnow()

                    email_idemp = generate_delivery_idempotency_key(
                        request.source_alert_id, "EMAIL", user_id
                    )

                    existing = await self.repo.get_delivery_by_idempotency_key(email_idemp)
                    if not existing:
                        email_deliv = await self.repo.create_delivery(
                            source_alert_id=request.source_alert_id,
                            channel_id=ch_email.id,
                            recipient_user_id=user_id,
                            recipient_address=recipient_email,
                            idempotency_key=email_idemp,
                            status=deliv_status,
                            priority=request.priority_band or "P2_ELEVATED",
                            title=f"[{request.severity}] {request.title}",
                            payload_json={
                                "summary": request.summary,
                                "portfolio_id": request.portfolio_id,
                                "portfolio_name": request.portfolio_name,
                                "instrument_id": request.instrument_id,
                                "metric_values": request.metric_values,
                                "severity": request.severity,
                            },
                            scheduled_at=scheduled_time,
                        )
                        queued_deliveries.append(email_deliv)

                        # Write to outbox for transactional event handoff
                        await self.repo.create_outbox_event(
                            event_type="EMAIL_NOTIFICATION_QUEUED",
                            aggregate_id=email_deliv.id,
                            payload_json={
                                "delivery_id": email_deliv.id,
                                "recipient_email": recipient_email,
                                "title": email_deliv.title,
                            },
                            idempotency_key=f"outbox_{email_idemp}",
                        )

        return {
            "source_alert_id": request.source_alert_id,
            "in_app_notifications_created": len(created_in_app),
            "email_deliveries_queued": len(queued_deliveries),
            "deliveries": [d.id for d in queued_deliveries],
        }

    # -------------------------------------------------------------
    # Email Template Renderer
    # -------------------------------------------------------------
    def render_email_content(
        self,
        delivery: NotificationChannelDelivery,
    ) -> Tuple[str, str, str]:
        """
        Renders subject line, plaintext body and sanitized HTML body.
        Guarantees no HTML injection via untrusted inputs.
        """
        p = delivery.payload_json
        safe_title = html.escape(delivery.title)
        safe_summary = html.escape(str(p.get("summary", "")))
        safe_portfolio = html.escape(str(p.get("portfolio_name") or p.get("portfolio_id") or "N/A"))
        safe_instrument = html.escape(str(p.get("instrument_id") or "N/A"))
        safe_severity = html.escape(str(p.get("severity", "CRITICAL")))

        subject = delivery.title

        text_body = (
            f"{delivery.title}\n\n"
            f"Severity: {safe_severity}\n"
            f"Portfolio: {safe_portfolio}\n"
            f"Instrument: {safe_instrument}\n"
            f"Timestamp: {delivery.scheduled_at.isoformat()} UTC\n\n"
            f"Summary:\n{p.get('summary', '')}\n\n"
            f"Access Dashboard: https://risk-dashboard.institutional.internal/alerts/{delivery.source_alert_id}\n\n"
            f"--- CONFIDENTIAL FINANCIAL RISK NOTIFICATION ---"
        )

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; color: #1e293b; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px; }}
            .header {{ padding: 12px 16px; border-radius: 6px; font-weight: bold; margin-bottom: 16px; }}
            .severity-EMERGENCY {{ background-color: #fee2e2; color: #991b1b; border: 1px solid #f87171; }}
            .severity-CRITICAL {{ background-color: #ffedd5; color: #9a3412; border: 1px solid #fb923c; }}
            .severity-WARNING {{ background-color: #fef9c3; color: #854d0e; border: 1px solid #facc15; }}
            .content {{ margin-bottom: 20px; }}
            .metric-box {{ background: #f8fafc; padding: 12px; border-radius: 4px; border: 1px solid #e2e8f0; margin-bottom: 16px; }}
            .btn {{ display: inline-block; padding: 8px 16px; background-color: #0f172a; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: 500; }}
            .disclaimer {{ font-size: 11px; color: #64748b; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 12px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header severity-{safe_severity}">
              [{safe_severity}] {safe_title}
            </div>
            <div class="content">
              <p><strong>Summary:</strong> {safe_summary}</p>
              <div class="metric-box">
                <p><strong>Portfolio:</strong> {safe_portfolio}</p>
                <p><strong>Instrument:</strong> {safe_instrument}</p>
                <p><strong>Event Time:</strong> {delivery.scheduled_at.isoformat()} UTC</p>
                <p><strong>Source Alert ID:</strong> <code>{delivery.source_alert_id}</code></p>
              </div>
              <p>
                <a href="https://risk-dashboard.institutional.internal/alerts/{delivery.source_alert_id}" class="btn">View in Risk Dashboard</a>
              </p>
            </div>
            <div class="disclaimer">
              This message was generated automatically by the Institutional Portfolio Risk Dashboard Notification Engine (M12.07).
              Please do not reply directly to this email. Market-risk metrics are subject to verification against authoritative risk ledgers.
            </div>
          </div>
        </body>
        </html>
        """
        return subject, text_body, html_body

    # -------------------------------------------------------------
    # Queue Processing & Delivery Worker Execution
    # -------------------------------------------------------------
    async def process_delivery_job(
        self,
        delivery_id: str,
    ) -> Dict[str, Any]:
        """
        Processes a single delivery job:
        - Claims the delivery
        - Delivers via email provider adapter
        - Records attempt diagnostics
        - Updates delivery status and outbox
        - Schedules retries or dead-letters on failure
        """
        delivery = await self.repo.get_delivery_by_id(delivery_id)
        if not delivery:
            return {"status": "NOT_FOUND", "delivery_id": delivery_id}

        if delivery.status in ("SENT", "PROVIDER_ACCEPTED", "DELIVERED", "DEAD_LETTERED", "CANCELLED"):
            return {"status": "ALREADY_COMPLETED", "current_status": delivery.status}

        # Transition to PROCESSING
        await self.repo.update_delivery_status(
            delivery_id=delivery.id,
            new_status="PROCESSING",
            transition_reason="Worker claimed delivery job",
            actor_type="WORKER",
            actor_id="notification_worker_1",
        )

        started_at = datetime.utcnow()
        attempt_num = delivery.attempt_count + 1
        delivery.attempt_count = attempt_num

        subject, text_body, html_body = self.render_email_content(delivery)
        recipient_addr = delivery.recipient_address or f"{delivery.recipient_user_id}@institutional.internal"

        # Dispatch via email provider
        result = await self.email_provider.send_email(
            to_address=recipient_addr,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

        completed_at = datetime.utcnow()
        latency_ms = calculate_delivery_latency_ms(started_at, completed_at)

        # Record attempt
        await self.repo.record_delivery_attempt(
            delivery_id=delivery.id,
            attempt_number=attempt_num,
            outcome=result.outcome,
            started_at=started_at,
            completed_at=completed_at,
            provider_response_code=result.provider_response_code,
            provider_message_id=result.provider_message_id,
            error_category=result.error_category,
            error_code=result.error_code,
            error_message=result.error_message,
            duration_ms=Decimal(str(round(latency_ms, 2))),
        )

        if result.success:
            # Mark SENT / PROVIDER_ACCEPTED
            await self.repo.update_delivery_status(
                delivery_id=delivery.id,
                new_status="PROVIDER_ACCEPTED",
                transition_reason=f"Provider accepted message (code={result.provider_response_code})",
                actor_type="WORKER",
                actor_id="notification_worker_1",
                provider_message_id=result.provider_message_id,
            )
            # Update channel health
            await self.repo.update_channel_status(
                channel_id=delivery.channel_id,
                mark_success=True,
            )
            return {
                "delivery_id": delivery.id,
                "status": "PROVIDER_ACCEPTED",
                "attempt_number": attempt_num,
                "provider_message_id": result.provider_message_id,
            }
        else:
            # Failure handling
            await self.repo.update_channel_status(
                channel_id=delivery.channel_id,
                health_status="DEGRADED",
                last_error=result.error_message,
            )

            # Check retry eligibility
            is_transient = result.outcome in ("TRANSIENT_FAILURE", "TIMEOUT", "RATE_LIMITED")
            if is_transient and attempt_num < delivery.max_attempts:
                # Schedule retry with exponential backoff + jitter
                delay_sec = calculate_retry_delay(
                    attempt_n=attempt_num,
                    initial_delay_seconds=30.0,
                    max_delay_seconds=3600.0,
                    jitter_factor=0.1,
                )
                from datetime import timedelta
                next_retry = datetime.utcnow() + timedelta(seconds=delay_sec)

                await self.repo.update_delivery_status(
                    delivery_id=delivery.id,
                    new_status="RETRY_SCHEDULED",
                    transition_reason=f"Transient failure (delay={delay_sec}s): {result.error_message}",
                    actor_type="WORKER",
                    actor_id="notification_worker_1",
                    next_retry_at=next_retry,
                    last_error_code=result.error_code,
                    last_error_message=result.error_message,
                )
                return {
                    "delivery_id": delivery.id,
                    "status": "RETRY_SCHEDULED",
                    "attempt_number": attempt_num,
                    "next_retry_at": next_retry.isoformat(),
                    "error": result.error_message,
                }
            else:
                # Terminal failure or retry exhausted -> DEAD_LETTERED
                await self.repo.update_delivery_status(
                    delivery_id=delivery.id,
                    new_status="DEAD_LETTERED",
                    transition_reason=f"Permanent failure or retries exhausted: {result.error_message}",
                    actor_type="WORKER",
                    actor_id="notification_worker_1",
                    last_error_code=result.error_code,
                    last_error_message=result.error_message,
                )
                # Create dead letter record
                ch = await self.repo.get_channel_by_id(delivery.channel_id)
                ch_code = ch.channel_code if ch else "EMAIL"
                await self.repo.create_dead_letter(
                    delivery_id=delivery.id,
                    channel_code=ch_code,
                    recipient_user_id=delivery.recipient_user_id,
                    failure_category=result.error_category or "UNKNOWN_FAILURE",
                    final_error=result.error_message or "Max retries exceeded",
                    attempt_count=attempt_num,
                )
                return {
                    "delivery_id": delivery.id,
                    "status": "DEAD_LETTERED",
                    "attempt_number": attempt_num,
                    "error": result.error_message,
                }

    async def run_queue_batch(self, limit: int = 20) -> Dict[str, Any]:
        """
        Executes a batch of scheduled or pending deliveries.
        """
        now = datetime.utcnow()
        pending = await self.repo.list_pending_or_scheduled_deliveries(as_of_utc=now, limit=limit)
        results = []
        for d in pending:
            res = await self.process_delivery_job(d.id)
            results.append(res)
        return {
            "batch_size": len(pending),
            "processed": results,
            "timestamp": now.isoformat(),
        }

    # -------------------------------------------------------------
    # Manual Retry Operation
    # -------------------------------------------------------------
    async def retry_failed_delivery(
        self,
        delivery_id: str,
        authorized_by: str,
        retry_reason: str,
    ) -> Dict[str, Any]:
        """
        Allows authorized operators to retry a dead-lettered or failed delivery.
        """
        delivery = await self.repo.get_delivery_by_id(delivery_id)
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")

        # Update status to QUEUED
        await self.repo.update_delivery_status(
            delivery_id=delivery.id,
            new_status="QUEUED",
            transition_reason=f"Manual retry authorized by {authorized_by}: {retry_reason}",
            actor_type="ADMIN_USER",
            actor_id=authorized_by,
        )

        # Process immediately
        return await self.process_delivery_job(delivery.id)

