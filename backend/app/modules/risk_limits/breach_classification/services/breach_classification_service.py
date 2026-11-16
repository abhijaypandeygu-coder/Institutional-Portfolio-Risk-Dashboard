"""
Core business logic and severity evaluation engine for M11.07 — Breach Classification.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from backend.app.modules.risk_limits.breach_classification.models.breach_classification_models import (
    ClassificationPolicy,
    ClassificationPolicyVersion,
    ClassificationRule,
    BreachClassification,
    ClassificationEvidence,
    ClassificationHistory,
    ClassificationEvent,
    ClassificationAuditEvent,
)
from backend.app.modules.risk_limits.breach_classification.repositories.breach_classification_repository import (
    BreachClassificationRepository,
)
from backend.app.modules.risk_limits.breach_classification.schemas.breach_classification_schemas import (
    ClassificationPolicyCreate,
    ClassificationPolicyVersionCreate,
    PolicyApprovalRequest,
    ClassifyBreachRequest,
    ReclassificationRequest,
)
from backend.app.modules.risk_limits.breach_classification.calculations.breach_classification_math import (
    to_decimal,
    calculate_portfolio_materiality,
    resolve_higher_severity,
    evaluate_severity_rule,
    SEVERITY_WARNING,
    SEVERITY_CRITICAL,
    SEVERITY_EMERGENCY,
    STATUS_CLASSIFIED,
    STATUS_UNCLASSIFIED,
    SEVERITY_RANKS,
)
from backend.app.modules.risk_limits.breach_detection.models.breach_detection_models import BreachEvent


class BreachClassificationService:
    def __init__(self, repo: BreachClassificationRepository):
        self.repo = repo

    # ---------------------------------------------------------
    # Policy Lifecycle & Maker-Checker
    # ---------------------------------------------------------

    async def create_policy(self, data: ClassificationPolicyCreate) -> ClassificationPolicy:
        existing = await self.repo.get_policy_by_code(data.policy_code)
        if existing:
            raise ValueError(f"Classification policy '{data.policy_code}' already exists.")

        policy_id = f"clp_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        policy = ClassificationPolicy(
            id=policy_id,
            policy_code=data.policy_code,
            name=data.name,
            description=data.description,
            scope_type=data.scope_type,
            scope_id=data.scope_id,
            risk_category=data.risk_category,
            priority=data.priority,
            lifecycle_status="DRAFT",
            current_version=1,
            created_by=data.created_by,
            created_at=now,
            updated_at=now,
        )

        created_policy = await self.repo.create_policy(policy)

        # Create initial version if supplied
        if data.initial_version:
            await self.create_policy_version(policy_id, data.initial_version, author=data.created_by)

        await self.repo.create_audit_event(
            ClassificationAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="POLICY",
                entity_id=policy_id,
                event_type="POLICY_CREATED",
                new_state="DRAFT",
                actor_id=data.created_by,
                reason="Policy initialization",
                correlation_id=uuid.uuid4().hex,
                timestamp=now,
            )
        )

        return await self.repo.get_policy_by_id(policy_id)

    async def create_policy_version(
        self,
        policy_id: str,
        data: ClassificationPolicyVersionCreate,
        author: str = "risk_analyst"
    ) -> ClassificationPolicyVersion:
        policy = await self.repo.get_policy_by_id(policy_id)
        if not policy:
            raise ValueError(f"Policy '{policy_id}' not found.")

        next_ver = len(policy.versions) + 1
        ver_id = f"clv_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        version = ClassificationPolicyVersion(
            id=ver_id,
            policy_id=policy_id,
            version_number=next_ver,
            configuration_json=data.configuration_json,
            severity_mapping=data.severity_mapping,
            precedence_configuration=data.precedence_configuration,
            materiality_configuration=data.materiality_configuration,
            persistence_configuration=data.persistence_configuration,
            emergency_rules=data.emergency_rules,
            approval_status="DRAFT",
            created_by=author,
            created_at=now,
        )

        for r in data.rules:
            rule_id = f"clr_{uuid.uuid4().hex[:12]}"
            version.rules.append(
                ClassificationRule(
                    id=rule_id,
                    policy_version_id=ver_id,
                    rule_code=r.rule_code,
                    rule_name=r.rule_name,
                    target_metric_code=r.target_metric_code,
                    target_limit_type=r.target_limit_type,
                    condition_operator=r.condition_operator,
                    threshold_value=r.threshold_value,
                    upper_threshold_value=r.upper_threshold_value,
                    unit=r.unit,
                    target_severity=r.target_severity.upper(),
                    priority=r.priority,
                    persistence_requirement=r.persistence_requirement,
                    immediate_classification=r.immediate_classification,
                    materiality_requirement=r.materiality_requirement,
                    enabled=r.enabled,
                    created_at=now,
                )
            )

        created_version = await self.repo.create_version(version)
        return created_version

    async def approve_policy_version(
        self, policy_id: str, version_id: str, approval: PolicyApprovalRequest
    ) -> ClassificationPolicyVersion:
        version = await self.repo.get_version_by_id(version_id)
        if not version or version.policy_id != policy_id:
            raise ValueError(f"Version '{version_id}' not found for policy '{policy_id}'.")

        # Maker-Checker: Author cannot approve their own policy version
        if version.created_by == approval.approved_by:
            raise ValueError(
                f"Maker-Checker violation: Creator '{version.created_by}' cannot approve their own policy version."
            )

        now = datetime.utcnow()
        version.approval_status = "APPROVED"
        version.approved_by = approval.approved_by
        version.approved_at = now
        await self.repo.db.commit()
        await self.repo.db.refresh(version)

        policy = await self.repo.get_policy_by_id(policy_id)
        policy.current_version = version.version_number
        policy.lifecycle_status = "ACTIVE"
        policy.approved_by = approval.approved_by
        policy.approved_at = now
        policy.updated_at = now

        await self.repo.update_policy(policy)

        await self.repo.create_audit_event(
            ClassificationAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="VERSION",
                entity_id=version_id,
                event_type="POLICY_APPROVED",
                new_state="ACTIVE",
                actor_id=approval.approved_by,
                reason=approval.comments or "Governance approval",
                correlation_id=uuid.uuid4().hex,
                timestamp=now,
            )
        )

        return version

    # ---------------------------------------------------------
    # Severity Classification Engine
    # ---------------------------------------------------------

    async def classify_breach(
        self,
        req: ClassifyBreachRequest,
        # Injected BreachEvent from M11.06 (either query or pre-fetched)
        breach_event: Optional[BreachEvent] = None,
    ) -> BreachClassification:
        # Check if already classified (idempotency check)
        existing = await self.repo.get_classification_by_event_id(req.breach_event_id)
        if existing:
            return existing

        now = datetime.utcnow()

        # If breach_event not injected, fetch from database session
        if not breach_event:
            breach_event = await self.repo.db.get(BreachEvent, req.breach_event_id)
            if not breach_event:
                raise ValueError(f"Breach event '{req.breach_event_id}' not found in M11.06 database.")

        # 1. Resolve Active Classification Policy
        if req.policy_code:
            policy = await self.repo.get_policy_by_code(req.policy_code)
        else:
            policy = await self.repo.get_active_policy(portfolio_id=breach_event.portfolio_id)

        # Fallback default baseline policy if none explicitly configured
        policy_id = policy.id if policy else "DEFAULT_POLICY"
        policy_ver_num = policy.current_version if policy else 1

        # 2. Materiality Assessment
        materiality_pct, mat_status = calculate_portfolio_materiality(
            impact_amount=breach_event.breach_magnitude,
            portfolio_nav=req.portfolio_nav
        )

        # 3. Rule-Based Severity Evaluation
        candidate_severities: List[Tuple[str, str]] = []  # (severity, reason)

        # Baseline severity from M11.06 event type:
        # WARNING_ENTERED / WARNING_PERSISTENT -> WARNING
        # HARD_BREACH_ENTERED / HARD_BREACH_PERSISTENT -> CRITICAL
        if "WARNING" in breach_event.event_type.upper():
            candidate_severities.append((SEVERITY_WARNING, "M11.06 soft warning boundary violation"))
        elif "HARD_BREACH" in breach_event.event_type.upper():
            candidate_severities.append((SEVERITY_CRITICAL, "M11.06 hard limit boundary violation"))

        # Evaluate Policy Rules if active policy versions exist
        if policy and policy.versions:
            active_version = next((v for v in policy.versions if v.version_number == policy.current_version), None)
            if active_version:
                for r in sorted([rule for rule in active_version.rules if rule.enabled], key=lambda x: x.priority):
                    # Check metric code match
                    if r.target_metric_code not in ("ALL", breach_event.metric_code):
                        continue

                    # Check persistence requirement if configured
                    if r.persistence_requirement:
                        if r.persistence_requirement.upper() != breach_event.persistence_status.upper():
                            continue

                    # Check materiality requirement if configured
                    if r.materiality_requirement is not None:
                        if materiality_pct is None or materiality_pct < r.materiality_requirement:
                            continue

                    # Evaluate boundary rule against breach magnitude
                    is_match = evaluate_severity_rule(
                        rule_operator=r.condition_operator,
                        metric_value=breach_event.breach_magnitude,
                        threshold_low=r.threshold_value,
                        threshold_high=r.upper_threshold_value
                    )

                    if is_match:
                        candidate_severities.append((r.target_severity.upper(), f"Rule {r.rule_code}: {r.rule_name} triggered"))

        # 4. Resolve Final Severity using Precedence: EMERGENCY > CRITICAL > WARNING
        final_severity = SEVERITY_WARNING
        reasons: List[str] = []
        for sev, rsn in candidate_severities:
            final_severity = resolve_higher_severity(final_severity, sev)
            reasons.append(rsn)

        if not reasons:
            reasons.append("Default baseline classification")

        # Read properties from breach_event before commits/expire
        evt_id = breach_event.id
        evt_ep_id = breach_event.breach_episode_id
        evt_pf_id = breach_event.portfolio_id
        evt_rl_id = breach_event.risk_limit_id
        evt_metric = breach_event.metric_code
        evt_entity_type = breach_event.target_entity_type
        evt_entity_id = breach_event.target_entity_id
        evt_obs_val = breach_event.observed_value
        evt_thresh = breach_event.threshold_value
        evt_mag = breach_event.breach_magnitude
        evt_util = breach_event.utilization
        evt_pers = breach_event.persistence_status
        evt_snap_id = breach_event.effective_limit_snapshot_id
        evt_unit = breach_event.metric_unit
        evt_detected_at = breach_event.detected_at
        evt_type = breach_event.event_type
        evt_corr_id = breach_event.correlation_id

        # 5. Persist Immutable Classification
        classif_id = f"cls_{uuid.uuid4().hex[:12]}"
        classif_ref = f"CLS-{final_severity}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        classification = BreachClassification(
            id=classif_id,
            classification_reference=classif_ref,
            breach_event_id=evt_id,
            breach_episode_id=evt_ep_id,
            portfolio_id=evt_pf_id,
            risk_limit_id=evt_rl_id,
            metric_code=evt_metric,
            target_entity_type=evt_entity_type,
            target_entity_id=evt_entity_id,
            severity=final_severity,
            classification_status=STATUS_CLASSIFIED,
            classification_reason="; ".join(reasons),
            policy_id=policy_id,
            policy_version=policy_ver_num,
            observed_value=evt_obs_val,
            applied_threshold=evt_thresh,
            breach_magnitude=evt_mag,
            utilization=evt_util,
            persistence_status=evt_pers,
            materiality_value=materiality_pct,
            materiality_status=mat_status,
            effective_limit_snapshot_id=evt_snap_id,
            classified_at=now,
            created_at=now,
        )
        saved_classif = await self.repo.create_classification(classification)

        # 6. Store Evidence Record
        ev_id = f"cld_{uuid.uuid4().hex[:12]}"
        evidence = ClassificationEvidence(
            id=ev_id,
            classification_id=saved_classif.id,
            evidence_type="BREACH_EVENT_SNAPSHOT",
            source_module="M11.06_BREACH_DETECTION",
            source_record_id=evt_id,
            metric_code=evt_metric,
            observed_value=evt_obs_val,
            threshold_value=evt_thresh,
            unit=evt_unit,
            source_timestamp=evt_detected_at,
            evidence_json={
                "breach_event_id": evt_id,
                "breach_episode_id": evt_ep_id,
                "event_type": evt_type,
                "persistence_status": evt_pers,
                "utilization": str(evt_util),
                "breach_magnitude": str(evt_mag),
                "portfolio_nav": str(req.portfolio_nav) if req.portfolio_nav else None,
                "materiality_pct": str(materiality_pct) if materiality_pct else None,
            },
            created_at=now,
        )
        await self.repo.create_evidence(evidence)

        # 7. Generate Structured Downstream Classification Event for M11.08
        ce_id = f"cle_{uuid.uuid4().hex[:12]}"
        ce_ref = f"EVENT-{final_severity}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        cl_event = ClassificationEvent(
            id=ce_id,
            event_reference=ce_ref,
            classification_id=saved_classif.id,
            breach_event_id=evt_id,
            event_type=f"{final_severity}_CLASSIFIED",
            severity=final_severity,
            previous_severity=None,
            portfolio_id=evt_pf_id,
            risk_limit_id=evt_rl_id,
            policy_version=policy_ver_num,
            event_payload={
                "classification_id": saved_classif.id,
                "severity": final_severity,
                "breach_magnitude": str(evt_mag),
                "utilization": str(evt_util),
                "emergency_indicator": final_severity == SEVERITY_EMERGENCY,
            },
            correlation_id=evt_corr_id,
            created_at=now,
        )
        await self.repo.create_classification_event(cl_event)

        return await self.repo.get_classification_by_id(saved_classif.id)

    # ---------------------------------------------------------
    # Reclassification Workflow
    # ---------------------------------------------------------

    async def reclassify(
        self,
        classification_id: str,
        req: ReclassificationRequest
    ) -> BreachClassification:
        classif = await self.repo.get_classification_by_id(classification_id)
        if not classif:
            raise ValueError(f"Classification '{classification_id}' not found.")

        old_sev = classif.severity
        new_sev = req.new_severity.upper()

        if old_sev == new_sev:
            return classif

        # Determine Change Type (UPGRADE vs DOWNGRADE)
        old_rank = SEVERITY_RANKS.get(old_sev, 0)
        new_rank = SEVERITY_RANKS.get(new_sev, 0)
        change_type = "UPGRADE" if new_rank > old_rank else "DOWNGRADE"

        now = datetime.utcnow()
        classif.severity = new_sev
        classif.classification_status = "RECLASSIFIED"
        classif.classification_reason = f"Manual reclassification: {req.reason_text or req.reason_code}"

        await self.repo.update_classification(classif)

        # Log in ClassificationHistory
        hist_id = f"clh_{uuid.uuid4().hex[:12]}"
        history = ClassificationHistory(
            id=hist_id,
            classification_id=classification_id,
            previous_severity=old_sev,
            new_severity=new_sev,
            change_type=change_type,
            reason_code=req.reason_code,
            reason_text=req.reason_text,
            policy_version=classif.policy_version,
            changed_by=req.changed_by,
            changed_at=now,
        )
        await self.repo.create_history_record(history)

        # Downstream Event for M11.08
        ce_id = f"cle_{uuid.uuid4().hex[:12]}"
        ce_ref = f"EVENT-{change_type}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        cl_event = ClassificationEvent(
            id=ce_id,
            event_reference=ce_ref,
            classification_id=classif.id,
            breach_event_id=classif.breach_event_id,
            event_type=f"SEVERITY_{change_type}D",
            severity=new_sev,
            previous_severity=old_sev,
            portfolio_id=classif.portfolio_id,
            risk_limit_id=classif.risk_limit_id,
            policy_version=classif.policy_version,
            event_payload={"change_type": change_type, "reason_code": req.reason_code},
            correlation_id=uuid.uuid4().hex,
            created_at=now,
        )
        await self.repo.create_classification_event(cl_event)

        return await self.repo.get_classification_by_id(classification_id)
