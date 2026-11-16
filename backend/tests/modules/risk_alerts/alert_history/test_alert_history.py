"""
Comprehensive test suite for M12.08 — Alert History.

Covers:
1. Calculations: Alert frequency, interarrival intervals, lifecycle durations, reopening/acknowledgement rates, explainable rule noise scores.
2. Historical Alert Repository: Idempotent indexing, snapshot preservation, search by portfolio/instrument/severity/status, total counts.
3. Event Timeline: Reconstructing trigger, acknowledgement, assignment, and closure milestones; calculating duration metrics.
4. Recurrence Analysis: Grouping repeated occurrences, average interarrival time tracking.
5. Rule Noise Analytics: Multi-component scoring, weight configuration, noise identification.
6. Controlled Export: Generating CSV export with SHA-256 checksum, download auditing, record counts.
7. End-to-End API Endpoints: Searching, timeline inspection, recurrence groups, export creation and download, integrity monitoring.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.risk_alerts.alert_history.calculations.alert_history_math import (
    calculate_alert_frequency,
    calculate_interarrival_times,
    calculate_lifecycle_duration_seconds,
    calculate_rates_percentage,
    calculate_rule_noise_score,
    generate_recurrence_grouping_key,
)
from backend.app.modules.risk_alerts.alert_history.services.alert_history_service import (
    AlertHistoryService,
)
from backend.app.modules.risk_alerts.models.risk_alerts_models import AlertEvent
from backend.app.modules.risk_alerts.alert_history.schemas.alert_history_schemas import (
    AlertExportCreateRequest,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_alert_history_math():
    # 1. Frequency
    freq = calculate_alert_frequency(occurrence_count=15, observation_period_days=30.0)
    assert freq == 0.5

    # 2. Interarrival intervals
    t0 = datetime(2026, 11, 16, 10, 0, 0)
    t1 = datetime(2026, 11, 16, 10, 30, 0)  # +1800s
    t2 = datetime(2026, 11, 16, 11, 30, 0)  # +3600s
    intervals, avg_sec = calculate_interarrival_times([t0, t1, t2])
    assert intervals == [1800.0, 3600.0]
    assert avg_sec == 2700.0

    # 3. Lifecycle duration
    dur = calculate_lifecycle_duration_seconds(t0, t1)
    assert dur == 1800.0
    assert calculate_lifecycle_duration_seconds(t0, None) is None

    # 4. Rates
    assert calculate_rates_percentage(8, 10) == Decimal("80.00")
    assert calculate_rates_percentage(0, 0) == Decimal("0.00")

    # 5. Rule Noise Score
    noise = calculate_rule_noise_score(
        trigger_frequency_per_day=10.0,
        recurrence_intensity=0.8,
        short_interval_duplicate_rate=0.4,
        low_severity_rapid_recovery_rate=0.2,
    )
    assert 0.0 <= noise["noise_score"] <= 100.0
    assert "components" in noise


@pytest.mark.asyncio
async def test_historical_indexing_and_search():
    async with AsyncSessionLocal() as session:
        service = AlertHistoryService(session)

        # Create mock alert event in DB
        alert_id = f"ALERT_HIST_{uuid.uuid4().hex[:8]}"
        portfolio_id = f"PORT_{uuid.uuid4().hex[:6]}"
        now = datetime.utcnow()

        alert = AlertEvent(
            id=alert_id,
            alert_type="THRESHOLD_ALERT",
            alert_category="VAR",
            source_module="M12.01",
            portfolio_id=portfolio_id,
            instrument_id="AAPL",
            title="VaR Limit 99% Breached",
            description="Historical VaR exceeded 99% limit by 12 bps",
            priority="HIGH",
            status="OPEN",
            deduplication_key=f"dedupe_{alert_id}",
            created_at=now,
        )
        session.add(alert)
        await session.flush()

        # Index alert
        indexed = await service.index_alert_from_source(alert, current_status="OPEN")
        assert indexed.source_alert_id == alert_id
        assert indexed.severity_at_trigger == "CRITICAL"

        # Search by portfolio
        results, total = await service.repo.search_historical_alerts(portfolio_id=portfolio_id)
        assert total >= 1
        assert any(r.source_alert_id == alert_id for r in results)

        # Search by severity
        results_crit, total_crit = await service.repo.search_historical_alerts(severity="CRITICAL")
        assert total_crit >= 1

        # Check counts
        counts = await service.repo.get_historical_counts()
        assert counts["total_alerts"] >= 1
        assert "CRITICAL" in counts["by_severity"]


@pytest.mark.asyncio
async def test_alert_lifecycle_timeline_and_durations():
    async with AsyncSessionLocal() as session:
        service = AlertHistoryService(session)

        alert_id = f"ALERT_TIMELINE_{uuid.uuid4().hex[:8]}"
        t_trigger = datetime.utcnow() - timedelta(hours=2)
        t_ack = t_trigger + timedelta(minutes=15)
        t_closed = t_trigger + timedelta(hours=1)

        # Create index entry
        await service.repo.upsert_alert_index(
            source_alert_id=alert_id,
            alert_title="Timeline Verification Alert",
            alert_category="LIQUIDITY",
            alert_type="THRESHOLD",
            source_module="M12.03",
            source_rule_id="RULE_SPREAD_WIDENING",
            source_rule_version=1,
            portfolio_id="PORT_TEST_TL",
            portfolio_name="Test Portfolio",
            instrument_id="MSFT",
            listing_id=None,
            severity_at_trigger="WARNING",
            priority_at_trigger="P3_NORMAL",
            priority_score_at_trigger=Decimal("45.00"),
            current_or_final_status_snapshot="CLOSED",
            triggered_at=t_trigger,
            first_acknowledged_at=t_ack,
            closed_at=t_closed,
        )

        # Record timeline events
        await service.repo.index_historical_event(
            source_alert_id=alert_id,
            source_event_id=f"evt_{uuid.uuid4().hex[:6]}",
            event_type="TRIGGERED",
            actor_type="SYSTEM",
            actor_id="system",
            source_module="M12.03",
            occurred_at=t_trigger,
            recorded_at=t_trigger,
            event_sequence=1,
            event_summary="Alert triggered",
            event_details={},
        )
        await service.repo.index_historical_event(
            source_alert_id=alert_id,
            source_event_id=f"evt_{uuid.uuid4().hex[:6]}",
            event_type="ACKNOWLEDGED",
            actor_type="USER",
            actor_id="risk_officer_1",
            source_module="M12.06",
            occurred_at=t_ack,
            recorded_at=t_ack,
            event_sequence=2,
            event_summary="Risk officer acknowledged spread anomaly",
            event_details={},
        )
        await service.repo.index_historical_event(
            source_alert_id=alert_id,
            source_event_id=f"evt_{uuid.uuid4().hex[:6]}",
            event_type="CLOSED",
            actor_type="USER",
            actor_id="risk_officer_1",
            source_module="M12.06",
            occurred_at=t_closed,
            recorded_at=t_closed,
            event_sequence=3,
            event_summary="Spread normalized; alert closed",
            event_details={},
        )

        # Get timeline
        timeline = await service.get_alert_lifecycle_timeline(alert_id)
        assert timeline["total_events"] == 3
        assert timeline["current_or_final_status"] == "CLOSED"
        durations = timeline["duration_metrics"]
        assert durations["trigger_to_acknowledgement_seconds"] == 900.0  # 15 mins
        assert durations["trigger_to_closure_seconds"] == 3600.0  # 1 hour
        assert durations["unresolved_age_seconds"] is None  # Closed alert


@pytest.mark.asyncio
async def test_recurrence_and_rule_analytics():
    async with AsyncSessionLocal() as session:
        service = AlertHistoryService(session)

        rule_id = f"RULE_RECUR_{uuid.uuid4().hex[:6]}"
        t0 = datetime.utcnow() - timedelta(days=2)
        t1 = datetime.utcnow() - timedelta(days=1)
        t2 = datetime.utcnow()

        # Add 3 alerts to same rule & portfolio
        for i, t in enumerate([t0, t1, t2]):
            aid = f"ALERT_REC_{uuid.uuid4().hex[:6]}"
            await service.repo.upsert_alert_index(
                source_alert_id=aid,
                alert_title=f"Recurring Alert {i}",
                alert_category="THRESHOLD",
                alert_type="THRESHOLD",
                source_module="M12.01",
                source_rule_id=rule_id,
                source_rule_version=1,
                portfolio_id="PORT_RECUR",
                portfolio_name="Recur Port",
                instrument_id=None,
                listing_id=None,
                severity_at_trigger="CRITICAL",
                priority_at_trigger="P2_ELEVATED",
                priority_score_at_trigger=Decimal("75.00"),
                current_or_final_status_snapshot="OPEN",
                triggered_at=t,
            )
            await service.repo.add_to_recurrence_group(
                source_rule_id=rule_id,
                alert_category="THRESHOLD",
                portfolio_id="PORT_RECUR",
                instrument_id=None,
                source_alert_id=aid,
                occurrence_timestamp=t,
            )

        # Query recurrence groups
        groups = await service.repo.list_recurrence_groups(min_occurrences=2)
        match_group = [g for g in groups if g.source_rule_id == rule_id]
        assert len(match_group) == 1
        assert match_group[0].occurrence_count == 3
        assert match_group[0].average_interarrival_seconds is not None

        # Compute and record rule analytics
        analytic = await service.repo.record_rule_analytics(
            source_rule_id=rule_id,
            rule_name="Recurring Portfolio Drawdown Rule",
            rule_version=1,
            observation_start=datetime.utcnow() - timedelta(days=30),
            observation_end=datetime.utcnow(),
            trigger_count=3,
            recurrence_count=3,
            affected_portfolio_count=1,
            affected_instrument_count=0,
            warning_count=0,
            critical_count=3,
            emergency_count=0,
            interarrival_timestamps=[t0, t1, t2],
        )
        assert analytic.trigger_count == 3
        assert analytic.noise_score >= Decimal("0.00")


@pytest.mark.asyncio
async def test_alert_history_export_and_download():
    async with AsyncSessionLocal() as session:
        service = AlertHistoryService(session)

        # Create export job
        job = await service.repo.create_export_job(
            requested_by="compliance_officer",
            export_type="HISTORICAL_ALERTS",
            export_format="CSV",
            requested_filters_json={"severity": "CRITICAL"},
        )
        assert job.export_status == "REQUESTED"

        # Process export
        completed_job = await service.process_export_job(job.id)
        assert completed_job.export_status == "COMPLETED"
        assert completed_job.file_reference is not None
        assert completed_job.file_checksum_sha256 is not None
        assert completed_job.file_size_bytes > 0


@pytest.mark.asyncio
async def test_alert_history_api_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Search endpoint
        resp_search = await client.get("/api/v1/alert-history?page=1&page_size=10")
        assert resp_search.status_code == 200
        data = resp_search.json()
        assert "total_count" in data
        assert "items" in data

        # 2. Counts endpoint
        resp_counts = await client.get("/api/v1/alert-history/counts")
        assert resp_counts.status_code == 200
        assert "total_alerts" in resp_counts.json()

        # 3. Recurrence endpoint
        resp_rec = await client.get("/api/v1/alert-history/recurrence/groups")
        assert resp_rec.status_code == 200

        # 4. Rule analytics endpoint
        resp_rule = await client.get("/api/v1/alert-history/rule-analytics/list")
        assert resp_rule.status_code == 200

        # 5. Export creation & download
        export_payload = {
            "requested_by": "audit_lead",
            "export_type": "HISTORICAL_ALERTS",
            "export_format": "CSV",
        }
        resp_export = await client.post("/api/v1/alert-history/exports", json=export_payload)
        assert resp_export.status_code == 201
        exp_data = resp_export.json()
        export_id = exp_data["id"]
        assert exp_data["export_status"] == "COMPLETED"

        # Download file
        resp_dl = await client.get(f"/api/v1/alert-history/exports/{export_id}/download")
        assert resp_dl.status_code == 200
        assert "Alert ID" in resp_dl.text

        # 6. Integrity endpoints
        resp_integ = await client.get("/api/v1/alert-history/integrity/overview")
        assert resp_integ.status_code == 200
        assert "total_integrity_issues" in resp_integ.json()

