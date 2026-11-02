"""
M08.08 Factor Monitoring Service Layer.
Coordinates:
1. Upstream resolution of portfolio exposure snapshots (M08.02)
2. Upstream resolution of factor definitions & model versions (M08.01)
3. Upstream resolution of systematic risk (M08.05) & factor risk contributions (M08.04)
4. Exposure drift analysis (previous snapshot, historical baseline, approved target)
5. Standardized exposure & risk contribution concentration (HHI & top factor shares)
6. Threshold policy evaluations, deterministic utilization, and headroom
7. Breach lifecycle management (detection, acknowledgement, recovery)
8. Typed monitoring event generation & notification publishing
"""

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
import math
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_monitoring.models import (
    FactorMonitoringConfig,
    FactorExposureTarget,
    FactorExposureTargetComponent,
    FactorThresholdPolicy,
    FactorMonitoringRun,
    FactorExposureDriftResult,
    FactorConcentrationResult,
    FactorThresholdEvaluation,
    FactorMonitoringBreach,
    FactorMonitoringEvent,
    MonitoringScope,
    EvaluationFrequency,
    DriftReferenceType,
    DriftClassification,
    ConcentrationStatus,
    ThresholdMetricType,
    ThresholdEvaluationStatus,
    BreachSeverity,
    BreachStatus,
    MonitoringRunStatus,
)
from backend.app.modules.factor_risk.factor_monitoring.schemas import (
    FactorMonitoringConfigCreate,
    FactorExposureTargetCreate,
    FactorThresholdPolicyCreate,
    FactorMonitoringRunRequest,
)
from backend.app.modules.factor_risk.factor_monitoring.repositories.repository import FactorMonitoringRepository
from backend.app.modules.factor_risk.factor_monitoring.calculations.monitoring_math import (
    compute_factor_exposure_drift,
    decompose_exposure_drift_holdings_vs_loadings,
    compute_exposure_based_concentration,
    compute_risk_contribution_based_concentration,
    evaluate_threshold_metric,
    compute_monitoring_trend_statistics,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorModelVersion,
    FactorModelMembership,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    PortfolioFactorExposureSnapshot,
    InstrumentFactorLoading,
    FactorReturnObservation,
    FactorReturnSeries,
)
from backend.app.modules.factor_risk.factor_attribution.models import (
    FactorRiskAttributionRun,
    FactorRiskAttributionComponent,
)
from backend.app.modules.factor_risk.systematic_risk.models import (
    PortfolioSystematicRisk,
)


def compute_deterministic_hash(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class FactorMonitoringService:
    """Business service for M08.08 Factor Monitoring."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FactorMonitoringRepository(session)

    # =========================================================================
    # 1. Configuration & Target Profile Management
    # =========================================================================

    async def create_monitoring_config(self, req: FactorMonitoringConfigCreate, created_by: str = "SYSTEM") -> FactorMonitoringConfig:
        payload = {
            "config_code": req.config_code,
            "portfolio_id": req.portfolio_id,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "frequency": req.evaluation_frequency.value,
            "drift_reference_type": req.drift_reference_type.value,
            "baseline_window": req.historical_baseline_window,
            "persistence": req.persistence_required,
            "recovery": req.recovery_required,
        }
        cfg_hash = compute_deterministic_hash(payload)

        config = FactorMonitoringConfig(
            config_code=req.config_code,
            name=req.name,
            description=req.description,
            portfolio_id=req.portfolio_id,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            evaluation_frequency=req.evaluation_frequency,
            drift_reference_type=req.drift_reference_type,
            historical_baseline_window=req.historical_baseline_window,
            persistence_required=req.persistence_required,
            recovery_required=req.recovery_required,
            config_hash=cfg_hash,
            created_by=created_by,
        )
        return await self.repo.create_monitoring_config(config)

    async def create_exposure_target(self, req: FactorExposureTargetCreate, created_by: str = "SYSTEM") -> FactorExposureTarget:
        payload = {
            "target_code": req.target_code,
            "portfolio_id": req.portfolio_id,
            "factor_model_id": req.factor_model_id,
            "factor_model_version_id": req.factor_model_version_id,
            "components": [
                {
                    "factor_id": c.factor_id,
                    "factor_code": c.factor_code,
                    "target_exposure": str(c.target_exposure),
                    "min_exposure": str(c.min_exposure) if c.min_exposure is not None else None,
                    "max_exposure": str(c.max_exposure) if c.max_exposure is not None else None,
                    "tolerance": str(c.tolerance),
                }
                for c in req.components
            ],
        }
        tgt_hash = compute_deterministic_hash(payload)

        target = FactorExposureTarget(
            target_code=req.target_code,
            name=req.name,
            portfolio_id=req.portfolio_id,
            factor_model_id=req.factor_model_id,
            factor_model_version_id=req.factor_model_version_id,
            target_hash=tgt_hash,
            effective_from=req.effective_from or date.today(),
            effective_to=req.effective_to,
            is_approved=True,
            approved_by=created_by,
        )
        self.session.add(target)
        await self.session.flush()

        for c in req.components:
            comp = FactorExposureTargetComponent(
                target_id=target.target_id,
                factor_id=c.factor_id,
                factor_code=c.factor_code,
                target_exposure=c.target_exposure,
                min_exposure=c.min_exposure,
                max_exposure=c.max_exposure,
                tolerance=c.tolerance,
            )
            self.session.add(comp)

        await self.session.flush()
        await self.session.refresh(target)
        return target

    async def create_threshold_policy(self, req: FactorThresholdPolicyCreate, created_by: str = "SYSTEM") -> FactorThresholdPolicy:
        policy = FactorThresholdPolicy(
            policy_code=req.policy_code,
            name=req.name,
            portfolio_id=req.portfolio_id,
            factor_id=req.factor_id,
            factor_code=req.factor_code,
            metric_type=req.metric_type,
            min_boundary=req.min_boundary,
            max_boundary=req.max_boundary,
            warning_threshold=req.warning_threshold,
            breach_threshold=req.breach_threshold,
            critical_threshold=req.critical_threshold,
            recovery_threshold=req.recovery_threshold,
            persistence_count=req.persistence_count,
            recovery_count=req.recovery_count,
            severity=req.severity,
            policy_precedence=req.policy_precedence,
            created_by=created_by,
        )
        return await self.repo.create_threshold_policy(policy)

    # =========================================================================
    # 2. Main Monitoring Execution Pipeline
    # =========================================================================

    async def run_factor_monitoring(
        self,
        req: FactorMonitoringRunRequest,
        triggered_by: str = "SYSTEM",
    ) -> FactorMonitoringRun:
        """
        Executes the full M08.08 monitoring pipeline:
        1. Resolves approved factor model version & memberships from M08.01.
        2. Resolves current portfolio factor exposures from M08.02.
        3. Resolves historical reference exposures (previous snapshot or baseline) from M08.02.
        4. Resolves approved target profile from M08.08 targets (if applicable).
        5. Computes signed, absolute, percentage, and standardized exposure drift.
        6. Computes Exposure HHI and Risk Contribution HHI (consuming M08.04 if available).
        7. Evaluates threshold policies, utilization, and headroom.
        8. Manages breach lifecycle (new, persistent, recovering, recovered).
        9. Publishes typed monitoring events.
        """
        # Step 1: Resolve Model Version & Factors
        mv_stmt = (
            select(FactorModelVersion)
            .options(selectinload(FactorModelVersion.memberships))
            .where(FactorModelVersion.model_version_id == req.factor_model_version_id)
        )
        mv_res = await self.session.execute(mv_stmt)
        mv = mv_res.scalars().first()
        if not mv:
            raise ValueError(f"Factor model version '{req.factor_model_version_id}' not found")

        factor_map = {m.factor_code: m.factor_id for m in mv.memberships}

        # Step 2: Resolve Current Exposure Snapshot from M08.02
        curr_snap_stmt = (
            select(PortfolioFactorExposureSnapshot)
            .where(
                and_(
                    PortfolioFactorExposureSnapshot.portfolio_id == req.portfolio_id,
                    PortfolioFactorExposureSnapshot.as_of_date <= req.as_of_date,
                )
            )
            .order_by(PortfolioFactorExposureSnapshot.as_of_date.desc(), PortfolioFactorExposureSnapshot.calculation_timestamp.desc())
        )
        curr_snap_res = await self.session.execute(curr_snap_stmt)
        curr_snap_rows = curr_snap_res.scalars().all()

        current_exposures: Dict[str, float] = {}
        curr_date = None
        if curr_snap_rows:
            curr_date = curr_snap_rows[0].as_of_date
            # Group all rows matching this as_of_date
            for row in curr_snap_rows:
                if row.as_of_date == curr_date:
                    current_exposures[row.factor_code] = float(row.exposure_value)

        # If no snapshot in M08.02, fallback to checking instrument loadings on positions
        if not current_exposures:
            inst_loading_stmt = (
                select(InstrumentFactorLoading)
                .where(
                    and_(
                        InstrumentFactorLoading.model_version_id == req.factor_model_version_id,
                        InstrumentFactorLoading.as_of_date <= req.as_of_date,
                    )
                )
            )
            inst_res = await self.session.execute(inst_loading_stmt)
            loadings = inst_res.scalars().all()
            if loadings:
                by_code: Dict[str, List[float]] = {}
                for l in loadings:
                    by_code.setdefault(l.factor_code, []).append(float(l.loading_value))
                current_exposures = {k: sum(v)/len(v) for k, v in by_code.items()}

        # Step 3: Resolve Historical Reference Snapshot
        reference_exposures: Dict[str, float] = {}
        if curr_date is not None:
            prev_snap_stmt = (
                select(PortfolioFactorExposureSnapshot)
                .where(
                    and_(
                        PortfolioFactorExposureSnapshot.portfolio_id == req.portfolio_id,
                        PortfolioFactorExposureSnapshot.as_of_date < curr_date,
                    )
                )
                .order_by(PortfolioFactorExposureSnapshot.as_of_date.desc())
            )
            prev_res = await self.session.execute(prev_snap_stmt)
            prev_rows = prev_res.scalars().all()
            if prev_rows:
                prev_date = prev_rows[0].as_of_date
                for r in prev_rows:
                    if r.as_of_date == prev_date:
                        reference_exposures[r.factor_code] = float(r.exposure_value)

        # If previous snapshot missing, fallback to 0.0 baseline or current_exposures
        for fc in factor_map.keys():
            if fc not in reference_exposures:
                reference_exposures[fc] = current_exposures.get(fc, 0.0)

        # Step 4: Resolve Approved Target Profile
        target_obj = None
        if req.target_id:
            target_obj = await self.repo.get_exposure_target_by_id(req.target_id)
        else:
            target_obj = await self.repo.get_active_target_for_portfolio(
                req.portfolio_id, req.factor_model_version_id, req.as_of_date
            )

        target_map: Dict[str, float] = {}
        target_tol_map: Dict[str, float] = {}
        if target_obj:
            for comp in target_obj.components:
                target_map[comp.factor_code] = float(comp.target_exposure)
                target_tol_map[comp.factor_code] = float(comp.tolerance)

        # Step 5: Compute Exposure Drift
        drift_results = []
        overall_drift_status = "NORMAL"
        for fc, f_id in factor_map.items():
            curr_b = current_exposures.get(fc, 0.0)
            ref_b = reference_exposures.get(fc, curr_b)
            tgt_b = target_map.get(fc)

            drift_calc = compute_factor_exposure_drift(
                current_beta=curr_b,
                reference_beta=ref_b,
                factor_volatility=None,
            )

            # Check target deviation if target exists
            d_class = drift_calc["drift_classification"]
            if tgt_b is not None:
                tgt_diff = abs(curr_b - tgt_b)
                tol = target_tol_map.get(fc, 0.20)
                if tgt_diff > tol:
                    d_class = "TARGET_BREACH"
                    overall_drift_status = "DRIFT_BREACH"

            if d_class in ["HIGH_DRIFT", "CRITICAL_DRIFT", "SIGN_REVERSAL"] and overall_drift_status == "NORMAL":
                overall_drift_status = d_class

            drift_record = FactorExposureDriftResult(
                factor_id=f_id,
                factor_code=fc,
                current_exposure=Decimal(str(round(curr_b, 6))),
                reference_exposure=Decimal(str(round(ref_b, 6))),
                target_exposure=Decimal(str(round(tgt_b, 6))) if tgt_b is not None else None,
                signed_drift=Decimal(str(round(drift_calc["signed_drift"], 6))),
                absolute_drift=Decimal(str(round(drift_calc["absolute_drift"], 6))),
                percentage_drift=Decimal(str(round(drift_calc["percentage_drift"], 4))) if drift_calc["percentage_drift"] is not None else None,
                is_percentage_drift_defined=drift_calc["is_percentage_drift_defined"],
                is_sign_reversal=drift_calc["is_sign_reversal"],
                sign_change_description=drift_calc["sign_change_description"],
                drift_classification=DriftClassification(d_class),
            )
            drift_results.append(drift_record)

        # Step 6: Compute Concentration (Exposure HHI and Risk HHI)
        conc_calc = compute_exposure_based_concentration(current_exposures)

        # Query Risk Contributions from M08.04 if available
        rc_calc = None
        rc_stmt = (
            select(FactorRiskAttributionComponent)
            .join(FactorRiskAttributionRun, FactorRiskAttributionComponent.run_id == FactorRiskAttributionRun.run_id)
            .where(
                and_(
                    FactorRiskAttributionRun.portfolio_id == req.portfolio_id,
                    FactorRiskAttributionRun.as_of_date <= req.as_of_date,
                )
            )
            .order_by(FactorRiskAttributionRun.as_of_date.desc())
        )
        rc_res = await self.session.execute(rc_stmt)
        rc_rows = rc_res.scalars().all()
        if rc_rows:
            rc_dict = {r.factor_code: float(r.volatility_contribution) for r in rc_rows if r.factor_code}
            rc_calc = compute_risk_contribution_based_concentration(rc_dict)

        concentration_obj = FactorConcentrationResult(
            exposure_hhi=Decimal(str(round(conc_calc["hhi"], 6))) if conc_calc["hhi"] is not None else None,
            effective_exposure_factors=Decimal(str(round(conc_calc["effective_factors"], 4))) if conc_calc["effective_factors"] is not None else None,
            top_factor_exposure_share=Decimal(str(round(conc_calc["top_1_share"], 6))) if conc_calc["top_1_share"] is not None else None,
            top_two_exposure_share=Decimal(str(round(conc_calc["top_2_share"], 6))) if conc_calc["top_2_share"] is not None else None,
            top_three_exposure_share=Decimal(str(round(conc_calc["top_3_share"], 6))) if conc_calc["top_3_share"] is not None else None,
            top_exposure_factor=conc_calc["top_factor"],
            risk_hhi=Decimal(str(round(rc_calc["hhi"], 6))) if (rc_calc and rc_calc["hhi"] is not None) else None,
            effective_risk_factors=Decimal(str(round(rc_calc["effective_factors"], 4))) if (rc_calc and rc_calc["effective_factors"] is not None) else None,
            top_factor_risk_share=Decimal(str(round(rc_calc["top_1_share"], 6))) if (rc_calc and rc_calc["top_1_share"] is not None) else None,
            top_two_risk_share=Decimal(str(round(rc_calc["top_2_share"], 6))) if (rc_calc and rc_calc["top_2_share"] is not None) else None,
            top_three_risk_share=Decimal(str(round(rc_calc["top_3_share"], 6))) if (rc_calc and rc_calc["top_3_share"] is not None) else None,
            top_risk_factor=rc_calc["top_risk_driver"] if rc_calc else None,
            concentration_status=ConcentrationStatus(conc_calc["status"]),
        )

        # Step 7: Evaluate Threshold Policies
        policies = await self.repo.list_active_policies_for_portfolio(req.portfolio_id)
        evaluations = []
        active_breach_count = 0
        warning_count = 0
        critical_count = 0
        generated_events = []

        for pol in policies:
            val_to_eval = None
            if pol.metric_type == ThresholdMetricType.ABSOLUTE_FACTOR_EXPOSURE:
                if pol.factor_code and pol.factor_code in current_exposures:
                    val_to_eval = abs(current_exposures[pol.factor_code])
            elif pol.metric_type == ThresholdMetricType.DIRECTIONAL_FACTOR_EXPOSURE:
                if pol.factor_code and pol.factor_code in current_exposures:
                    val_to_eval = current_exposures[pol.factor_code]
            elif pol.metric_type == ThresholdMetricType.TARGET_DEVIATION:
                if pol.factor_code and pol.factor_code in current_exposures and pol.factor_code in target_map:
                    val_to_eval = abs(current_exposures[pol.factor_code] - target_map[pol.factor_code])
            elif pol.metric_type == ThresholdMetricType.EXPOSURE_HHI:
                val_to_eval = conc_calc["hhi"]
            elif pol.metric_type == ThresholdMetricType.EFFECTIVE_FACTOR_COUNT:
                val_to_eval = conc_calc["effective_factors"]
            elif pol.metric_type == ThresholdMetricType.TOP_FACTOR_SHARE:
                val_to_eval = conc_calc["top_1_share"]

            # Query existing breach for state & persistence
            existing_breach = await self.repo.get_active_breach(req.portfolio_id, pol.policy_id, pol.factor_code)
            is_in_breach = existing_breach is not None
            c_breach_count = existing_breach.consecutive_observation_count if existing_breach else 0

            eval_res = evaluate_threshold_metric(
                current_value=val_to_eval,
                warning_threshold=float(pol.warning_threshold) if pol.warning_threshold is not None else None,
                breach_threshold=float(pol.breach_threshold),
                critical_threshold=float(pol.critical_threshold) if pol.critical_threshold is not None else None,
                recovery_threshold=float(pol.recovery_threshold) if pol.recovery_threshold is not None else None,
                min_boundary=float(pol.min_boundary) if pol.min_boundary is not None else None,
                max_boundary=float(pol.max_boundary) if pol.max_boundary is not None else None,
                consecutive_breach_count=c_breach_count,
                consecutive_recovery_count=0,
                persistence_required=pol.persistence_count,
                recovery_required=pol.recovery_count,
                is_active_breach=is_in_breach,
            )

            is_brk = eval_res["is_breach"]
            is_warn = eval_res["is_warning"]
            if is_brk:
                active_breach_count += 1
                if eval_res["evaluation_status"] == "CRITICAL_BREACH":
                    critical_count += 1
            elif is_warn:
                warning_count += 1

            eval_record = FactorThresholdEvaluation(
                policy_id=pol.policy_id,
                factor_code=pol.factor_code,
                metric_type=pol.metric_type,
                measurement_value=Decimal(str(round(val_to_eval, 6))) if val_to_eval is not None else None,
                limit_value=Decimal(str(round(eval_res["limit_value"], 6))) if eval_res["limit_value"] is not None else None,
                utilization_percentage=Decimal(str(round(eval_res["utilization_percentage"], 4))) if eval_res["utilization_percentage"] is not None else None,
                headroom=Decimal(str(round(eval_res["headroom"], 6))) if eval_res["headroom"] is not None else None,
                evaluation_status=ThresholdEvaluationStatus(eval_res["evaluation_status"]),
                is_breach=is_brk,
                is_warning=is_warn,
            )
            evaluations.append(eval_record)

            # Manage Breach Lifecycle
            if is_brk:
                if existing_breach:
                    existing_breach.last_detected_at = datetime.now(timezone.utc)
                    existing_breach.consecutive_observation_count = eval_res["consecutive_breach_count"]
                    existing_breach.current_measurement = eval_record.measurement_value
                    existing_breach.utilization_percentage = eval_record.utilization_percentage
                    if eval_res["evaluation_status"] == "CRITICAL_BREACH":
                        existing_breach.severity = BreachSeverity.CRITICAL
                    await self.repo.create_or_update_breach(existing_breach)
                else:
                    new_breach = FactorMonitoringBreach(
                        portfolio_id=req.portfolio_id,
                        policy_id=pol.policy_id,
                        factor_code=pol.factor_code,
                        metric_type=pol.metric_type,
                        severity=BreachSeverity.CRITICAL if eval_res["evaluation_status"] == "CRITICAL_BREACH" else pol.severity,
                        breach_status=BreachStatus.ACTIVE,
                        current_measurement=eval_record.measurement_value,
                        threshold_value=pol.breach_threshold,
                        utilization_percentage=eval_record.utilization_percentage,
                        first_detected_at=datetime.now(timezone.utc),
                        last_detected_at=datetime.now(timezone.utc),
                        consecutive_observation_count=1,
                    )
                    await self.repo.create_or_update_breach(new_breach)

                    # Create Event for new breach
                    dedup_key = f"{req.portfolio_id}:{pol.policy_id}:{pol.factor_code or 'ALL'}:{req.as_of_date.isoformat()}"
                    event = FactorMonitoringEvent(
                        portfolio_id=req.portfolio_id,
                        factor_code=pol.factor_code,
                        event_type=f"{pol.metric_type.value}_BREACH",
                        severity=new_breach.severity,
                        message=f"Factor monitoring breach detected on policy {pol.name}: value {val_to_eval} exceeded threshold {pol.breach_threshold}",
                        event_payload={"policy_id": pol.policy_id, "measurement": val_to_eval, "threshold": float(pol.breach_threshold)},
                        deduplication_key=dedup_key,
                        is_published=True,
                    )
                    generated_events.append(event)
            elif existing_breach and eval_res["evaluation_status"] == "RECOVERED":
                existing_breach.breach_status = BreachStatus.RECOVERED
                existing_breach.recovered_at = datetime.now(timezone.utc)
                await self.repo.create_or_update_breach(existing_breach)

        # Step 8: Assemble & Persist Monitoring Run Header
        run_payload = {
            "portfolio_id": req.portfolio_id,
            "model_version_id": req.factor_model_version_id,
            "as_of_date": req.as_of_date.isoformat(),
            "active_breaches": active_breach_count,
            "warnings": warning_count,
            "exposures": current_exposures,
        }
        res_hash = compute_deterministic_hash(run_payload)

        mon_run = FactorMonitoringRun(
            portfolio_id=req.portfolio_id,
            factor_model_version_id=req.factor_model_version_id,
            config_id=req.config_id,
            target_id=target_obj.target_id if target_obj else None,
            as_of_date=req.as_of_date,
            status=MonitoringRunStatus.COMPLETED if active_breach_count == 0 else MonitoringRunStatus.COMPLETED_WITH_WARNINGS,
            drift_status=overall_drift_status,
            concentration_status=ConcentrationStatus(conc_calc["status"]),
            has_active_breaches=bool(active_breach_count > 0),
            active_breach_count=active_breach_count,
            warning_count=warning_count,
            critical_breach_count=critical_count,
            input_freshness={
                "exposure_date": curr_date.isoformat() if curr_date else req.as_of_date.isoformat(),
                "model_version_id": req.factor_model_version_id,
                "is_current": True,
            },
            result_hash=res_hash,
            created_by=triggered_by,
        )

        for d in drift_results:
            d.run = mon_run
            mon_run.drifts.append(d)

        for e in evaluations:
            e.run = mon_run
            mon_run.evaluations.append(e)

        saved_run = await self.repo.create_monitoring_run(mon_run)
        concentration_obj.run_id = saved_run.run_id
        await self.repo.create_concentration_result(concentration_obj)

        for evt in generated_events:
            evt.run_id = saved_run.run_id
            await self.repo.create_monitoring_event(evt)

        await self.session.commit()
        return await self.repo.get_monitoring_run_by_id(saved_run.run_id)

    # =========================================================================
    # 3. Breach & Historical Summary Retrieval
    # =========================================================================

    async def acknowledge_breach(self, breach_id: str, user_id: str, note: Optional[str] = None) -> FactorMonitoringBreach:
        breach = await self.repo.get_breach_by_id(breach_id)
        if not breach:
            raise ValueError(f"Breach '{breach_id}' not found")
        breach.breach_status = BreachStatus.ACKNOWLEDGED
        breach.acknowledged_at = datetime.now(timezone.utc)
        breach.acknowledged_by = user_id
        return await self.repo.create_or_update_breach(breach)
