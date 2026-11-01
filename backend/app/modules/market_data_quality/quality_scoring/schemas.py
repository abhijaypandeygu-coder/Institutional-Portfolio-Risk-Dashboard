"""
Pydantic Schemas for M03.07 - Quality Scoring.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class FeedReliabilityInput(BaseModel):
    provider_id: str
    feed_id: str
    instrument_id: Optional[str] = None
    data_type: str = "ALL"
    expected_duration_seconds: int = Field(..., ge=0)
    unavailable_duration_seconds: int = Field(0, ge=0)
    eligible_operations: int = Field(..., ge=0)
    failed_operations: int = Field(0, ge=0)
    eligible_expected_observations: int = Field(..., ge=0)
    timely_observations: int = Field(0, ge=0)
    late_observations: int = Field(0, ge=0)


class FeedReliabilityResponse(BaseModel):
    score_id: str
    provider_id: str
    feed_id: str
    instrument_id: Optional[str] = None
    data_type: str
    availability_score: Decimal
    timeliness_score: Decimal
    error_score: Decimal
    reliability_score: Decimal
    reliability_classification: str
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompletenessEvaluationInput(BaseModel):
    provider_id: str
    feed_id: str
    instrument_id: str
    data_type: str = "OHLCV"
    expected_records: int = Field(..., ge=0)
    observed_unique_records: int = Field(..., ge=0)
    valid_records: int = Field(..., ge=0)
    missing_records: int = Field(0, ge=0)
    invalid_records: int = Field(0, ge=0)
    duplicate_receipts: int = Field(0, ge=0)
    expected_fields_count: int = Field(1, ge=1)
    valid_fields_count: int = Field(1, ge=0)


class CompletenessScoreResponse(BaseModel):
    score_id: str
    provider_id: str
    feed_id: str
    instrument_id: str
    data_type: str
    expected_records: int
    observed_unique_records: int
    completeness_score: Decimal
    completeness_classification: str
    field_completeness_ratio: Decimal
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FreshnessEvaluationInput(BaseModel):
    provider_id: str
    feed_id: str
    instrument_id: str
    data_type: str = "TICK"
    calculation_context: str = "LIVE_MONITORING"
    target_age_ms: int = Field(1000, ge=0)
    maximum_age_ms: int = Field(10000, ge=1)
    observed_age_ms: int = Field(..., ge=0)
    is_market_closed: bool = False
    is_historical_eod: bool = False


class FreshnessScoreResponse(BaseModel):
    score_id: str
    provider_id: str
    feed_id: str
    instrument_id: str
    data_type: str
    calculation_context: str
    observed_age_ms: int
    freshness_score: Decimal
    freshness_classification: str
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompositeQualityRequest(BaseModel):
    provider_id: str
    feed_id: str
    instrument_id: Optional[str] = None
    data_type: str = "ALL"
    data_origin: str = "SIMULATED"  # REAL, SIMULATED
    reliability: FeedReliabilityInput
    completeness: CompletenessEvaluationInput
    freshness: FreshnessEvaluationInput


class CompositeQualitySnapshotResponse(BaseModel):
    snapshot_id: str
    provider_id: str
    feed_id: str
    instrument_id: Optional[str] = None
    reliability_score: Decimal
    completeness_score: Decimal
    freshness_score: Decimal
    composite_quality_score: Decimal
    score_status: str
    data_origin: str
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EligibilityEvaluationRequest(BaseModel):
    profile_code: str  # DAILY_VALUATION, HISTORICAL_VAR, SPREAD_CALCULATION, ORDER_BOOK_IMBALANCE
    provider_id: str
    feed_id: str
    instrument_id: Optional[str] = None
    calculation_context: str = "DEFAULT"
    data_origin: str = "SIMULATED"

    # Component Scores
    reliability_score: Decimal
    completeness_score: Decimal
    freshness_score: Decimal

    # Mandatory Upstream Hard-Gate Signals
    is_price_valid: bool = True
    is_timestamp_valid: bool = True
    is_order_book_continuous: bool = True
    has_unresolved_cross_feed_conflict: bool = False
    is_capability_supported: bool = True


class UseEligibilityDecisionResponse(BaseModel):
    decision_id: str
    profile_code: str
    provider_id: str
    feed_id: str
    instrument_id: Optional[str] = None
    calculation_context: str
    eligibility_status: str  # ACCEPTED, ACCEPTED_WITH_WARNING, RESTRICTED, REJECTED, NOT_SUPPORTED, UNKNOWN
    reliability_score: Decimal
    completeness_score: Decimal
    freshness_score: Decimal
    hard_gate_results: Dict[str, Any] = Field(default_factory=dict)
    decision_explanation: str
    evaluated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityScoringPolicyCreate(BaseModel):
    policy_code: str
    policy_name: str
    score_type: str = "COMPOSITE"
    provider_id: Optional[str] = None
    feed_id: Optional[str] = None
    instrument_id: Optional[str] = None
    data_type: str = "ALL"
    rolling_window: str = "24h"
    availability_weight: Decimal = Decimal("0.4000")
    timeliness_weight: Decimal = Decimal("0.3500")
    error_weight: Decimal = Decimal("0.2500")
    reliability_weight: Decimal = Decimal("0.3500")
    completeness_weight: Decimal = Decimal("0.3500")
    freshness_weight: Decimal = Decimal("0.3000")
    enabled: bool = True


class QualityScoringPolicyResponse(QualityScoringPolicyCreate):
    id: int
    version: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

