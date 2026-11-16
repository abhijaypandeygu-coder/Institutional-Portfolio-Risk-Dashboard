"""
Services for M12.08 — Alert History.
"""

import csv
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import io
import os
from typing import Optional, List, Dict, Any, Tuple
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.risk_alerts.alert_history.models.alert_history_models import (
    HistoricalAlertIndex,
    HistoricalAlertEventIndex,
    AlertRecurrenceGroup,
    AlertRecurrenceMember,
    AlertRuleAnalytics,
    AlertExportJob,
    AlertExportDownloadHistory,
    AlertHistoryIntegrityIssue,
)
from backend.app.modules.risk_alerts.alert_history.repositories.alert_history_repository import (
    AlertHistoryRepository,
)
from backend.app.modules.risk_alerts.alert_history.calculations.alert_history_math import (
    calculate_lifecycle_duration_seconds,
    calculate_rates_percentage,
)
from backend.app.modules.risk_alerts.models.risk_alerts_models import AlertEvent
from backend.app.modules.risk_alerts.alert_management.models.alert_management_models import (
    AlertWorkflowState,
    AlertWorkflowEvent,
    AlertClosure,
)


class AlertHistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AlertHistoryRepository(session)

    # -------------------------------------------------------------
    # Ingestion & Historical Indexing
    # -------------------------------------------------------------
    async def index_alert_from_source(
        self,
        alert_event: AlertEvent,
        current_status: str = "OPEN",
    ) -> HistoricalAlertIndex:
        """
        Idempotently indexes an AlertEvent into HistoricalAlertIndex.
        """
        # Determine metric & threshold snapshot from evidence or alert_event
        metric_val = getattr(alert_event, "current_metric_value", None)
        threshold_val = getattr(alert_event, "threshold_value", None)

        source_rule = getattr(alert_event, "rule_id", None) or "DEFAULT_RULE"
        category = getattr(alert_event, "alert_category", None) or getattr(alert_event, "category", "GENERAL")
        # In AlertEvent model, priority contains the severity string (e.g. CRITICAL, HIGH, etc.)
        p_val = getattr(alert_event, "priority", None)
        s_val = getattr(alert_event, "severity", None)
        if s_val:
            severity = s_val
        elif p_val in ("CRITICAL", "EMERGENCY", "WARNING"):
            severity = p_val
        elif p_val == "HIGH":
            severity = "CRITICAL"
        else:
            severity = "WARNING"
            
        priority = p_val or "P3_NORMAL"

        indexed = await self.repo.upsert_alert_index(
            source_alert_id=alert_event.id,
            alert_title=alert_event.title or f"Alert {alert_event.id}",
            alert_category=category,
            alert_type=getattr(alert_event, "alert_type", "THRESHOLD"),
            source_module="M12.01",
            source_rule_id=source_rule,
            source_rule_version=1,
            portfolio_id=getattr(alert_event, "portfolio_id", None),
            portfolio_name=getattr(alert_event, "portfolio_name", None),
            instrument_id=getattr(alert_event, "instrument_id", None),
            listing_id=None,
            severity_at_trigger=severity,
            priority_at_trigger=priority,
            priority_score_at_trigger=getattr(alert_event, "priority_score", Decimal("50.00")),
            current_or_final_status_snapshot=current_status,
            triggered_at=getattr(alert_event, "created_at", datetime.utcnow()),
            metric_value_snapshot=metric_val,
            threshold_value_snapshot=threshold_val,
        )

        # Create initial TRIGGERED event in timeline
        await self.repo.index_historical_event(
            source_alert_id=indexed.source_alert_id,
            source_event_id=f"trigger_{indexed.source_alert_id}",
            event_type="TRIGGERED",
            actor_type="SYSTEM",
            actor_id="risk_engine",
            source_module="M12.01",
            occurred_at=indexed.triggered_at,
            recorded_at=indexed.indexed_at,
            event_sequence=1,
            event_summary=f"Alert triggered with severity {indexed.severity_at_trigger}",
            event_details={"rule_id": indexed.source_rule_id},
        )

        # Add to recurrence group
        await self.repo.add_to_recurrence_group(
            source_rule_id=indexed.source_rule_id,
            alert_category=indexed.alert_category,
            portfolio_id=indexed.portfolio_id,
            instrument_id=indexed.instrument_id,
            source_alert_id=indexed.source_alert_id,
            occurrence_timestamp=indexed.triggered_at,
        )

        return indexed

    # -------------------------------------------------------------
    # Timeline Reconstruction & Durations
    # -------------------------------------------------------------
    async def get_alert_lifecycle_timeline(
        self,
        source_alert_id: str,
    ) -> Dict[str, Any]:
        """
        Reconstructs the full lifecycle timeline and duration metrics.
        """
        alert = await self.repo.get_indexed_alert(source_alert_id)
        if not alert:
            raise ValueError(f"Alert {source_alert_id} not found in historical index")

        events = await self.repo.get_alert_timeline(source_alert_id)

        # Compute durations
        t_trigger = alert.triggered_at
        t_ack = alert.first_acknowledged_at
        t_assigned = alert.first_assigned_at
        t_closed = alert.closed_at

        d_ack = calculate_lifecycle_duration_seconds(t_trigger, t_ack)
        d_assigned = calculate_lifecycle_duration_seconds(t_trigger, t_assigned)
        d_closed = calculate_lifecycle_duration_seconds(t_trigger, t_closed)
        
        # Unresolved age if still open
        is_open = alert.current_or_final_status_snapshot not in ("CLOSED", "RESOLVED")
        unresolved_age = calculate_lifecycle_duration_seconds(t_trigger, datetime.utcnow()) if is_open else None

        durations = {
            "trigger_to_acknowledgement_seconds": d_ack,
            "trigger_to_assignment_seconds": d_assigned,
            "trigger_to_closure_seconds": d_closed,
            "unresolved_age_seconds": unresolved_age,
        }

        return {
            "source_alert_id": alert.source_alert_id,
            "total_events": len(events),
            "first_triggered_at": alert.triggered_at,
            "current_or_final_status": alert.current_or_final_status_snapshot,
            "duration_metrics": durations,
            "events": events,
        }

    # -------------------------------------------------------------
    # Historical Backfill Execution
    # -------------------------------------------------------------
    async def run_historical_backfill(self) -> Dict[str, Any]:
        """
        Scans existing AlertEvent, AlertWorkflowEvent, and AlertWorkflowState
        and backfills historical indexes and timelines safely and idempotently.
        """
        alerts_stmt = select(AlertEvent)
        res = await self.session.execute(alerts_stmt)
        alerts = list(res.scalars().all())

        indexed_count = 0
        events_count = 0

        for a in alerts:
            # Query workflow state if exists
            wf_stmt = select(AlertWorkflowState).where(AlertWorkflowState.alert_id == a.id)
            wf_res = await self.session.execute(wf_stmt)
            wf_state = wf_res.scalar_one_or_none()
            curr_status = wf_state.current_state if wf_state else "OPEN"

            # Index alert
            hist_alert = await self.index_alert_from_source(a, current_status=curr_status)
            indexed_count += 1

            # Backfill M12.06 workflow events
            ev_stmt = select(AlertWorkflowEvent).where(AlertWorkflowEvent.alert_id == a.id).order_by(AlertWorkflowEvent.created_at)
            ev_res = await self.session.execute(ev_stmt)
            wf_events = list(ev_res.scalars().all())

            for ev in wf_events:
                await self.repo.index_historical_event(
                    source_alert_id=a.id,
                    source_event_id=ev.id,
                    event_type=ev.event_type,
                    actor_type="USER" if ev.actor_id != "system" else "SYSTEM",
                    actor_id=ev.actor_id,
                    source_module="M12.06",
                    occurred_at=ev.created_at,
                    recorded_at=ev.created_at,
                    event_sequence=ev.workflow_cycle,
                    event_summary=f"Workflow transition to {ev.new_state}: {ev.transition_reason or ''}",
                    event_details=ev.event_context or {},
                )
                events_count += 1

                # Update acknowledgement / closure timestamps on index
                if ev.new_state == "ACKNOWLEDGED" and not hist_alert.first_acknowledged_at:
                    hist_alert.first_acknowledged_at = ev.created_at
                elif ev.new_state == "ASSIGNED" and not hist_alert.first_assigned_at:
                    hist_alert.first_assigned_at = ev.created_at
                elif ev.new_state == "CLOSED" and not hist_alert.closed_at:
                    hist_alert.closed_at = ev.created_at

        return {
            "status": "BACKFILL_COMPLETED",
            "indexed_alerts": indexed_count,
            "indexed_events": events_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # -------------------------------------------------------------
    # Controlled Export Generation (CSV, JSON/XLSX)
    # -------------------------------------------------------------
    async def process_export_job(self, export_id: str) -> AlertExportJob:
        """
        Executes export job asynchronously or synchronously, generating a CSV file with SHA-256 checksum.
        """
        job = await self.repo.get_export_job(export_id)
        if not job:
            raise ValueError(f"Export job {export_id} not found")

        job.export_status = "PROCESSING"
        job.started_at = datetime.utcnow()
        await self.session.flush()

        filters = job.requested_filters_json
        alerts, total = await self.repo.search_historical_alerts(
            portfolio_id=filters.get("portfolio_id"),
            instrument_id=filters.get("instrument_id"),
            severity=filters.get("severity"),
            category=filters.get("alert_category"),
            source_rule_id=filters.get("source_rule_id"),
            limit=5000,  # Max export limit
        )

        # Build CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Alert ID",
            "Title",
            "Category",
            "Type",
            "Rule ID",
            "Portfolio ID",
            "Portfolio Name",
            "Instrument ID",
            "Severity",
            "Priority",
            "Priority Score",
            "Status",
            "Triggered At UTC",
            "First Acknowledged At UTC",
            "Closed At UTC",
            "Metric Value",
            "Threshold Value",
        ])

        for a in alerts:
            writer.writerow([
                a.source_alert_id,
                a.alert_title,
                a.alert_category,
                a.alert_type,
                a.source_rule_id,
                a.portfolio_id or "",
                a.portfolio_name or "",
                a.instrument_id or "",
                a.severity_at_trigger,
                a.priority_at_trigger,
                str(a.priority_score_at_trigger),
                a.current_or_final_status_snapshot,
                a.triggered_at.isoformat() if a.triggered_at else "",
                a.first_acknowledged_at.isoformat() if a.first_acknowledged_at else "",
                a.closed_at.isoformat() if a.closed_at else "",
                str(a.metric_value_snapshot or ""),
                str(a.threshold_value_snapshot or ""),
            ])

        csv_content = output.getvalue().encode("utf-8")
        checksum = hashlib.sha256(csv_content).hexdigest()

        # Save to local controlled storage
        export_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, f"alert_export_{job.id}.csv")
        with open(file_path, "wb") as f:
            f.write(csv_content)

        job.record_count = len(alerts)
        job.file_reference = file_path
        job.file_checksum_sha256 = checksum
        job.file_size_bytes = len(csv_content)
        job.completed_at = datetime.utcnow()
        job.expires_at = datetime.utcnow() + timedelta(days=7)
        job.export_status = "COMPLETED"
        await self.session.flush()

        return job

