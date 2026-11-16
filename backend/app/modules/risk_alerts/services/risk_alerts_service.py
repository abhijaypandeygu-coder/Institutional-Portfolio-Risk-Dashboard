"""
Service layer for M12 Risk Alerts & Notification Engine.
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_alerts.calculations.risk_alerts_math import (
    to_decimal,
    calculate_threshold_proximity,
    calculate_relative_var_pct,
    calculate_volatility_change,
    calculate_drawdown_magnitude,
    evaluate_threshold_state,
    build_deduplication_key,
)
from backend.app.modules.risk_alerts.models.risk_alerts_models import (
    AlertRule,
    AlertRuleVersion,
    AlertThresholdDefinition,
    AlertThresholdState,
    AlertThresholdTransition,
    AlertEvent,
    AlertEvidence,
    AlertLifecycleEvent,
    NotificationPreference,
    NotificationMessage,
    NotificationDeliveryAttempt,
    AlertAuditLog,
)
from backend.app.modules.risk_alerts.repositories.risk_alerts_repository import RiskAlertsRepository
from backend.app.modules.risk_alerts.schemas.risk_alerts_schemas import (
    AlertRuleCreateInput,
    ThresholdMetricEvaluateInput,
    EventAlertCreateInput,
    AlertAcknowledgeInput,
    AlertAssignInput,
    AlertResolveInput,
    AlertReopenInput,
    NotificationPreferenceUpdateInput,
    AlertRuleResponse,
    AlertEventResponse,
    AlertEvidenceResponse,
    ThresholdEvaluationResultResponse,
    AlertDashboardSummary,
)


class RiskAlertsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RiskAlertsRepository(db)

    async def create_alert_rule(self, payload: AlertRuleCreateInput) -> AlertRule:
        now = datetime.utcnow()
        existing = await self.repo.get_rule_by_code(payload.rule_code)
        if existing:
            raise HTTPException(status_code=400, detail=f"Rule code {payload.rule_code} already exists")

        rule_id = f"RULE_{uuid.uuid4().hex[:10]}"
        rule = AlertRule(
            id=rule_id,
            rule_code=payload.rule_code,
            name=payload.name,
            description=payload.description,
            metric_category=payload.metric_category.upper(),
            metric_identifier=payload.metric_identifier,
            scope_type=payload.scope_type.upper(),
            scope_id=payload.scope_id,
            priority=payload.priority.upper(),
            status="ACTIVE",
            current_version=1,
            created_by=payload.created_by,
            created_at=now,
            updated_at=now,
        )
        await self.repo.save_rule(rule)

        version_id = f"RVER_{uuid.uuid4().hex[:10]}"
        ver = AlertRuleVersion(
            id=version_id,
            rule_id=rule.id,
            version_number=1,
            configuration_json={},
            created_by=payload.created_by,
            created_at=now,
        )
        self.db.add(ver)
        await self.db.flush()

        th_def = AlertThresholdDefinition(
            id=f"TH_{uuid.uuid4().hex[:10]}",
            rule_version_id=ver.id,
            comparison_operator=payload.threshold.comparison_operator,
            warning_threshold=payload.threshold.warning_threshold,
            critical_threshold=payload.threshold.critical_threshold,
            recovery_threshold=payload.threshold.recovery_threshold,
            metric_unit=payload.threshold.metric_unit,
            currency=payload.threshold.currency,
            created_at=now,
        )
        self.db.add(th_def)
        await self.db.commit()
        return await self.repo.get_rule_by_id(rule.id)

    async def evaluate_threshold_metric(self, payload: ThresholdMetricEvaluateInput) -> ThresholdEvaluationResultResponse:
        now = datetime.utcnow()
        # Find matching active rule
        rules = await self.repo.list_rules(payload.metric_category.upper())
        matching_rule = None
        for r in rules:
            if r.metric_identifier == payload.metric_identifier and r.status == "ACTIVE":
                matching_rule = r
                break

        if not matching_rule or not matching_rule.versions or not matching_rule.versions[0].thresholds:
            raise HTTPException(status_code=404, detail=f"No active threshold rule found for {payload.metric_identifier}")

        th_def = matching_rule.versions[0].thresholds[0]
        warn_th = th_def.warning_threshold
        crit_th = th_def.critical_threshold
        rec_th = th_def.recovery_threshold
        comp_op = th_def.comparison_operator
        m_unit = th_def.metric_unit
        m_curr = th_def.currency
        rule_name = matching_rule.name
        rule_cat = matching_rule.metric_category
        rule_id = matching_rule.id

        # Retrieve current state
        state_rec = await self.repo.get_threshold_state(rule_id, payload.portfolio_id)
        current_state = state_rec.current_state if state_rec else "NORMAL"

        # Check for stale data gate
        if payload.data_quality_status == "STALE":
            new_state = "STALE"
            state_changed = (new_state != current_state)
        elif payload.data_quality_status == "MISSING":
            new_state = "UNAVAILABLE"
            state_changed = (new_state != current_state)
        else:
            new_state, state_changed = evaluate_threshold_state(
                current_value=payload.current_value,
                warning_threshold=warn_th,
                critical_threshold=crit_th,
                recovery_threshold=rec_th,
                current_state=current_state,
                operator=comp_op,
            )

        # Update or create threshold state
        if not state_rec:
            state_rec = AlertThresholdState(
                id=f"STATE_{uuid.uuid4().hex[:10]}",
                rule_id=rule_id,
                portfolio_id=payload.portfolio_id,
                current_state=new_state,
                current_metric_value=payload.current_value,
                last_metric_timestamp=payload.source_timestamp or now,
                consecutive_breaches=1 if new_state in ["WARNING", "CRITICAL"] else 0,
                updated_at=now,
            )
            await self.repo.save_threshold_state(state_rec)
        else:
            state_rec.current_state = new_state
            state_rec.current_metric_value = payload.current_value
            state_rec.last_metric_timestamp = payload.source_timestamp or now
            if new_state in ["WARNING", "CRITICAL"]:
                state_rec.consecutive_breaches += 1
            else:
                state_rec.consecutive_breaches = 0
            state_rec.updated_at = now
            await self.repo.save_threshold_state(state_rec)

        # Log transition if state changed
        if state_changed:
            trans = AlertThresholdTransition(
                id=f"TRN_{uuid.uuid4().hex[:10]}",
                rule_id=rule_id,
                portfolio_id=payload.portfolio_id,
                previous_state=current_state,
                new_state=new_state,
                metric_value=payload.current_value,
                threshold_value=warn_th,
                transition_timestamp=now,
            )
            await self.repo.add_threshold_transition(trans)

        rule_triggered = new_state in ["WARNING", "CRITICAL"]
        created_or_updated_alert = None

        if rule_triggered:
            priority = "CRITICAL" if new_state == "CRITICAL" else "HIGH"
            dedup_key = build_deduplication_key(
                "THRESHOLD_ALERT", payload.portfolio_id, payload.metric_identifier, new_state
            )

            # Check deduplication
            active_alert = await self.repo.get_active_alert_by_dedup_key(dedup_key)
            if active_alert:
                active_alert.occurrence_count += 1
                active_alert.last_seen_at = now
                active_alert.priority = priority
                await self.repo.save_alert(active_alert)
                created_or_updated_alert = active_alert
            else:
                alert_id = f"ALT_{uuid.uuid4().hex[:10]}"
                title = f"{rule_name} [{new_state}] - Portfolio {payload.portfolio_id}"
                desc = (
                    f"Metric {payload.metric_identifier} reached {payload.current_value} "
                    f"violating {new_state} threshold {crit_th if new_state == 'CRITICAL' else warn_th} {m_unit}."
                )
                alert = AlertEvent(
                    id=alert_id,
                    alert_type="THRESHOLD_ALERT",
                    alert_category=rule_cat,
                    source_module=payload.source_module,
                    source_event_id=None,
                    source_entity_type="METRIC",
                    source_entity_id=payload.metric_identifier,
                    portfolio_id=payload.portfolio_id,
                    instrument_id=payload.instrument_id,
                    rule_id=rule_id,
                    title=title,
                    description=desc,
                    priority=priority,
                    status="OPEN",
                    deduplication_key=dedup_key,
                    first_seen_at=now,
                    last_seen_at=now,
                    occurrence_count=1,
                    created_at=now,
                    updated_at=now,
                )
                await self.repo.save_alert(alert)

                ev = AlertEvidence(
                    id=f"EVD_{uuid.uuid4().hex[:10]}",
                    alert_id=alert.id,
                    metric_value=payload.current_value,
                    threshold_value=crit_th if new_state == "CRITICAL" else warn_th,
                    metric_unit=m_unit,
                    currency=m_curr,
                    evidence_payload={"operator": comp_op, "state": new_state},
                    source_timestamp=payload.source_timestamp or now,
                    created_at=now,
                )
                await self.repo.add_evidence(ev)

                lc = AlertLifecycleEvent(
                    id=f"ALC_{uuid.uuid4().hex[:10]}",
                    alert_id=alert.id,
                    previous_status="NONE",
                    new_status="OPEN",
                    action_type="CREATED",
                    actor_id="THRESHOLD_ENGINE",
                    action_note=desc,
                    created_at=now,
                )
                await self.repo.add_lifecycle_event(lc)

                # Outbound Notification Task
                notif = NotificationMessage(
                    id=f"NMSG_{uuid.uuid4().hex[:10]}",
                    alert_id=alert.id,
                    recipient_user_id="default_risk_officer",
                    channel="IN_APP",
                    delivery_status="SENT",
                    title=title,
                    body=desc,
                    created_at=now,
                    sent_at=now,
                )
                await self.repo.add_notification(notif)
                created_or_updated_alert = alert

        await self.db.commit()

        prox_pct = calculate_threshold_proximity(payload.current_value, warn_th)
        alert_resp = None
        if created_or_updated_alert:
            fresh_alert = await self.repo.get_alert_by_id(created_or_updated_alert.id)
            if fresh_alert:
                alert_resp = self._serialize_alert(fresh_alert)

        return ThresholdEvaluationResultResponse(
            rule_triggered=rule_triggered,
            state_changed=state_changed,
            current_state=new_state,
            current_value=payload.current_value,
            warning_threshold=warn_th,
            critical_threshold=crit_th,
            proximity_pct=prox_pct,
            alert=alert_resp,
        )

    async def create_event_alert(self, payload: EventAlertCreateInput) -> AlertEventResponse:
        now = datetime.utcnow()
        dedup_key = build_deduplication_key(
            payload.alert_type, payload.portfolio_id, payload.alert_category, payload.source_event_id
        )

        active = await self.repo.get_active_alert_by_dedup_key(dedup_key)
        if active:
            active.occurrence_count += 1
            active.last_seen_at = now
            await self.repo.save_alert(active)
            await self.db.commit()
            fresh = await self.repo.get_alert_by_id(active.id)
            return self._serialize_alert(fresh)

        alert_id = f"ALT_{uuid.uuid4().hex[:10]}"
        alert = AlertEvent(
            id=alert_id,
            alert_type=payload.alert_type.upper(),
            alert_category=payload.alert_category.upper(),
            source_module=payload.source_module,
            source_event_id=payload.source_event_id,
            source_entity_type="CONTROL_EVENT",
            source_entity_id=payload.source_event_id,
            portfolio_id=payload.portfolio_id,
            instrument_id=payload.instrument_id,
            rule_id=None,
            title=payload.title,
            description=payload.description,
            priority=payload.priority.upper(),
            status="OPEN",
            deduplication_key=dedup_key,
            first_seen_at=now,
            last_seen_at=now,
            occurrence_count=1,
            created_at=now,
            updated_at=now,
        )
        await self.repo.save_alert(alert)

        ev = AlertEvidence(
            id=f"EVD_{uuid.uuid4().hex[:10]}",
            alert_id=alert.id,
            metric_value=Decimal("0.00"),
            threshold_value=Decimal("0.00"),
            metric_unit="EVENT",
            currency="USD",
            evidence_payload=payload.evidence_payload,
            source_timestamp=now,
            created_at=now,
        )
        await self.repo.add_evidence(ev)

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:10]}",
            alert_id=alert.id,
            previous_status="NONE",
            new_status="OPEN",
            action_type="CREATED",
            actor_id="EVENT_ALERT_ENGINE",
            action_note=payload.description,
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)

        notif = NotificationMessage(
            id=f"NMSG_{uuid.uuid4().hex[:10]}",
            alert_id=alert.id,
            recipient_user_id="default_risk_officer",
            channel="IN_APP",
            delivery_status="SENT",
            title=payload.title,
            body=payload.description,
            created_at=now,
            sent_at=now,
        )
        await self.repo.add_notification(notif)
        await self.db.commit()

        fresh = await self.repo.get_alert_by_id(alert.id)
        return self._serialize_alert(fresh)

    async def acknowledge_alert(self, alert_id: str, payload: AlertAcknowledgeInput) -> AlertEventResponse:
        alert = await self.repo.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        now = datetime.utcnow()
        prev = alert.status
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = now
        alert.acknowledged_by_user_id = payload.acknowledged_by_user_id
        alert.updated_at = now
        await self.repo.save_alert(alert)

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:10]}",
            alert_id=alert.id,
            previous_status=prev,
            new_status="ACKNOWLEDGED",
            action_type="ACKNOWLEDGED",
            actor_id=payload.acknowledged_by_user_id,
            action_note=payload.action_note or "Alert formally acknowledged",
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)
        await self.db.commit()

        fresh = await self.repo.get_alert_by_id(alert.id)
        return self._serialize_alert(fresh)

    async def assign_alert(self, alert_id: str, payload: AlertAssignInput) -> AlertEventResponse:
        alert = await self.repo.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        now = datetime.utcnow()
        prev = alert.status
        alert.status = "ASSIGNED"
        alert.assigned_user_id = payload.assigned_user_id
        alert.updated_at = now
        await self.repo.save_alert(alert)

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:10]}",
            alert_id=alert.id,
            previous_status=prev,
            new_status="ASSIGNED",
            action_type="ASSIGNED",
            actor_id=payload.assigned_by_user_id,
            action_note=payload.action_note or f"Assigned to {payload.assigned_user_id}",
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)
        await self.db.commit()

        fresh = await self.repo.get_alert_by_id(alert.id)
        return self._serialize_alert(fresh)

    async def resolve_alert(self, alert_id: str, payload: AlertResolveInput) -> AlertEventResponse:
        alert = await self.repo.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        now = datetime.utcnow()
        prev = alert.status
        alert.status = "RESOLVED"
        alert.resolved_at = now
        alert.resolved_by_user_id = payload.resolved_by_user_id
        alert.updated_at = now
        await self.repo.save_alert(alert)

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:10]}",
            alert_id=alert.id,
            previous_status=prev,
            new_status="RESOLVED",
            action_type="RESOLVED",
            actor_id=payload.resolved_by_user_id,
            action_note=f"Reason: {payload.resolution_reason}. Note: {payload.action_note or ''}",
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)
        await self.db.commit()

        fresh = await self.repo.get_alert_by_id(alert.id)
        return self._serialize_alert(fresh)

    async def reopen_alert(self, alert_id: str, payload: AlertReopenInput) -> AlertEventResponse:
        alert = await self.repo.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        now = datetime.utcnow()
        prev = alert.status
        alert.status = "REOPENED"
        alert.resolved_at = None
        alert.updated_at = now
        await self.repo.save_alert(alert)

        lc = AlertLifecycleEvent(
            id=f"ALC_{uuid.uuid4().hex[:10]}",
            alert_id=alert.id,
            previous_status=prev,
            new_status="REOPENED",
            action_type="REOPENED",
            actor_id=payload.reopened_by_user_id,
            action_note=payload.reopen_reason,
            created_at=now,
        )
        await self.repo.add_lifecycle_event(lc)
        await self.db.commit()

        fresh = await self.repo.get_alert_by_id(alert.id)
        return self._serialize_alert(fresh)

    async def get_dashboard_summary(self) -> AlertDashboardSummary:
        stats = await self.repo.get_dashboard_summary()
        return AlertDashboardSummary(
            total_active_alerts=stats["total_active_alerts"],
            open_alerts=stats["open_alerts"],
            acknowledged_alerts=stats["acknowledged_alerts"],
            resolved_alerts=stats["resolved_alerts"],
            priority_breakdown=stats["priority_breakdown"],
            category_breakdown=stats["category_breakdown"],
            unacknowledged_critical_count=stats["unacknowledged_critical_count"],
        )

    def _serialize_alert(self, alert: AlertEvent) -> AlertEventResponse:
        ev_list = [
            AlertEvidenceResponse(
                id=e.id,
                metric_value=e.metric_value,
                threshold_value=e.threshold_value,
                metric_unit=e.metric_unit,
                currency=e.currency,
                evidence_payload=e.evidence_payload,
                source_timestamp=e.source_timestamp,
                created_at=e.created_at,
            )
            for e in alert.evidence
        ]
        return AlertEventResponse(
            id=alert.id,
            alert_type=alert.alert_type,
            alert_category=alert.alert_category,
            source_module=alert.source_module,
            source_event_id=alert.source_event_id,
            portfolio_id=alert.portfolio_id,
            instrument_id=alert.instrument_id,
            rule_id=alert.rule_id,
            title=alert.title,
            description=alert.description,
            priority=alert.priority,
            status=alert.status,
            deduplication_key=alert.deduplication_key,
            occurrence_count=alert.occurrence_count,
            first_seen_at=alert.first_seen_at,
            last_seen_at=alert.last_seen_at,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by_user_id=alert.acknowledged_by_user_id,
            assigned_user_id=alert.assigned_user_id,
            resolved_at=alert.resolved_at,
            resolved_by_user_id=alert.resolved_by_user_id,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            evidence=ev_list,
        )
