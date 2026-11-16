"""
Core business logic and evaluation pipeline for M11.06 — Breach Detection.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from backend.app.modules.risk_limits.breach_detection.models.breach_detection_models import (
    BreachEvaluation,
    BreachEpisode,
    BreachObservation,
    BreachEvent,
    BreachDetectionRule,
    BreachDetectionRuleVersion,
    BreachEventLink,
    BreachAuditEvent,
)
from backend.app.modules.risk_limits.breach_detection.repositories.breach_detection_repository import (
    BreachDetectionRepository,
)
from backend.app.modules.risk_limits.breach_detection.schemas.breach_detection_schemas import (
    RiskMetricInput,
    DetectionRuleCreate,
    DetectionRuleApprovalRequest,
)
from backend.app.modules.risk_limits.breach_detection.calculations.breach_detection_math import (
    to_decimal,
    evaluate_boundary_violation,
    calculate_utilization_and_magnitude,
    check_input_freshness,
    classify_breach_severity,
    evaluate_persistence,
    check_recovery_hysteresis,
    THRESHOLD_TYPE_MAX,
    THRESHOLD_TYPE_MIN,
    STATUS_WITHIN_LIMIT,
    STATUS_WARNING,
    STATUS_HARD_BREACH,
    STATUS_PERSISTENT_BREACH,
    STATUS_RECOVERY_PENDING,
    STATUS_RECOVERED,
    STATUS_STALE_INPUT,
    STATUS_INVALID_INPUT,
    STATUS_LIMIT_UNAVAILABLE,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH,
    SEVERITY_CRITICAL,
)


class BreachDetectionService:
    def __init__(self, repo: BreachDetectionRepository):
        self.repo = repo

    # ---------------------------------------------------------
    # Detection Rules Lifecycle
    # ---------------------------------------------------------

    async def create_rule(self, data: DetectionRuleCreate, created_by: str = "risk_analyst") -> BreachDetectionRule:
        existing = await self.repo.get_rule_by_code(data.rule_code)
        if existing:
            raise ValueError(f"Detection rule with code '{data.rule_code}' already exists.")

        rule_id = f"rl_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        rule = BreachDetectionRule(
            id=rule_id,
            rule_code=data.rule_code,
            rule_name=data.rule_name,
            metric_code=data.metric_code,
            applicable_scope=data.applicable_scope,
            persistence_mode=data.persistence_mode.upper(),
            required_duration_seconds=data.required_duration_seconds,
            required_consecutive_observations=data.required_consecutive_observations,
            observation_window_seconds=data.observation_window_seconds,
            required_observation_count=data.required_observation_count,
            permitted_gap_seconds=data.permitted_gap_seconds,
            recovery_duration_seconds=data.recovery_duration_seconds,
            immediate_breach=data.immediate_breach,
            hysteresis_config=data.hysteresis_config,
            missing_data_behavior=data.missing_data_behavior,
            rule_version=1,
            status="ACTIVE",
            created_at=now,
        )

        created_rule = await self.repo.create_rule(rule)

        # Create version 1 record
        ver_id = f"rlv_{uuid.uuid4().hex[:12]}"
        v = BreachDetectionRuleVersion(
            id=ver_id,
            rule_id=rule_id,
            version_number=1,
            configuration_json=data.model_dump(),
            approved_by=created_by,
            approved_at=now,
            created_at=now,
        )
        self.repo.db.add(v)
        await self.repo.db.commit()

        await self.repo.create_audit_event(
            BreachAuditEvent(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="RULE",
                entity_id=rule_id,
                event_type="RULE_CREATED",
                new_state="ACTIVE",
                actor_id=created_by,
                reason="Initial rule configuration",
                correlation_id=uuid.uuid4().hex,
                timestamp=now,
            )
        )

        return await self.repo.get_rule_by_id(rule_id)

    # ---------------------------------------------------------
    # Core Evaluation Engine
    # ---------------------------------------------------------

    async def evaluate_metric(
        self,
        metric: RiskMetricInput,
        evaluation_timestamp: Optional[datetime] = None,
        # Injected or resolved limits (e.g. from M11.01, M11.04, or M11.05 snapshot)
        hard_threshold: Optional[Decimal] = None,
        warning_threshold: Optional[Decimal] = None,
        limit_nature: str = "CAP",
        comparison_operator: str = "GREATER_THAN",
        active_limit_id: Optional[str] = None,
        effective_limit_snapshot_id: Optional[str] = None,
        max_permitted_age_seconds: int = 3600
    ) -> BreachEvaluation:
        now = evaluation_timestamp or datetime.utcnow()
        corr_id = metric.correlation_id or uuid.uuid4().hex
        eval_id = f"evl_{uuid.uuid4().hex[:12]}"
        eval_ref = f"EVAL-{metric.metric_code}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        # 1. Input Quality and Freshness Checks
        # Validate data quality state (from M03)
        if metric.input_quality_status.upper() in ("INVALID", "CORRUPTED", "ERROR"):
            evaluation = BreachEvaluation(
                id=eval_id,
                evaluation_reference=eval_ref,
                portfolio_id=metric.portfolio_id,
                target_entity_type=metric.target_entity_type,
                target_entity_id=metric.target_entity_id,
                metric_code=metric.metric_code,
                metric_source_module=metric.metric_source_module,
                metric_value=metric.metric_value,
                metric_unit=metric.metric_unit,
                metric_currency=metric.metric_currency,
                metric_timestamp=metric.metric_timestamp,
                processing_timestamp=now,
                input_quality_status=metric.input_quality_status,
                active_limit_id=active_limit_id,
                effective_limit_snapshot_id=effective_limit_snapshot_id,
                warning_threshold=warning_threshold,
                hard_threshold=hard_threshold or Decimal("0"),
                applied_threshold=hard_threshold or Decimal("0"),
                comparison_operator=comparison_operator,
                evaluation_status=STATUS_INVALID_INPUT,
                severity=SEVERITY_MEDIUM,
                breach_magnitude=Decimal("0"),
                utilization=Decimal("0"),
                created_at=now,
            )
            return await self.repo.create_evaluation(evaluation)

        # Freshness Check
        is_fresh, age_sec = check_input_freshness(
            metric.metric_timestamp, now, max_permitted_age_seconds=max_permitted_age_seconds
        )
        if not is_fresh or metric.input_quality_status.upper() == "STALE":
            evaluation = BreachEvaluation(
                id=eval_id,
                evaluation_reference=eval_ref,
                portfolio_id=metric.portfolio_id,
                target_entity_type=metric.target_entity_type,
                target_entity_id=metric.target_entity_id,
                metric_code=metric.metric_code,
                metric_source_module=metric.metric_source_module,
                metric_value=metric.metric_value,
                metric_unit=metric.metric_unit,
                metric_currency=metric.metric_currency,
                metric_timestamp=metric.metric_timestamp,
                processing_timestamp=now,
                input_quality_status="STALE",
                active_limit_id=active_limit_id,
                effective_limit_snapshot_id=effective_limit_snapshot_id,
                warning_threshold=warning_threshold,
                hard_threshold=hard_threshold or Decimal("0"),
                applied_threshold=hard_threshold or Decimal("0"),
                comparison_operator=comparison_operator,
                evaluation_status=STATUS_STALE_INPUT,
                severity=SEVERITY_MEDIUM,
                breach_magnitude=Decimal("0"),
                utilization=Decimal("0"),
                created_at=now,
            )
            return await self.repo.create_evaluation(evaluation)

        # 2. Check Limit Availability
        if hard_threshold is None:
            # Applicable limit cannot be resolved: Never interpret as zero or automatic pass!
            evaluation = BreachEvaluation(
                id=eval_id,
                evaluation_reference=eval_ref,
                portfolio_id=metric.portfolio_id,
                target_entity_type=metric.target_entity_type,
                target_entity_id=metric.target_entity_id,
                metric_code=metric.metric_code,
                metric_source_module=metric.metric_source_module,
                metric_value=metric.metric_value,
                metric_unit=metric.metric_unit,
                metric_currency=metric.metric_currency,
                metric_timestamp=metric.metric_timestamp,
                processing_timestamp=now,
                input_quality_status=metric.input_quality_status,
                active_limit_id=None,
                effective_limit_snapshot_id=effective_limit_snapshot_id,
                warning_threshold=None,
                hard_threshold=Decimal("0"),
                applied_threshold=Decimal("0"),
                comparison_operator=comparison_operator,
                evaluation_status=STATUS_LIMIT_UNAVAILABLE,
                severity=SEVERITY_HIGH,
                breach_magnitude=Decimal("0"),
                utilization=Decimal("0"),
                created_at=now,
            )
            return await self.repo.create_evaluation(evaluation)

        # 3. Quantitative Threshold Evaluation
        obs_val = to_decimal(metric.metric_value)
        l_type = THRESHOLD_TYPE_MAX if limit_nature.upper() == "CAP" else THRESHOLD_TYPE_MIN

        # Evaluate Hard Boundary
        is_hard_violation = evaluate_boundary_violation(
            observed_value=obs_val,
            threshold=hard_threshold,
            operator=comparison_operator
        )

        # Evaluate Warning Boundary (if present)
        is_warning_violation = False
        if warning_threshold is not None:
            is_warning_violation = evaluate_boundary_violation(
                observed_value=obs_val,
                threshold=warning_threshold,
                operator=comparison_operator
            )

        # Calculate Utilization & Magnitude against Hard Limit
        utilization, magnitude, excess_pct = calculate_utilization_and_magnitude(
            observed_value=obs_val,
            threshold=hard_threshold,
            limit_type=l_type
        )

        # Fetch detection rule for this metric (if any)
        rule = await self.repo.get_rule_for_metric(metric.metric_code)
        immediate_breach = rule.immediate_breach if rule else False
        persistence_mode = rule.persistence_mode if rule else "DURATION"
        req_dur = rule.required_duration_seconds if rule else 300
        req_consec = rule.required_consecutive_observations if rule else 3
        rule_version_str = str(rule.rule_version) if rule else "1"

        # Classify Severity
        severity = classify_breach_severity(
            breach_magnitude=magnitude,
            threshold=hard_threshold,
            excess_pct=excess_pct,
            is_hard_breach=is_hard_violation,
            immediate_breach=immediate_breach
        )

        # Determine Baseline Evaluation Status
        if is_hard_violation:
            eval_status = STATUS_HARD_BREACH
        elif is_warning_violation:
            eval_status = STATUS_WARNING
        else:
            eval_status = STATUS_WITHIN_LIMIT

        # Create evaluation record
        evaluation = BreachEvaluation(
            id=eval_id,
            evaluation_reference=eval_ref,
            portfolio_id=metric.portfolio_id,
            target_entity_type=metric.target_entity_type,
            target_entity_id=metric.target_entity_id,
            metric_code=metric.metric_code,
            metric_source_module=metric.metric_source_module,
            metric_value=obs_val,
            metric_unit=metric.metric_unit,
            metric_currency=metric.metric_currency,
            metric_timestamp=metric.metric_timestamp,
            processing_timestamp=now,
            input_quality_status=metric.input_quality_status,
            active_limit_id=active_limit_id,
            effective_limit_snapshot_id=effective_limit_snapshot_id,
            warning_threshold=warning_threshold,
            hard_threshold=hard_threshold,
            applied_threshold=hard_threshold if is_hard_violation else (warning_threshold or hard_threshold),
            comparison_operator=comparison_operator,
            evaluation_status=eval_status,
            severity=severity,
            breach_magnitude=magnitude,
            utilization=utilization,
            detection_rule_version=rule_version_str,
            created_at=now,
        )
        created_eval = await self.repo.create_evaluation(evaluation)

        # 4. Stateful Breach Episode & Persistence Tracking
        active_episode = await self.repo.get_active_episode(
            portfolio_id=metric.portfolio_id,
            target_entity_id=metric.target_entity_id,
            metric_code=metric.metric_code
        )

        limit_id_ref = active_limit_id or f"lim_{metric.metric_code}"

        if is_hard_violation or is_warning_violation:
            if not active_episode:
                # Open a new breach episode
                ep_id = f"bep_{uuid.uuid4().hex[:12]}"
                active_episode = BreachEpisode(
                    id=ep_id,
                    portfolio_id=metric.portfolio_id,
                    risk_limit_id=limit_id_ref,
                    target_entity_type=metric.target_entity_type,
                    target_entity_id=metric.target_entity_id,
                    metric_code=metric.metric_code,
                    limit_version="1",
                    episode_status="ACTIVE_HARD_BREACH" if is_hard_violation else "ACTIVE_WARNING",
                    first_violation_at=metric.metric_timestamp,
                    breach_detected_at=now,
                    maximum_breach_magnitude=magnitude,
                    maximum_observed_value=obs_val,
                    first_evaluation_id=eval_id,
                    latest_evaluation_id=eval_id,
                    created_at=now,
                    updated_at=now,
                )
                active_episode = await self.repo.create_episode(active_episode)

                # Record initial breach event
                event_type = "HARD_BREACH_ENTERED" if is_hard_violation else "WARNING_ENTERED"
                evt_id = f"evt_{uuid.uuid4().hex[:12]}"
                evt_ref = f"BREACH-{event_type}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                
                event = BreachEvent(
                    id=evt_id,
                    event_reference=evt_ref,
                    breach_episode_id=active_episode.id,
                    portfolio_id=metric.portfolio_id,
                    target_entity_type=metric.target_entity_type,
                    target_entity_id=metric.target_entity_id,
                    risk_limit_id=limit_id_ref,
                    metric_code=metric.metric_code,
                    event_type=event_type,
                    severity=severity,
                    observed_value=obs_val,
                    threshold_value=hard_threshold,
                    warning_threshold=warning_threshold,
                    hard_threshold=hard_threshold,
                    metric_unit=metric.metric_unit,
                    metric_currency=metric.metric_currency,
                    breach_magnitude=magnitude,
                    utilization=utilization,
                    metric_timestamp=metric.metric_timestamp,
                    detected_at=now,
                    persistence_status="PERSISTENT" if immediate_breach else "TRANSIENT",
                    evaluation_id=eval_id,
                    effective_limit_snapshot_id=effective_limit_snapshot_id,
                    source_event_reference=metric.source_event_reference,
                    correlation_id=corr_id,
                    created_at=now,
                )
                await self.repo.create_event(event)

            else:
                # Update existing ongoing episode
                active_episode.latest_evaluation_id = eval_id
                active_episode.updated_at = now
                if magnitude > active_episode.maximum_breach_magnitude:
                    active_episode.maximum_breach_magnitude = magnitude
                if obs_val > active_episode.maximum_observed_value:
                    active_episode.maximum_observed_value = obs_val

            # Log Observation within episode
            existing_obs = await self.repo.list_observations_for_episode(active_episode.id)
            seq = len(existing_obs) + 1
            obs_id = f"obs_{uuid.uuid4().hex[:12]}"
            observation = BreachObservation(
                id=obs_id,
                episode_id=active_episode.id,
                evaluation_id=eval_id,
                metric_value=obs_val,
                threshold_value=hard_threshold,
                warning_threshold=warning_threshold,
                hard_threshold=hard_threshold,
                comparison_result="VIOLATING" if is_hard_violation else "WARNING",
                quality_status=metric.input_quality_status,
                metric_timestamp=metric.metric_timestamp,
                processing_timestamp=now,
                observation_sequence=seq,
                created_at=now,
            )
            await self.repo.create_observation(observation)

            # Evaluate Persistence
            obs_history = [(o.metric_timestamp, o.comparison_result == "VIOLATING") for o in existing_obs]
            obs_history.append((metric.metric_timestamp, is_hard_violation))

            is_persistent, pers_status = evaluate_persistence(
                observations=obs_history,
                first_violation_at=active_episode.first_violation_at,
                current_time=now,
                persistence_mode=persistence_mode,
                required_duration_seconds=req_dur,
                required_consecutive_count=req_consec,
                immediate_breach=immediate_breach,
            )

            if is_persistent and active_episode.episode_status != "PERSISTENT_BREACH":
                active_episode.episode_status = "PERSISTENT_BREACH"
                # Generate PERSISTENT_BREACH Event
                p_evt_id = f"evt_{uuid.uuid4().hex[:12]}"
                p_evt_ref = f"BREACH-PERSISTENT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                p_event = BreachEvent(
                    id=p_evt_id,
                    event_reference=p_evt_ref,
                    breach_episode_id=active_episode.id,
                    portfolio_id=metric.portfolio_id,
                    target_entity_type=metric.target_entity_type,
                    target_entity_id=metric.target_entity_id,
                    risk_limit_id=limit_id_ref,
                    metric_code=metric.metric_code,
                    event_type="HARD_BREACH_PERSISTENT" if is_hard_violation else "WARNING_PERSISTENT",
                    severity=SEVERITY_CRITICAL if severity == SEVERITY_HIGH else severity,
                    observed_value=obs_val,
                    threshold_value=hard_threshold,
                    warning_threshold=warning_threshold,
                    hard_threshold=hard_threshold,
                    metric_unit=metric.metric_unit,
                    metric_currency=metric.metric_currency,
                    breach_magnitude=magnitude,
                    utilization=utilization,
                    metric_timestamp=metric.metric_timestamp,
                    detected_at=now,
                    persistence_status="PERSISTENT",
                    evaluation_id=eval_id,
                    effective_limit_snapshot_id=effective_limit_snapshot_id,
                    source_event_reference=metric.source_event_reference,
                    correlation_id=corr_id,
                    created_at=now,
                )
                await self.repo.create_event(p_event)

            await self.repo.update_episode(active_episode)

        else:
            # Metric is compliant (WITHIN_LIMIT)
            if active_episode and active_episode.episode_status != "RECOVERED":
                # Check recovery under hysteresis
                hysteresis_rec = rule.hysteresis_config.get("recovery_threshold") if rule and rule.hysteresis_config else None
                rec_threshold = to_decimal(hysteresis_rec) if hysteresis_rec is not None else hard_threshold

                has_recovered = check_recovery_hysteresis(
                    observed_value=obs_val,
                    threshold=hard_threshold,
                    recovery_threshold=rec_threshold,
                    limit_type=l_type
                )

                if has_recovered:
                    active_episode.episode_status = "RECOVERED"
                    active_episode.recovered_at = now
                    active_episode.updated_at = now
                    await self.repo.update_episode(active_episode)

                    # Generate BREACH_RECOVERED event
                    r_evt_id = f"evt_{uuid.uuid4().hex[:12]}"
                    r_evt_ref = f"BREACH-RECOVERED-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                    r_event = BreachEvent(
                        id=r_evt_id,
                        event_reference=r_evt_ref,
                        breach_episode_id=active_episode.id,
                        portfolio_id=metric.portfolio_id,
                        target_entity_type=metric.target_entity_type,
                        target_entity_id=metric.target_entity_id,
                        risk_limit_id=limit_id_ref,
                        metric_code=metric.metric_code,
                        event_type="BREACH_RECOVERED",
                        severity=SEVERITY_LOW,
                        observed_value=obs_val,
                        threshold_value=hard_threshold,
                        warning_threshold=warning_threshold,
                        hard_threshold=hard_threshold,
                        metric_unit=metric.metric_unit,
                        metric_currency=metric.metric_currency,
                        breach_magnitude=Decimal("0"),
                        utilization=utilization,
                        metric_timestamp=metric.metric_timestamp,
                        detected_at=now,
                        persistence_status="TRANSIENT",
                        evaluation_id=eval_id,
                        effective_limit_snapshot_id=effective_limit_snapshot_id,
                        source_event_reference=metric.source_event_reference,
                        correlation_id=corr_id,
                        created_at=now,
                    )
                    await self.repo.create_event(r_event)

        return created_eval

    async def evaluate_batch(
        self,
        metrics: List[RiskMetricInput],
        hard_thresholds: Dict[str, Decimal],
        warning_thresholds: Optional[Dict[str, Decimal]] = None
    ) -> List[BreachEvaluation]:
        results: List[BreachEvaluation] = []
        for m in metrics:
            h_thresh = hard_thresholds.get(m.metric_code)
            w_thresh = warning_thresholds.get(m.metric_code) if warning_thresholds else None
            res = await self.evaluate_metric(
                metric=m,
                hard_threshold=h_thresh,
                warning_threshold=w_thresh
            )
            results.append(res)
        return results
