from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.instrument_reference_data.instrument_lifecycle.state_machine.transitions import (
    ListingLifecycleStatus,
    InstrumentLifecycleStatus
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.models import (
    SuspensionType,
    ResumptionType,
    DelistingType,
    VerificationStatus
)


class RegisterListingLifecycleRequest(BaseModel):
    listing_id: str = Field(..., min_length=3, max_length=64)
    instrument_id: str = Field(..., min_length=3, max_length=64)
    exchange_code: str = Field(..., min_length=2, max_length=32)
    market_segment: str = "EQUITY_CASH"
    first_listing_date: Optional[date] = None
    first_trading_date: Optional[date] = None
    initial_status: ListingLifecycleStatus = ListingLifecycleStatus.ACTIVE


class ListingLifecycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    listing_id: str
    instrument_id: str
    exchange_code: str
    market_segment: str
    first_listing_date: Optional[date] = None
    first_trading_date: Optional[date] = None
    last_trading_date: Optional[date] = None
    effective_delisting_date: Optional[date] = None
    current_status: ListingLifecycleStatus
    status_as_of: datetime
    verification_status: VerificationStatus


class RegisterSuspensionRequest(BaseModel):
    suspension_id: str = Field(..., min_length=3, max_length=64)
    listing_id: str = Field(..., min_length=3, max_length=64)
    suspension_type: SuspensionType = SuspensionType.REGULATORY_SUSPENSION
    effective_start_date: date
    expected_end_date: Optional[date] = None
    is_open_ended: bool = True
    reason: str
    source_reference: Optional[str] = None


class RegisterResumptionRequest(BaseModel):
    resumption_id: str = Field(..., min_length=3, max_length=64)
    listing_id: str = Field(..., min_length=3, max_length=64)
    related_suspension_id: Optional[str] = None
    resumption_type: ResumptionType = ResumptionType.NORMAL_RESUMPTION
    effective_resume_date: date
    conditions: Optional[str] = None
    reason: str


class RegisterDelistingRequest(BaseModel):
    delisting_id: str = Field(..., min_length=3, max_length=64)
    listing_id: str = Field(..., min_length=3, max_length=64)
    delisting_type: DelistingType = DelistingType.VOLUNTARY_DELISTING
    announcement_date: date
    last_trading_date: date
    effective_delisting_date: date
    reason: str
    successor_instrument_id: Optional[str] = None
    source_reference: Optional[str] = None


class LifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    listing_id: str
    instrument_id: str
    event_type: str
    previous_status: ListingLifecycleStatus
    new_status: ListingLifecycleStatus
    effective_date: date
    recorded_at: datetime
    reason: str
    source_name: str
    verification_status: VerificationStatus


class InstrumentLifecycleSummary(BaseModel):
    instrument_id: str
    derived_status: InstrumentLifecycleStatus
    total_listings: int
    active_listings_count: int
    suspended_listings_count: int
    delisted_listings_count: int
    listings: List[ListingLifecycleResponse]

