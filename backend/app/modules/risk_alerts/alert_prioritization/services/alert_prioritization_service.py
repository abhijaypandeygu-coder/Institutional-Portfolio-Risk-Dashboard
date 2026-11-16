"""
Core Prioritization Engine and Services for M12.05 — Alert Prioritization.

Features implemented:
- M12.05.01: Alert Severity Classification (WARNING, CRITICAL, EMERGENCY with M11 authoritative precedence)
- M12.05.02: Severity Policy Configuration
- M12.05.03: Urgency Evaluation (U1_IMMEDIATE, U2_HIGH, U3_NORMAL, U4_LOW, deterioration velocity)
- M12.05.04: Time-to-Action Assessment (Action windows, deadline detection)
- M12.05.05: Portfolio Impact Assessment (NAV %, financial scaling, missing-data confidence)
- M12.05.06: Risk Impact Assessment (Limit utilization, VaR, stress loss)
- M12.05.07: Instrument and Entity Impact Assessment (Breadth score)
- M12.05.08: Composite Priority Scoring (S, U, I, P weighted scoring)
- M12.05.09: Priority Band Assignment (P1 to P5 with Emergency safeguards)
- M12.05.10: Dynamic Priority Recalculation (Priority transitions & history logging)
- M12.05.11: Alert Deduplication (Canonical SHA256 dedupe keys, window evaluation)
- M12.05.12: Alert Correlation and Grouping (Parent clusters, group priority max)
- M12.05.13: Escalation-Aware Grouping (Preserves worsening severity and priority jumps)
- M12.05.14: Alert Occurrence Tracking (Audit occurrence log with idempotency)
- M12.05.15: Priority Explanation and Evidence (Human and audit-readable explanation)
- M12.05.16: Prioritization Dashboard Services (Queues, distribution, detail views)
- M12.05.17: Prioritization Analytics and Monitoring (Latency, distributions, dedupe rate)
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_alerts.alert_prioritization.calculations.alert_prioritization_math import (
    normalize_score,
    calculate_deterioration_velocity,
    calculate_time_to_action,
    calculate_financial_impact_score,
    calculate_risk_impact_score,
    calculate_breadth_impact_score,
    calculate_composite_impact,
    calculate_persistence_score,
    calculate_priority_score,
    assign_priority_band,
    build_canonical_dedupe_key,
    to_decimal,
)
from backend.app.modules.risk_alerts.alert_prioritization.models.alert_prioritization_models import (
    AlertPriorityPolicy,
    AlertGroup,
    AlertGroupMember,
    AlertPriorityEvaluation,
    AlertPriorityHistory,
    AlertDeduplicationRecord,
    AlertOccurrence,
    AlertEscalationEvent,
)
from backend.app.modules.risk_alerts.alert_prioritization.repositories.alert_prioritization_repository import (
    AlertPrioritizationRepository,
)
from backend.app.modules.risk_alerts.alert_prioritization.schemas.alert_prioritization_schemas import (
    AlertPrioritizationRequest,
    AlertPriorityPolicyCreate,
)


class AlertPrioritizationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AlertPrioritizationRepository(session)

    # ------------------ Policy Management ------------------
    async def create_policy(self, req: AlertPriorityPolicyCreate) -> AlertPriorityPolicy:
        policy = AlertPriorityPolicy(
            id=f"POL-{uuid.uuid4().hex[:12].upper()}",
            policy_name=req.policy_name,
            policy_type=req.policy_type,
            alert_category=req.alert_category,
            event_type=req.event_type,
            source_module=req.source_module,
            severity_rules=req.severity_rules,
            urgency_rules=req.urgency_rules,
            impact_weights=req.impact_weights,
            priority_weights=req.priority_weights,
            priority_band_config=req.priority_band_config,
            priority_floor_config=req.priority_floor_config,
            effective_from=req.effective_from or datetime.utcnow(),
            effective_to=req.effective_to,
            policy_version=req.policy_version,
            enabled=req.enabled,
            created_by=req.created_by,
        )
        return await self.repo.create_policy(policy)

    async def list_policies(self, enabled_only: bool = False) -> List[AlertPriorityPolicy]:
        return await self.repo.list_policies(enabled_only=enabled_only)

    # ------------------ Core Prioritization Pipeline ------------------
    async def prioritize_alert(self, req: AlertPrioritizationRequest) -> AlertPriorityEvaluation:
        """
        Executes the end-to-end prioritization pipeline:
        1. Idempotency validation
        2. Policy retrieval & Authoritative precedence
        3. Severity & Urgency scoring
        4. Multi-dimension Impact calculation (F, R, B)
        5. Composite priority scoring & band assignment (Safeguard: Emergency floor)
        6. Canonical deduplication evaluation
        7. Correlation, grouping & Escalation detection
        8. Occurrence & Evaluation persistence
        """
        now = datetime.utcnow()

        # 1. Idempotency check if idempotency_key is supplied
        if req.idempotency_key:
            existing_occ = await self.repo.get_occurrence_by_idempotency_key(req.idempotency_key)
            if existing_occ:
                if existing_occ.evaluation_id:
                    eval_rec = await self.repo.get_evaluation_by_id(existing_occ.evaluation_id)
                    if eval_rec:
                        return eval_rec
                latest_eval = await self.repo.get_latest_evaluation_by_alert_id(req.alert_id)
                if latest_eval:
                    return latest_eval

        # 2. Retrieve applicable governed policy
        policy = await self.repo.get_applicable_policy(
            category=req.category,
            event_type=req.event_type,
            source_module=req.source_module,
        )
        policy_ver = policy.policy_version if policy else 1
        priority_weights = policy.priority_weights if policy else {"S": 0.35, "U": 0.30, "I": 0.25, "P": 0.10}
        impact_weights = policy.impact_weights if policy else {"F": 0.45, "R": 0.40, "B": 0.15}
        floor_config = policy.priority_floor_config if policy else {"EMERGENCY": 90.0, "CRITICAL": 50.0}

        # 3. Determine Severity (Authoritative M11 precedence)
        severity = "WARNING"
        severity_score = 30.0
        is_auth = False
        sev_source = "M12.05_POLICY"

        if req.is_authoritative_severity and req.source_severity:
            severity = req.source_severity.upper()
            is_auth = True
            sev_source = f"{req.source_module}_AUTHORITATIVE"
            if severity == "EMERGENCY":
                severity_score = 100.0
            elif severity == "CRITICAL":
                severity_score = 70.0
            else:
                severity_score = 30.0
        else:
            # Policy-based severity determination
            if req.observed_value is not None and policy and policy.severity_rules:
                rules = policy.severity_rules.get("rules", [])
                for r in rules:
                    op = r.get("operator", "GTE")
                    th = to_decimal(r.get("threshold"))
                    if th is not None:
                        if op == "GTE" and req.observed_value >= th:
                            severity = r.get("severity", severity)
                        elif op == "LTE" and req.observed_value <= th:
                            severity = r.get("severity", severity)
            elif req.source_severity:
                severity = req.source_severity.upper()

            if severity == "EMERGENCY":
                severity_score = 100.0
            elif severity == "CRITICAL":
                severity_score = 70.0
            else:
                severity_score = 30.0

        # 4. Urgency evaluation & Deterioration Velocity
        velocity = 0.0
        if req.observed_value is not None and req.previous_value is not None:
            velocity = calculate_deterioration_velocity(
                req.observed_value, req.previous_value, req.dt_seconds or 60.0
            )

        urgency = "U3_NORMAL"
        urgency_score = 45.0
        if severity == "EMERGENCY" or velocity >= 5.0 or (req.deadline_remaining_seconds and req.deadline_remaining_seconds <= 300):
            urgency = "U1_IMMEDIATE"
            urgency_score = 100.0
        elif severity == "CRITICAL" or velocity >= 1.0 or (req.deadline_remaining_seconds and req.deadline_remaining_seconds <= 1800):
            urgency = "U2_HIGH"
            urgency_score = 75.0
        elif velocity < 0.2:
            urgency = "U4_LOW"
            urgency_score = 20.0

        tta_label, tta_mins = calculate_time_to_action(
            urgency, severity, velocity, req.deadline_remaining_seconds
        )

        # 5. Financial, Risk, and Breadth Impact
        f_score, pct_nav, f_conf = calculate_financial_impact_score(req.affected_value, req.nav)
        r_score, r_conf = calculate_risk_impact_score(
            req.limit_utilization_pct, req.var_increase_pct, req.stress_loss_pct_nav
        )
        b_score = calculate_breadth_impact_score(
            affected_instruments=req.affected_instruments,
            total_instruments=req.total_instruments,
            affected_portfolios=req.affected_portfolios,
            affected_sectors=req.affected_sectors,
        )
        composite_impact = calculate_composite_impact(f_score, r_score, b_score, impact_weights)

        # Confidence synthesis
        if f_conf == "UNKNOWN" and r_conf == "UNKNOWN":
            overall_confidence = "LOW"
            quality_status = "MISSING_FINANCIAL_AND_RISK_DATA"
        elif f_conf == "UNKNOWN" or r_conf == "UNKNOWN":
            overall_confidence = "MEDIUM"
            quality_status = "PARTIAL_VALUATION_OR_RISK"
        else:
            overall_confidence = "HIGH"
            quality_status = "VALID"

        # 6. Persistence & Occurrence history lookup
        prior_eval = await self.repo.get_latest_evaluation_by_alert_id(req.alert_id)
        prior_occurrences_count = await self.repo.count_occurrences(req.alert_id)
        current_occurrences_count = prior_occurrences_count + 1

        p_score = calculate_persistence_score(
            current_occurrences_count,
            prior_eval.evaluated_at if prior_eval else now,
            now,
        )

        # 7. Composite Priority Score & Priority Floor Safeguard
        priority_floor = 0.0
        floor_applied = False
        floor_reason = None

        if severity == "EMERGENCY":
            priority_floor = float(floor_config.get("EMERGENCY", 90.0))
        elif severity == "CRITICAL":
            priority_floor = float(floor_config.get("CRITICAL", 50.0))

        raw_priority_score = calculate_priority_score(
            severity_score, urgency_score, composite_impact, p_score, priority_weights, priority_floor=0.0
        )
        
        final_priority_score = max(raw_priority_score, priority_floor)
        if final_priority_score > raw_priority_score:
            floor_applied = True
            floor_reason = f"Floor enforced for {severity} severity"

        priority_band = assign_priority_band(final_priority_score, is_emergency=(severity == "EMERGENCY"))

        # 8. Deduplication key & Alert Grouping / Correlation
        dedupe_key = build_canonical_dedupe_key(
            source_module=req.source_module,
            category=req.category,
            event_type=req.event_type,
            portfolio_scope=req.portfolio_id,
            entity_scope=req.entity_scope or req.instrument_id or "PORTFOLIO",
            condition_id=req.condition_id or req.alert_id,
        )

        group = await self.repo.get_group_by_key(dedupe_key)
        is_new_group = False
        if not group:
            is_new_group = True
            group = AlertGroup(
                id=f"GRP-{uuid.uuid4().hex[:12].upper()}",
                group_key=dedupe_key,
                group_type="CORRELATED_CONDITION",
                primary_alert_id=req.alert_id,
                current_priority_score=final_priority_score,
                current_priority_band=priority_band,
                maximum_severity=severity,
                maximum_priority_score=final_priority_score,
                active_child_count=1,
                occurrence_count=1,
                group_status="ACTIVE",
            )
            await self.repo.create_group(group)
            
            # Add initial membership
            member = AlertGroupMember(
                id=f"MEM-{uuid.uuid4().hex[:12].upper()}",
                group_id=group.id,
                alert_id=req.alert_id,
                relationship_type="PRIMARY_CONDITION",
                correlation_method="EXACT_KEY",
                correlation_confidence=1.0,
            )
            await self.repo.add_group_member(member)
        else:
            # Update existing group stats
            group.occurrence_count += 1
            group.current_priority_score = max(group.current_priority_score, final_priority_score)
            group.maximum_priority_score = max(group.maximum_priority_score, final_priority_score)
            if severity == "EMERGENCY" or (severity == "CRITICAL" and group.maximum_severity != "EMERGENCY"):
                group.maximum_severity = severity
            group.current_priority_band = assign_priority_band(group.current_priority_score, is_emergency=(group.maximum_severity == "EMERGENCY"))

        # 9. Deduplication Audit Record
        dedupe_result = "NEW_ALERT" if is_new_group else "DUPLICATE_OCCURRENCE"
        
        # Check for Escalation (WARNING -> CRITICAL/EMERGENCY, or score jump > 15)
        escalation_detected = False
        escalation_reason = ""
        if prior_eval:
            sev_levels = {"WARNING": 1, "CRITICAL": 2, "EMERGENCY": 3}
            if sev_levels.get(severity, 1) > sev_levels.get(prior_eval.severity, 1):
                escalation_detected = True
                escalation_reason = f"Severity escalated from {prior_eval.severity} to {severity}"
            elif final_priority_score - prior_eval.priority_score >= 15.0:
                escalation_detected = True
                escalation_reason = f"Priority score jumped by {round(final_priority_score - prior_eval.priority_score, 2)} points"

            if escalation_detected:
                dedupe_result = "ESCALATED_OCCURRENCE"
                esc_event = AlertEscalationEvent(
                    id=f"ESC-{uuid.uuid4().hex[:12].upper()}",
                    alert_id=req.alert_id,
                    group_id=group.id,
                    previous_severity=prior_eval.severity,
                    new_severity=severity,
                    previous_priority_score=prior_eval.priority_score,
                    new_priority_score=final_priority_score,
                    previous_urgency=prior_eval.urgency,
                    new_urgency=urgency,
                    escalation_reason=escalation_reason,
                    source_event_id=req.source_event_id,
                    policy_version=policy_ver,
                )
                await self.repo.save_escalation(esc_event)

                # Priority History
                hist = AlertPriorityHistory(
                    id=f"HIS-{uuid.uuid4().hex[:12].upper()}",
                    alert_id=req.alert_id,
                    previous_priority_score=prior_eval.priority_score,
                    new_priority_score=final_priority_score,
                    previous_priority_band=prior_eval.priority_band,
                    new_priority_band=priority_band,
                    previous_severity=prior_eval.severity,
                    new_severity=severity,
                    previous_urgency=prior_eval.urgency,
                    new_urgency=urgency,
                    trigger_event_id=req.source_event_id,
                    change_reason=escalation_reason,
                    policy_version=policy_ver,
                )
                await self.repo.add_priority_history(hist)

        # Save Deduplication record
        dedupe_record = AlertDeduplicationRecord(
            id=f"DED-{uuid.uuid4().hex[:12].upper()}",
            incoming_event_id=req.source_event_id or req.alert_id,
            existing_alert_id=req.alert_id,
            group_id=group.id,
            deduplication_key=dedupe_key,
            deduplication_result=dedupe_result,
            matching_dimensions={
                "portfolio_id": req.portfolio_id,
                "category": req.category,
                "event_type": req.event_type,
            },
            confidence=1.0,
            policy_version=policy_ver,
        )
        await self.repo.save_deduplication_record(dedupe_record)

        # 10. Build Transparent Explanation & Save Evaluation
        eval_id = f"EVL-{uuid.uuid4().hex[:12].upper()}"
        explanation = (
            f"Alert evaluated as {priority_band} (Score: {final_priority_score:.1f}/100). "
            f"Severity: {severity} ({sev_source}). Urgency: {urgency} (TTA: {tta_label}). "
            f"Financial impact: {f_score:.1f}% ({pct_nav or 'N/A'}% NAV), Risk impact: {r_score:.1f}%, "
            f"Breadth: {b_score:.1f}%. Grouped under {group.id} with {group.occurrence_count} occurrences."
        )

        evaluation = AlertPriorityEvaluation(
            id=eval_id,
            alert_id=req.alert_id,
            group_id=group.id,
            severity=severity,
            severity_score=severity_score,
            is_authoritative_severity=is_auth,
            severity_source=sev_source,
            urgency=urgency,
            urgency_score=urgency_score,
            time_to_action_label=tta_label,
            recommended_action_window_minutes=tta_mins,
            affected_value=req.affected_value,
            affected_currency=req.currency,
            affected_value_pct_nav=pct_nav,
            financial_impact_score=f_score,
            risk_impact_score=r_score,
            breadth_impact_score=b_score,
            composite_impact_score=composite_impact,
            persistence_score=p_score,
            priority_score=final_priority_score,
            priority_band=priority_band,
            priority_floor_applied=floor_applied,
            priority_floor_reason=floor_reason,
            confidence=overall_confidence,
            quality_status=quality_status,
            policy_version=policy_ver,
            scoring_model_version="1.0.0",
            explanation_summary=explanation,
            evidence_json={
                "weights": priority_weights,
                "velocity": velocity,
                "occurrences": current_occurrences_count,
                "escalated": escalation_detected,
                "group_id": group.id,
            },
            evaluated_at=now,
        )

        # 11. Record Occurrence with evaluation_id link
        occ = AlertOccurrence(
            id=f"OCC-{uuid.uuid4().hex[:12].upper()}",
            alert_id=req.alert_id,
            evaluation_id=eval_id,
            group_id=group.id,
            source_event_id=req.source_event_id,
            idempotency_key=req.idempotency_key,
            observed_value=req.observed_value,
            severity=severity,
            urgency=urgency,
            priority_score=final_priority_score,
            event_timestamp=req.event_timestamp or now,
            received_at=now,
            evidence_reference={
                "affected_value": str(req.affected_value) if req.affected_value else None,
                "nav": str(req.nav) if req.nav else None,
                "velocity": velocity,
            },
        )
        await self.repo.save_occurrence(occ)

        return await self.repo.save_evaluation(evaluation)

    # ------------------ Query Services ------------------
    async def get_evaluation_by_alert_id(self, alert_id: str) -> Optional[AlertPriorityEvaluation]:
        return await self.repo.get_latest_evaluation_by_alert_id(alert_id)

    async def list_evaluations(
        self,
        priority_band: Optional[str] = None,
        severity: Optional[str] = None,
        urgency: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AlertPriorityEvaluation]:
        return await self.repo.list_evaluations(priority_band, severity, urgency, limit, offset)

    async def get_alert_history(self, alert_id: str) -> List[AlertPriorityHistory]:
        return await self.repo.list_priority_history(alert_id)

    async def get_alert_occurrences(self, alert_id: str, limit: int = 50) -> List[AlertOccurrence]:
        return await self.repo.list_occurrences_for_alert(alert_id, limit)

    async def get_group_details(self, group_id: str) -> Optional[AlertGroup]:
        return await self.repo.get_group_by_id(group_id)

    async def list_groups(self, status: Optional[str] = None, limit: int = 50) -> List[AlertGroup]:
        return await self.repo.list_groups(status, limit)

    async def get_analytics_summary(self) -> Dict[str, Any]:
        return await self.repo.get_prioritization_summary_stats()

