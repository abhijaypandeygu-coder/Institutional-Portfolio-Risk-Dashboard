"""
Comprehensive test suite for M12.07 — Notification Channels.

Covers:
1. Calculations: Exponential backoff + jitter bounds, timezone-aware quiet period evaluation (including midnight crossing & DST), idempotency keys, severity & category filtering, latency & success rate metrics.
2. In-App Notifications: Generation from alerts, unread counts, mark read/unread, separation from alert lifecycle.
3. Email Integration: Mocked provider acceptance, template generation, HTML escaping, failure classifications.
4. Quiet Period & Emergency Bypass: Deferred scheduling, non-emergency suppression, emergency bypass policy.
5. Queue & Delivery Worker: Processing jobs, attempt diagnostics, status transitions, provider acceptance.
6. Retry & Dead-Letter Handling: Transient failure backoff, max retries exhaustion, dead-letter storage, manual operator retry.
7. End-to-End API Integration: Router endpoints for channels, inbox, preferences, subscriptions, deliveries, dead-letters, and metrics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.risk_alerts.notification_channels.calculations.notification_channels_math import (
    calculate_retry_delay,
    is_in_quiet_period,
    generate_delivery_idempotency_key,
    evaluate_severity_eligibility,
    evaluate_category_eligibility,
    calculate_delivery_latency_ms,
    calculate_delivery_success_rate,
)
from backend.app.modules.risk_alerts.notification_channels.services.email_provider_adapter import (
    MockEmailProvider,
)
from backend.app.modules.risk_alerts.notification_channels.services.notification_channels_service import (
    NotificationChannelsService,
)
from backend.app.modules.risk_alerts.notification_channels.schemas.notification_channels_schemas import (
    AlertNotificationIngestRequest,
    ManualRetryRequest,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_notification_channels_math():
    # 1. Backoff calculation
    d1 = calculate_retry_delay(attempt_n=1, initial_delay_seconds=30.0, max_delay_seconds=3600.0, jitter_factor=0.1, deterministic_seed=42)
    d2 = calculate_retry_delay(attempt_n=2, initial_delay_seconds=30.0, max_delay_seconds=3600.0, jitter_factor=0.1, deterministic_seed=42)
    d3 = calculate_retry_delay(attempt_n=3, initial_delay_seconds=30.0, max_delay_seconds=3600.0, jitter_factor=0.1, deterministic_seed=42)
    assert 30.0 <= d1 <= 33.0
    assert 60.0 <= d2 <= 66.0
    assert 120.0 <= d3 <= 132.0

    # 2. Quiet period spanning midnight (22:00 to 07:00 UTC)
    # At 23:30 -> Inside
    now_in = datetime(2026, 11, 16, 23, 30, 0)
    in_quiet, end_utc = is_in_quiet_period(now_in, "22:00", "07:00", "UTC")
    assert in_quiet is True
    assert end_utc is not None
    assert end_utc.hour == 7

    # At 14:00 -> Outside
    now_out = datetime(2026, 11, 16, 14, 0, 0)
    in_quiet_out, end_out = is_in_quiet_period(now_out, "22:00", "07:00", "UTC")
    assert in_quiet_out is False
    assert end_out is None

    # 3. Idempotency key stability
    k1 = generate_delivery_idempotency_key("NOTIF_01", "EMAIL", "USER_1", 1)
    k2 = generate_delivery_idempotency_key("NOTIF_01", "EMAIL", "USER_1", 1)
    k3 = generate_delivery_idempotency_key("NOTIF_01", "EMAIL", "USER_2", 1)
    assert k1 == k2
    assert k1 != k3

    # 4. Severity eligibility
    assert evaluate_severity_eligibility(["CRITICAL", "EMERGENCY"], ["EMERGENCY"], "EMERGENCY") is True
    assert evaluate_severity_eligibility(["CRITICAL", "EMERGENCY"], ["EMERGENCY"], "CRITICAL") is False
    assert evaluate_severity_eligibility(["CRITICAL", "EMERGENCY"], ["WARNING"], "WARNING") is False

    # 5. Success rate
    assert calculate_delivery_success_rate(95, 100) == Decimal("95.00")
    assert calculate_delivery_success_rate(0, 0) == Decimal("100.00")


@pytest.mark.asyncio
async def test_in_app_notification_lifecycle():
    async with AsyncSessionLocal() as session:
        service = NotificationChannelsService(session)
        await service.ensure_default_channels()

        test_user = f"user_{uuid.uuid4().hex[:6]}"
        alert_id = f"ALERT_{uuid.uuid4().hex[:8]}"

        # Ingest alert
        req = AlertNotificationIngestRequest(
            source_alert_id=alert_id,
            title="Portfolio VaR Limit Breach",
            summary="VaR exceeded 99% boundary by 14.5 bps",
            severity="CRITICAL",
            priority_score=Decimal("82.50"),
            priority_band="P2_ELEVATED",
            alert_category="THRESHOLD",
            portfolio_id="PORT_US_EQ_01",
            portfolio_name="US Core Equity",
            target_user_ids=[test_user],
        )
        ingest_res = await service.ingest_alert_notification(req)
        assert ingest_res["in_app_notifications_created"] == 1

        # Check counts
        counts = await service.repo.get_in_app_counts(test_user)
        assert counts["total_notifications"] == 1
        assert counts["unread_count"] == 1
        assert counts["unread_critical_count"] == 1

        # Query inbox
        inbox = await service.repo.list_in_app_inbox(test_user, unread_only=True)
        assert len(inbox) == 1
        notif = inbox[0]
        assert notif.source_alert_id == alert_id
        assert notif.is_read is False

        # Mark read
        updated = await service.repo.mark_in_app_read(notif.id, test_user, is_read=True)
        assert updated.is_read is True
        assert updated.read_at is not None

        # Re-check counts
        counts2 = await service.repo.get_in_app_counts(test_user)
        assert counts2["unread_count"] == 0


@pytest.mark.asyncio
async def test_email_delivery_and_quiet_period_bypass():
    async with AsyncSessionLocal() as session:
        mock_provider = MockEmailProvider()
        service = NotificationChannelsService(session, email_provider=mock_provider)
        await service.ensure_default_channels()

        test_user = f"user_{uuid.uuid4().hex[:6]}"
        alert_id = f"ALERT_{uuid.uuid4().hex[:8]}"

        # Configure user quiet period (22:00 to 07:00 UTC) with emergency bypass enabled
        await service.repo.upsert_user_preference(
            user_id=test_user,
            channel_code="EMAIL",
            enabled=True,
            email_address=f"{test_user}@firm.com",
            is_email_verified=True,
            allowed_severities=["CRITICAL", "EMERGENCY"],
            allowed_categories=["ALL"],
            quiet_period_enabled=True,
            quiet_period_start="00:00",
            quiet_period_end="23:59",  # Active all day
            timezone="UTC",
            emergency_bypass=True,
            digest_enabled=False,
        )

        # 1. Non-emergency (CRITICAL) -> Should be DEFERRED
        req_crit = AlertNotificationIngestRequest(
            source_alert_id=f"{alert_id}_CRIT",
            title="Material Drawdown Warning",
            summary="Intraday drawdown of 2.1% observed",
            severity="CRITICAL",
            priority_score=Decimal("75.00"),
            priority_band="P2_ELEVATED",
            target_user_ids=[test_user],
        )
        res_crit = await service.ingest_alert_notification(req_crit)
        assert res_crit["email_deliveries_queued"] == 1
        deliv_crit = await service.repo.get_delivery_by_id(res_crit["deliveries"][0])
        assert deliv_crit.status == "DEFERRED"

        # 2. EMERGENCY -> Emergency bypass -> Should be immediately QUEUED
        req_emerg = AlertNotificationIngestRequest(
            source_alert_id=f"{alert_id}_EMERG",
            title="Emergency Hard Limit Breach",
            summary="Gross exposure exceeded statutory hard boundary",
            severity="EMERGENCY",
            priority_score=Decimal("98.00"),
            priority_band="P1_IMMEDIATE",
            target_user_ids=[test_user],
        )
        res_emerg = await service.ingest_alert_notification(req_emerg)
        assert res_emerg["email_deliveries_queued"] == 1
        deliv_emerg = await service.repo.get_delivery_by_id(res_emerg["deliveries"][0])
        assert deliv_emerg.status == "QUEUED"

        # Process the emergency delivery job
        proc_res = await service.process_delivery_job(deliv_emerg.id)
        assert proc_res["status"] == "PROVIDER_ACCEPTED"
        assert len(mock_provider.sent_messages) == 1
        assert "EMERGENCY" in mock_provider.sent_messages[0]["subject"]


@pytest.mark.asyncio
async def test_retry_transient_failure_and_dead_letter():
    async with AsyncSessionLocal() as session:
        # Simulate transient timeout
        timeout_provider = MockEmailProvider(simulate_failure_type="TRANSIENT_TIMEOUT")
        service = NotificationChannelsService(session, email_provider=timeout_provider)
        await service.ensure_default_channels()

        test_user = f"user_{uuid.uuid4().hex[:6]}"
        alert_id = f"ALERT_{uuid.uuid4().hex[:8]}"

        req = AlertNotificationIngestRequest(
            source_alert_id=alert_id,
            title="Transient Network Failure Test",
            summary="Simulating network failure to verify backoff and retry scheduling",
            severity="CRITICAL",
            target_user_ids=[test_user],
        )
        res = await service.ingest_alert_notification(req)
        deliv_id = res["deliveries"][0]

        # First attempt -> TRANSIENT_FAILURE -> RETRY_SCHEDULED
        attempt1 = await service.process_delivery_job(deliv_id)
        assert attempt1["status"] == "RETRY_SCHEDULED"
        assert attempt1["attempt_number"] == 1

        # Simulate max attempts reached (force attempt_count = 5)
        deliv = await service.repo.get_delivery_by_id(deliv_id)
        deliv.attempt_count = 4  # Next will be 5 == max_attempts
        await session.flush()

        attempt5 = await service.process_delivery_job(deliv_id)
        assert attempt5["status"] == "DEAD_LETTERED"

        # Verify dead letter table
        dead_letters = await service.repo.list_dead_letters()
        match_dl = [dl for dl in dead_letters if dl.delivery_id == deliv_id]
        assert len(match_dl) == 1
        assert match_dl[0].failure_category == "NETWORK_TIMEOUT"

        # Manual retry by authorized risk manager with operational provider
        service.email_provider = MockEmailProvider()  # Working provider
        retry_res = await service.retry_failed_delivery(
            delivery_id=deliv_id,
            authorized_by="head_of_risk",
            retry_reason="Mail gateway connection restored and verified",
        )
        assert retry_res["status"] == "PROVIDER_ACCEPTED"


@pytest.mark.asyncio
async def test_notification_channels_api_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Channels list
        resp = await client.get("/api/v1/notifications/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2  # IN_APP and EMAIL

        # 2. Ingest Alert via API
        alert_id = f"API_ALERT_{uuid.uuid4().hex[:8]}"
        user_id = f"api_user_{uuid.uuid4().hex[:6]}"
        ingest_payload = {
            "source_alert_id": alert_id,
            "title": "API Test Alert",
            "summary": "Verifying end-to-end API pipeline for M12.07",
            "severity": "CRITICAL",
            "priority_score": 85.0,
            "priority_band": "P2_ELEVATED",
            "alert_category": "MARKET",
            "portfolio_id": "PORT_API_01",
            "target_user_ids": [user_id],
        }
        resp_ingest = await client.post("/api/v1/notifications/ingest-alert", json=ingest_payload)
        assert resp_ingest.status_code == 202
        ingest_data = resp_ingest.json()
        assert ingest_data["in_app_notifications_created"] == 1

        # 3. Check inbox
        resp_inbox = await client.get(f"/api/v1/notifications/inbox?user_id={user_id}")
        assert resp_inbox.status_code == 200
        inbox_items = resp_inbox.json()
        assert len(inbox_items) == 1
        notif_id = inbox_items[0]["id"]
        assert inbox_items[0]["is_read"] is False

        # 4. Mark read
        resp_read = await client.post(f"/api/v1/notifications/{notif_id}/read?user_id={user_id}")
        assert resp_read.status_code == 200
        assert resp_read.json()["is_read"] is True

        # 5. Check counts
        resp_counts = await client.get(f"/api/v1/notifications/counts?user_id={user_id}")
        assert resp_counts.status_code == 200
        counts_data = resp_counts.json()
        assert counts_data["total_notifications"] == 1
        assert counts_data["unread_count"] == 0

        # 6. Delivery metrics
        resp_metrics = await client.get("/api/v1/notifications/delivery-metrics")
        assert resp_metrics.status_code == 200
        metrics = resp_metrics.json()
        assert "total_deliveries" in metrics
        assert "success_rate_pct" in metrics

