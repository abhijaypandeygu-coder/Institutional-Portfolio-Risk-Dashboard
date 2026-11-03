"""
M09.01 Bid-Ask Spread - Pydantic 2.x Schemas.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BookScope(str, Enum):
    VENUE_SPECIFIC = "VENUE_SPECIFIC"
    CONSOLIDATED = "CONSOLIDATED"


class RelativeSpreadMethod(str, Enum):
    MIDPOINT_NORMALIZED = "MIDPOINT_NORMALIZED"
    BID_NORMALIZED = "BID_NORMALIZED"
    ASK_NORMALIZED = "ASK_NORMALIZED"
    REFERENCE_PRICE_NORMALIZED = "REFERENCE_PRICE_NORMALIZED"


class LockedBookPolicy(str, Enum):
    INCLUDE_AS_ZERO = "INCLUDE_AS_ZERO"
    EXCLUDE = "EXCLUDE"
    FLAG_ANOMALY = "FLAG_ANOMALY"


class SpreadQualityStatus(str, Enum):
    VALID = "VALID"
    VALID_LOCKED = "VALID_LOCKED"
    STALE_QUOTE = "STALE_QUOTE"
    CROSSED_BOOK = "CROSSED_BOOK"
    LOCKED_BOOK = "LOCKED_BOOK"
    MISSING_BID = "MISSING_BID"
    MISSING_ASK = "MISSING_ASK"
    MISSING_BOTH_SIDES = "MISSING_BOTH_SIDES"
    UNSYNCHRONIZED_QUOTES = "UNSYNCHRONIZED_QUOTES"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_TICK_SIZE = "INVALID_TICK_SIZE"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    OUT_OF_SESSION = "OUT_OF_SESSION"
    TRADING_HALTED = "TRADING_HALTED"
    EXTREME_SPREAD_WARNING = "EXTREME_SPREAD_WARNING"
    INSUFFICIENT_SOURCE_QUALITY = "INSUFFICIENT_SOURCE_QUALITY"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class SpreadCalculationConfigCreate(BaseModel):
    config_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    book_scope: BookScope = BookScope.VENUE_SPECIFIC
    relative_spread_method: RelativeSpreadMethod = RelativeSpreadMethod.MIDPOINT_NORMALIZED
    locked_book_policy: LockedBookPolicy = LockedBookPolicy.INCLUDE_AS_ZERO
    maximum_quote_age_seconds: float = Field(default=5.0, ge=0.01)
    maximum_quote_skew_seconds: float = Field(default=0.5, ge=0.001)
    session_policy: str = "CONTINUOUS_ONLY"
    minimum_source_quality: str = "NORMAL"
    tick_validation_policy: str = "STRICT_ALIGNMENT"
    outlier_warning_policy: str = "FLAG_ONLY"


class SpreadCalculationConfigResponse(SpreadCalculationConfigCreate):
    config_id: str
    version: int
    config_hash: str
    status: str
    created_at: datetime
    created_by: str
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DirectSpreadCalculationRequest(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str = "NSE"
    venue: str = "NSE"
    book_scope: BookScope = BookScope.VENUE_SPECIFIC
    source_feed_id: str = "FEED_SIM"
    source_quote_reference: Optional[str] = None

    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    bid_quantity: Optional[Decimal] = None
    ask_quantity: Optional[Decimal] = None
    bid_timestamp: Optional[datetime] = None
    ask_timestamp: Optional[datetime] = None
    book_timestamp: Optional[datetime] = None

    tick_size: Optional[Decimal] = None
    session_type: str = "REGULAR_TRADING"
    config_code: Optional[str] = None
    relative_spread_method: Optional[RelativeSpreadMethod] = None
    persist_observation: bool = True


class SpreadObservationResponse(BaseModel):
    observation_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    venue: str
    book_scope: str
    source_feed_id: str
    source_quote_reference: Optional[str] = None

    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_quantity: Optional[Decimal] = None
    ask_quantity: Optional[Decimal] = None

    bid_timestamp: Optional[datetime] = None
    ask_timestamp: Optional[datetime] = None
    book_timestamp: datetime
    receive_timestamp: datetime

    quote_skew_seconds: Optional[float] = None
    quote_age_seconds: Optional[float] = None

    absolute_spread: Optional[Decimal] = None
    midpoint_price: Optional[Decimal] = None
    relative_spread_decimal: Optional[Decimal] = None
    relative_spread_percentage: Optional[Decimal] = None
    relative_spread_bps: Optional[Decimal] = None

    spread_ticks: Optional[Decimal] = None
    tick_size_reference: Optional[Decimal] = None

    session_type: str
    quality_status: str
    quality_reason_codes: Optional[str] = None

    calculation_config_id: str
    calculation_config_version: int
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpreadQualityResultResponse(BaseModel):
    result_id: str
    observation_id: Optional[str] = None
    source_quote_reference: Optional[str] = None
    quality_check_type: str
    quality_status: str
    severity: str
    measured_value: Optional[str] = None
    threshold_value: Optional[str] = None
    reason_code: str
    diagnostic_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpreadIntervalAggregateResponse(BaseModel):
    aggregate_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    venue: str
    book_scope: str

    aggregation_start: datetime
    aggregation_end: datetime
    aggregation_frequency: str
    aggregation_method: str

    mean_absolute_spread: Optional[Decimal] = None
    median_absolute_spread: Optional[Decimal] = None
    minimum_absolute_spread: Optional[Decimal] = None
    maximum_absolute_spread: Optional[Decimal] = None
    p90_absolute_spread: Optional[Decimal] = None
    p95_absolute_spread: Optional[Decimal] = None
    p99_absolute_spread: Optional[Decimal] = None

    mean_relative_spread: Optional[Decimal] = None
    median_relative_spread: Optional[Decimal] = None
    p90_relative_spread: Optional[Decimal] = None
    p95_relative_spread: Optional[Decimal] = None

    mean_relative_spread_bps: Optional[Decimal] = None
    median_relative_spread_bps: Optional[Decimal] = None

    mean_time_weighted_spread: Optional[Decimal] = None
    mean_time_weighted_relative_spread: Optional[Decimal] = None

    valid_observation_count: int
    invalid_observation_count: int
    stale_observation_count: int
    locked_book_count: int
    crossed_book_count: int

    valid_time_coverage_seconds: float
    expected_time_coverage_seconds: float
    coverage_percentage: float

    calculation_config_version: int
    result_version: int

    model_config = ConfigDict(from_attributes=True)


class SpreadStatisticsResponse(BaseModel):
    instrument_id: str
    exchange: str
    venue: str
    observation_count: int
    valid_observation_count: int
    mean_absolute_spread: Optional[float] = None
    median_absolute_spread: Optional[float] = None
    std_absolute_spread: Optional[float] = None
    min_absolute_spread: Optional[float] = None
    max_absolute_spread: Optional[float] = None
    p5_absolute_spread: Optional[float] = None
    p25_absolute_spread: Optional[float] = None
    p75_absolute_spread: Optional[float] = None
    p90_absolute_spread: Optional[float] = None
    p95_absolute_spread: Optional[float] = None
    p99_absolute_spread: Optional[float] = None

    mean_relative_spread_bps: Optional[float] = None
    median_relative_spread_bps: Optional[float] = None
    time_weighted_spread: Optional[float] = None
    time_weighted_relative_spread: Optional[float] = None
    time_coverage_percentage: Optional[float] = None


class SpreadQualitySummaryResponse(BaseModel):
    instrument_id: str
    exchange: str
    venue: str
    valid_quote_count: int
    stale_quote_count: int
    crossed_book_count: int
    locked_book_count: int
    missing_bid_count: int
    missing_ask_count: int
    unsynchronized_quote_count: int
    sequence_error_count: int
    invalid_price_count: int
    quality_coverage_percentage: float
    summary_status: str

    model_config = ConfigDict(from_attributes=True)


class VenueSpreadComparisonItem(BaseModel):
    venue: str
    exchange: str
    book_scope: str
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    absolute_spread: Optional[Decimal] = None
    relative_spread_bps: Optional[Decimal] = None
    midpoint_price: Optional[Decimal] = None
    quality_status: str
    quote_age_seconds: Optional[float] = None
    observation_count: int
    coverage_percentage: float
