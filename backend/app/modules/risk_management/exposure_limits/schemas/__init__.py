"""
Pydantic 2.x Schemas for M06.08 Exposure Limits.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.risk_management.exposure_limits.models import (
    ExposureLimitCategory,
    ExposureMeasurementBasis,
    ExposureLimitDirection,
    ExposureLimitDenominatorType,
    ExposureLimitStatus,
    ExposureBreachEventType,
)


class ExposureLimitConfigCreateRequest(BaseModel):
    limit_code: str
    limit_name: str
    limit_category: ExposureLimitCategory
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    target_entity_id: Optional[str] = None
    target_entity_name: Optional[str] = None

    exposure_basis: ExposureMeasurementBasis = ExposureMeasurementBasis.GROSS_MARKET_VALUE
    limit_direction: ExposureLimitDirection = ExposureLimitDirection.MAXIMUM
    denominator_type: ExposureLimitDenominatorType = ExposureLimitDenominatorType.PORTFOLIO_NAV

    limit_value: Decimal
    warning_threshold_ratio: Decimal = Decimal("0.850000")
    severe_breach_threshold_ratio: Decimal = Decimal("1.100000")
    reporting_currency: str = "USD"
    policy_version: str = "v1.0"


class ExposureLimitConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    limit_id: str
    limit_code: str
    limit_name: str
    limit_category: ExposureLimitCategory
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    target_entity_id: Optional[str] = None
    target_entity_name: Optional[str] = None

    exposure_basis: ExposureMeasurementBasis
    limit_direction: ExposureLimitDirection
    denominator_type: ExposureLimitDenominatorType

    limit_value: Decimal
    warning_threshold_ratio: Decimal
    severe_breach_threshold_ratio: Decimal
    reporting_currency: str
    is_active: bool
    policy_version: str
    effective_from: datetime


class ExposureLimitEvaluateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    as_of_date: Optional[datetime] = None
    reporting_currency: str = "USD"
    snapshot_id: Optional[str] = None


class ExposureLimitEvaluationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: str
    limit_id: str
    limit_code: str
    limit_name: str
    limit_category: ExposureLimitCategory
    target_entity_id: Optional[str] = None
    target_entity_name: Optional[str] = None

    exposure_basis: ExposureMeasurementBasis
    limit_direction: ExposureLimitDirection
    denominator_type: ExposureLimitDenominatorType

    measured_exposure: Decimal
    denominator_value: Decimal
    limit_value: Decimal
    utilization_percentage: Decimal
    headroom: Decimal
    shortfall: Decimal

    status: ExposureLimitStatus
    data_completeness_status: str
    source_reference: Optional[str] = None
    evaluated_at: datetime


class ExposureLimitEvaluationSummaryResponse(BaseModel):
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    total_evaluated_limits: int
    within_limit_count: int
    warning_count: int
    breached_count: int
    severely_breached_count: int
    unavailable_count: int

    items: List[ExposureLimitEvaluationItemResponse]


class ExposureLimitBreachHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    limit_id: str
    portfolio_id: Optional[str] = None
    target_entity_id: Optional[str] = None

    previous_status: Optional[ExposureLimitStatus] = None
    new_status: ExposureLimitStatus
    event_type: ExposureBreachEventType

    measured_exposure: Decimal
    limit_value: Decimal
    headroom: Decimal
    details: Optional[str] = None
    recorded_at: datetime


class ExposureLimitSimulateRequest(BaseModel):
    portfolio_id: str
    limit_id: str
    proposed_exposure_delta: Decimal
    reporting_currency: str = "USD"


class ExposureLimitSimulationResponse(BaseModel):
    portfolio_id: str
    limit_id: str
    current_exposure: Decimal
    proposed_exposure_delta: Decimal
    projected_exposure: Decimal
    limit_value: Decimal
    current_utilization: Decimal
    projected_utilization: Decimal
    current_headroom: Decimal
    projected_headroom: Decimal
    current_status: ExposureLimitStatus
    projected_status: ExposureLimitStatus
