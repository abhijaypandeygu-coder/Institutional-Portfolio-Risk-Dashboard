from datetime import date
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PreviousCloseResolution,
    PriceBasisMetadata,
    PriceCurrencyConversion,
    PriceReferenceType,
    VerificationStatus
)


class PriceReferenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_observation_by_id(self, price_reference_id: str) -> Optional[PriceReferenceObservation]:
        stmt = select(PriceReferenceObservation).where(PriceReferenceObservation.price_reference_id == price_reference_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_observations_by_instrument(
        self,
        instrument_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[PriceReferenceObservation]:
        stmt = (
            select(PriceReferenceObservation)
            .where(PriceReferenceObservation.instrument_id == instrument_id)
            .order_by(PriceReferenceObservation.trading_date.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def find_official_close(
        self,
        instrument_id: str,
        exchange_code: str,
        trading_date: date
    ) -> Optional[PriceReferenceObservation]:
        stmt = (
            select(PriceReferenceObservation)
            .where(
                PriceReferenceObservation.instrument_id == instrument_id,
                PriceReferenceObservation.exchange_code == exchange_code.upper(),
                PriceReferenceObservation.trading_date == trading_date,
                PriceReferenceObservation.reference_type == PriceReferenceType.OFFICIAL_CLOSE,
                PriceReferenceObservation.verification_status.in_([VerificationStatus.VERIFIED, VerificationStatus.APPROVED])
            )
            .order_by(PriceReferenceObservation.observation_version.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def add_observation(self, obs: PriceReferenceObservation) -> PriceReferenceObservation:
        self.session.add(obs)
        await self.session.flush()
        return obs

    async def add_resolution(self, res_obj: PreviousCloseResolution) -> PreviousCloseResolution:
        self.session.add(res_obj)
        await self.session.flush()
        return res_obj

    async def get_resolution(self, resolution_id: str) -> Optional[PreviousCloseResolution]:
        stmt = select(PreviousCloseResolution).where(PreviousCloseResolution.resolution_id == resolution_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_conversion(self, conv: PriceCurrencyConversion) -> PriceCurrencyConversion:
        self.session.add(conv)
        await self.session.flush()
        return conv

    async def add_basis_metadata(self, meta: PriceBasisMetadata) -> PriceBasisMetadata:
        self.session.add(meta)
        await self.session.flush()
        return meta
