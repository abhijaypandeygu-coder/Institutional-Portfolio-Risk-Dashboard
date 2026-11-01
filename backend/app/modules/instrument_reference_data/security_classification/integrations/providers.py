"""
Integration interfaces exposing M04.02 Security Classification to Portfolio Management and Risk Analytics.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.instrument_reference_data.security_classification.services.service import (
    SecurityClassificationService,
)
from backend.app.modules.instrument_reference_data.security_classification.schemas import (
    BulkClassificationLookupRequest,
    BulkClassificationLookupResponse,
    InstrumentClassificationDetail,
)


class PortfolioClassificationProvider:
    """Interface consumed by Portfolio Management for concentration calculations and sector breakdowns."""

    @classmethod
    async def get_holdings_classifications(
        cls,
        session: AsyncSession,
        instrument_ids: List[str],
        scheme_code: Optional[str] = None,
        as_of_date: Optional[datetime] = None,
    ) -> BulkClassificationLookupResponse:
        req = BulkClassificationLookupRequest(
            instrument_ids=instrument_ids,
            scheme_code=scheme_code,
            as_of_valid_time=as_of_date,
        )
        return await SecurityClassificationService.bulk_lookup(session, req)


class RiskClassificationProvider:
    """Interface consumed by Risk Analytics for sector factor risk aggregation and exposure matrices."""

    @classmethod
    async def get_instrument_sector_and_industry(
        cls,
        session: AsyncSession,
        instrument_id: str,
        scheme_code: Optional[str] = None,
        as_of_date: Optional[datetime] = None,
    ) -> Optional[InstrumentClassificationDetail]:
        return await SecurityClassificationService.lookup_instrument_classification(
            session=session,
            instrument_id=instrument_id,
            scheme_code=scheme_code,
            as_of_valid_time=as_of_date,
        )
