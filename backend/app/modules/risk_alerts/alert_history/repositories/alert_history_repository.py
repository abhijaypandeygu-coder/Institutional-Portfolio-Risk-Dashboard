"""
Repository for M12.08 — Alert History.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
import uuid

from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from backend.app.modules.risk_alerts.models.risk_alerts_models import AlertEvent, AlertLifecycleEvent
from backend.app.modules.risk_alerts.alert_management.models.alert_management_models import (
    AlertWorkflowState,
    AlertWorkflowEvent,
    AlertClosure,
)
from backend.app.modules.risk_alerts.alert_history.calculations.alert_history_math import (
    generate_recurrence_grouping_key,
    calculate_interarrival_times,
    calculate_alert_frequency,
    calculate_rule_noise_score,
)


class AlertHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------
    # Historical Alert Indexing & Retrieval
    # -------------------------------------------------------------
    async def get_indexed_alert(self, source_alert_id: str) -> Optional[HistoricalAlertIndex]:
        stmt = (
            select(HistoricalAlertIndex)
            .where(HistoricalAlertIndex.source_alert_id == source_alert_id)
            .options(selectinload(HistoricalAlertIndex.events))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def upsert_alert_index(
        self,
        source_alert_id: str,
        alert_title: str,
        alert_category: str,
        alert_type: str,
        source_module: str,
        source_rule_id: str,
        source_rule_version: int,
        portfolio_id: Optional[str],
        portfolio_name: Optional[str],
        instrument_id: Optional[str],
        listing_id: Optional[str],
        severity_at_trigger: str,
        priority_at_trigger: str,
        priority_score_at_trigger: Decimal,
        current_or_final_status_snapshot: str,
        triggered_at: datetime,
        first_acknowledged_at: Optional[datetime] = None,
        first_assigned_at: Optional[datetime] = None,
        closed_at: Optional[datetime] = None,
        metric_value_snapshot: Optional[Decimal] = None,
        threshold_value_snapshot: Optional[Decimal] = None,
        metric_unit_snapshot: Optional[str] = "NAV_PCT",
    ) -> HistoricalAlertIndex:
        item = await self.get_indexed_alert(source_alert_id)
        if item:
            item.alert_title = alert_title
            item.current_or_final_status_snapshot = current_or_final_status_snapshot
            if first_acknowledged_at and not item.first_acknowledged_at:
                item.first_acknowledged_at = first_acknowledged_at
            if first_assigned_at and not item.first_assigned_at:
                item.first_assigned_at = first_assigned_at
            if closed_at and not item.closed_at:
                item.closed_at = closed_at
            item.last_event_at = datetime.utcnow()
        else:
            item = HistoricalAlertIndex(
                id=str(uuid.uuid4()),
                source_alert_id=source_alert_id,
                alert_title=alert_title,
                alert_category=alert_category.upper(),
                alert_type=alert_type.upper(),
                source_module=source_module,
                source_rule_id=source_rule_id,
                source_rule_version=source_rule_version,
                portfolio_id=portfolio_id,
                portfolio_name=portfolio_name,
                instrument_id=instrument_id,
                listing_id=listing_id,
                severity_at_trigger=severity_at_trigger.upper(),
                priority_at_trigger=priority_at_trigger,
                priority_score_at_trigger=priority_score_at_trigger,
                current_or_final_status_snapshot=current_or_final_status_snapshot.upper(),
                triggered_at=triggered_at,
                first_acknowledged_at=first_acknowledged_at,
                first_assigned_at=first_assigned_at,
                closed_at=closed_at,
                last_event_at=triggered_at,
                metric_value_snapshot=metric_value_snapshot,
                threshold_value_snapshot=threshold_value_snapshot,
                metric_unit_snapshot=metric_unit_snapshot,
            )
            self.session.add(item)
        await self.session.flush()
        return item

    async def search_historical_alerts(
        self,
        portfolio_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        source_rule_id: Optional[str] = None,
        source_module: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        sort_by: str = "newest",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[HistoricalAlertIndex], int]:
        stmt = select(HistoricalAlertIndex)
        count_stmt = select(func.count(HistoricalAlertIndex.id))

        filters = []
        if portfolio_id:
            filters.append(HistoricalAlertIndex.portfolio_id == portfolio_id)
        if instrument_id:
            filters.append(HistoricalAlertIndex.instrument_id == instrument_id)
        if severity:
            filters.append(HistoricalAlertIndex.severity_at_trigger == severity.upper())
        if category:
            filters.append(HistoricalAlertIndex.alert_category == category.upper())
        if status:
            filters.append(HistoricalAlertIndex.current_or_final_status_snapshot == status.upper())
        if source_rule_id:
            filters.append(HistoricalAlertIndex.source_rule_id == source_rule_id)
        if source_module:
            filters.append(HistoricalAlertIndex.source_module == source_module)
        if start_time:
            filters.append(HistoricalAlertIndex.triggered_at >= start_time)
        if end_time:
            filters.append(HistoricalAlertIndex.triggered_at <= end_time)

        if filters:
            stmt = stmt.where(and_(*filters))
            count_stmt = count_stmt.where(and_(*filters))

        # Sorting
        if sort_by == "oldest":
            stmt = stmt.order_by(HistoricalAlertIndex.triggered_at.asc())
        elif sort_by == "highest_severity":
            # Order EMERGENCY, CRITICAL, WARNING
            stmt = stmt.order_by(
                desc(HistoricalAlertIndex.severity_at_trigger == "EMERGENCY"),
                desc(HistoricalAlertIndex.severity_at_trigger == "CRITICAL"),
                desc(HistoricalAlertIndex.triggered_at),
            )
        elif sort_by == "highest_priority":
            stmt = stmt.order_by(desc(HistoricalAlertIndex.priority_score_at_trigger))
        else:  # newest
            stmt = stmt.order_by(HistoricalAlertIndex.triggered_at.desc())

        total_res = await self.session.execute(count_stmt)
        total_count = total_res.scalar_one()

        stmt = stmt.offset(offset).limit(limit)
        items_res = await self.session.execute(stmt)
        return list(items_res.scalars().all()), total_count

    async def get_historical_counts(self) -> Dict[str, Any]:
        stmt = select(HistoricalAlertIndex)
        res = await self.session.execute(stmt)
        items = list(res.scalars().all())

        total = len(items)
        by_sev: Dict[str, int] = {}
        by_cat: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        reopened = sum(1 for i in items if i.current_or_final_status_snapshot == "REOPENED")

        for i in items:
            by_sev[i.severity_at_trigger] = by_sev.get(i.severity_at_trigger, 0) + 1
            by_cat[i.alert_category] = by_cat.get(i.alert_category, 0) + 1
            by_status[i.current_or_final_status_snapshot] = by_status.get(i.current_or_final_status_snapshot, 0) + 1

        rec_stmt = select(func.count(AlertRecurrenceMember.id))
        rec_res = await self.session.execute(rec_stmt)
        recurring_count = rec_res.scalar_one()

        return {
            "total_alerts": total,
            "by_severity": by_sev,
            "by_category": by_cat,
            "by_status": by_status,
            "recurring_count": recurring_count,
            "reopened_count": reopened,
        }

    # -------------------------------------------------------------
    # Timeline Event Indexing
    # -------------------------------------------------------------
    async def index_historical_event(
        self,
        source_alert_id: str,
        source_event_id: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        source_module: str,
        occurred_at: datetime,
        recorded_at: datetime,
        event_sequence: int,
        event_summary: str,
        event_details: Dict[str, Any],
        source_reference: Optional[str] = None,
    ) -> HistoricalAlertEventIndex:
        # Check idempotency
        stmt = select(HistoricalAlertEventIndex).where(
            and_(
                HistoricalAlertEventIndex.source_alert_id == source_alert_id,
                HistoricalAlertEventIndex.source_event_id == source_event_id,
            )
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        ev = HistoricalAlertEventIndex(
            id=str(uuid.uuid4()),
            source_alert_id=source_alert_id,
            source_event_id=source_event_id,
            event_type=event_type.upper(),
            actor_type=actor_type.upper(),
            actor_id=actor_id,
            source_module=source_module,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            event_sequence=event_sequence,
            event_summary=event_summary,
            event_details=event_details,
            source_reference=source_reference,
        )
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def get_alert_timeline(self, source_alert_id: str) -> List[HistoricalAlertEventIndex]:
        stmt = (
            select(HistoricalAlertEventIndex)
            .where(HistoricalAlertEventIndex.source_alert_id == source_alert_id)
            .order_by(HistoricalAlertEventIndex.occurred_at.asc(), HistoricalAlertEventIndex.event_sequence.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------
    # Recurrence Groups & Memberships
    # -------------------------------------------------------------
    async def get_recurrence_group_by_key(self, grouping_key: str) -> Optional[AlertRecurrenceGroup]:
        stmt = (
            select(AlertRecurrenceGroup)
            .where(AlertRecurrenceGroup.grouping_key == grouping_key)
            .options(selectinload(AlertRecurrenceGroup.members))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_to_recurrence_group(
        self,
        source_rule_id: str,
        alert_category: str,
        portfolio_id: Optional[str],
        instrument_id: Optional[str],
        source_alert_id: str,
        occurrence_timestamp: datetime,
    ) -> AlertRecurrenceGroup:
        grouping_key = generate_recurrence_grouping_key(
            source_rule_id, alert_category, portfolio_id, instrument_id
        )
        group = await self.get_recurrence_group_by_key(grouping_key)

        if not group:
            group = AlertRecurrenceGroup(
                id=str(uuid.uuid4()),
                grouping_key=grouping_key,
                source_rule_id=source_rule_id,
                alert_category=alert_category.upper(),
                portfolio_id=portfolio_id,
                instrument_id=instrument_id,
                first_occurrence_at=occurrence_timestamp,
                last_occurrence_at=occurrence_timestamp,
                occurrence_count=1,
                average_interarrival_seconds=None,
            )
            self.session.add(group)
            await self.session.flush()

            member = AlertRecurrenceMember(
                id=str(uuid.uuid4()),
                recurrence_group_id=group.id,
                source_alert_id=source_alert_id,
                occurrence_timestamp=occurrence_timestamp,
                membership_reason="INITIAL_OCCURRENCE",
            )
            self.session.add(member)
        else:
            # Check if alert already in group
            stmt = select(AlertRecurrenceMember).where(
                and_(
                    AlertRecurrenceMember.recurrence_group_id == group.id,
                    AlertRecurrenceMember.source_alert_id == source_alert_id,
                )
            )
            res = await self.session.execute(stmt)
            if not res.scalar_one_or_none():
                member = AlertRecurrenceMember(
                    id=str(uuid.uuid4()),
                    recurrence_group_id=group.id,
                    source_alert_id=source_alert_id,
                    occurrence_timestamp=occurrence_timestamp,
                    membership_reason="REPEATED_OCCURRENCE",
                )
                self.session.add(member)
                group.occurrence_count += 1
                if occurrence_timestamp > group.last_occurrence_at:
                    group.last_occurrence_at = occurrence_timestamp
                if occurrence_timestamp < group.first_occurrence_at:
                    group.first_occurrence_at = occurrence_timestamp

                # Recalculate average interarrival
                all_stmt = select(AlertRecurrenceMember.occurrence_timestamp).where(
                    AlertRecurrenceMember.recurrence_group_id == group.id
                )
                all_res = await self.session.execute(all_stmt)
                ts_list = list(all_res.scalars().all()) + [occurrence_timestamp]
                _, avg_sec = calculate_interarrival_times(ts_list)
                group.average_interarrival_seconds = Decimal(str(avg_sec)) if avg_sec > 0 else None
                group.updated_at = datetime.utcnow()

        await self.session.flush()
        return group

    async def list_recurrence_groups(
        self,
        min_occurrences: int = 2,
        limit: int = 50,
    ) -> List[AlertRecurrenceGroup]:
        stmt = (
            select(AlertRecurrenceGroup)
            .where(AlertRecurrenceGroup.occurrence_count >= min_occurrences)
            .order_by(desc(AlertRecurrenceGroup.occurrence_count))
            .options(selectinload(AlertRecurrenceGroup.members))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------
    # Rule Analytics
    # -------------------------------------------------------------
    async def record_rule_analytics(
        self,
        source_rule_id: str,
        rule_name: Optional[str],
        rule_version: int,
        observation_start: datetime,
        observation_end: datetime,
        trigger_count: int,
        recurrence_count: int,
        affected_portfolio_count: int,
        affected_instrument_count: int,
        warning_count: int,
        critical_count: int,
        emergency_count: int,
        interarrival_timestamps: List[datetime],
    ) -> AlertRuleAnalytics:
        obs_days = max(1.0, (observation_end - observation_start).total_seconds() / 86400.0)
        freq = calculate_alert_frequency(trigger_count, obs_days)
        _, avg_sec = calculate_interarrival_times(interarrival_timestamps)

        rec_intensity = (recurrence_count / trigger_count) if trigger_count > 0 else 0.0
        # Calculate short interval duplicate rate (<= 15 min / 900s)
        short_intervals = sum(1 for i in range(1, len(interarrival_timestamps)) if (interarrival_timestamps[i] - interarrival_timestamps[i-1]).total_seconds() <= 900)
        short_rate = (short_intervals / max(1, trigger_count - 1)) if trigger_count > 1 else 0.0
        low_val_rate = (warning_count / trigger_count) if trigger_count > 0 else 0.0

        noise_calc = calculate_rule_noise_score(
            trigger_frequency_per_day=freq,
            recurrence_intensity=rec_intensity,
            short_interval_duplicate_rate=short_rate,
            low_severity_rapid_recovery_rate=low_val_rate,
        )

        analytic = AlertRuleAnalytics(
            id=str(uuid.uuid4()),
            source_rule_id=source_rule_id,
            rule_name=rule_name,
            rule_version=rule_version,
            observation_start=observation_start,
            observation_end=observation_end,
            observation_days=Decimal(str(round(obs_days, 2))),
            trigger_count=trigger_count,
            recurrence_count=recurrence_count,
            affected_portfolio_count=affected_portfolio_count,
            affected_instrument_count=affected_instrument_count,
            warning_count=warning_count,
            critical_count=critical_count,
            emergency_count=emergency_count,
            trigger_frequency_per_day=Decimal(str(round(freq, 4))),
            average_interarrival_seconds=Decimal(str(avg_sec)) if avg_sec > 0 else None,
            noise_score=Decimal(str(noise_calc["noise_score"])),
            is_noisy=noise_calc["is_noisy"],
            score_components_json=noise_calc["components"],
            score_configuration_version=noise_calc["version"],
        )
        self.session.add(analytic)
        await self.session.flush()
        return analytic

    async def list_rule_analytics(self, limit: int = 50) -> List[AlertRuleAnalytics]:
        stmt = select(AlertRuleAnalytics).order_by(desc(AlertRuleAnalytics.noise_score)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------
    # Export Jobs & Audit
    # -------------------------------------------------------------
    async def create_export_job(
        self,
        requested_by: str,
        export_type: str,
        export_format: str,
        requested_filters_json: Dict[str, Any],
    ) -> AlertExportJob:
        job = AlertExportJob(
            id=str(uuid.uuid4()),
            requested_by=requested_by,
            export_type=export_type.upper(),
            export_format=export_format.upper(),
            requested_filters_json=requested_filters_json,
            export_status="REQUESTED",
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_export_job(self, export_id: str) -> Optional[AlertExportJob]:
        stmt = (
            select(AlertExportJob)
            .where(AlertExportJob.id == export_id)
            .options(selectinload(AlertExportJob.downloads))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_export_jobs(self, limit: int = 50) -> List[AlertExportJob]:
        stmt = select(AlertExportJob).order_by(desc(AlertExportJob.requested_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def record_export_download(
        self,
        export_job_id: str,
        downloaded_by: str,
        download_result: str = "SUCCESS",
    ) -> AlertExportDownloadHistory:
        dl = AlertExportDownloadHistory(
            id=str(uuid.uuid4()),
            export_job_id=export_job_id,
            downloaded_by=downloaded_by,
            download_result=download_result,
        )
        self.session.add(dl)
        await self.session.flush()
        return dl

    # -------------------------------------------------------------
    # Integrity Issues
    # -------------------------------------------------------------
    async def record_integrity_issue(
        self,
        source_alert_id: str,
        issue_type: str,
        issue_description: str,
        severity: str = "WARNING",
        source_event_id: Optional[str] = None,
    ) -> AlertHistoryIntegrityIssue:
        issue = AlertHistoryIntegrityIssue(
            id=str(uuid.uuid4()),
            source_alert_id=source_alert_id,
            source_event_id=source_event_id,
            issue_type=issue_type.upper(),
            issue_description=issue_description,
            severity=severity.upper(),
        )
        self.session.add(issue)
        await self.session.flush()
        return issue

    async def list_integrity_issues(self, limit: int = 50) -> List[AlertHistoryIntegrityIssue]:
        stmt = select(AlertHistoryIntegrityIssue).order_by(desc(AlertHistoryIntegrityIssue.detected_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_integrity_overview(self) -> Dict[str, Any]:
        alert_cnt_res = await self.session.execute(select(func.count(HistoricalAlertIndex.id)))
        event_cnt_res = await self.session.execute(select(func.count(HistoricalAlertEventIndex.id)))
        issues_res = await self.session.execute(select(AlertHistoryIntegrityIssue))
        all_issues = list(issues_res.scalars().all())

        by_type: Dict[str, int] = {}
        open_cnt = 0
        for i in all_issues:
            by_type[i.issue_type] = by_type.get(i.issue_type, 0) + 1
            if i.investigation_status == "DETECTED":
                open_cnt += 1

        return {
            "total_indexed_alerts": alert_cnt_res.scalar_one(),
            "total_indexed_events": event_cnt_res.scalar_one(),
            "total_integrity_issues": len(all_issues),
            "open_integrity_issues": open_cnt,
            "issues_by_type": by_type,
        }

