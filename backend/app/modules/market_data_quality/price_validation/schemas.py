"""
Module 03.02: Price Validation - Canonical Schemas (Pydantic 2.x).
Defines request, response, and canonical inspection contracts for:
- Price validation evaluation
- Batch price validation
- Validation results & evidence
- Rule definition & management
- Anomaly incidents & lifecycle
- Reference price snapshot creation & cross-source comparisons
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.market_data_quality.price_validation.models import (
    AnomalyIncidentStatus,
    EnforcementAction,
    RuleCategory,
    ValidationSeverity,
    ValidationStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# Price Observation Input
# ============================================================================

class PriceObservationInput(BaseModel):
    """Canonical input structure for price validation."""
    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument_id: str
    feed_id: str
    provider_id: str = "SIMULATOR"
    exchange: str = "NSE"
    observation_type: str = "TICK"  # TICK, OHLCV, TRADE, ORDER_BOOK_L1
    price_field: str = "last_traded_price"  # last_traded_price, close, open, bid, ask
    
    raw_price: Any = None  # May be string, float, Decimal, None, or invalid object
    
    # Contextual fields for OHLC relationships if observation_type == 'OHLCV'
    open_price: Optional[Any] = None
    high_price: Optional[Any] = None
    low_price: Optional[Any] = None
    close_price: Optional[Any] = None
    volume: Optional[Any] = None
    
    currency: Optional[str] = "INR"
    observation_timestamp: datetime = Field(default_factory=utc_now)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class BatchPriceObservationInput(BaseModel):
    observations: List[PriceObservationInput]


# ============================================================================
# Rule Schemas
# ============================================================================

class RuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    rule_category: RuleCategory
    observation_type: str = "ALL"
    price_field: str = "ALL"
    instrument_id: Optional[str] = None
    exchange: str = "ALL"
    provider_id: Optional[str] = None
    currency: Optional[str] = None
    
    threshold_type: Optional[str] = None  # PERCENTAGE, ABSOLUTE, Z_SCORE
    threshold_value: Optional[Decimal] = None
    severity: ValidationSeverity = ValidationSeverity.MEDIUM
    enforcement_action: EnforcementAction = EnforcementAction.WARN
    rule_parameters: Dict[str, Any] = Field(default_factory=dict)
    
    priority: int = 100
    description: Optional[str] = None


class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    threshold_value: Optional[Decimal] = None
    severity: Optional[ValidationSeverity] = None
    enforcement_action: Optional[EnforcementAction] = None
    rule_parameters: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class RuleResponse(BaseModel):
    id: UUID
    rule_code: str
    rule_name: str
    rule_category: RuleCategory
    observation_type: str
    price_field: str
    instrument_id: Optional[str]
    exchange: str
    provider_id: Optional[str]
    currency: Optional[str]
    threshold_type: Optional[str]
    threshold_value: Optional[Decimal]
    severity: ValidationSeverity
    enforcement_action: EnforcementAction
    rule_parameters: Dict[str, Any]
    priority: int
    version: int
    effective_from: datetime
    effective_until: Optional[datetime]
    enabled: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Validation Evidence & Results
# ============================================================================

class EvidenceItem(BaseModel):
    rule_code: str
    evidence_type: str
    observed_value: Optional[Decimal] = None
    reference_value: Optional[Decimal] = None
    threshold_value: Optional[Decimal] = None
    calculated_difference: Optional[Decimal] = None
    calculated_percentage: Optional[Decimal] = None
    source_reference: Optional[str] = None
    status: ValidationStatus
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class ValidationResultResponse(BaseModel):
    id: UUID
    observation_id: str
    instrument_id: str
    feed_id: str
    provider_id: str
    exchange: str
    observation_type: str
    price_field: str
    original_price_value: Optional[str]
    parsed_price_value: Optional[Decimal]
    validation_status: ValidationStatus
    overall_severity: ValidationSeverity
    failed_rule_count: int
    warning_count: int
    is_downstream_eligible: bool
    rule_version_summary: Dict[str, Any]
    evidence_summary: Dict[str, Any]
    validation_timestamp: datetime
    evidence_items: List[EvidenceItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Price Anomaly Incident
# ============================================================================

class IncidentResolutionRequest(BaseModel):
    status: AnomalyIncidentStatus
    resolution_reason: str


class PriceAnomalyIncidentResponse(BaseModel):
    id: UUID
    incident_key: str
    instrument_id: str
    feed_id: str
    provider_id: str
    exchange: str
    anomaly_type: str
    observed_price: Optional[Decimal]
    reference_price: Optional[Decimal]
    absolute_difference: Optional[Decimal]
    percentage_difference: Optional[Decimal]
    applicable_threshold: Optional[Decimal]
    severity: ValidationSeverity
    incident_status: AnomalyIncidentStatus
    first_detected_at: datetime
    last_detected_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    resolution_reason: Optional[str]
    evidence: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Reference Price Snapshot & Cross-Source Comparison
# ============================================================================

class ReferenceSnapshotCreate(BaseModel):
    instrument_id: str
    exchange: str
    reference_type: str  # PREVIOUS_CLOSE, OFFICIAL_REFERENCE, etc.
    reference_value: Decimal
    currency: str = "INR"
    source_provider: str = "EXCHANGE"
    effective_date: Optional[date] = None
    adjustment_basis: str = "UNADJUSTED"
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class ReferenceSnapshotResponse(BaseModel):
    id: UUID
    instrument_id: str
    exchange: str
    reference_type: str
    reference_value: Decimal
    currency: str
    source_provider: str
    source_timestamp: datetime
    retrieval_timestamp: datetime
    effective_date: Optional[date]
    adjustment_basis: str
    metadata_payload: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class CrossSourceCompareRequest(BaseModel):
    instrument_id: str
    exchange: str
    observation_type: str = "TICK"
    price_a: Decimal
    provider_a: str
    price_b: Decimal
    provider_b: str
    currency: str = "INR"
    timestamp_a: datetime = Field(default_factory=utc_now)
    timestamp_b: datetime = Field(default_factory=utc_now)
    max_tolerance_percentage: Decimal = Decimal("1.0")


class CrossSourceCompareResponse(BaseModel):
    instrument_id: str
    exchange: str
    price_a: Decimal
    provider_a: str
    price_b: Decimal
    provider_b: str
    absolute_difference: Decimal
    percentage_discrepancy: Optional[Decimal]
    tolerance_percentage: Decimal
    is_discrepant: bool
    status: ValidationStatus
    notes: Optional[str] = None


class PriceQualitySummary(BaseModel):
    total_observations_validated: int
    accepted_count: int
    warning_count: int
    rejected_count: int
    quarantined_count: int
    open_anomalies_count: int
    eligibility_rate_percentage: float
