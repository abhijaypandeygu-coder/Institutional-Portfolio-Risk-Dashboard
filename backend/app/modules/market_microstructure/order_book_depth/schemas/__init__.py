"""
M09.02 Order Book Depth - Pydantic 2.x Schemas.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DepthAggregationMode(str, Enum):
    LEVEL_BASED = "LEVEL_BASED"
    TICK_DISTANCE = "TICK_DISTANCE"
    BPS_DISTANCE = "BPS_DISTANCE"
    ABSOLUTE_DISTANCE = "ABSOLUTE_DISTANCE"


class DepthQualityStatus(str, Enum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"
    STALE = "STALE"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class DepthCalculationConfigCreate(BaseModel):
    config_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    instrument_id: Optional[str] = None
    venue: Optional[str] = None
    aggregation_mode: DepthAggregationMode = DepthAggregationMode.LEVEL_BASED
    level_count: int = Field(default=5, ge=1, le=50)
    distance_unit: str = "BPS"
    distance_threshold: Optional[float] = None
    reference_price_method: str = "MIDPOINT"
    currency: str = "INR"
    contract_multiplier: Decimal = Decimal("1.0")
    weighting_method: str = "EXPONENTIAL_DECAY"
    weighting_parameter: float = Field(default=0.05, ge=0.0)
    minimum_depth_threshold: Optional[Decimal] = None
    maximum_state_age_seconds: float = Field(default=10.0, ge=0.1)


class DepthCalculationConfigResponse(DepthCalculationConfigCreate):
    config_id: str
    version: int
    config_hash: str
    status: str
    created_at: datetime
    created_by: str

    model_config = ConfigDict(from_attributes=True)


class DirectDepthLevelInput(BaseModel):
    price: Decimal
    quantity: Decimal
    order_count: Optional[int] = None


class DirectDepthCalculationRequest(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str = "NSE"
    venue: str = "NSE"
    book_scope: str = "VENUE_SPECIFIC"
    source_feed_id: str = "FEED_DIRECT"
    source_book_snapshot_id: Optional[str] = None
    sequence_number: Optional[int] = None
    event_timestamp: Optional[datetime] = None

    bids: List[DirectDepthLevelInput]
    asks: List[DirectDepthLevelInput]

    contract_multiplier: Decimal = Decimal("1.0")
    tick_size: Optional[Decimal] = None
    config_code: Optional[str] = None
    level_count: Optional[int] = 5
    persist_snapshot: bool = True


class OrderBookDepthLevelResponse(BaseModel):
    side: str
    level_index: int
    price: Decimal
    displayed_quantity: Decimal
    displayed_notional: Decimal
    cumulative_quantity: Decimal
    cumulative_notional: Decimal
    distance_from_midpoint: Optional[Decimal] = None
    distance_bps: Optional[Decimal] = None
    distance_ticks: Optional[Decimal] = None
    order_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class OrderBookDepthBandResponse(BaseModel):
    band_id: str
    band_lower_bound: float
    band_upper_bound: float
    distance_unit: str
    bid_quantity: Decimal
    ask_quantity: Decimal
    bid_notional: Decimal
    ask_notional: Decimal
    bid_level_count: int
    ask_level_count: int
    quantity_imbalance: Optional[Decimal] = None
    notional_imbalance: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class OrderBookDepthSnapshotResponse(BaseModel):
    depth_snapshot_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    venue: str
    book_scope: str
    source_feed_id: str
    sequence_number: Optional[int] = None

    event_timestamp: datetime
    calculation_timestamp: datetime

    best_bid_price: Optional[Decimal] = None
    best_ask_price: Optional[Decimal] = None
    midpoint_price: Optional[Decimal] = None

    bid_level_count: int
    ask_level_count: int
    bid_total_quantity: Decimal
    ask_total_quantity: Decimal
    bid_total_notional: Decimal
    ask_total_notional: Decimal

    quantity_imbalance: Optional[Decimal] = None
    notional_imbalance: Optional[Decimal] = None
    weighted_imbalance: Optional[Decimal] = None

    depth_quality_status: str
    quality_reasons: Optional[str] = None
    calculation_config_id: str
    calculation_config_version: int

    levels: Optional[List[OrderBookDepthLevelResponse]] = None
    bands: Optional[List[OrderBookDepthBandResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class CumulativeDepthResponse(BaseModel):
    instrument_id: str
    venue: str
    levels_requested: int
    midpoint: Optional[Decimal] = None
    bid_cumulative_quantity: Decimal
    bid_cumulative_notional: Decimal
    ask_cumulative_quantity: Decimal
    ask_cumulative_notional: Decimal
    quantity_imbalance: Optional[Decimal] = None
    notional_imbalance: Optional[Decimal] = None
    bids: List[OrderBookDepthLevelResponse]
    asks: List[OrderBookDepthLevelResponse]


class DepthImbalanceResponse(BaseModel):
    instrument_id: str
    venue: str
    levels_considered: int
    bid_quantity: Decimal
    ask_quantity: Decimal
    bid_notional: Decimal
    ask_notional: Decimal
    quantity_imbalance: Optional[Decimal] = None
    quantity_imbalance_percentage: Optional[Decimal] = None
    notional_imbalance: Optional[Decimal] = None
    notional_imbalance_percentage: Optional[Decimal] = None
    weighted_imbalance: Optional[Decimal] = None
    weighted_imbalance_percentage: Optional[Decimal] = None


class DepthPersistenceResponse(BaseModel):
    instrument_id: str
    venue: str
    window_start: datetime
    window_end: datetime
    window_duration_seconds: float

    bid_time_weighted_mean: Optional[Decimal] = None
    ask_time_weighted_mean: Optional[Decimal] = None
    bid_time_weighted_stddev: Optional[Decimal] = None
    ask_time_weighted_stddev: Optional[Decimal] = None
    bid_depth_cv: Optional[float] = None
    ask_depth_cv: Optional[float] = None

    bid_threshold_persistence: Optional[float] = None
    ask_threshold_persistence: Optional[float] = None
    price_level_persistence: Optional[float] = None
    depth_stability_score: Optional[float] = None

    valid_duration_seconds: float
    expected_duration_seconds: float
    coverage_percentage: float
    valid_state_count: int
    quality_status: str

    model_config = ConfigDict(from_attributes=True)

