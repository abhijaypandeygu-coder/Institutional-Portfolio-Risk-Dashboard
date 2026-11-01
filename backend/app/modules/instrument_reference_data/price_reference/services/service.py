import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PreviousCloseResolution,
    PriceBasisMetadata,
    PriceCurrencyConversion,
    PriceReferenceType,
    PriceOrigin,
    PriceBasis,
    CurrencyBasis,
    VerificationStatus,
    ResolutionStatus
)
from backend.app.modules.instrument_reference_data.price_reference.schemas import (
    PriceReferenceObservationCreate,
    ResolvePreviousCloseRequest,
    RegisterCurrencyConversionRequest
)
from backend.app.modules.instrument_reference_data.price_reference.repositories.repository import PriceReferenceRepository
from backend.app.modules.instrument_reference_data.price_reference.calculations.currency_conversion import convert_currency_price
from backend.app.modules.instrument_reference_data.trading_calendar.services.service import TradingCalendarService
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument


class PriceReferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PriceReferenceRepository(session)
        self.calendar_service = TradingCalendarService(session)

    async def register_observation(self, payload: PriceReferenceObservationCreate) -> PriceReferenceObservation:
        # Validate instrument exists
        inst_res = await self.session.execute(
            select(Instrument).where(Instrument.instrument_id == payload.instrument_id)
        )
        if not inst_res.scalar_one_or_none():
            raise ValueError(f"Instrument '{payload.instrument_id}' does not exist in Instrument Master.")

        # Check existing ID
        existing = await self.repo.get_observation_by_id(payload.price_reference_id)
        if existing:
            raise ValueError(f"Price reference observation '{payload.price_reference_id}' already exists.")

        obs = PriceReferenceObservation(
            price_reference_id=payload.price_reference_id,
            instrument_id=payload.instrument_id,
            listing_id=payload.listing_id,
            exchange_code=payload.exchange_code.upper(),
            market_segment=payload.market_segment.upper(),
            trading_date=payload.trading_date,
            reference_type=payload.reference_type,
            price_value=payload.price_value,
            currency=payload.currency.upper(),
            quotation_unit=payload.quotation_unit,
            price_basis=payload.price_basis,
            currency_basis=payload.currency_basis,
            price_origin=payload.price_origin,
            source_name=payload.source_name,
            source_reference=payload.source_reference,
            verification_status=payload.verification_status,
            publication_timestamp=payload.publication_timestamp
        )
        await self.repo.add_observation(obs)
        await self.session.commit()
        await self.session.refresh(obs)
        return obs

    async def resolve_previous_close(self, req: ResolvePreviousCloseRequest) -> PreviousCloseResolution:
        # 1. Look up prior trading day from M04.04 Trading Calendar
        try:
            prev_trading_day = await self.calendar_service.get_previous_trading_day(
                exchange_code=req.exchange_code,
                start_date=req.target_trading_date
            )
        except Exception as e:
            raise ValueError(f"Failed to resolve prior trading date via trading calendar: {e}")

        # 2. Look up official close on prior trading day
        prior_close_obs = await self.repo.find_official_close(
            instrument_id=req.instrument_id,
            exchange_code=req.exchange_code,
            trading_date=prev_trading_day
        )
        if not prior_close_obs:
            raise ValueError(
                f"No verified official close available for instrument '{req.instrument_id}' on previous trading day {prev_trading_day}"
            )

        # 3. Create previous-close resolution record
        res_id = f"PCR_{uuid.uuid4().hex[:12].upper()}"
        resolution = PreviousCloseResolution(
            resolution_id=res_id,
            instrument_id=req.instrument_id,
            listing_id=prior_close_obs.listing_id,
            exchange_code=req.exchange_code.upper(),
            target_trading_date=req.target_trading_date,
            previous_trading_date=prev_trading_day,
            source_price_reference_id=prior_close_obs.price_reference_id,
            resolved_price_value=prior_close_obs.price_value,
            currency=prior_close_obs.currency,
            price_basis=prior_close_obs.price_basis,
            calendar_version="v1.0",
            selection_policy=req.selection_policy,
            resolution_status=ResolutionStatus.RESOLVED,
            resolved_at=datetime.utcnow()
        )
        await self.repo.add_resolution(resolution)
        await self.session.commit()
        await self.session.refresh(resolution)
        return resolution

    async def register_currency_conversion(
        self,
        payload: RegisterCurrencyConversionRequest
    ) -> PriceCurrencyConversion:
        original = await self.repo.get_observation_by_id(payload.original_price_reference_id)
        if not original:
            raise ValueError(f"Original price reference '{payload.original_price_reference_id}' not found.")

        # Convert price
        converted_val = convert_currency_price(
            source_price=Decimal(str(original.price_value)),
            fx_rate=payload.fx_rate,
            direction=payload.conversion_direction
        )

        # Register converted observation
        converted_obs = PriceReferenceObservation(
            price_reference_id=payload.converted_price_reference_id,
            instrument_id=original.instrument_id,
            listing_id=original.listing_id,
            exchange_code=original.exchange_code,
            market_segment=original.market_segment,
            trading_date=original.trading_date,
            reference_type=original.reference_type,
            price_value=converted_val,
            currency=payload.target_currency.upper(),
            quotation_unit=original.quotation_unit,
            price_basis=original.price_basis,
            currency_basis=CurrencyBasis.CONVERTED_CURRENCY,
            price_origin=PriceOrigin.INTERNAL_CALCULATION,
            source_name=payload.fx_source,
            source_reference=f"FX {payload.fx_pair} @ {payload.fx_rate}",
            verification_status=VerificationStatus.VERIFIED
        )
        await self.repo.add_observation(converted_obs)

        # Register conversion metadata
        conv = PriceCurrencyConversion(
            converted_price_reference_id=payload.converted_price_reference_id,
            original_price_reference_id=payload.original_price_reference_id,
            source_currency=original.currency,
            target_currency=payload.target_currency.upper(),
            fx_rate=payload.fx_rate,
            fx_pair=payload.fx_pair,
            conversion_direction=payload.conversion_direction,
            fx_source=payload.fx_source,
            conversion_timestamp=datetime.utcnow()
        )
        await self.repo.add_conversion(conv)

        await self.session.commit()
        await self.session.refresh(conv)
        return conv
