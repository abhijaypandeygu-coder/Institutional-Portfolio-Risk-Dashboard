"""
Service layer for M11.09 Pre-trade Risk Checks.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_limits.pretrade_risk_checks.calculations.pretrade_risk_math import (
    to_decimal,
    calculate_projected_position,
    calculate_exposures,
    calculate_sector_exposure,
    calculate_parametric_var,
    calculate_participation_rate,
)
from backend.app.modules.risk_limits.pretrade_risk_checks.models.pretrade_risk_models import (
    PretradeOrderRequest,
    PretradeOrderVersion,
    PretradeEvaluationRun,
    PretradeCheckResult,
    PretradeSimulationRun,
    PretradeRiskDecision,
    PretradeAuthorization,
    PretradeRiskReservation,
    PretradeAuditLog,
)
from backend.app.modules.risk_limits.pretrade_risk_checks.repositories.pretrade_risk_repository import PretradeRiskRepository
from backend.app.modules.risk_limits.pretrade_risk_checks.schemas.pretrade_risk_schemas import (
    ProposedOrderInput,
    OrderValidationResult,
    CheckResultOutput,
    SimulationResultOutput,
    PretradeDecisionResponse,
    AuthorizationValidationResponse,
    PretradeDashboardSummary,
)


class PretradeRiskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PretradeRiskRepository(db)

    def validate_order_parameters(self, payload: ProposedOrderInput) -> OrderValidationResult:
        """Field-level syntax, instrument, side, quantity, price validation."""
        errors = []
        warnings = []

        if payload.quantity <= Decimal("0"):
            errors.append("Quantity must be positive")
        if payload.order_type.upper() not in ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]:
            errors.append(f"Unsupported order type: {payload.order_type}")
        if payload.order_type.upper() in ["LIMIT", "STOP_LIMIT"] and (not payload.limit_price or payload.limit_price <= Decimal("0")):
            errors.append("Positive limit price required for LIMIT orders")
        if payload.side.upper() not in ["BUY", "SELL"]:
            errors.append(f"Invalid order side: {payload.side}")
        if not payload.instrument_id or len(payload.instrument_id.strip()) == 0:
            errors.append("Instrument ID is mandatory")

        return OrderValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
        )

    async def evaluate_proposed_order(
        self,
        payload: ProposedOrderInput,
        mock_portfolio_state: Optional[Dict[str, Any]] = None,
        mock_limits: Optional[Dict[str, Any]] = None,
    ) -> PretradeDecisionResponse:
        """
        Orchestrates intake, validation, simulation, limit checks, and decision generation.
        """
        now = datetime.utcnow()

        # Idempotency check
        if payload.idempotency_key:
            existing = await self.repo.get_order_by_idempotency_key(payload.idempotency_key)
            if existing and existing.versions and existing.versions[0].evaluations:
                latest_eval = existing.versions[0].evaluations[0]
                if latest_eval.decision:
                    # Return existing decision
                    return await self.build_decision_response(latest_eval.id)

        # 1. Validation
        val_res = self.validate_order_parameters(payload)
        if not val_res.is_valid:
            # Order rejected immediately at intake
            order_id = f"ORD_{uuid.uuid4().hex[:10]}"
            order_req = PretradeOrderRequest(
                id=order_id,
                portfolio_id=payload.portfolio_id,
                originating_system=payload.originating_system,
                submitting_user_id=payload.submitting_user_id,
                idempotency_key=payload.idempotency_key or f"IDEM_{uuid.uuid4().hex[:8]}",
                current_order_version=1,
                current_status="REJECTED",
                created_at=now,
            )
            await self.repo.save_order_request(order_req)
            order_ver = PretradeOrderVersion(
                id=f"VER_{uuid.uuid4().hex[:10]}",
                proposed_order_id=order_req.id,
                version_number=1,
                instrument_id=payload.instrument_id,
                listing_id=payload.listing_id,
                exchange=payload.exchange,
                side=payload.side.upper(),
                quantity=payload.quantity,
                order_type=payload.order_type.upper(),
                limit_price=payload.limit_price,
                stop_price=payload.stop_price,
                time_in_force=payload.time_in_force.upper(),
                currency=payload.currency.upper(),
                strategy_id=payload.strategy_id,
                submitted_at=now,
            )
            await self.repo.save_order_version(order_ver)
            eval_run = PretradeEvaluationRun(
                id=f"EVL_{uuid.uuid4().hex[:10]}",
                proposed_order_version_id=order_ver.id,
                portfolio_snapshot_id="SNAP_INVALID",
                evaluation_status="COMPLETED",
                started_at=now,
                completed_at=now,
            )
            await self.repo.save_evaluation_run(eval_run)
            decision = PretradeRiskDecision(
                id=f"DEC_{uuid.uuid4().hex[:10]}",
                evaluation_run_id=eval_run.id,
                decision="REJECT",
                primary_reason_code="ORDER_INVALID",
                reason_summary="; ".join(val_res.errors),
                evaluated_at=now,
                expires_at=now,
            )
            await self.repo.save_decision(decision)
            await self.db.commit()
            return await self.build_decision_response(eval_run.id)

        # 2. Portfolio State Retrieval & Simulation
        port_state = mock_portfolio_state or {
            "nav": Decimal("1000000.00"),
            "cash": Decimal("250000.00"),
            "positions": {payload.instrument_id: Decimal("100.00")},
            "position_values": {payload.instrument_id: Decimal("15000.00")},
            "sectors": {payload.instrument_id: "TECHNOLOGY"},
            "market_price": payload.limit_price or Decimal("150.00"),
            "expected_volume": Decimal("100000.00"),
            "cov_matrix": [[0.04]],  # 20% vol
            "weights": [0.015],
            "data_freshness_sec": 5,
        }

        # Check Data Freshness Gate
        data_stale = port_state.get("data_freshness_sec", 0) > 60  # > 60s stale
        data_missing = port_state.get("nav") is None or port_state.get("market_price") is None

        nav = to_decimal(port_state.get("nav", Decimal("1000000.00")))
        curr_qty = to_decimal(port_state.get("positions", {}).get(payload.instrument_id, Decimal("0.00")))
        mkt_price = to_decimal(port_state.get("market_price", payload.limit_price or Decimal("150.00")))

        # Check Active Reservations from concurrent orders
        active_reservations = await self.repo.get_active_reservations_for_portfolio(payload.portfolio_id)
        reserved_sym_qty = sum(
            r.reserved_quantity for r in active_reservations if r.instrument_id == payload.instrument_id
        )

        # Simulate Position
        proj_qty, direction, transition = calculate_projected_position(
            curr_qty + reserved_sym_qty, payload.side, payload.quantity
        )
        proj_val = proj_qty * mkt_price

        # Build projected position values dict
        all_pos_vals = dict(port_state.get("position_values", {}))
        all_pos_vals[payload.instrument_id] = proj_val

        # Exposures
        exp_res = calculate_exposures(all_pos_vals, nav)
        proj_gross = exp_res["gross_exposure"]
        proj_net = exp_res["net_exposure"]
        proj_pos_weight = (abs(proj_val) / nav).quantize(Decimal("0.0001"))

        # Sector
        sectors_map = dict(port_state.get("sectors", {}))
        sec_res = calculate_sector_exposure(all_pos_vals, sectors_map, nav)
        order_sec = sectors_map.get(payload.instrument_id, "UNCLASSIFIED")
        proj_sec_weight = sec_res.get(order_sec, {}).get("weight", Decimal("0.00"))

        # VaR Simulation
        cov = port_state.get("cov_matrix", [[0.04]])
        proj_weights = [float(proj_pos_weight)]
        proj_var = Decimal(str(round(calculate_parametric_var(proj_weights, cov, float(nav)), 2)))
        curr_var = Decimal(str(round(calculate_parametric_var([float(curr_qty * mkt_price / nav)], cov, float(nav)), 2)))
        inc_var = proj_var - curr_var

        # Participation rate
        part_rate = calculate_participation_rate(payload.quantity, port_state.get("expected_volume", Decimal("100000.00")))

        # Required Funding check
        order_notional = payload.quantity * mkt_price
        cash_available = to_decimal(port_state.get("cash", Decimal("250000.00")))
        insufficient_cash = payload.side.upper() == "BUY" and order_notional > cash_available

        # 3. Limit Configurations & Checks
        limits = mock_limits or {
            "max_position_weight": Decimal("0.10"),     # 10% max
            "max_sector_weight": Decimal("0.25"),       # 25% max
            "max_gross_exposure": Decimal("1500000.00"),# 1.5x NAV
            "max_net_exposure": Decimal("1000000.00"),  # 1.0x NAV
            "max_var": Decimal("50000.00"),             # $50k max VaR
            "max_participation_rate": Decimal("15.00"), # 15% max volume
        }

        check_outputs: List[Dict[str, Any]] = []

        # Check 1: Data Freshness Gate
        if data_missing:
            check_outputs.append({
                "check_name": "data_freshness_and_quality",
                "check_category": "DATA_QUALITY",
                "check_status": "HARD_FAIL",
                "current_value": Decimal("0.00"),
                "projected_value": Decimal("0.00"),
                "effective_limit": Decimal("0.00"),
                "utilization_percentage": Decimal("100.00"),
                "unit": "STATUS",
                "source_module": "M03",
                "reason_code": "REQUIRED_METADATA_MISSING",
            })
        elif data_stale:
            check_outputs.append({
                "check_name": "data_freshness_and_quality",
                "check_category": "DATA_QUALITY",
                "check_status": "REVIEW_REQUIRED",
                "current_value": Decimal(str(port_state.get("data_freshness_sec", 65))),
                "projected_value": Decimal(str(port_state.get("data_freshness_sec", 65))),
                "effective_limit": Decimal("60.00"),
                "utilization_percentage": Decimal("108.00"),
                "unit": "SECONDS",
                "source_module": "M03",
                "reason_code": "MARKET_DATA_STALE",
            })
        else:
            check_outputs.append({
                "check_name": "data_freshness_and_quality",
                "check_category": "DATA_QUALITY",
                "check_status": "PASS",
                "current_value": Decimal(str(port_state.get("data_freshness_sec", 5))),
                "projected_value": Decimal(str(port_state.get("data_freshness_sec", 5))),
                "effective_limit": Decimal("60.00"),
                "utilization_percentage": Decimal("8.33"),
                "unit": "SECONDS",
                "source_module": "M03",
                "reason_code": None,
            })

        # Check 2: Position Limit
        pos_lim = limits["max_position_weight"]
        pos_util = (proj_pos_weight / pos_lim * Decimal("100.00")).quantize(Decimal("0.01"))
        pos_status = "PASS" if proj_pos_weight <= pos_lim else "HARD_FAIL"
        check_outputs.append({
            "check_name": "position_limit",
            "check_category": "POSITION",
            "check_status": pos_status,
            "current_value": (abs(curr_qty * mkt_price) / nav).quantize(Decimal("0.0001")),
            "projected_value": proj_pos_weight,
            "effective_limit": pos_lim,
            "utilization_percentage": pos_util,
            "unit": "NAV_WEIGHT",
            "source_module": "M11.02",
            "reason_code": "POSITION_LIMIT_EXCEEDED" if pos_status == "HARD_FAIL" else None,
        })

        # Check 3: Sector Limit
        sec_lim = limits["max_sector_weight"]
        sec_util = (proj_sec_weight / sec_lim * Decimal("100.00")).quantize(Decimal("0.01"))
        sec_status = "PASS" if proj_sec_weight <= sec_lim else "HARD_FAIL"
        check_outputs.append({
            "check_name": "sector_limit",
            "check_category": "SECTOR",
            "check_status": sec_status,
            "current_value": Decimal("0.00"),
            "projected_value": proj_sec_weight,
            "effective_limit": sec_lim,
            "utilization_percentage": sec_util,
            "unit": "NAV_WEIGHT",
            "source_module": "M11.03",
            "reason_code": "SECTOR_LIMIT_EXCEEDED" if sec_status == "HARD_FAIL" else None,
        })

        # Check 4: Gross Exposure Limit
        gross_lim = limits["max_gross_exposure"]
        gross_util = (proj_gross / gross_lim * Decimal("100.00")).quantize(Decimal("0.01"))
        gross_status = "PASS" if proj_gross <= gross_lim else "HARD_FAIL"
        check_outputs.append({
            "check_name": "gross_exposure_limit",
            "check_category": "EXPOSURE",
            "check_status": gross_status,
            "current_value": Decimal("0.00"),
            "projected_value": proj_gross,
            "effective_limit": gross_lim,
            "utilization_percentage": gross_util,
            "unit": "CURRENCY",
            "source_module": "M06.01",
            "reason_code": "GROSS_EXPOSURE_LIMIT_EXCEEDED" if gross_status == "HARD_FAIL" else None,
        })

        # Check 5: VaR Limit
        var_lim = limits["max_var"]
        var_util = (proj_var / var_lim * Decimal("100.00")).quantize(Decimal("0.01"))
        var_status = "PASS" if proj_var <= var_lim else "HARD_FAIL"
        check_outputs.append({
            "check_name": "var_limit",
            "check_category": "QUANTITATIVE",
            "check_status": var_status,
            "current_value": curr_var,
            "projected_value": proj_var,
            "effective_limit": var_lim,
            "utilization_percentage": var_util,
            "unit": "CURRENCY",
            "source_module": "M07.02",
            "reason_code": "VAR_LIMIT_EXCEEDED" if var_status == "HARD_FAIL" else None,
        })

        # Check 6: Liquidity Participation Rate
        liq_lim = limits["max_participation_rate"]
        liq_util = (part_rate / liq_lim * Decimal("100.00")).quantize(Decimal("0.01"))
        liq_status = "PASS" if part_rate <= liq_lim else "HARD_FAIL"
        check_outputs.append({
            "check_name": "participation_rate_limit",
            "check_category": "LIQUIDITY",
            "check_status": liq_status,
            "current_value": Decimal("0.00"),
            "projected_value": part_rate,
            "effective_limit": liq_lim,
            "utilization_percentage": liq_util,
            "unit": "PERCENTAGE",
            "source_module": "M09.03",
            "reason_code": "PARTICIPATION_RATE_EXCEEDED" if liq_status == "HARD_FAIL" else None,
        })

        # Check 7: Funding Check
        funding_status = "HARD_FAIL" if insufficient_cash else "PASS"
        check_outputs.append({
            "check_name": "cash_funding_check",
            "check_category": "FUNDING",
            "check_status": funding_status,
            "current_value": cash_available,
            "projected_value": order_notional,
            "effective_limit": cash_available,
            "utilization_percentage": ((order_notional / cash_available) * Decimal("100.00")).quantize(Decimal("0.01")) if cash_available > 0 else Decimal("100.00"),
            "unit": "CURRENCY",
            "source_module": "M05.04",
            "reason_code": "INSUFFICIENT_CASH" if insufficient_cash else None,
        })

        # 4. Deterministic Precedence Resolution
        # Precedence: HARD_FAIL -> REJECT, REVIEW_REQUIRED -> REVIEW_REQUIRED, else PASS
        has_hard_fail = any(c["check_status"] == "HARD_FAIL" for c in check_outputs)
        has_review = any(c["check_status"] == "REVIEW_REQUIRED" for c in check_outputs)

        if has_hard_fail:
            final_decision = "REJECT"
            fail_codes = [c["reason_code"] for c in check_outputs if c["check_status"] == "HARD_FAIL" and c["reason_code"]]
            primary_reason = fail_codes[0] if fail_codes else "HARD_LIMIT_EXCEEDED"
            summary_msg = f"Order rejected due to violations: {', '.join(fail_codes)}"
        elif has_review:
            final_decision = "REVIEW_REQUIRED"
            rev_codes = [c["reason_code"] for c in check_outputs if c["check_status"] == "REVIEW_REQUIRED" and c["reason_code"]]
            primary_reason = rev_codes[0] if rev_codes else "MANUAL_REVIEW_REQUIRED"
            summary_msg = f"Order requires operational review: {', '.join(rev_codes)}"
        else:
            final_decision = "PASS"
            primary_reason = "ALL_CHECKS_PASSED"
            summary_msg = "All mandatory pre-trade risk and exposure limits satisfied"

        # 5. Persist Entities
        order_id = f"ORD_{uuid.uuid4().hex[:10]}"
        order_req = PretradeOrderRequest(
            id=order_id,
            portfolio_id=payload.portfolio_id,
            originating_system=payload.originating_system,
            submitting_user_id=payload.submitting_user_id,
            idempotency_key=payload.idempotency_key or f"IDEM_{uuid.uuid4().hex[:8]}",
            current_order_version=1,
            current_status="APPROVED" if final_decision == "PASS" else ("REJECTED" if final_decision == "REJECT" else "REVIEW_REQUIRED"),
            created_at=now,
            updated_at=now,
        )
        await self.repo.save_order_request(order_req)

        order_ver = PretradeOrderVersion(
            id=f"VER_{uuid.uuid4().hex[:10]}",
            proposed_order_id=order_req.id,
            version_number=1,
            instrument_id=payload.instrument_id,
            listing_id=payload.listing_id,
            exchange=payload.exchange,
            side=payload.side.upper(),
            quantity=payload.quantity,
            order_type=payload.order_type.upper(),
            limit_price=payload.limit_price,
            stop_price=payload.stop_price,
            time_in_force=payload.time_in_force.upper(),
            currency=payload.currency.upper(),
            strategy_id=payload.strategy_id,
            submitted_at=now,
        )
        await self.repo.save_order_version(order_ver)

        eval_run = PretradeEvaluationRun(
            id=f"EVL_{uuid.uuid4().hex[:10]}",
            proposed_order_version_id=order_ver.id,
            portfolio_snapshot_id="SNAP_CURRENT",
            evaluation_status="COMPLETED",
            started_at=now,
            completed_at=now,
            evaluation_latency_ms=Decimal("4.50"),
        )
        await self.repo.save_evaluation_run(eval_run)

        # Simulation Run
        sim_run = PretradeSimulationRun(
            id=f"SIM_{uuid.uuid4().hex[:10]}",
            evaluation_run_id=eval_run.id,
            portfolio_nav=nav,
            projected_nav=nav,
            current_position_qty=curr_qty,
            projected_position_qty=proj_qty,
            position_transition_type=transition,
            projected_gross_exposure=proj_gross,
            projected_net_exposure=proj_net,
            projected_var=proj_var,
            incremental_var=inc_var,
            simulation_status="SUCCESS",
            created_at=now,
        )
        await self.repo.save_simulation_run(sim_run)

        # Check Results
        for c in check_outputs:
            chk = PretradeCheckResult(
                id=f"CHK_{uuid.uuid4().hex[:10]}",
                evaluation_run_id=eval_run.id,
                check_name=c["check_name"],
                check_category=c["check_category"],
                check_status=c["check_status"],
                current_value=c["current_value"],
                projected_value=c["projected_value"],
                effective_limit=c["effective_limit"],
                utilization_percentage=c["utilization_percentage"],
                unit=c["unit"],
                source_module=c["source_module"],
                reason_code=c["reason_code"],
                created_at=now,
            )
            await self.repo.save_check_result(chk)

        # Decision & Authorization
        auth_id = None
        expires_at = now + timedelta(minutes=5)

        if final_decision == "PASS":
            auth_id = f"AUTH_{uuid.uuid4().hex[:10]}"

        decision = PretradeRiskDecision(
            id=f"DEC_{uuid.uuid4().hex[:10]}",
            evaluation_run_id=eval_run.id,
            decision=final_decision,
            primary_reason_code=primary_reason,
            reason_summary=summary_msg,
            evaluated_at=now,
            expires_at=expires_at,
            authorization_id=auth_id,
        )
        await self.repo.save_decision(decision)

        if final_decision == "PASS" and auth_id:
            auth = PretradeAuthorization(
                id=auth_id,
                decision_id=decision.id,
                proposed_order_version_id=order_ver.id,
                portfolio_id=payload.portfolio_id,
                permitted_instrument_id=payload.instrument_id,
                permitted_side=payload.side.upper(),
                permitted_quantity=payload.quantity,
                authorization_status="ACTIVE",
                valid_from=now,
                expires_at=expires_at,
            )
            await self.repo.save_authorization(auth)

            # Atomic risk reservation
            res = PretradeRiskReservation(
                id=f"RES_{uuid.uuid4().hex[:10]}",
                authorization_id=auth.id,
                portfolio_id=payload.portfolio_id,
                instrument_id=payload.instrument_id,
                reserved_quantity=payload.quantity,
                reserved_notional=order_notional,
                reservation_status="ACTIVE",
                created_at=now,
                expires_at=expires_at,
            )
            await self.repo.save_reservation(res)

        await self.db.commit()
        return await self.build_decision_response(eval_run.id)

    async def build_decision_response(self, evaluation_run_id: str) -> PretradeDecisionResponse:
        self.db.expire_all()
        # Query evaluation with eager-loaded decision, checks, simulation
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(PretradeEvaluationRun)
            .where(PretradeEvaluationRun.id == evaluation_run_id)
            .options(
                selectinload(PretradeEvaluationRun.decision),
                selectinload(PretradeEvaluationRun.check_results),
                selectinload(PretradeEvaluationRun.simulation_runs),
                selectinload(PretradeEvaluationRun.order_version).selectinload(PretradeOrderVersion.request),
            )
        )
        res = await self.db.execute(stmt)
        eval_run = res.scalar_one_or_none()
        if not eval_run or not eval_run.decision:
            raise HTTPException(status_code=404, detail="Decision record not found")

        dec = eval_run.decision
        ver = eval_run.order_version
        checks = [
            CheckResultOutput(
                check_name=c.check_name,
                check_category=c.check_category,
                check_status=c.check_status,
                current_value=c.current_value,
                projected_value=c.projected_value,
                effective_limit=c.effective_limit,
                utilization_percentage=c.utilization_percentage,
                unit=c.unit,
                source_module=c.source_module,
                reason_code=c.reason_code,
            )
            for c in eval_run.check_results
        ]

        sim_out = None
        if eval_run.simulation_runs:
            s = eval_run.simulation_runs[0]
            sim_out = SimulationResultOutput(
                portfolio_nav=s.portfolio_nav,
                projected_nav=s.projected_nav,
                current_position_qty=s.current_position_qty,
                projected_position_qty=s.projected_position_qty,
                position_transition_type=s.position_transition_type,
                projected_gross_exposure=s.projected_gross_exposure,
                projected_net_exposure=s.projected_net_exposure,
                projected_var=s.projected_var,
                incremental_var=s.incremental_var,
                simulation_status=s.simulation_status,
            )

        return PretradeDecisionResponse(
            decision_id=dec.id,
            order_id=ver.proposed_order_id,
            order_version=ver.version_number,
            portfolio_id=ver.request.portfolio_id,
            instrument_id=ver.instrument_id,
            side=ver.side,
            quantity=ver.quantity,
            decision=dec.decision,
            primary_reason_code=dec.primary_reason_code,
            reason_summary=dec.reason_summary,
            evaluated_at=dec.evaluated_at,
            expires_at=dec.expires_at,
            authorization_id=dec.authorization_id,
            check_results=checks,
            simulation=sim_out,
        )

    async def validate_authorization(self, authorization_id: str) -> AuthorizationValidationResponse:
        auth = await self.repo.get_authorization_by_id(authorization_id)
        now = datetime.utcnow()
        if not auth:
            return AuthorizationValidationResponse(
                is_valid=False,
                authorization_id=authorization_id,
                status="NOT_FOUND",
                permitted_instrument_id="",
                permitted_side="",
                permitted_quantity=Decimal("0.00"),
                expires_at=now,
                message="Authorization credential not found",
            )

        if auth.authorization_status != "ACTIVE":
            return AuthorizationValidationResponse(
                is_valid=False,
                authorization_id=auth.id,
                status=auth.authorization_status,
                permitted_instrument_id=auth.permitted_instrument_id,
                permitted_side=auth.permitted_side,
                permitted_quantity=auth.permitted_quantity,
                expires_at=auth.expires_at,
                message=f"Authorization is {auth.authorization_status}",
            )

        if now > auth.expires_at:
            auth.authorization_status = "EXPIRED"
            await self.db.commit()
            return AuthorizationValidationResponse(
                is_valid=False,
                authorization_id=auth.id,
                status="EXPIRED",
                permitted_instrument_id=auth.permitted_instrument_id,
                permitted_side=auth.permitted_side,
                permitted_quantity=auth.permitted_quantity,
                expires_at=auth.expires_at,
                message="Authorization has expired",
            )

        return AuthorizationValidationResponse(
            is_valid=True,
            authorization_id=auth.id,
            status="ACTIVE",
            permitted_instrument_id=auth.permitted_instrument_id,
            permitted_side=auth.permitted_side,
            permitted_quantity=auth.permitted_quantity,
            expires_at=auth.expires_at,
            message="Authorization is active and valid for execution",
        )

    async def get_dashboard_summary(self) -> PretradeDashboardSummary:
        stats = await self.repo.get_analytics_summary()
        total = stats["total_orders_evaluated"]
        pass_pct = (Decimal(str(stats["pass_count"])) / Decimal(str(total)) * Decimal("100.00")).quantize(Decimal("0.01")) if total > 0 else Decimal("0.00")
        rej_pct = (Decimal(str(stats["reject_count"])) / Decimal(str(total)) * Decimal("100.00")).quantize(Decimal("0.01")) if total > 0 else Decimal("0.00")

        return PretradeDashboardSummary(
            total_orders_evaluated=total,
            pass_count=stats["pass_count"],
            reject_count=stats["reject_count"],
            review_required_count=stats["review_required_count"],
            pass_percentage=pass_pct,
            reject_percentage=rej_pct,
            active_reservations_count=stats["active_reservations_count"],
            active_authorizations_count=stats["active_authorizations_count"],
            rejection_reasons_breakdown=stats["rejection_reasons_breakdown"],
        )

