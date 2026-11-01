import json
import hashlib
import uuid
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.instrument_reference_data.corporate_actions.models import (
    CorporateAction,
    CorporateActionInstrument,
    CorporateActionVersion,
    CorporateActionDividend,
    CorporateActionRatio,
    CorporateActionMerger,
    CorporateActionAdjustmentRun,
    CorporateActionAdjustmentLineage,
    CorporateActionType,
    LifecycleStatus,
    InstrumentRole
)
from backend.app.modules.instrument_reference_data.corporate_actions.schemas import (
    CorporateActionCreate,
    CorporateActionUpdate,
    CalculateAdjustmentRequest,
    AdjustmentResultResponse,
    AdjustmentLineageStep
)
from backend.app.modules.instrument_reference_data.corporate_actions.repositories.repository import CorporateActionRepository
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.split_calculator import compute_split_factors
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.bonus_calculator import compute_bonus_factors
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.dividend_calculator import compute_cash_dividend_factor
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.cumulative_calculator import compound_factors
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument


class CorporateActionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CorporateActionRepository(session)

    async def create_corporate_action(self, payload: CorporateActionCreate, user: str = "SYSTEM") -> CorporateAction:
        # Validate primary instrument exists
        inst_res = await self.session.execute(
            select(Instrument).where(Instrument.instrument_id == payload.primary_instrument_id)
        )
        instrument = inst_res.scalar_one_or_none()
        if not instrument:
            raise ValueError(f"Primary instrument '{payload.primary_instrument_id}' does not exist in Instrument Master.")

        # Check for duplicate event_id
        existing = await self.repo.get_by_id(payload.event_id)
        if existing:
            raise ValueError(f"Corporate action with event_id '{payload.event_id}' already exists.")

        action = CorporateAction(
            event_id=payload.event_id,
            corporate_action_type=payload.corporate_action_type,
            lifecycle_status=payload.lifecycle_status,
            primary_instrument_id=payload.primary_instrument_id,
            declaration_date=payload.declaration_date,
            ex_date=payload.ex_date,
            record_date=payload.record_date,
            payment_date=payload.payment_date,
            effective_date=payload.effective_date,
            source_name=payload.source_name,
            source_reference_id=payload.source_reference_id,
            description=payload.description,
            current_version=1
        )
        await self.repo.add_action(action)

        # Map original instrument link
        orig_link = CorporateActionInstrument(
            event_id=action.event_id,
            instrument_id=payload.primary_instrument_id,
            role=InstrumentRole.ORIGINAL_SECURITY
        )
        await self.repo.add_instrument_link(orig_link)

        # Attach specific terms
        if payload.corporate_action_type in (CorporateActionType.CASH_DIVIDEND, CorporateActionType.STOCK_DIVIDEND):
            if not payload.dividend_detail:
                raise ValueError("Dividend details required for dividend corporate action.")
            div = CorporateActionDividend(
                event_id=action.event_id,
                gross_amount=payload.dividend_detail.gross_amount,
                currency=payload.dividend_detail.currency,
                gross_net_basis=payload.dividend_detail.gross_net_basis,
                withholding_tax_rate=payload.dividend_detail.withholding_tax_rate,
                reinvestment_price=payload.dividend_detail.reinvestment_price
            )
            self.session.add(div)

        elif payload.corporate_action_type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT, CorporateActionType.BONUS_ISSUE):
            if not payload.ratio_detail:
                raise ValueError("Ratio details required for split/bonus corporate action.")
            ratio = CorporateActionRatio(
                event_id=action.event_id,
                numerator=payload.ratio_detail.numerator,
                denominator=payload.ratio_detail.denominator,
                additional_shares=payload.ratio_detail.additional_shares,
                existing_shares=payload.ratio_detail.existing_shares
            )
            self.session.add(ratio)

        elif payload.corporate_action_type == CorporateActionType.MERGER:
            if not payload.merger_detail:
                raise ValueError("Merger details required for merger corporate action.")
            merger = CorporateActionMerger(
                event_id=action.event_id,
                consideration_type=payload.merger_detail.consideration_type,
                successor_instrument_id=payload.merger_detail.successor_instrument_id,
                stock_conversion_numerator=payload.merger_detail.stock_conversion_numerator,
                stock_conversion_denominator=payload.merger_detail.stock_conversion_denominator,
                cash_per_share=payload.merger_detail.cash_per_share,
                cash_currency=payload.merger_detail.cash_currency
            )
            self.session.add(merger)
            if payload.merger_detail.successor_instrument_id:
                succ_link = CorporateActionInstrument(
                    event_id=action.event_id,
                    instrument_id=payload.merger_detail.successor_instrument_id,
                    role=InstrumentRole.SUCCESSOR_SECURITY
                )
                await self.repo.add_instrument_link(succ_link)

        # Snapshot version 1
        snapshot = {
            "event_id": payload.event_id,
            "type": payload.corporate_action_type.value,
            "status": payload.lifecycle_status.value,
            "effective_date": payload.effective_date.isoformat(),
            "terms": payload.model_dump(mode="json")
        }
        v1 = CorporateActionVersion(
            event_id=action.event_id,
            version_number=1,
            snapshot_payload=json.dumps(snapshot),
            reason="INITIAL_REGISTRATION",
            created_by=user
        )
        await self.repo.add_version(v1)

        await self.session.commit()
        await self.session.refresh(action)
        return action

    async def update_corporate_action(
        self,
        event_id: str,
        payload: CorporateActionUpdate,
        user: str = "SYSTEM"
    ) -> CorporateAction:
        action = await self.repo.get_by_id(event_id)
        if not action:
            raise ValueError(f"Corporate action '{event_id}' not found.")

        if payload.lifecycle_status:
            action.lifecycle_status = payload.lifecycle_status
        if payload.effective_date:
            action.effective_date = payload.effective_date
        if payload.ex_date:
            action.ex_date = payload.ex_date
        if payload.record_date:
            action.record_date = payload.record_date
        if payload.payment_date:
            action.payment_date = payload.payment_date
        if payload.description:
            action.description = payload.description

        action.current_version += 1
        action.updated_at = datetime.utcnow()

        # Record new immutable version
        snapshot = {
            "event_id": action.event_id,
            "version": action.current_version,
            "status": action.lifecycle_status.value,
            "effective_date": action.effective_date.isoformat(),
            "payload": payload.model_dump(mode="json", exclude_none=True)
        }
        version = CorporateActionVersion(
            event_id=action.event_id,
            version_number=action.current_version,
            snapshot_payload=json.dumps(snapshot),
            reason=payload.reason or "AMENDMENT",
            created_by=user
        )
        await self.repo.add_version(version)

        await self.session.commit()
        await self.session.refresh(action)
        return action

    async def calculate_adjustments(self, req: CalculateAdjustmentRequest, user: str = "SYSTEM") -> AdjustmentResultResponse:
        """
        Calculates cumulative and point-in-time price and quantity adjustments
        for observations prior to corporate action effective dates.
        """
        # Load all effective/confirmed events for this instrument on or after as_of_date
        stmt = (
            select(CorporateAction)
            .where(
                CorporateAction.primary_instrument_id == req.instrument_id,
                CorporateAction.lifecycle_status.in_([LifecycleStatus.CONFIRMED, LifecycleStatus.EFFECTIVE]),
                CorporateAction.effective_date >= req.as_of_date
            )
            .order_by(CorporateAction.effective_date.asc())
        )
        res = await self.session.execute(stmt)
        events = list(res.scalars().all())

        run_id = f"RUN_{uuid.uuid4().hex[:12].upper()}"
        running_price = req.unadjusted_price
        running_quantity = req.unadjusted_quantity

        lineages: List[AdjustmentLineageStep] = []
        event_factors = []

        for evt in events:
            p_factor = Decimal("1.0")
            q_factor = Decimal("1.0")
            formula_desc = ""

            if evt.corporate_action_type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT):
                ratio_stmt = select(CorporateActionRatio).where(CorporateActionRatio.event_id == evt.event_id)
                r_res = await self.session.execute(ratio_stmt)
                r_obj = r_res.scalar_one_or_none()
                if r_obj:
                    res_split = compute_split_factors(r_obj.numerator, r_obj.denominator)
                    p_factor = res_split["price_factor"]
                    q_factor = res_split["quantity_factor"]
                    formula_desc = f"Split {r_obj.numerator}:{r_obj.denominator} -> FP={p_factor}, FQ={q_factor}"

            elif evt.corporate_action_type == CorporateActionType.BONUS_ISSUE:
                ratio_stmt = select(CorporateActionRatio).where(CorporateActionRatio.event_id == evt.event_id)
                r_res = await self.session.execute(ratio_stmt)
                r_obj = r_res.scalar_one_or_none()
                if r_obj:
                    add_shares = r_obj.additional_shares or r_obj.numerator
                    exist_shares = r_obj.existing_shares or r_obj.denominator
                    res_bonus = compute_bonus_factors(add_shares, exist_shares)
                    p_factor = res_bonus["price_factor"]
                    q_factor = res_bonus["quantity_factor"]
                    formula_desc = f"Bonus {add_shares}-for-{exist_shares} -> FP={p_factor}, FQ={q_factor}"

            elif evt.corporate_action_type == CorporateActionType.CASH_DIVIDEND:
                div_stmt = select(CorporateActionDividend).where(CorporateActionDividend.event_id == evt.event_id)
                d_res = await self.session.execute(div_stmt)
                d_obj = d_res.scalar_one_or_none()
                if d_obj:
                    res_div = compute_cash_dividend_factor(
                        pre_event_price=running_price,
                        dividend_amount=Decimal(str(d_obj.gross_amount)),
                        withholding_tax_rate=Decimal(str(d_obj.withholding_tax_rate or 0)),
                        use_net_basis=False
                    )
                    p_factor = res_div["price_factor"]
                    q_factor = Decimal("1.0")
                    formula_desc = f"Cash Div {d_obj.gross_amount} {d_obj.currency} -> FP={p_factor}"

            elif evt.corporate_action_type == CorporateActionType.MERGER:
                merg_stmt = select(CorporateActionMerger).where(CorporateActionMerger.event_id == evt.event_id)
                m_res = await self.session.execute(merg_stmt)
                m_obj = m_res.scalar_one_or_none()
                if m_obj and m_obj.stock_conversion_numerator and m_obj.stock_conversion_denominator:
                    res_split = compute_split_factors(m_obj.stock_conversion_numerator, m_obj.stock_conversion_denominator)
                    p_factor = res_split["price_factor"]
                    q_factor = res_split["quantity_factor"]
                    formula_desc = f"Merger Stock Conversion {m_obj.stock_conversion_numerator}:{m_obj.stock_conversion_denominator}"

            # Step adjustment
            running_price = (running_price * p_factor).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
            running_quantity = (running_quantity * q_factor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)

            lineages.append(AdjustmentLineageStep(
                event_id=evt.event_id,
                event_version=evt.current_version,
                event_type=evt.corporate_action_type.value,
                observation_date=evt.effective_date,
                unadjusted_price=req.unadjusted_price,
                step_price_factor=p_factor,
                adjusted_price=running_price,
                unadjusted_quantity=req.unadjusted_quantity,
                step_quantity_factor=q_factor,
                adjusted_quantity=running_quantity,
                formula_description=formula_desc
            ))

            event_factors.append({
                "event_id": evt.event_id,
                "event_type": evt.corporate_action_type.value,
                "effective_date": evt.effective_date.isoformat(),
                "price_factor": p_factor,
                "quantity_factor": q_factor
            })

        compounded = compound_factors(event_factors)
        cum_p_factor = compounded["cumulative_price_factor"]
        cum_q_factor = compounded["cumulative_quantity_factor"]

        input_str = f"{req.instrument_id}:{req.unadjusted_price}:{req.unadjusted_quantity}:{req.as_of_date}:{req.policy_version}"
        input_checksum = hashlib.sha256(input_str.encode()).hexdigest()
        output_str = f"{running_price}:{running_quantity}:{cum_p_factor}:{cum_q_factor}:{len(events)}"
        output_checksum = hashlib.sha256(output_str.encode()).hexdigest()

        # Persist run & lineage
        adj_run = CorporateActionAdjustmentRun(
            run_id=run_id,
            instrument_id=req.instrument_id,
            policy_version=req.policy_version,
            calculated_at=datetime.utcnow(),
            calculated_by=user,
            total_events_applied=len(events),
            cumulative_price_factor=cum_p_factor,
            cumulative_quantity_factor=cum_q_factor,
            input_checksum=input_checksum,
            output_checksum=output_checksum
        )
        await self.repo.add_adjustment_run(adj_run)

        for step in lineages:
            lin_rec = CorporateActionAdjustmentLineage(
                run_id=run_id,
                event_id=step.event_id,
                event_version=step.event_version,
                event_type=step.event_type,
                observation_date=step.observation_date,
                unadjusted_price=step.unadjusted_price,
                step_price_factor=step.step_price_factor,
                adjusted_price=step.adjusted_price,
                unadjusted_quantity=step.unadjusted_quantity,
                step_quantity_factor=step.step_quantity_factor,
                adjusted_quantity=step.adjusted_quantity,
                formula_description=step.formula_description
            )
            await self.repo.add_lineage(lin_rec)

        await self.session.commit()

        return AdjustmentResultResponse(
            run_id=run_id,
            instrument_id=req.instrument_id,
            as_of_date=req.as_of_date,
            policy_version=req.policy_version,
            cumulative_price_factor=cum_p_factor,
            cumulative_quantity_factor=cum_q_factor,
            final_adjusted_price=running_price,
            final_adjusted_quantity=running_quantity,
            total_events_applied=len(events),
            input_checksum=input_checksum,
            output_checksum=output_checksum,
            lineage=lineages
        )

