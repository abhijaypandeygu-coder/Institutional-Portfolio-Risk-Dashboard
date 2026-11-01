"""
M03.04 - Order Book Validation Service.
Orchestrates crossed, locked, quantity, structure, and continuity validators.
Applies downstream metric gating and triggers M02 resynchronization when gaps are detected.
"""

import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.order_book.schemas import (
    OrderBookValidationInput,
    ValidationResultResponse,
    ResyncRequestCreate
)
from backend.app.modules.market_data_quality.order_book.validators.crossed_validator import CrossedBookValidator
from backend.app.modules.market_data_quality.order_book.validators.locked_validator import LockedBookValidator
from backend.app.modules.market_data_quality.order_book.validators.quantity_validator import QuantityValidator
from backend.app.modules.market_data_quality.order_book.validators.structure_validator import StructureValidator
from backend.app.modules.market_data_quality.order_book.validators.continuity_validator import ContinuityValidator
from backend.app.modules.market_data_quality.order_book.semantics.venue_resolver import VenuePolicyResolver
from backend.app.modules.market_data_quality.order_book.incidents.repository import BookIncidentRepository

logger = logging.getLogger(__name__)


class OrderBookValidationService:
    """
    Main orchestration service for Order Book validation.
    """

    @classmethod
    async def validate_order_book(
        cls,
        session: AsyncSession,
        input_data: OrderBookValidationInput
    ) -> ValidationResultResponse:
        """
        Validates an order book observation (snapshot or delta) and persists results.
        """
        validation_id = f"OBV_{uuid.uuid4().hex[:12].upper()}"

        # 1. Fetch effective validation rule
        rule = await BookIncidentRepository.get_effective_rule(
            session=session,
            feed_id=input_data.feed_id,
            symbol=input_data.symbol,
            venue=input_data.venue
        )

        max_crossed_ms = rule.max_crossed_duration_ms if rule else 50
        max_locked_ms = rule.max_locked_duration_ms if rule else 100
        allow_auction_cross = rule.allow_auction_cross if rule else True
        allow_auction_lock = rule.allow_auction_lock if rule else True
        allow_fractional = rule.allow_fractional_shares if rule else False
        min_lot_size = rule.min_lot_size if rule else Decimal("1.0")
        max_order_quantity = rule.max_order_quantity if rule else None
        max_allowed_gap = rule.max_allowed_sequence_gap if rule else 0
        auto_resync = rule.auto_trigger_resync if rule else True

        diagnostics: Dict[str, Any] = {
            "validation_id": validation_id,
            "feed_id": input_data.feed_id,
            "symbol": input_data.symbol,
            "venue": input_data.venue,
            "session_phase": input_data.session_phase,
            "is_snapshot": input_data.is_snapshot,
            "rule_code": rule.rule_code if rule else "SYSTEM_DEFAULT",
            "messages": []
        }

        # 2. Continuity Validation
        is_continuous, continuity_err, resync_payload = ContinuityValidator.evaluate(
            current_sequence=input_data.sequence_number,
            expected_sequence=input_data.expected_next_sequence,
            is_snapshot=input_data.is_snapshot,
            max_allowed_gap=max_allowed_gap
        )

        resync_requested = False
        if not is_continuous:
            diagnostics["messages"].append(f"Continuity break: {continuity_err}")
            diagnostics["continuity_error"] = continuity_err

            # Create continuity incident
            inc_key = f"CONT_INC_{input_data.feed_id}_{input_data.symbol}"
            await BookIncidentRepository.create_or_update_incident(
                session=session,
                incident_key=inc_key,
                incident_type="CONTINUITY_BREAK",
                feed_id=input_data.feed_id,
                symbol=input_data.symbol,
                venue=input_data.venue,
                session_phase=input_data.session_phase,
                severity="CRITICAL",
                details={"error": continuity_err, "resync_payload": resync_payload}
            )

            # Trigger M02 resynchronization if configured
            if auto_resync and resync_payload:
                resync_in = ResyncRequestCreate(
                    feed_id=input_data.feed_id,
                    symbol=input_data.symbol,
                    venue=input_data.venue,
                    reason=resync_payload.get("reason", "SEQUENCE_GAP"),
                    from_sequence=resync_payload.get("from_sequence"),
                    to_sequence=resync_payload.get("to_sequence")
                )
                await BookIncidentRepository.create_resync_request(session, resync_in)
                resync_requested = True
                diagnostics["resync_requested"] = True

        # 3. Structural & Quantity Validations
        has_qty_anomaly = False
        has_struct_defect = False
        parsed_bids = []
        parsed_asks = []
        best_bid_p: Optional[Decimal] = None
        best_bid_q: Optional[Decimal] = None
        best_ask_p: Optional[Decimal] = None
        best_ask_q: Optional[Decimal] = None

        if input_data.is_snapshot:
            # Validate Bids structure & quantity
            bid_struct_ok, bid_struct_errs, _ = StructureValidator.validate_levels_structure(
                levels=input_data.bids, side="BID"
            )
            bid_qty_ok, bid_qty_errs, parsed_bids = QuantityValidator.validate_snapshot_levels(
                levels=input_data.bids,
                side="BID",
                allow_fractional=allow_fractional,
                min_lot_size=min_lot_size,
                max_order_quantity=max_order_quantity
            )

            # Validate Asks structure & quantity
            ask_struct_ok, ask_struct_errs, _ = StructureValidator.validate_levels_structure(
                levels=input_data.asks, side="ASK"
            )
            ask_qty_ok, ask_qty_errs, parsed_asks = QuantityValidator.validate_snapshot_levels(
                levels=input_data.asks,
                side="ASK",
                allow_fractional=allow_fractional,
                min_lot_size=min_lot_size,
                max_order_quantity=max_order_quantity
            )

            if not (bid_struct_ok and ask_struct_ok):
                has_struct_defect = True
                diagnostics["messages"].extend(bid_struct_errs + ask_struct_errs)

            if not (bid_qty_ok and ask_qty_ok):
                has_qty_anomaly = True
                diagnostics["messages"].extend(bid_qty_errs + ask_qty_errs)

            if parsed_bids:
                best_bid_p = Decimal(str(parsed_bids[0]["price"]))
                best_bid_q = parsed_bids[0]["quantity"]

            if parsed_asks:
                best_ask_p = Decimal(str(parsed_asks[0]["price"]))
                best_ask_q = parsed_asks[0]["quantity"]

        else:
            # Incremental Delta
            delta_ok, delta_errs, parsed_delta = QuantityValidator.validate_delta(
                delta=input_data.delta,
                allow_fractional=allow_fractional,
                min_lot_size=min_lot_size,
                max_order_quantity=max_order_quantity
            )
            if not delta_ok:
                has_qty_anomaly = True
                diagnostics["messages"].extend(delta_errs)

            if input_data.delta:
                d_side = input_data.delta.side.upper()
                d_price = Decimal(str(input_data.delta.price))
                d_qty = Decimal(str(input_data.delta.quantity))
                if d_side == "BID":
                    best_bid_p = d_price
                    best_bid_q = d_qty
                else:
                    best_ask_p = d_price
                    best_ask_q = d_qty

        # 4. Crossed & Locked Validations
        crossed_eval = CrossedBookValidator.evaluate(
            best_bid=best_bid_p,
            best_ask=best_ask_p,
            session_phase=input_data.session_phase,
            venue=input_data.venue,
            duration_ms=input_data.last_crossed_duration_ms,
            max_transient_ms=max_crossed_ms,
            allow_auction_cross=allow_auction_cross
        )

        locked_eval = LockedBookValidator.evaluate(
            best_bid=best_bid_p,
            best_ask=best_ask_p,
            session_phase=input_data.session_phase,
            venue=input_data.venue,
            duration_ms=input_data.last_locked_duration_ms,
            max_transient_ms=max_locked_ms,
            allow_auction_lock=allow_auction_lock
        )

        is_crossed = crossed_eval["is_crossed"]
        is_locked = locked_eval["is_locked"]
        crossed_classification = crossed_eval.get("classification")
        locked_classification = locked_eval.get("classification")
        cross_amount = crossed_eval.get("cross_amount")

        # 5. Incident Lifecycle Management for Crossed & Locked
        if is_crossed and crossed_classification == "CROSSED_CONFIRMED":
            inc_key = f"CROSS_INC_{input_data.feed_id}_{input_data.symbol}"
            await BookIncidentRepository.create_or_update_incident(
                session=session,
                incident_key=inc_key,
                incident_type="CROSSED_BOOK",
                feed_id=input_data.feed_id,
                symbol=input_data.symbol,
                venue=input_data.venue,
                session_phase=input_data.session_phase,
                severity="ERROR",
                details={"cross_amount": str(cross_amount), "best_bid": str(best_bid_p), "best_ask": str(best_ask_p)},
                duration_ms=input_data.last_crossed_duration_ms
            )
        elif not is_crossed:
            inc_key = f"CROSS_INC_{input_data.feed_id}_{input_data.symbol}"
            await BookIncidentRepository.resolve_incident(session, inc_key)

        if is_locked and locked_classification == "LOCKED_SUSPICIOUS":
            inc_key = f"LOCK_INC_{input_data.feed_id}_{input_data.symbol}"
            await BookIncidentRepository.create_or_update_incident(
                session=session,
                incident_key=inc_key,
                incident_type="LOCKED_BOOK",
                feed_id=input_data.feed_id,
                symbol=input_data.symbol,
                venue=input_data.venue,
                session_phase=input_data.session_phase,
                severity="WARNING",
                details={"locked_price": str(best_bid_p)},
                duration_ms=input_data.last_locked_duration_ms
            )
        elif not is_locked:
            inc_key = f"LOCK_INC_{input_data.feed_id}_{input_data.symbol}"
            await BookIncidentRepository.resolve_incident(session, inc_key)

        # 6. Overall Validity & Metric Eligibility Gating
        is_valid = (
            is_continuous
            and not has_qty_anomaly
            and not has_struct_defect
            and crossed_eval["is_valid"]
            and locked_eval["is_valid"]
        )

        # Gate metric eligibilities
        spread_eligible = is_continuous and not has_struct_defect and crossed_eval["spread_eligible"] and locked_eval["spread_eligible"]
        imbalance_eligible = is_continuous and not has_qty_anomaly and not has_struct_defect and crossed_eval["imbalance_eligible"] and locked_eval["imbalance_eligible"]
        depth_eligible = is_continuous and not has_qty_anomaly and not has_struct_defect and crossed_eval["depth_eligible"] and locked_eval["depth_eligible"]
        liquidity_eligible = is_continuous and not has_qty_anomaly and not has_struct_defect and crossed_eval["liquidity_eligible"] and locked_eval["liquidity_eligible"]
        execution_research_eligible = is_valid

        # Determine overall severity
        if not is_continuous or (is_crossed and crossed_classification == "CROSSED_CONFIRMED"):
            severity = "CRITICAL" if not is_continuous else "ERROR"
        elif has_qty_anomaly or has_struct_defect or (is_locked and locked_classification == "LOCKED_SUSPICIOUS"):
            severity = "WARNING"
        elif is_crossed or is_locked:
            severity = "INFO"
        else:
            severity = "PASS"

        # 7. Persist Result & Evidence
        result_record = {
            "validation_id": validation_id,
            "timestamp": input_data.timestamp,
            "feed_id": input_data.feed_id,
            "symbol": input_data.symbol,
            "venue": input_data.venue,
            "session_phase": input_data.session_phase,
            "data_origin": input_data.data_origin,
            "sequence_number": input_data.sequence_number,
            "is_snapshot": input_data.is_snapshot,
            "best_bid_price": best_bid_p,
            "best_bid_quantity": best_bid_q,
            "best_ask_price": best_ask_p,
            "best_ask_quantity": best_ask_q,
            "is_valid": is_valid,
            "is_crossed": is_crossed,
            "is_locked": is_locked,
            "has_quantity_anomaly": has_qty_anomaly,
            "has_continuity_break": not is_continuous,
            "has_structural_defect": has_struct_defect,
            "crossed_classification": crossed_classification,
            "locked_classification": locked_classification,
            "cross_amount": cross_amount,
            "spread_eligible": spread_eligible,
            "imbalance_eligible": imbalance_eligible,
            "depth_eligible": depth_eligible,
            "liquidity_eligible": liquidity_eligible,
            "execution_research_eligible": execution_research_eligible,
            "severity": severity,
            "diagnostics": diagnostics
        }

        await BookIncidentRepository.record_result(session, result_record)

        # Store audit evidence (converting Decimals and floats to strings for SQLite/PostgreSQL JSON serialization)
        serializable_bids = [{"side": b["side"], "price": str(b["price"]), "quantity": str(b["quantity"]), "level_position": b["level_position"]} for b in parsed_bids]
        serializable_asks = [{"side": a["side"], "price": str(a["price"]), "quantity": str(a["quantity"]), "level_position": a["level_position"]} for a in parsed_asks]
        serializable_cross_eval = {
            k: (str(v) if isinstance(v, Decimal) else v) for k, v in crossed_eval.items()
        }
        serializable_lock_eval = {
            k: (str(v) if isinstance(v, Decimal) else v) for k, v in locked_eval.items()
        }

        await BookIncidentRepository.record_evidence(
            session=session,
            validation_id=validation_id,
            raw_payload=str(input_data.model_dump()),
            parsed_levels={"bids": serializable_bids, "asks": serializable_asks},
            rule_evals={
                "crossed": serializable_cross_eval,
                "locked": serializable_lock_eval,
                "continuity": {"is_continuous": is_continuous, "error": continuity_err}
            }
        )

        return ValidationResultResponse(
            validation_id=validation_id,
            feed_id=input_data.feed_id,
            symbol=input_data.symbol,
            venue=input_data.venue,
            timestamp=input_data.timestamp,
            session_phase=input_data.session_phase,
            sequence_number=input_data.sequence_number,
            is_snapshot=input_data.is_snapshot,
            best_bid_price=best_bid_p,
            best_bid_quantity=best_bid_q,
            best_ask_price=best_ask_p,
            best_ask_quantity=best_ask_q,
            is_valid=is_valid,
            is_crossed=is_crossed,
            is_locked=is_locked,
            has_quantity_anomaly=has_qty_anomaly,
            has_continuity_break=not is_continuous,
            has_structural_defect=has_struct_defect,
            crossed_classification=crossed_classification,
            locked_classification=locked_classification,
            cross_amount=cross_amount,
            spread_eligible=spread_eligible,
            imbalance_eligible=imbalance_eligible,
            depth_eligible=depth_eligible,
            liquidity_eligible=liquidity_eligible,
            execution_research_eligible=execution_research_eligible,
            severity=severity,
            diagnostics=diagnostics,
            resync_requested=resync_requested
        )
