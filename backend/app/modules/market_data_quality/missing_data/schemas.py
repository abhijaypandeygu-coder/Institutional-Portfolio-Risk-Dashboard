"""
Module 03.01: Missing Data Detection - Pydantic 2.x API Schemas.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.market_data_quality.missing_data.models import (
    CoverageStatus,
    IncidentSeverity,
    IncidentStatus,
    IssueType,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Policy Schemas
# ============================================================================

class PolicyCreate(BaseModel):
    policy_code: str = Field(..., min_length=3, max_length=64)
    instrument_id: Optional[str] = None
    exchange: str = "NSE"
    provider_id: str = "SIMULATOR"
    feed_id: Optional[str] = None
    data_channel: str = "TICK"
    observation_type: str = "REALTIME"
    expected_frequency: str = "REALTIME"
    grace_period_seconds: int = 60
    inactivity_threshold_seconds: int = 300
    policy_parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 10


class PolicyResponse(ORMModel):
    id: UUID
    policy_code: str
    instrument_id: Optional[str] = None
    exchange: str
    provider_id: str
    feed_id: Optional[str] = None
    data_channel: str
    observation_type: str
    expected_frequency: str
    grace_period_seconds: int
    inactivity_threshold_seconds: int
    priority: int
    enabled: bool
    created_at: datetime


# ============================================================================
# Incident Schemas
# ============================================================================

class IncidentResponse(ORMModel):
    id: UUID
    incident_key: str
    instrument_id: str
    feed_id: str
    provider_id: str
    exchange: str
    data_type: str
    issue_type: str
    missing_start: Optional[str] = None
    missing_end: Optional[str] = None
    missing_count: int
    first_detected_at: datetime
    last_detected_at: datetime
    confirmed_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    issue_status: str
    severity: str
    confidence: float
    evidence: Dict[str, Any]
    resolution_reason: Optional[str] = None


class IncidentActionRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=256)


# ============================================================================
# Coverage Window Schemas
# ============================================================================

class CoverageWindowResponse(ORMModel):
    id: UUID
    instrument_id: str
    feed_id: str
    provider_id: str
    exchange: str
    data_type: str
    interval_type: str
    window_start: datetime
    window_end: datetime
    expected_units: int
    observed_units: int
    missing_units: int
    coverage_percentage: float
    coverage_status: str
    calculation_timestamp: datetime
    calculation_metadata: Dict[str, Any]


class QualitySummaryResponse(BaseModel):
    open_incidents_count: int
    critical_incidents_count: int
    recent_coverage_average: float
    status: str

