from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceType,
    PriceOrigin,
    PriceBasis,
    CurrencyBasis,
    VerificationStatus,
    ResolutionStatus
)


class PriceReferenceObservationCreate(BaseModel):
    price_reference_id: str = Field(..., min_length=3, max_length=64)
    instrument_id: str = Field(..., min_length=3, max_length=64)
    listing_id: Optional[str] = None
    exchange_code: str = Field(..., min_length=2, max_length=32)
    market_segment: str = "EQUITY_CASH"
    trading_date: date
    reference_type: PriceReferenceType = PriceReferenceType.OFFICIAL_CLOSE
    price_value: Decimal = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    quotation_unit: str = "PER_SHARE"
    price_basis: PriceBasis = PriceBasis.RAW
    currency_basis: CurrencyBasis = CurrencyBasis.NATIVE_CURRENCY
    price_origin: PriceOrigin = PriceOrigin.EXCHANGE_OFFICIAL
    source_name: str = "EXCHANGE_FEED"
    source_reference: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    publication_timestamp: Optional[datetime] = None


class PriceReferenceObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price_reference_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange_code: str
    market_segment: str
    trading_date: date
    reference_type: PriceReferenceType
    price_value: Decimal
    currency: str
    quotation_unit: str
    price_basis: PriceBasis
    currency_basis: CurrencyBasis
    price_origin: PriceOrigin
    source_name: str
    verification_status: VerificationStatus
    observation_version: int
    created_at: datetime


class ResolvePreviousCloseRequest(BaseModel):
    instrument_id: str
    exchange_code: str
    target_trading_date: date
    selection_policy: str = "OFFICIAL_EXCHANGE_CLOSE_PREFERRED"


class PreviousCloseResolutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resolution_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange_code: str
    target_trading_date: date
    previous_trading_date: date
    source_price_reference_id: str
    resolved_price_value: Decimal
    currency: str
    price_basis: PriceBasis
    resolution_status: ResolutionStatus
    selection_policy: str
    resolved_at: datetime


class RegisterCurrencyConversionRequest(BaseModel):
    converted_price_reference_id: str
    original_price_reference_id: str
    target_currency: str = Field(..., min_length=3, max_length=3)
    fx_rate: Decimal = Field(..., gt=0)
    fx_pair: str
    conversion_direction: str = "SOURCE_TO_TARGET"
    fx_source: str = "CENTRAL_BANK_REFERENCE"


class CurrencyConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    converted_price_reference_id: str
    original_price_reference_id: str
    source_currency: str
    target_currency: str
    fx_rate: Decimal
    fx_pair: str
    conversion_direction: str
    conversion_timestamp: datetime
    converted_price_value: Optional[Decimal] = None
