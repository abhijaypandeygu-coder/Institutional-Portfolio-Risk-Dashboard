"""
Business logic and dynamic limit evaluation engine for M11.05 — Dynamic Limits.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from backend.app.modules.risk_limits.dynamic_limits.models.dynamic_limit_models import (
    DynamicLimitPolicy,
    DynamicLimitPolicyVersion,
    DynamicLimitCondition,
    DynamicLimitSchedule,
    DynamicLimitOverride,
    EffectiveLimitSnapshot,
    DynamicLimitAuditEvent,
)
from backend.app.modules.risk_limits.dynamic_limits.repositories.dynamic_limit_repository import DynamicLimitRepository
from backend.app.modules.risk_limits.dynamic_limits.schemas.dynamic_limit_schemas import (
    PolicyCreate,
    PolicyVersionCreate,
    PolicyApprovalRequest,
    OverrideCreate,
    OverrideApprovalRequest,
    OverrideRejectRequest,
    OverrideRevokeRequest,
    DynamicLimitEvaluationRequest,
)
from backend.app.modules.risk_limits.dynamic_limits.calculations.dynamic_limit_math import (
    to_decimal,
    evaluate_condition_operator,
    evaluate_hysteresis_state,
    calculate_adjusted_limit,
    resolve_market_session,
    generate_lineage_hash,
    LIMIT_NATURE_CAP,
    LIMIT_NATURE_FLOOR,
)


class DynamicLimitService:
    def __init__(self, repo: DynamicLimitRepository):
        self.repo = repo

    # ---------------------------------------------------------
    # Policy Lifecycle Management
    # ---------------------------------------------------------

    async def create_policy(self, data: PolicyCreate) -> DynamicLimitPolicy:
        existing = await self.repo.get_policy_by_code(data.policy_code)
        if existing:
            raise ValueError(f"Policy with code '{data.policy_code}' already exists.")

        policy_id = f"pol_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        policy = DynamicLimitPolicy(
            id=policy_id,
            policy_code=data.policy_code,
            name=data.name,
            description=data.description,
            portfolio_id=data.portfolio_id,
            market=data.market,
            asset_class=data.asset_class,
            status="DRAFT",
            created_by=data.created_by,
            created_at=now,
            updated_at=now,
        )

        created_policy = await self.repo.create_policy(policy)

        # Create initial version if provided
        if data.initial_version:
            v = await self.create_policy_version(policy_id, data.initial_version)
            created_policy.current_version_id = v.id
            await self.repo.update_policy(created_policy)

        # Audit event
        await self.repo.create_audit_event(
            DynamicLimitAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="POLICY",
                entity_id=policy_id,
                action="CREATE",
                performed_by=data.created_by,
                timestamp=now,
                details={"policy_code": data.policy_code, "name": data.name},
            )
        )

        return await self.repo.get_policy_by_id(policy_id)

    async def create_policy_version(
        self, policy_id: str, data: PolicyVersionCreate
    ) -> DynamicLimitPolicyVersion:
        policy = await self.repo.get_policy_by_id(policy_id)
        if not policy:
            raise ValueError(f"Policy with ID '{policy_id}' not found.")

        next_version_num = len(policy.versions) + 1
        version_id = f"ver_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        version = DynamicLimitPolicyVersion(
            id=version_id,
            policy_id=policy_id,
            version_number=next_version_num,
            target_limit_code=data.target_limit_code,
            limit_nature=data.limit_nature.upper(),
            base_limit_value=data.base_limit_value,
            restrictive_only=data.restrictive_only,
            min_allowed_value=data.min_allowed_value,
            max_allowed_value=data.max_allowed_value,
            status="DRAFT",
            authored_by=data.authored_by,
            change_reason=data.change_reason,
            created_at=now,
        )

        for c in data.conditions:
            cond_id = f"cnd_{uuid.uuid4().hex[:12]}"
            version.conditions.append(
                DynamicLimitCondition(
                    id=cond_id,
                    version_id=version_id,
                    rule_name=c.rule_name,
                    priority=c.priority,
                    is_active=c.is_active,
                    metric_source=c.metric_source.upper(),
                    metric_name=c.metric_name.upper(),
                    operator=c.operator.upper(),
                    threshold_low=c.threshold_low,
                    threshold_high=c.threshold_high,
                    hysteresis_entry=c.hysteresis_entry,
                    hysteresis_exit=c.hysteresis_exit,
                    hysteresis_direction=c.hysteresis_direction.upper(),
                    persistence_minutes=c.persistence_minutes,
                    regime_match=c.regime_match.upper() if c.regime_match else None,
                    adjustment_type=c.adjustment_type.upper(),
                    adjustment_value=c.adjustment_value,
                    description=c.description,
                )
            )

        for s in data.schedules:
            sched_id = f"sch_{uuid.uuid4().hex[:12]}"
            version.schedules.append(
                DynamicLimitSchedule(
                    id=sched_id,
                    version_id=version_id,
                    session_name=s.session_name.upper(),
                    market=s.market.upper(),
                    timezone=s.timezone,
                    adjustment_type=s.adjustment_type.upper(),
                    adjustment_value=s.adjustment_value,
                    is_active=s.is_active,
                )
            )

        created_version = await self.repo.create_version(version)

        # Audit event
        await self.repo.create_audit_event(
            DynamicLimitAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="VERSION",
                entity_id=version_id,
                action="CREATE",
                performed_by=data.authored_by,
                timestamp=now,
                details={"version_number": next_version_num, "policy_id": policy_id},
            )
        )

        return created_version

    async def approve_policy_version(
        self, policy_id: str, version_id: str, approval: PolicyApprovalRequest
    ) -> DynamicLimitPolicyVersion:
        version = await self.repo.get_version_by_id(version_id)
        if not version or version.policy_id != policy_id:
            raise ValueError(f"Version '{version_id}' not found for policy '{policy_id}'.")

        # Maker-Checker validation: author cannot approve own policy version
        if version.authored_by == approval.approved_by:
            raise ValueError(
                f"Maker-Checker violation: Author '{version.authored_by}' cannot approve their own policy version."
            )

        now = datetime.utcnow()
        version.status = "APPROVED"
        version.approved_by = approval.approved_by
        version.approval_timestamp = now

        # Update policy's active version pointer and status
        policy = await self.repo.get_policy_by_id(policy_id)
        policy.current_version_id = version.id
        policy.status = "ACTIVE"
        policy.updated_at = now

        await self.repo.update_policy(policy)

        # Audit event
        await self.repo.create_audit_event(
            DynamicLimitAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="VERSION",
                entity_id=version_id,
                action="APPROVE",
                performed_by=approval.approved_by,
                timestamp=now,
                details={"comments": approval.comments, "policy_id": policy_id},
            )
        )

        return version

    # ---------------------------------------------------------
    # Maker-Checker Manual Overrides
    # ---------------------------------------------------------

    async def request_override(self, data: OverrideCreate) -> DynamicLimitOverride:
        policy = await self.repo.get_policy_by_id(data.policy_id)
        if not policy:
            raise ValueError(f"Policy '{data.policy_id}' not found.")

        if data.effective_to <= data.effective_from:
            raise ValueError("Override expiry 'effective_to' must be strictly after 'effective_from'.")

        if not data.reason_code or not data.justification:
            raise ValueError("Override must include a valid reason_code and justification.")

        now = datetime.utcnow()
        override_id = f"ovr_{uuid.uuid4().hex[:12]}"

        override = DynamicLimitOverride(
            id=override_id,
            policy_id=data.policy_id,
            target_limit_code=data.target_limit_code,
            override_value=data.override_value,
            reason_code=data.reason_code,
            justification=data.justification,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            status="PENDING_APPROVAL",
            requested_by=data.requested_by,
            requested_at=now,
        )

        created_override = await self.repo.create_override(override)

        await self.repo.create_audit_event(
            DynamicLimitAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="OVERRIDE",
                entity_id=override_id,
                action="OVERRIDE_REQUEST",
                performed_by=data.requested_by,
                timestamp=now,
                details={
                    "override_value": str(data.override_value),
                    "reason_code": data.reason_code,
                    "policy_id": data.policy_id,
                },
            )
        )

        return created_override

    async def approve_override(
        self, override_id: str, approval: OverrideApprovalRequest
    ) -> DynamicLimitOverride:
        override = await self.repo.get_override_by_id(override_id)
        if not override:
            raise ValueError(f"Override '{override_id}' not found.")

        if override.status != "PENDING_APPROVAL":
            raise ValueError(f"Override '{override_id}' is not in PENDING_APPROVAL status (current: {override.status}).")

        # Maker-Checker governance: Requestor cannot approve their own override
        if override.requested_by == approval.approved_by:
            raise ValueError(
                f"Maker-Checker violation: Requestor '{override.requested_by}' cannot approve their own manual override."
            )

        now = datetime.utcnow()
        override.status = "APPROVED"
        override.approved_by = approval.approved_by
        override.approved_at = now

        await self.repo.db.commit()
        await self.repo.db.refresh(override)

        await self.repo.create_audit_event(
            DynamicLimitAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="OVERRIDE",
                entity_id=override_id,
                action="OVERRIDE_APPROVE",
                performed_by=approval.approved_by,
                timestamp=now,
                details={"comments": approval.comments},
            )
        )

        return override

    async def reject_override(
        self, override_id: str, rejection: OverrideRejectRequest
    ) -> DynamicLimitOverride:
        override = await self.repo.get_override_by_id(override_id)
        if not override:
            raise ValueError(f"Override '{override_id}' not found.")

        if override.status != "PENDING_APPROVAL":
            raise ValueError(f"Override '{override_id}' is not in PENDING_APPROVAL status.")

        now = datetime.utcnow()
        override.status = "REJECTED"
        override.rejection_reason = rejection.rejection_reason

        await self.repo.db.commit()
        await self.repo.db.refresh(override)

        await self.repo.create_audit_event(
            DynamicLimitAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="OVERRIDE",
                entity_id=override_id,
                action="OVERRIDE_REJECT",
                performed_by=rejection.rejected_by,
                timestamp=now,
                details={"rejection_reason": rejection.rejection_reason},
            )
        )

        return override

    async def revoke_override(
        self, override_id: str, revocation: OverrideRevokeRequest
    ) -> DynamicLimitOverride:
        override = await self.repo.get_override_by_id(override_id)
        if not override:
            raise ValueError(f"Override '{override_id}' not found.")

        if override.status != "APPROVED":
            raise ValueError(f"Only APPROVED overrides can be revoked (current: {override.status}).")

        now = datetime.utcnow()
        override.status = "REVOKED"
        override.revoked_by = revocation.revoked_by
        override.revoked_at = now

        await self.repo.db.commit()
        await self.repo.db.refresh(override)

        await self.repo.create_audit_event(
            DynamicLimitAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="OVERRIDE",
                entity_id=override_id,
                action="OVERRIDE_REVOKE",
                performed_by=revocation.revoked_by,
                timestamp=now,
                details={"revocation_reason": revocation.revocation_reason},
            )
        )

        return override

    # ---------------------------------------------------------
    # Dynamic Limit Evaluation Engine
    # ---------------------------------------------------------

    async def evaluate_limits(
        self, req: DynamicLimitEvaluationRequest
    ) -> List[EffectiveLimitSnapshot]:
        """
        Evaluates active policies for the portfolio/market, computes dynamic adjustments,
        applies conflict resolution precedence, and saves immutable snapshots with full lineage.
        """
        as_of = req.as_of_time or datetime.utcnow()
        policies = await self.repo.list_policies(
            portfolio_id=req.portfolio_id,
            market=req.market,
            status="ACTIVE"
        )

        snapshots: List[EffectiveLimitSnapshot] = []

        for pol in policies:
            if not pol.current_version_id:
                continue

            # Load active version
            version = await self.repo.get_version_by_id(pol.current_version_id)
            if not version:
                continue

            base_limit = version.base_limit_value
            nature = version.limit_nature
            restrictive_only = version.restrictive_only
            min_bound = version.min_allowed_value
            max_bound = version.max_allowed_value

            lineage: Dict[str, Any] = {
                "policy_code": pol.policy_code,
                "version_number": version.version_number,
                "target_limit_code": version.target_limit_code,
                "base_limit": str(base_limit),
                "limit_nature": nature,
                "input_metrics": req.current_metrics,
                "as_of_time": as_of.isoformat(),
            }

            active_regime = req.current_metrics.get("MARKET_REGIME")
            session_name = resolve_market_session(as_of, req.market)
            lineage["resolved_session"] = session_name
            lineage["resolved_regime"] = active_regime

            # 1. Condition-based adjustment check
            applied_condition_name: Optional[str] = None
            condition_adjustment_value: Optional[Decimal] = None
            condition_adj_type: Optional[str] = None

            # Sort active conditions by priority (lowest number first)
            sorted_conditions = sorted(
                [c for c in version.conditions if c.is_active],
                key=lambda x: x.priority
            )

            for cond in sorted_conditions:
                # Metric value lookup
                metric_val = req.current_metrics.get(cond.metric_name)
                
                # Check categorical regime match
                if cond.metric_source == "REGIME":
                    if active_regime and cond.regime_match and active_regime.upper() == cond.regime_match.upper():
                        applied_condition_name = cond.rule_name
                        condition_adj_type = cond.adjustment_type
                        condition_adjustment_value = cond.adjustment_value
                        break
                elif metric_val is not None:
                    dec_val = to_decimal(metric_val)
                    # Check hysteresis if configured
                    if cond.hysteresis_entry is not None and cond.hysteresis_exit is not None:
                        is_triggered = evaluate_hysteresis_state(
                            current_value=dec_val,
                            currently_active=False,  # Evaluated afresh or from state
                            entry_threshold=cond.hysteresis_entry,
                            exit_threshold=cond.hysteresis_exit,
                            direction=cond.hysteresis_direction,
                        )
                    else:
                        is_triggered = evaluate_condition_operator(
                            current_value=dec_val,
                            operator=cond.operator,
                            threshold_low=cond.threshold_low,
                            threshold_high=cond.threshold_high,
                        )

                    if is_triggered:
                        applied_condition_name = cond.rule_name
                        condition_adj_type = cond.adjustment_type
                        condition_adjustment_value = cond.adjustment_value
                        break

            # 2. Time-based profile schedule check
            active_schedule: Optional[DynamicLimitSchedule] = None
            for sch in version.schedules:
                if sch.is_active and sch.session_name.upper() == session_name.upper():
                    active_schedule = sch
                    break

            # 3. Check for approved active manual override
            active_overrides = await self.repo.list_active_overrides(
                policy_id=pol.id,
                target_limit_code=version.target_limit_code,
                as_of_time=as_of,
            )
            selected_override = active_overrides[0] if active_overrides else None

            # 4. Resolve effective limit based on Precedence Hierarchy:
            # Precedence: Override (if bounds compliant) vs Condition vs Schedule vs Base
            current_candidate = base_limit
            adjustment_trace = []

            # Step A: Apply Schedule adjustment if active
            if active_schedule:
                raw, eff = calculate_adjusted_limit(
                    base_limit=current_candidate,
                    adjustment_type=active_schedule.adjustment_type,
                    adjustment_value=active_schedule.adjustment_value,
                    nature=nature,
                    restrictive_only=restrictive_only,
                    min_bound=min_bound,
                    max_bound=max_bound,
                )
                current_candidate = eff
                adjustment_trace.append({
                    "step": "SCHEDULE",
                    "session": session_name,
                    "adj_type": active_schedule.adjustment_type,
                    "adj_val": str(active_schedule.adjustment_value),
                    "resulting_limit": str(eff),
                })

            # Step B: Apply Condition adjustment if triggered (Higher precedence than schedule)
            if condition_adjustment_value is not None and condition_adj_type:
                raw, eff = calculate_adjusted_limit(
                    base_limit=current_candidate,
                    adjustment_type=condition_adj_type,
                    adjustment_value=condition_adjustment_value,
                    nature=nature,
                    restrictive_only=restrictive_only,
                    min_bound=min_bound,
                    max_bound=max_bound,
                )
                current_candidate = eff
                adjustment_trace.append({
                    "step": "CONDITION",
                    "condition": applied_condition_name,
                    "adj_type": condition_adj_type,
                    "adj_val": str(condition_adjustment_value),
                    "resulting_limit": str(eff),
                })

            # Step C: Apply Approved Override if present
            applied_override_id = None
            if selected_override:
                applied_override_id = selected_override.id
                raw, eff = calculate_adjusted_limit(
                    base_limit=current_candidate,
                    adjustment_type="ABSOLUTE_REPLACEMENT",
                    adjustment_value=selected_override.override_value,
                    nature=nature,
                    restrictive_only=False,  # Approved overrides explicitly replace candidate
                    min_bound=min_bound,
                    max_bound=max_bound,
                )
                current_candidate = eff
                adjustment_trace.append({
                    "step": "MANUAL_OVERRIDE",
                    "override_id": selected_override.id,
                    "reason_code": selected_override.reason_code,
                    "resulting_limit": str(eff),
                })

            final_effective = current_candidate
            lineage["adjustment_trace"] = adjustment_trace
            lineage["final_effective_limit"] = str(final_effective)

            snapshot_hash = generate_lineage_hash(lineage)

            snapshot = EffectiveLimitSnapshot(
                id=f"snp_{uuid.uuid4().hex[:12]}",
                policy_id=pol.id,
                policy_version_id=version.id,
                portfolio_id=req.portfolio_id or pol.portfolio_id,
                target_limit_code=version.target_limit_code,
                base_limit_value=base_limit,
                effective_limit_value=final_effective,
                limit_nature=nature,
                active_regime=active_regime,
                active_session=session_name,
                condition_adjustment_applied=applied_condition_name,
                override_applied_id=applied_override_id,
                as_of_time=as_of,
                snapshot_hash=snapshot_hash,
                lineage_metadata=lineage,
            )

            created_snapshot = await self.repo.create_snapshot(snapshot)
            snapshots.append(created_snapshot)

        return snapshots

