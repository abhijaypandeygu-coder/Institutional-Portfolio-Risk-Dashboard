import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class TestProfileType(str, enum.Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    PERFORMANCE = "performance"
    SMOKE = "smoke"
    FULL = "full"


class TestRunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIALLY_PASSED = "PARTIALLY_PASSED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class QualityGateStatus(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


class TestProfile(Base):
    """Institutional execution profile for automated test pipelines."""
    __tablename__ = "testing_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    profile_type = Column(SQLEnum(TestProfileType), nullable=False, default=TestProfileType.UNIT)
    configuration = Column(JSON, nullable=False, default=dict) # discovery args, timeout, markers
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    runs = relationship("TestRun", back_populates="profile", cascade="all, delete-orphan")


class TestRun(Base):
    """Record of an automated test execution suite."""
    __tablename__ = "testing_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    profile_id = Column(String(64), ForeignKey("testing_profiles.profile_id"), nullable=False, index=True)
    status = Column(SQLEnum(TestRunStatus), nullable=False, default=TestRunStatus.QUEUED)
    code_revision = Column(String(64), nullable=True, default="HEAD")
    environment_metadata = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Float, nullable=True)
    triggered_by = Column(String(128), nullable=False, default="system")
    passed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    error_summary = Column(Text, nullable=True)
    artifact_reference = Column(String(256), nullable=True)

    profile = relationship("TestProfile", back_populates="runs")
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")
    benchmarks = relationship("PerformanceBenchmark", back_populates="test_run", cascade="all, delete-orphan")
    gate_results = relationship("QualityGateResult", back_populates="test_run", cascade="all, delete-orphan")


class TestResult(Base):
    """Summarized individual test or test module outcome."""
    __tablename__ = "testing_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(String(64), unique=True, nullable=False, index=True)
    test_run_id = Column(String(64), ForeignKey("testing_runs.run_id"), nullable=False, index=True)
    test_identifier = Column(String(256), nullable=False)
    module_name = Column(String(128), nullable=False, index=True)
    test_category = Column(String(64), nullable=False) # unit, integration, math, regression
    status = Column(String(32), nullable=False) # PASSED, FAILED, SKIPPED
    duration_ms = Column(Float, nullable=True)
    failure_code = Column(String(64), nullable=True)
    artifact_reference = Column(String(256), nullable=True)

    test_run = relationship("TestRun", back_populates="results")


class TestDataset(Base):
    """Registry of version-controlled deterministic test datasets."""
    __tablename__ = "testing_datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    version = Column(String(32), nullable=False, default="1.0.0")
    dataset_type = Column(String(64), nullable=False) # portfolio, market_data, order_book, factor
    schema_version = Column(String(32), nullable=False, default="v1")
    generator_version = Column(String(64), nullable=True)
    checksum = Column(String(64), nullable=False)
    storage_reference = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    approved = Column(Boolean, nullable=False, default=True)


class RegressionBaseline(Base):
    """Expected-output reference baselines for mathematical and risk calculations."""
    __tablename__ = "testing_regression_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    baseline_id = Column(String(64), unique=True, nullable=False, index=True)
    dataset_id = Column(String(64), ForeignKey("testing_datasets.dataset_id"), nullable=False, index=True)
    calculation_name = Column(String(128), nullable=False, index=True) # var_95, gross_exposure, covariance
    methodology_version = Column(String(32), nullable=False, default="v1.0")
    expected_output_reference = Column(JSON, nullable=False) # hand-calculated values, expected matrices
    tolerance_config = Column(JSON, nullable=False) # atol, rtol
    version = Column(String(32), nullable=False, default="1.0.0")
    approval_status = Column(String(32), nullable=False, default="APPROVED")
    approved_by = Column(String(128), nullable=False, default="Lead Quant Architect")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PerformanceBenchmark(Base):
    """Recorded latency, throughput, and hardware benchmarks."""
    __tablename__ = "testing_performance_benchmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    benchmark_id = Column(String(64), unique=True, nullable=False, index=True)
    test_run_id = Column(String(64), ForeignKey("testing_runs.run_id"), nullable=True, index=True)
    benchmark_name = Column(String(128), nullable=False, index=True)
    workload_config = Column(JSON, nullable=False)
    environment_metadata = Column(JSON, nullable=False)
    latency_metrics = Column(JSON, nullable=False) # mean_ms, p50_ms, p95_ms, p99_ms
    throughput_metrics = Column(JSON, nullable=False) # ops_per_sec
    resource_metrics = Column(JSON, nullable=False) # cpu_pct, memory_mb
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    test_run = relationship("TestRun", back_populates="benchmarks")


class CoverageSnapshot(Base):
    """Aggregated test coverage metrics."""
    __tablename__ = "testing_coverage_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), unique=True, nullable=False, index=True)
    test_run_id = Column(String(64), ForeignKey("testing_runs.run_id"), nullable=False, index=True)
    total_coverage = Column(Float, nullable=False)
    module_coverage = Column(JSON, nullable=False)
    branch_coverage = Column(Float, nullable=True)
    artifact_reference = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class QualityGateResult(Base):
    """Institutional quality gate verification results."""
    __tablename__ = "testing_quality_gate_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gate_result_id = Column(String(64), unique=True, nullable=False, index=True)
    test_run_id = Column(String(64), ForeignKey("testing_runs.run_id"), nullable=False, index=True)
    gate_name = Column(String(128), nullable=False)
    status = Column(SQLEnum(QualityGateStatus), nullable=False, default=QualityGateStatus.PASSED)
    threshold_config = Column(JSON, nullable=False)
    actual_result = Column(JSON, nullable=False)
    failure_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    test_run = relationship("TestRun", back_populates="gate_results")
