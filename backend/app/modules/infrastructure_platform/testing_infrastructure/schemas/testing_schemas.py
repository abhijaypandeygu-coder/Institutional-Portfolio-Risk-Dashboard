from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.testing_infrastructure.models.testing_models import (
    TestProfileType,
    TestRunStatus,
    QualityGateStatus,
)


class TestProfileCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    profile_type: TestProfileType = Field(default=TestProfileType.UNIT)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class TestProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    profile_type: Optional[TestProfileType] = None
    configuration: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class TestProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: str
    name: str
    description: Optional[str] = None
    profile_type: TestProfileType
    configuration: Dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class TestRunTriggerRequest(BaseModel):
    profile_id: str
    module_target: Optional[str] = None # e.g. "portfolio_management" or "all"
    triggered_by: Optional[str] = "tester"


class TestResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: str
    test_identifier: str
    module_name: str
    test_category: str
    status: str
    duration_ms: Optional[float] = None
    failure_code: Optional[str] = None


class TestRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    profile_id: str
    status: TestRunStatus
    code_revision: Optional[str] = None
    environment_metadata: Dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    triggered_by: str
    passed_count: int
    failed_count: int
    skipped_count: int
    error_summary: Optional[str] = None
    artifact_reference: Optional[str] = None


class RegressionComparisonItem(BaseModel):
    calculation_name: str
    dataset_id: str
    baseline_version: str
    passed: bool
    expected_value: Any
    actual_value: Any
    absolute_diff: Optional[float] = None
    relative_diff: Optional[float] = None
    tolerance: Dict[str, float]
    notes: Optional[str] = None


class RegressionComparisonResponse(BaseModel):
    baseline_id: str
    calculation_name: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    comparisons: List[RegressionComparisonItem]


class PerformanceBenchmarkCreate(BaseModel):
    benchmark_name: str
    workload_config: Dict[str, Any]
    environment_metadata: Dict[str, Any]
    latency_metrics: Dict[str, float]
    throughput_metrics: Dict[str, float]
    resource_metrics: Dict[str, float]


class PerformanceBenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    benchmark_id: str
    test_run_id: Optional[str] = None
    benchmark_name: str
    workload_config: Dict[str, Any]
    environment_metadata: Dict[str, Any]
    latency_metrics: Dict[str, float]
    throughput_metrics: Dict[str, float]
    resource_metrics: Dict[str, float]
    created_at: datetime


class CoverageResponse(BaseModel):
    total_coverage: float
    module_coverage: Dict[str, float]
    branch_coverage: Optional[float] = None
    uncovered_critical_modules: List[str] = Field(default_factory=list)


class QualityGateEvaluationResponse(BaseModel):
    gate_name: str
    overall_status: QualityGateStatus
    criteria_evaluated: List[Dict[str, Any]]
    blocking_failures: List[str]
    warnings: List[str]
    timestamp: datetime
