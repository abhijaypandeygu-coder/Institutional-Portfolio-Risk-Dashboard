"""
Pydantic Schemas for M03.06 - Data Consistency.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class ObservationComparisonInput(BaseModel):
    observation_id: str
    provider_id: str
    feed_id: str
    instrument_id: str
    exchange: str = "NSE"
    currency: str = "INR"
    observation_type: str = "TICK"  # TICK, TRADE, OHLCV, QUOTE, DEPTH
    timestamp: datetime
    value: Any = Field(..., description="Observed price or metric value")
    data_origin: str = "SIMULATOR"  # REAL, SIMULATOR
    is_valid: bool = True
    is_stale: bool = False


class CrossFeedCompareRequest(BaseModel):
    instrument_id: str
    exchange: str = "NSE"
    observation_type: str = "TICK"
    currency: str = "INR"
    source_a: ObservationComparisonInput
    source_b: ObservationComparisonInput
    percentage_tolerance: Optional[Decimal] = None
    absolute_tolerance: Optional[Decimal] = None
    max_time_alignment_ms: int = 5000
    allow_real_vs_sim: bool = False  # Strict safety: reject comparing real vs simulated by default


class ComparisonResultResponse(BaseModel):
    result_id: str
    instrument_id: str
    exchange: str
    observation_type: str
    source_a_provider: str
    observation_a_id: str
    value_a: Decimal
    timestamp_a: datetime
    source_b_provider: str
    observation_b_id: str
    value_b: Decimal
    timestamp_b: datetime
    currency: str
    absolute_difference: Decimal
    percentage_difference: Optional[Decimal] = None
    tolerance_applied: Decimal
    comparison_status: str  # CONSISTENT, INCONSISTENT, UNCOMPARABLE, CURRENCY_MISMATCH, TIMESTAMP_MISMATCH
    severity: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    conflict_created: bool = False
    conflict_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OHLCFieldValidationInput(BaseModel):
    observation_id: str
    instrument_id: str
    exchange: str = "NSE"
    open_price: Any
    high_price: Any
    low_price: Any
    close_price: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QuoteFieldValidationInput(BaseModel):
    observation_id: str
    instrument_id: str
    exchange: str = "NSE"
    bid_price: Any
    ask_price: Any
    bid_quantity: Any
    ask_quantity: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FieldConsistencyResponse(BaseModel):
    result_id: str
    instrument_id: str
    observation_id: str
    observation_type: str
    validation_status: str  # FIELD_CONSISTENT, FIELD_INCONSISTENT
    violations: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class ConflictResolutionActionRequest(BaseModel):
    action: str = Field(..., description="ACCEPT_SOURCE_A, ACCEPT_SOURCE_B, REJECT_BOTH, MANUAL_OVERRIDE")
    justification: str = Field(..., description="Auditable reasoning for resolution")
    selected_observation_id: Optional[str] = None


class ConflictResponse(BaseModel):
    conflict_key: str
    instrument_id: str
    exchange: str
    conflict_type: str
    observation_type: str
    severity: str
    conflict_status: str
    selected_source: Optional[str] = None
    selected_observation_id: Optional[str] = None
    resolution_method: Optional[str] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    evidence: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class SourcePrecedenceRuleCreate(BaseModel):
    rule_code: str
    exchange: str = "NSE"
    market: str = "IN"
    instrument_id: Optional[str] = None
    observation_type: str = "ALL"
    provider_id: str
    feed_id: Optional[str] = None
    priority: int = 100
    enabled: bool = True


class SourcePrecedenceRuleResponse(SourcePrecedenceRuleCreate):
    id: int
    version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsistencySummary(BaseModel):
    total_comparisons: int
    consistent_count: int
    inconsistent_count: int
    uncomparable_count: int
    open_conflicts: int
    resolved_conflicts: int
    consistency_rate_percentage: float
