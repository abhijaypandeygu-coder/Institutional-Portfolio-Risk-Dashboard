"""
Integration interfaces exposing M04.01 Instrument Master to other modules.
"""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentResolutionResponse,
)


class MarketDataIdentityProvider:
    """Interface consumed by M02 (Market Data Ingestion) to resolve canonical instrument IDs."""

    @classmethod
    async def resolve_market_data_symbol(
        cls, session: AsyncSession, exchange: str, symbol: str
    ) -> InstrumentResolutionResponse:
        """Resolves market data ticker to internal instrument_id and listing_id."""
        return await InstrumentMasterService.resolve_identifier(
            session=session, exchange=exchange, symbol=symbol
        )


class QualityReferenceProvider:
    """Interface consumed by M03 (Quality & Validation) to check listing validity and security metadata."""

    @classmethod
    async def verify_listing_exists(
        cls, session: AsyncSession, exchange: str, symbol: str
    ) -> bool:
        res = await InstrumentMasterService.resolve_identifier(
            session=session, exchange=exchange, symbol=symbol
        )
        return res.match_status == "EXACT_MATCH" and res.listing_status == "ACTIVE"
