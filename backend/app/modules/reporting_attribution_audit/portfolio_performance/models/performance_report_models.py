"""
SQLAlchemy database models for M14.02 — Portfolio Performance Reports.
"""

from datetime import datetime, timezone, date
from decimal import Decimal
import enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Date,
    Boolean,
    Text,
    ForeignKey,
    JSON,
    Enum as SAEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReportingPeriodType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YTD = "YTD"
    ONE_YEAR = "ONE_YEAR"
    CUSTOM = "CUSTOM"


class ReportingFrequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


class ReturnMethodology(str, enum.Enum):
    TWR = "TWR"
    MODIFIED_DIETZ = "MODIFIED_DIETZ"
    MWR_XIRR = "MWR_XIRR"


class CashFlowTimingPolicy(str, enum.Enum):
    VALUATION_AT_FLOW_BOUNDARY = "VALUATION_AT_FLOW_BOUNDARY"
    START_OF_DAY = "START_OF_DAY"
    END_OF_DAY = "END_OF_DAY"
    MID_DAY_APPROXIMATION = "MID_DAY_APPROXIMATION"


class BenchmarkReturnType(str, enum.Enum):
    TOTAL_RETURN = "TOTAL_RETURN"
    PRICE_RETURN = "PRICE_RETURN"


class BenchmarkCurrencyPolicy(str, enum.Enum):
    NATIVE = "NATIVE"
    PORTFOLIO_REPORTING_CURRENCY = "PORTFOLIO_REPORTING_CURRENCY"
    EXPLICIT_CONVERSION = "EXPLICIT_CONVERSION"


class PerformanceDataStatus(str, enum.Enum):
    COMPLETE = "COMPLETE"
    COMPLETE_WITH_APPROXIMATIONS = "COMPLETE_WITH_APPROXIMATIONS"
    PARTIAL = "PARTIAL"
    INCOMPLETE = "INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


class ReportGenerationStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PerformanceReportConfiguration(Base):
    """Configuration profile for M14.02 Performance Reports."""
    __tablename__ = "m14_performance_report_configurations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    configuration_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reporting_period_type: Mapped[ReportingPeriodType] = mapped_column(
        SAEnum(ReportingPeriodType), default=ReportingPeriodType.MONTHLY, nullable=False
    )
    custom_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    custom_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reporting_frequency: Mapped[ReportingFrequency] = mapped_column(
        SAEnum(ReportingFrequency), default=ReportingFrequency.DAILY, nullable=False
    )
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    return_methodology: Mapped[ReturnMethodology] = mapped_column(
        SAEnum(ReturnMethodology), default=ReturnMethodology.TWR, nullable=False
    )
    cash_flow_timing_policy: Mapped[CashFlowTimingPolicy] = mapped_column(
        SAEnum(CashFlowTimingPolicy), default=CashFlowTimingPolicy.VALUATION_AT_FLOW_BOUNDARY, nullable=False
    )
    benchmark_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    benchmark_return_type: Mapped[BenchmarkReturnType] = mapped_column(
        SAEnum(BenchmarkReturnType), default=BenchmarkReturnType.TOTAL_RETURN, nullable=False
    )
    benchmark_currency_policy: Mapped[BenchmarkCurrencyPolicy] = mapped_column(
        SAEnum(BenchmarkCurrencyPolicy), default=BenchmarkCurrencyPolicy.PORTFOLIO_REPORTING_CURRENCY, nullable=False
    )
    pnl_breakdown_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    data_completeness_policy: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    runs = relationship("PerformanceReportRun", back_populates="configuration")


class PerformanceReportRun(Base):
    """Immutable execution record of a performance report."""
    __tablename__ = "m14_performance_report_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    configuration_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("m14_performance_report_configurations.id"), nullable=True, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    benchmark_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    reporting_start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    reporting_end_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    generation_status: Mapped[ReportGenerationStatus] = mapped_column(
        SAEnum(ReportGenerationStatus), default=ReportGenerationStatus.COMPLETED, nullable=False
    )
    performance_data_status: Mapped[PerformanceDataStatus] = mapped_column(
        SAEnum(PerformanceDataStatus), default=PerformanceDataStatus.COMPLETE, nullable=False
    )
    report_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    report_schema_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    return_methodology_version: Mapped[str] = mapped_column(String(32), default="TWR_v1.0", nullable=False)
    benchmark_methodology_version: Mapped[str] = mapped_column(String(32), default="BMK_v1.0", nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)

    # Financial Summary rollups
    beginning_nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    ending_nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    period_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    cumulative_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    annualized_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    total_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    realized_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    unrealized_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    net_external_flow: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    benchmark_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    active_return_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)

    # Manifests and Caveats
    source_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    caveat_summary: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    configuration = relationship("PerformanceReportConfiguration", back_populates="runs")
    return_observations = relationship("PerformanceReturnObservation", back_populates="report_run", cascade="all, delete-orphan")
    pnl_components = relationship("PerformancePnLComponent", back_populates="report_run", cascade="all, delete-orphan")
    benchmark_observations = relationship("PerformanceBenchmarkObservation", back_populates="report_run", cascade="all, delete-orphan")
    caveats = relationship("PerformanceCaveat", back_populates="report_run", cascade="all, delete-orphan")
    artifacts = relationship("PerformanceReportArtifact", back_populates="report_run", cascade="all, delete-orphan")


class PerformanceReturnObservation(Base):
    """Subperiod / periodic return observations."""
    __tablename__ = "m14_performance_return_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m14_performance_report_runs.id"), nullable=False, index=True
    )
    observation_start: Mapped[date] = mapped_column(Date, nullable=False)
    observation_end: Mapped[date] = mapped_column(Date, nullable=False)
    beginning_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    ending_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    external_contributions: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    external_withdrawals: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    periodic_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    cumulative_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    annualized_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    methodology: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    source_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    calculation_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    report_run = relationship("PerformanceReportRun", back_populates="return_observations")


class PerformancePnLComponent(Base):
    """Detailed P&L breakdown components (Realized, Unrealized, Fees, Income, etc.)."""
    __tablename__ = "m14_performance_pnl_components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m14_performance_report_runs.id"), nullable=False, index=True
    )
    component_type: Mapped[str] = mapped_column(String(64), nullable=False)  # REALIZED, UNREALIZED, FEES, DIVIDEND, FX, etc.
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reporting_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    classification_status: Mapped[str] = mapped_column(String(32), default="CLASSIFIED", nullable=False)
    reconciliation_status: Mapped[str] = mapped_column(String(32), default="RECONCILED", nullable=False)

    report_run = relationship("PerformanceReportRun", back_populates="pnl_components")


class PerformanceBenchmarkObservation(Base):
    """Time-series observation of benchmark levels and returns aligned with portfolio."""
    __tablename__ = "m14_performance_benchmark_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m14_performance_report_runs.id"), nullable=False, index=True
    )
    benchmark_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    benchmark_level: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    periodic_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    cumulative_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    return_type: Mapped[str] = mapped_column(String(32), default="TOTAL_RETURN", nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    observation_status: Mapped[str] = mapped_column(String(32), default="MATCHED", nullable=False)

    report_run = relationship("PerformanceReportRun", back_populates="benchmark_observations")


class PerformanceCaveat(Base):
    """Caveat and limitation disclosure attached to a report."""
    __tablename__ = "m14_performance_caveats"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m14_performance_report_runs.id"), nullable=False, index=True
    )
    caveat_category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="WARNING", nullable=False)  # INFO, WARNING, CRITICAL
    affected_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    affected_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    affected_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_references: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    affects_completeness: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    report_run = relationship("PerformanceReportRun", back_populates="caveats")


class PerformanceReportArtifact(Base):
    """Rendered report file artifact (PDF, HTML, CSV)."""
    __tablename__ = "m14_performance_report_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m14_performance_report_runs.id"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(16), nullable=False)  # PDF, HTML, CSV, JSON
    storage_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    report_run = relationship("PerformanceReportRun", back_populates="artifacts")


class PerformanceReportVersion(Base):
    """Audit table tracking version lineage across regenerated reports."""
    __tablename__ = "m14_performance_report_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    reporting_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m14_performance_report_runs.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    version_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
