"""
Pydantic Schemas for M08.08 Factor Monitoring.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.factor_monitoring.models import (
    MonitoringScope,
    EvaluationFrequency,
    DriftReferenceType,
    DriftClassification,
    ConcentrationStatus,
    ThresholdMetricType,
    ThresholdEvaluationStatus,
    BreachSeverity,
    BreachStatus,
    MonitoringRunStatus,
)


# ---------------------------------------------------------
# Configuration Schemas
# ---------------------------------------------------------

class FactorMonitoringConfigCreate(BaseModel):
    config_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    evaluation_frequency: EvaluationFrequency = EvaluationFrequency.DAILY
    drift_reference_type: DriftReferenceType = DriftReferenceType.PREVIOUS_SNAPSHOT
    historical_baseline_window: int = Field(60, ge=5, le=504)
    persistence_required: int = Field(1, ge=1)
    recovery_required: int = Field(2, ge=1)


class FactorMonitoringConfigResponse(BaseModel):
    id: int
    config_id: str
    config_code: str
    version_number: int
    name: str
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    evaluation_frequency: EvaluationFrequency
    drift_reference_type: DriftReferenceType
    historical_baseline_window: int
    persistence_required: int
    recovery_required: int
    config_hash: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Target Profile Schemas
# ---------------------------------------------------------

class FactorExposureTargetComponentCreate(BaseModel):
    factor_id: str
    factor_code: str
    target_exposure: Decimal
    min_exposure: Optional[Decimal] = None
    max_exposure: Optional[Decimal] = None
    tolerance: Decimal = Decimal("0.20")


class FactorExposureTargetComponentResponse(BaseModel):
    id: int
    factor_id: str
    factor_code: str
    target_exposure: Decimal
    min_exposure: Optional[Decimal] = None
    max_exposure: Optional[Decimal] = None
    tolerance: Decimal
    model_config = ConfigDict(from_attributes=True)


class FactorExposureTargetCreate(BaseModel):
    target_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    portfolio_id: str
    factor_model_id: str
    factor_model_version_id: str
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    components: List[FactorExposureTargetComponentCreate] = []


class FactorExposureTargetResponse(BaseModel):
    id: int
    target_id: str
    target_code: str
    name: str
    portfolio_id: str
    factor_model_id: str
    factor_model_version_id: str
    target_hash: str
    effective_from: date
    effective_to: Optional[date] = None
    is_approved: bool
    approved_by: Optional[str] = None
    created_at: datetime
    components: List[FactorExposureTargetComponentResponse] = []
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Threshold Policy Schemas
# ---------------------------------------------------------

class FactorThresholdPolicyCreate(BaseModel):
    policy_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    portfolio_id: Optional[str] = None
    factor_id: Optional[str] = None
    factor_code: Optional[str] = None
    metric_type: ThresholdMetricType
    min_boundary: Optional[Decimal] = None
    max_boundary: Optional[Decimal] = None
    warning_threshold: Optional[Decimal] = None
    breach_threshold: Decimal
    critical_threshold: Optional[Decimal] = None
    recovery_threshold: Optional[Decimal] = None
    persistence_count: int = Field(1, ge=1)
    recovery_count: int = Field(2, ge=1)
    severity: BreachSeverity = BreachSeverity.WARNING
    policy_precedence: int = 100


class FactorThresholdPolicyResponse(BaseModel):
    id: int
    policy_id: str
    policy_code: str
    name: str
    portfolio_id: Optional[str] = None
    factor_id: Optional[str] = None
    factor_code: Optional[str] = None
    metric_type: ThresholdMetricType
    min_boundary: Optional[Decimal] = None
    max_boundary: Optional[Decimal] = None
    warning_threshold: Optional[Decimal] = None
    breach_threshold: Decimal
    critical_threshold: Optional[Decimal] = None
    recovery_threshold: Optional[Decimal] = None
    persistence_count: int
    recovery_count: int
    severity: BreachSeverity
    policy_precedence: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Drift & Concentration Schemas
# ---------------------------------------------------------

class FactorExposureDriftResponse(BaseModel):
    id: int
    factor_id: str
    factor_code: str
    current_exposure: Decimal
    reference_exposure: Decimal
    target_exposure: Optional[Decimal] = None
    signed_drift: Decimal
    absolute_drift: Decimal
    percentage_drift: Optional[Decimal] = None
    is_percentage_drift_defined: bool
    standardized_current_exposure: Optional[Decimal] = None
    standardized_reference_exposure: Optional[Decimal] = None
    standardized_drift: Optional[Decimal] = None
    is_sign_reversal: bool
    sign_change_description: str
    drift_classification: DriftClassification
    model_config = ConfigDict(from_attributes=True)


class FactorConcentrationResponse(BaseModel):
    id: int
    run_id: str
    exposure_hhi: Optional[Decimal] = None
    effective_exposure_factors: Optional[Decimal] = None
    top_factor_exposure_share: Optional[Decimal] = None
    top_two_exposure_share: Optional[Decimal] = None
    top_three_exposure_share: Optional[Decimal] = None
    top_exposure_factor: Optional[str] = None
    risk_hhi: Optional[Decimal] = None
    effective_risk_factors: Optional[Decimal] = None
    top_factor_risk_share: Optional[Decimal] = None
    top_two_risk_share: Optional[Decimal] = None
    top_three_risk_share: Optional[Decimal] = None
    top_risk_factor: Optional[str] = None
    concentration_status: ConcentrationStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FactorThresholdEvaluationResponse(BaseModel):
    id: int
    policy_id: str
    factor_code: Optional[str] = None
    metric_type: ThresholdMetricType
    measurement_value: Optional[Decimal] = None
    limit_value: Optional[Decimal] = None
    utilization_percentage: Optional[Decimal] = None
    headroom: Optional[Decimal] = None
    evaluation_status: ThresholdEvaluationStatus
    is_breach: bool
    is_warning: bool
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Run Execution Schemas
# ---------------------------------------------------------

class FactorMonitoringRunRequest(BaseModel):
    portfolio_id: str
    factor_model_version_id: str
    as_of_date: date
    config_id: Optional[str] = None
    target_id: Optional[str] = None
    drift_reference_type: Optional[DriftReferenceType] = DriftReferenceType.PREVIOUS_SNAPSHOT
    evaluate_thresholds: bool = True
    publish_events: bool = True


class FactorMonitoringRunResponse(BaseModel):
    id: int
    run_id: str
    portfolio_id: str
    factor_model_version_id: str
    config_id: Optional[str] = None
    target_id: Optional[str] = None
    as_of_date: date
    status: MonitoringRunStatus
    drift_status: str
    concentration_status: ConcentrationStatus
    has_active_breaches: bool
    active_breach_count: int
    warning_count: int
    critical_breach_count: int
    input_freshness: Dict[str, Any] = {}
    result_hash: str
    drifts: List[FactorExposureDriftResponse] = []
    concentration: Optional[FactorConcentrationResponse] = None
    evaluations: List[FactorThresholdEvaluationResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Breach & Event Schemas
# ---------------------------------------------------------

class FactorMonitoringBreachResponse(BaseModel):
    id: int
    breach_id: str
    portfolio_id: str
    policy_id: str
    factor_code: Optional[str] = None
    metric_type: ThresholdMetricType
    severity: BreachSeverity
    breach_status: BreachStatus
    current_measurement: Decimal
    threshold_value: Decimal
    utilization_percentage: Optional[Decimal] = None
    first_detected_at: datetime
    last_detected_at: datetime
    consecutive_observation_count: int
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    recovered_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class FactorMonitoringEventResponse(BaseModel):
    id: int
    event_id: str
    run_id: str
    portfolio_id: str
    factor_code: Optional[str] = None
    event_type: str
    severity: BreachSeverity
    message: str
    event_payload: Dict[str, Any] = {}
    deduplication_key: str
    is_published: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BreachAcknowledgeRequest(BaseModel):
    user_id: str
    note: Optional[str] = None

