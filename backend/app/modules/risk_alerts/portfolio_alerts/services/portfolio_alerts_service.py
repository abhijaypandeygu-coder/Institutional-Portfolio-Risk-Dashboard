"""
Core service implementation for M12.04 Portfolio Alerts.

Implements all 17 features:
- M12.04.01 Portfolio Loss Detection
- M12.04.02 Intraday Loss Monitoring
- M12.04.03 Period Loss Monitoring
- M12.04.04 Loss Attribution & Context
- M12.04.05 Portfolio Concentration Change Detection
- M12.04.06 Instrument & Issuer Concentration Alerts
- M12.04.07 Sector & Industry Concentration Alerts
- M12.04.08 Portfolio Composition Change Monitoring
- M12.04.09 Position Movement Detection
- M12.04.10 Unusual Position Activity Detection
- M12.04.11 Cash Movement Alerts
- M12.04.12 Reconciliation Break Alerting
- M12.04.13 Reconciliation Break Persistence Monitoring
- M12.04.14 Portfolio Alert Rule Configuration
- M12.04.15 Portfolio Alert Evidence & Context
- M12.04.16 Portfolio Alert Dashboard
- M12.04.17 Portfolio Alert Analytics
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_alerts.portfolio_alerts.models.portfolio_alerts_models import (
    PortfolioAlertRule,
    PortfolioAlertRuleVersion,
    PortfolioAlertEvent,
    PortfolioAlertEvidence,
    PortfolioAlertOccurrence,
    PortfolioAlertBaseline,
    PortfolioAlertRuleEvaluation,
    PortfolioAlertReconciliationLink,
)
from backend.app.modules.risk_alerts.portfolio_alerts.repositories.portfolio_alerts_repository import PortfolioAlertsRepository
from backend.app.modules.risk_alerts.portfolio_alerts.schemas.portfolio_alerts_schemas import (
    PortfolioAlertRuleCreate,
    PortfolioAlertRuleUpdate,
    PortfolioLossEvaluationRequest,
    ConcentrationEvaluationRequest,
    PositionMovementEvaluationRequest,
    CashMovementEvaluationRequest,
    ReconciliationBreakEvaluationRequest,
)
from backend.app.modules.risk_alerts.portfolio_alerts.calculations.portfolio_alerts_math import (
    calculate_portfolio_loss,
    calculate_loss_velocity,
    calculate_loss_attribution,
    calculate_concentration_changes,
    calculate_hhi,
    classify_position_movement,
    calculate_cash_movement,
    calculate_reconciliation_break_magnitude,
    generate_portfolio_event_fingerprint,
)


class PortfolioAlertsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PortfolioAlertsRepository(session)

    # -------------------------------------------------------------
    # M12.04.14 Rule Configuration
    # -------------------------------------------------------------
    async def create_rule(self, req: PortfolioAlertRuleCreate) -> PortfolioAlertRule:
        rule_id = f"PRULE_{uuid.uuid4().hex[:12].upper()}"
        version_id = f"PVER_{uuid.uuid4().hex[:12].upper()}"

        rule = PortfolioAlertRule(
            id=rule_id,
            rule_code=req.rule_code,
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            rule_name=req.rule_name,
            description=req.description,
            category=req.category,
            event_type=req.event_type,
            metric_name=req.metric_name,
            operator=req.operator,
            threshold_value=req.threshold_value,
            threshold_currency=req.threshold_currency,
            threshold_unit=req.threshold_unit,
            baseline_type=req.baseline_type,
            evaluation_interval=req.evaluation_interval,
            persistence_count=req.persistence_count,
            cooldown_seconds=req.cooldown_seconds,
            severity_preference=req.severity_preference,
            rule_version=1,
            enabled=True,
            created_by=req.created_by,
        )

        version = PortfolioAlertRuleVersion(
            id=version_id,
            rule_id=rule_id,
            version_number=1,
            configuration_json=req.model_dump(mode="json"),
            change_reason="Initial rule configuration",
            changed_by=req.created_by,
            is_active=True,
        )

        rule.versions.append(version)
        return await self.repo.create_rule(rule)

    async def update_rule(self, rule_id: str, req: PortfolioAlertRuleUpdate) -> Optional[PortfolioAlertRule]:
        rule = await self.repo.get_rule_by_id(rule_id)
        if not rule:
            return None

        next_ver = len(rule.versions) + 1 if rule.versions else 1
        rule.rule_version = next_ver

        if req.rule_name is not None:
            rule.rule_name = req.rule_name
        if req.description is not None:
            rule.description = req.description
        if req.threshold_value is not None:
            rule.threshold_value = req.threshold_value
        if req.threshold_unit is not None:
            rule.threshold_unit = req.threshold_unit
        if req.cooldown_seconds is not None:
            rule.cooldown_seconds = req.cooldown_seconds
        if req.enabled is not None:
            rule.enabled = req.enabled

        version = PortfolioAlertRuleVersion(
            id=f"PVER_{uuid.uuid4().hex[:12].upper()}",
            rule_id=rule.id,
            version_number=next_ver,
            configuration_json=req.model_dump(mode="json"),
            change_reason=req.change_reason,
            changed_by=req.changed_by,
            is_active=True,
        )
        rule.versions.append(version)
        await self.session.flush()
        return rule

    async def list_rules(self, portfolio_id: Optional[str] = None, category: Optional[str] = None) -> List[PortfolioAlertRule]:
        return await self.repo.list_rules(portfolio_id=portfolio_id, category=category)

    # -------------------------------------------------------------
    # M12.04.01 – M12.04.04 Portfolio Loss Monitoring & Attribution
    # -------------------------------------------------------------
    async def evaluate_portfolio_loss(self, req: PortfolioLossEvaluationRequest) -> Optional[PortfolioAlertEvent]:
        rule = await self.repo.get_rule_by_code(req.rule_code)
        if not rule or not rule.enabled:
            return None

        rule_version_id = rule.versions[0].id if rule.versions else "V1"
        threshold_val = rule.threshold_value
        threshold_unit = rule.threshold_unit

        pnl, pnl_pct, loss_mag, nav_loss_pct = calculate_portfolio_loss(
            current_val=req.current_valuation,
            reference_val=req.reference_valuation,
            reference_nav=req.reference_nav,
        )

        # Quality check: Reject stale / missing valuation
        if req.quality_status in ["INVALID", "STALE", "MISSING"]:
            eval_rec = PortfolioAlertRuleEvaluation(
                id=f"PEVAL_{uuid.uuid4().hex[:12].upper()}",
                rule_id=rule.id,
                rule_version=rule.rule_version,
                portfolio_id=req.portfolio_id,
                threshold_value=threshold_val,
                evaluation_result="SUPPRESSED",
                eligibility_status=req.quality_status,
                suppression_reason=f"Valuation quality was {req.quality_status}",
            )
            await self.repo.save_evaluation(eval_rec)
            return None

        triggered = False
        observed_val = loss_mag
        if threshold_unit == "CURRENCY":
            observed_val = loss_mag
            if loss_mag >= threshold_val:
                triggered = True
        elif threshold_unit == "PERCENT_NAV" and nav_loss_pct is not None:
            observed_val = nav_loss_pct
            if nav_loss_pct >= threshold_val:
                triggered = True
        elif threshold_unit == "PERCENT":
            observed_val = abs(pnl_pct) if pnl < Decimal("0") else Decimal("0")
            if pnl < Decimal("0") and abs(pnl_pct) >= threshold_val:
                triggered = True

        eval_rec = PortfolioAlertRuleEvaluation(
            id=f"PEVAL_{uuid.uuid4().hex[:12].upper()}",
            rule_id=rule.id,
            rule_version=rule.rule_version,
            portfolio_id=req.portfolio_id,
            observed_value=observed_val,
            threshold_value=threshold_val,
            evaluation_result="TRIGGERED" if triggered else "NOT_TRIGGERED",
            eligibility_status="ELIGIBLE",
            source_snapshot_id=req.source_snapshot_id,
        )
        await self.repo.save_evaluation(eval_rec)

        if not triggered:
            return None

        window_ts_str = req.event_timestamp.strftime("%Y%m%d%H%M")
        fingerprint = generate_portfolio_event_fingerprint("PORTFOLIO_LOSS", rule.event_type, req.portfolio_id, None, window_ts_str)

        existing = await self.repo.get_event_by_fingerprint(fingerprint)
        if existing:
            existing.last_updated_at = datetime.utcnow()
            occ = PortfolioAlertOccurrence(
                id=f"POCC_{uuid.uuid4().hex[:12].upper()}",
                portfolio_alert_event_id=existing.id,
                observed_value=observed_val,
                occurrence_metadata={"pnl": str(pnl), "loss_mag": str(loss_mag)},
            )
            existing.occurrences.append(occ)
            await self.session.flush()
            return existing

        event_id = f"PEVT_{uuid.uuid4().hex[:12].upper()}"
        alert_code = f"EVT-LOSS-{req.portfolio_id}-{uuid.uuid4().hex[:6].upper()}"
        summary = (
            f"Portfolio {req.portfolio_id} experienced a material loss of {req.currency} {loss_mag:,.2f} "
            f"({nav_loss_pct or pnl_pct:.2f}% of NAV), exceeding configured threshold {threshold_val:.2f} {threshold_unit}."
        )

        alert_evt = PortfolioAlertEvent(
            id=event_id,
            alert_code=alert_code,
            portfolio_id=req.portfolio_id,
            category="PORTFOLIO_LOSS",
            event_type=rule.event_type,
            observed_value=observed_val,
            baseline_value=req.reference_valuation,
            threshold_value=threshold_val,
            delta_value=-loss_mag,
            currency=req.currency,
            source_module="M05.03_POSITION_VALUATION",
            source_record_id=req.source_snapshot_id,
            event_timestamp=req.event_timestamp,
            detected_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
            event_state="ACTIVE",
            evidence_summary=summary,
            idempotency_key=fingerprint,
            rule_version_id=rule_version_id,
        )

        # Loss evidence
        ev1 = PortfolioAlertEvidence(
            id=f"PEVI_{uuid.uuid4().hex[:12].upper()}",
            portfolio_alert_event_id=event_id,
            evidence_type="PORTFOLIO_LOSS",
            metric_name="portfolio_loss_amount",
            observed_value=loss_mag,
            baseline_value=req.reference_valuation,
            threshold_value=threshold_val if threshold_unit == "CURRENCY" else None,
            unit=req.currency,
            currency=req.currency,
            evidence_payload={"pnl": str(pnl), "nav_loss_pct": str(nav_loss_pct)},
        )
        alert_evt.evidence_items.append(ev1)

        # Loss attribution evidence if available
        if req.instrument_pnls:
            inst_contribs, contrib_pcts, residual = calculate_loss_attribution(pnl, req.instrument_pnls, req.reference_nav)
            ev2 = PortfolioAlertEvidence(
                id=f"PEVI_{uuid.uuid4().hex[:12].upper()}",
                portfolio_alert_event_id=event_id,
                evidence_type="LOSS_ATTRIBUTION",
                metric_name="instrument_loss_attribution",
                observed_value=loss_mag,
                unit="CURRENCY",
                currency=req.currency,
                evidence_payload={
                    "instrument_pnls": {k: str(v) for k, v in inst_contribs.items()},
                    "contrib_pcts_nav": {k: str(v) for k, v in contrib_pcts.items()},
                    "residual": str(residual),
                },
            )
            alert_evt.evidence_items.append(ev2)

        await self.repo.save_alert_event(alert_evt)
        return alert_evt

    # -------------------------------------------------------------
    # M12.04.05 – M12.04.07 Concentration Change Monitoring
    # -------------------------------------------------------------
    async def evaluate_concentration_change(self, req: ConcentrationEvaluationRequest) -> Optional[PortfolioAlertEvent]:
        rule = await self.repo.get_rule_by_code(req.rule_code)
        if not rule or not rule.enabled:
            return None

        rule_version_id = rule.versions[0].id if rule.versions else "V1"
        threshold_val = rule.threshold_value
        threshold_unit = rule.threshold_unit  # PERCENT_POINTS or HHI

        delta_pp, rel_change = calculate_concentration_changes(req.current_weight, req.baseline_weight)

        triggered = False
        observed_val = delta_pp
        if threshold_unit == "PERCENT_POINTS":
            observed_val = delta_pp
            if delta_pp >= threshold_val:
                triggered = True
        elif threshold_unit == "HHI" and req.hhi_weights:
            hhi = calculate_hhi(req.hhi_weights)
            observed_val = hhi
            if hhi >= threshold_val:
                triggered = True

        eval_rec = PortfolioAlertRuleEvaluation(
            id=f"PEVAL_{uuid.uuid4().hex[:12].upper()}",
            rule_id=rule.id,
            rule_version=rule.rule_version,
            portfolio_id=req.portfolio_id,
            observed_value=observed_val,
            threshold_value=threshold_val,
            evaluation_result="TRIGGERED" if triggered else "NOT_TRIGGERED",
            eligibility_status="ELIGIBLE",
        )
        await self.repo.save_evaluation(eval_rec)

        if not triggered:
            return None

        window_ts_str = req.event_timestamp.strftime("%Y%m%d%H%M")
        fingerprint = generate_portfolio_event_fingerprint("CONCENTRATION", rule.event_type, req.portfolio_id, req.entity_key, window_ts_str)

        existing = await self.repo.get_event_by_fingerprint(fingerprint)
        if existing:
            existing.last_updated_at = datetime.utcnow()
            await self.session.flush()
            return existing

        event_id = f"PEVT_{uuid.uuid4().hex[:12].upper()}"
        summary = (
            f"Concentration in {req.entity_key} for portfolio {req.portfolio_id} increased by {delta_pp:+.2f} pp "
            f"(from {req.baseline_weight * 100:.1f}% to {req.current_weight * 100:.1f}%), exceeding tolerance of {threshold_val:.2f} {threshold_unit}."
        )

        alert_evt = PortfolioAlertEvent(
            id=event_id,
            alert_code=f"EVT-CONC-{req.portfolio_id}-{uuid.uuid4().hex[:6].upper()}",
            portfolio_id=req.portfolio_id,
            category="CONCENTRATION",
            event_type=rule.event_type,
            observed_value=observed_val,
            baseline_value=req.baseline_weight * Decimal("100"),
            threshold_value=threshold_val,
            delta_value=delta_pp,
            currency="PERCENT",
            source_module="M06_EXPOSURE_MANAGEMENT",
            event_timestamp=req.event_timestamp,
            detected_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
            event_state="ACTIVE",
            evidence_summary=summary,
            idempotency_key=fingerprint,
            rule_version_id=rule_version_id,
        )

        ev = PortfolioAlertEvidence(
            id=f"PEVI_{uuid.uuid4().hex[:12].upper()}",
            portfolio_alert_event_id=event_id,
            evidence_type="CONCENTRATION_WEIGHT",
            metric_name="concentration_percentage_points",
            observed_value=delta_pp,
            baseline_value=req.baseline_weight * Decimal("100"),
            threshold_value=threshold_val,
            unit="PERCENT_POINTS",
            evidence_payload={"entity_key": req.entity_key, "current_weight": str(req.current_weight)},
        )
        alert_evt.evidence_items.append(ev)

        await self.repo.save_alert_event(alert_evt)
        return alert_evt

    # -------------------------------------------------------------
    # M12.04.09 & M12.04.10 Position Movement & Unusual Activity
    # -------------------------------------------------------------
    async def evaluate_position_movement(self, req: PositionMovementEvaluationRequest) -> Optional[PortfolioAlertEvent]:
        rule = await self.repo.get_rule_by_code(req.rule_code)
        if not rule or not rule.enabled:
            return None

        rule_version_id = rule.versions[0].id if rule.versions else "V1"
        threshold_val = rule.threshold_value
        threshold_unit = rule.threshold_unit  # SHARES, PERCENT_CHANGE, or PERCENT_NAV

        movement_type, delta_q, pct_change = classify_position_movement(req.prior_quantity, req.current_quantity)

        triggered = False
        observed_val = abs(delta_q)
        if threshold_unit == "SHARES":
            observed_val = abs(delta_q)
            if abs(delta_q) >= threshold_val:
                triggered = True
        elif threshold_unit == "PERCENT_CHANGE" and pct_change is not None:
            observed_val = abs(pct_change)
            if abs(pct_change) >= threshold_val:
                triggered = True
        elif threshold_unit == "PERCENT_NAV" and req.current_notional and req.reference_nav and req.reference_nav > Decimal("0"):
            pct_nav = ((req.current_notional / req.reference_nav) * Decimal("100")).quantize(Decimal("0.01"))
            observed_val = pct_nav
            if pct_nav >= threshold_val:
                triggered = True

        eval_rec = PortfolioAlertRuleEvaluation(
            id=f"PEVAL_{uuid.uuid4().hex[:12].upper()}",
            rule_id=rule.id,
            rule_version=rule.rule_version,
            portfolio_id=req.portfolio_id,
            observed_value=observed_val,
            threshold_value=threshold_val,
            evaluation_result="TRIGGERED" if triggered else "NOT_TRIGGERED",
            eligibility_status="ELIGIBLE",
        )
        await self.repo.save_evaluation(eval_rec)

        if not triggered:
            return None

        window_ts_str = req.event_timestamp.strftime("%Y%m%d%H%M")
        fingerprint = generate_portfolio_event_fingerprint("POSITION_MOVEMENT", movement_type, req.portfolio_id, req.instrument_id, window_ts_str)

        existing = await self.repo.get_event_by_fingerprint(fingerprint)
        if existing:
            existing.last_updated_at = datetime.utcnow()
            await self.session.flush()
            return existing

        event_id = f"PEVT_{uuid.uuid4().hex[:12].upper()}"
        summary = (
            f"Position movement ({movement_type}) in {req.instrument_id} for portfolio {req.portfolio_id}: "
            f"Quantity changed by {delta_q:+,.0f} shares ({req.prior_quantity:,.0f} -> {req.current_quantity:,.0f}), "
            f"exceeding threshold {threshold_val:.0f} {threshold_unit}."
        )

        alert_evt = PortfolioAlertEvent(
            id=event_id,
            alert_code=f"EVT-POS-{req.portfolio_id}-{uuid.uuid4().hex[:6].upper()}",
            portfolio_id=req.portfolio_id,
            category="POSITION_MOVEMENT",
            event_type=movement_type,
            observed_value=observed_val,
            baseline_value=req.prior_quantity,
            threshold_value=threshold_val,
            delta_value=delta_q,
            currency="SHARES",
            source_module="M05.02_POSITION_MANAGEMENT",
            source_record_id=req.source_transaction_id,
            event_timestamp=req.event_timestamp,
            detected_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
            event_state="ACTIVE",
            evidence_summary=summary,
            idempotency_key=fingerprint,
            rule_version_id=rule_version_id,
        )

        ev = PortfolioAlertEvidence(
            id=f"PEVI_{uuid.uuid4().hex[:12].upper()}",
            portfolio_alert_event_id=event_id,
            evidence_type="POSITION_MOVEMENT",
            metric_name="position_quantity_delta",
            observed_value=delta_q,
            baseline_value=req.prior_quantity,
            threshold_value=threshold_val,
            unit="SHARES",
            evidence_payload={"movement_type": movement_type, "pct_change": str(pct_change)},
        )
        alert_evt.evidence_items.append(ev)

        await self.repo.save_alert_event(alert_evt)
        return alert_evt

    # -------------------------------------------------------------
    # M12.04.11 Cash Movement Alerts
    # -------------------------------------------------------------
    async def evaluate_cash_movement(self, req: CashMovementEvaluationRequest) -> Optional[PortfolioAlertEvent]:
        rule = await self.repo.get_rule_by_code(req.rule_code)
        if not rule or not rule.enabled:
            return None

        rule_version_id = rule.versions[0].id if rule.versions else "V1"
        threshold_val = rule.threshold_value
        threshold_unit = rule.threshold_unit  # CURRENCY or PERCENT_NAV

        delta_cash, pct_nav = calculate_cash_movement(req.current_cash, req.prior_cash, req.reference_nav)

        triggered = False
        observed_val = abs(delta_cash)
        if threshold_unit == "CURRENCY":
            observed_val = abs(delta_cash)
            if abs(delta_cash) >= threshold_val:
                triggered = True
        elif threshold_unit == "PERCENT_NAV" and pct_nav is not None:
            observed_val = pct_nav
            if pct_nav >= threshold_val:
                triggered = True

        eval_rec = PortfolioAlertRuleEvaluation(
            id=f"PEVAL_{uuid.uuid4().hex[:12].upper()}",
            rule_id=rule.id,
            rule_version=rule.rule_version,
            portfolio_id=req.portfolio_id,
            observed_value=observed_val,
            threshold_value=threshold_val,
            evaluation_result="TRIGGERED" if triggered else "NOT_TRIGGERED",
            eligibility_status="ELIGIBLE",
        )
        await self.repo.save_evaluation(eval_rec)

        if not triggered:
            return None

        window_ts_str = req.event_timestamp.strftime("%Y%m%d%H%M")
        fingerprint = generate_portfolio_event_fingerprint("CASH_MOVEMENT", req.movement_type, req.portfolio_id, None, window_ts_str)

        existing = await self.repo.get_event_by_fingerprint(fingerprint)
        if existing:
            existing.last_updated_at = datetime.utcnow()
            await self.session.flush()
            return existing

        event_id = f"PEVT_{uuid.uuid4().hex[:12].upper()}"
        summary = (
            f"Cash movement ({req.movement_type}) for portfolio {req.portfolio_id}: "
            f"Balance shifted by {req.currency} {delta_cash:+,.2f} ({req.prior_cash:,.2f} -> {req.current_cash:,.2f}), "
            f"exceeding threshold {threshold_val:,.2f} {threshold_unit}."
        )

        alert_evt = PortfolioAlertEvent(
            id=event_id,
            alert_code=f"EVT-CASH-{req.portfolio_id}-{uuid.uuid4().hex[:6].upper()}",
            portfolio_id=req.portfolio_id,
            category="CASH_MOVEMENT",
            event_type=req.movement_type,
            observed_value=observed_val,
            baseline_value=req.prior_cash,
            threshold_value=threshold_val,
            delta_value=delta_cash,
            currency=req.currency,
            source_module="M05.04_CASH_MANAGEMENT",
            event_timestamp=req.event_timestamp,
            detected_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
            event_state="ACTIVE",
            evidence_summary=summary,
            idempotency_key=fingerprint,
            rule_version_id=rule_version_id,
        )

        ev = PortfolioAlertEvidence(
            id=f"PEVI_{uuid.uuid4().hex[:12].upper()}",
            portfolio_alert_event_id=event_id,
            evidence_type="CASH_FLOW",
            metric_name="cash_balance_delta",
            observed_value=delta_cash,
            baseline_value=req.prior_cash,
            threshold_value=threshold_val,
            unit=req.currency,
            currency=req.currency,
            evidence_payload={"pct_nav": str(pct_nav) if pct_nav else None},
        )
        alert_evt.evidence_items.append(ev)

        await self.repo.save_alert_event(alert_evt)
        return alert_evt

    # -------------------------------------------------------------
    # M12.04.12 & M12.04.13 Reconciliation Break Alerting
    # -------------------------------------------------------------
    async def evaluate_reconciliation_break(self, req: ReconciliationBreakEvaluationRequest) -> Optional[PortfolioAlertEvent]:
        rule = await self.repo.get_rule_by_code(req.rule_code)
        if not rule or not rule.enabled:
            return None

        rule_version_id = rule.versions[0].id if rule.versions else "V1"
        threshold_val = rule.threshold_value
        threshold_unit = rule.threshold_unit  # CURRENCY, SHARES, or PERCENT

        signed_break, break_mag, rel_break_pct = calculate_reconciliation_break_magnitude(
            req.internal_value, req.external_value, req.reference_value
        )

        triggered = False
        observed_val = break_mag
        if threshold_unit in ["CURRENCY", "SHARES"]:
            observed_val = break_mag
            if break_mag >= threshold_val:
                triggered = True
        elif threshold_unit == "PERCENT" and rel_break_pct is not None:
            observed_val = rel_break_pct
            if rel_break_pct >= threshold_val:
                triggered = True

        eval_rec = PortfolioAlertRuleEvaluation(
            id=f"PEVAL_{uuid.uuid4().hex[:12].upper()}",
            rule_id=rule.id,
            rule_version=rule.rule_version,
            portfolio_id=req.portfolio_id,
            observed_value=observed_val,
            threshold_value=threshold_val,
            evaluation_result="TRIGGERED" if triggered else "NOT_TRIGGERED",
            eligibility_status="ELIGIBLE",
            source_snapshot_id=req.reconciliation_break_id,
        )
        await self.repo.save_evaluation(eval_rec)

        if not triggered:
            return None

        window_ts_str = req.event_timestamp.strftime("%Y%m%d%H%M")
        fingerprint = generate_portfolio_event_fingerprint("RECONCILIATION_BREAK", req.break_category, req.portfolio_id, req.reconciliation_break_id, window_ts_str)

        existing = await self.repo.get_event_by_fingerprint(fingerprint)
        if existing:
            existing.last_updated_at = datetime.utcnow()
            await self.session.flush()
            return existing

        event_id = f"PEVT_{uuid.uuid4().hex[:12].upper()}"
        summary = (
            f"Material reconciliation break ({req.break_category}) detected for portfolio {req.portfolio_id}: "
            f"Internal={req.internal_value:,.2f}, External={req.external_value:,.2f} (Discrepancy: {break_mag:,.2f} {req.currency}), "
            f"exceeding tolerance of {threshold_val:,.2f} {threshold_unit}."
        )

        alert_evt = PortfolioAlertEvent(
            id=event_id,
            alert_code=f"EVT-REC-{req.portfolio_id}-{uuid.uuid4().hex[:6].upper()}",
            portfolio_id=req.portfolio_id,
            category="RECONCILIATION_BREAK",
            event_type=req.break_category,
            observed_value=observed_val,
            baseline_value=req.external_value,
            threshold_value=threshold_val,
            delta_value=signed_break,
            currency=req.currency,
            source_module="M05.06_PORTFOLIO_RECONCILIATION",
            source_record_id=req.reconciliation_break_id,
            event_timestamp=req.event_timestamp,
            detected_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
            event_state="ACTIVE",
            evidence_summary=summary,
            idempotency_key=fingerprint,
            rule_version_id=rule_version_id,
        )

        ev = PortfolioAlertEvidence(
            id=f"PEVI_{uuid.uuid4().hex[:12].upper()}",
            portfolio_alert_event_id=event_id,
            evidence_type="RECONCILIATION_BREAK",
            metric_name="reconciliation_break_magnitude",
            observed_value=break_mag,
            baseline_value=req.external_value,
            threshold_value=threshold_val,
            unit=req.currency,
            currency=req.currency,
            source_reference=req.reconciliation_break_id,
            evidence_payload={"internal_value": str(req.internal_value), "external_value": str(req.external_value)},
        )
        alert_evt.evidence_items.append(ev)

        # Explicit M05.06 link
        rec_link = PortfolioAlertReconciliationLink(
            id=f"PRL_{uuid.uuid4().hex[:12].upper()}",
            portfolio_alert_event_id=event_id,
            reconciliation_break_id=req.reconciliation_break_id,
            break_category=req.break_category,
            break_magnitude=break_mag,
            relationship_type="PRIMARY",
        )
        alert_evt.reconciliation_links.append(rec_link)

        await self.repo.save_alert_event(alert_evt)
        return alert_evt

    # -------------------------------------------------------------
    # M12.04.16 Dashboard & Overview
    # -------------------------------------------------------------
    async def get_overview(self, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        counts = await self.repo.get_overview_counts(portfolio_id)
        counts["timestamp"] = datetime.utcnow()
        return counts

    async def list_events(
        self,
        portfolio_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[PortfolioAlertEvent]:
        return await self.repo.list_events(portfolio_id=portfolio_id, category=category, limit=limit)

    async def get_event_detail(self, event_id: str) -> Optional[PortfolioAlertEvent]:
        return await self.repo.get_event_by_id(event_id)

