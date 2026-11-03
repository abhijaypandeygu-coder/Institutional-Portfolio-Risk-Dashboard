"""
Pydantic 2.x schemas for M09.08 Order Book Imbalance.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class LevelInputSchema(BaseModel):
    level_index: int = Field(..., ge=1)
    bid_price: Decimal
    ask_price: Decimal
    bid_quantity: Decimal = Field(..., ge=0)
    ask_quantity: Decimal = Field(..., ge=0)
    bid_notional: Optional[Decimal] = None
    ask_notional: Optional[Decimal] = None


class ImbalanceConfigCreateRequest(BaseModel):
    config_name: str
    description: Optional[str] = None
    depth_level_count: int = 5
    weighting_method: str = "EQUAL"  # EQUAL, EXPONENTIAL_LEVEL, LINEAR_LEVEL, DISTANCE_DECAY, CUSTOM
    decay_parameter: Decimal = Decimal("0.5000")
    distance_unit: str = "PRICE"  # PRICE, TICK, BPS
    custom_weights: Optional[List[float]] = None
    persistence_threshold: Decimal = Decimal("0.2000")
    reversal_entry_threshold: Decimal = Decimal("0.2000")
    reversal_exit_threshold: Decimal = Decimal("0.0500")


class ImbalanceConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    config_name: str
    description: Optional[str] = None
    depth_level_count: int
    weighting_method: str
    decay_parameter: Decimal
    distance_unit: str
    persistence_threshold: Decimal
    reversal_entry_threshold: Decimal
    reversal_exit_threshold: Decimal
    version: int
    is_active: bool
    created_at: datetime


class ImbalanceCalculateRequest(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    venue_id: Optional[str] = "XNYS"
    config_id: Optional[str] = None
    requested_levels: int = 5
    weighting_method: str = "EQUAL"
    decay_parameter: float = 0.5
    distance_unit: str = "PRICE"
    tick_size: Decimal = Decimal("0.01")
    levels: List[LevelInputSchema]


class ImbalanceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    instrument_id: str
    venue_id: Optional[str] = None
    event_timestamp: datetime
    best_level_imbalance: Optional[Decimal] = None
    multi_level_quantity_imbalance: Optional[Decimal] = None
    multi_level_notional_imbalance: Optional[Decimal] = None
    weighted_quantity_imbalance: Optional[Decimal] = None
    weighted_notional_imbalance: Optional[Decimal] = None
    bid_share: Optional[Decimal] = None
    ask_share: Optional[Decimal] = None
    total_bid_quantity: Decimal
    total_ask_quantity: Decimal
    total_bid_notional: Decimal
    total_ask_notional: Decimal
    microprice: Optional[Decimal] = None
    midpoint: Optional[Decimal] = None
    microprice_deviation_bps: Optional[Decimal] = None
    actual_level_count: int
    regime: str
    quality_status: str
    config_id: str


class PersistenceAnalysisRequest(BaseModel):
    instrument_id: str
    venue_id: Optional[str] = None
    threshold: Decimal = Decimal("0.2000")
    observations: List[Dict[str, Any]]  # [{timestamp, imbalance, duration_seconds}]


class PersistenceResponse(BaseModel):
    instrument_id: str
    venue_id: Optional[str] = None
    bid_persistence_ratio: Decimal
    ask_persistence_ratio: Decimal
    neutral_persistence_ratio: Decimal
    current_state: str
    current_run_duration_seconds: Decimal
    max_bid_run_seconds: Decimal
    max_ask_run_seconds: Decimal
    average_bid_run_seconds: Decimal
    average_ask_run_seconds: Decimal
    total_valid_duration_seconds: Decimal


class ReversalDetectionRequest(BaseModel):
    instrument_id: str
    venue_id: Optional[str] = None
    entry_threshold: Decimal = Decimal("0.2000")
    exit_threshold: Decimal = Decimal("0.0500")
    observations: List[Dict[str, Any]]  # [{timestamp, imbalance, duration_seconds}]


class ReversalEventSchema(BaseModel):
    timestamp: datetime
    previous_state: str
    new_state: str
    previous_imbalance: Decimal
    current_imbalance: Decimal
    reversal_magnitude: Decimal
    reversal_rate_per_sec: Decimal
    duration_seconds: Decimal


class ReversalDetectionResponse(BaseModel):
    instrument_id: str
    reversal_count: int
    reversals: List[ReversalEventSchema]


class VenueComparisonRequest(BaseModel):
    instrument_id: str
    venues_data: Dict[str, List[LevelInputSchema]]  # e.g. {"XNYS": [...], "XNAS": [...]}


class VenueComparisonResponse(BaseModel):
    instrument_id: str
    venues: Dict[str, Any]

