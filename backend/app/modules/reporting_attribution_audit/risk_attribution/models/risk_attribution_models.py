"""
M14.03 Risk Attribution Reports ORM Models.
Durable, auditable storage for risk attribution reports across securities, sectors,
industries, and systematic factors.
"""
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    Date,
    Boolean,
    Integer,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class RiskMeasureType(str, Enum):
    PORTFOLIO_VOLATILITY = "PORTFOLIO_VOLATILITY"
    PORTFOLIO_VARIANCE = "PORTFOLIO_VARIANCE"
    PARAMETRIC_VAR = "PARAMETRIC_VAR"
    HISTORICAL_VAR = "HISTORICAL_VAR"
    EXPECTED_SHORTFALL = "EXPECTED_SHORTFALL"
    SYSTEMATIC_FACTOR_RISK = "SYSTEMATIC_FACTOR_RISK"
    IDIOSYNCRATIC_RISK = "IDIOSYNCRATIC_RISK"


class ValuationCutoffPolicy(str, Enum):
    OFFICIAL_CLOSE = "OFFICIAL_CLOSE"
    INTRADAY_SNAPSHOT = "INTRADAY_SNAPSHOT"
    LATEST_AVAILABLE = "LATEST_AVAILABLE"


class AttributionGranularity(str, Enum):
    SECURITY = "SECURITY"
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    FACTOR = "FACTOR"
    ALL = "ALL"


class AttributionGroupType(str, Enum):
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"


class AttributionContributionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNCLASSIFIED = "UNCLASSIFIED"
    APPROXIMATED = "APPROXIMATED"
    UNAVAILABLE = "UNAVAILABLE"


class ReconciliationStatusType(str, Enum):
    EXACT_RECONCILIATION = "EXACT_RECONCILIATION"
    ROUNDING_DIFFERENCE = "ROUNDING_DIFFERENCE"
    RESIDUAL_PRESENT = "RESIDUAL_PRESENT"
    NON_ADDITIVE = "NON_ADDITIVE"
    INCOMPLETE = "INCOMPLETE"


class CaveatCategory(str, Enum):
    DATA_GAP = "DATA_GAP"
    CLASSIFICATION_MISSING = "CLASSIFICATION_MISSING"
    NON_ADDITIVE_METHODOLOGY = "NON_ADDITIVE_METHODOLOGY"
    COVARIANCE_APPROXIMATION = "COVARIANCE_APPROXIMATION"
    FACTOR_MODEL_MISMATCH = "FACTOR_MODEL_MISMATCH"
    ROUNDING_RESIDUAL = "ROUNDING_RESIDUAL"


class CaveatSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ReportArtifactType(str, Enum):
    PDF = "PDF"
    HTML = "HTML"
    CSV = "CSV"


class ReportGenerationStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RiskAttributionReportConfiguration(Base):
    """
    Configuration profile for risk attribution reports.
    """
    __tablename__ = "m14_risk_attribution_configurations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    configuration_name: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_measure: Mapped[RiskMeasureType] = mapped_column(SQLEnum(RiskMeasureType), nullable=False, default=RiskMeasureType.PORTFOLIO_VOLATILITY)
    valuation_cutoff_policy: Mapped[ValuationCutoffPolicy] = mapped_column(SQLEnum(ValuationCutoffPolicy), nullable=False, default=ValuationCutoffPolicy.OFFICIAL_CLOSE)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    attribution_levels: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=lambda: ["SECURITY", "SECTOR", "INDUSTRY", "FACTOR"])
    factor_model_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reconciliation_absolute_tolerance: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=Decimal("0.0001"))
    reconciliation_relative_tolerance: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=Decimal("0.001"))
    ranking_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    runs: Mapped[List["RiskAttributionReportRun"]] = relationship("RiskAttributionReportRun", back_populates="configuration", cascade="all, delete-orphan")


class RiskAttributionReportRun(Base):
    """
    Execution run of a risk attribution report.
    """
    __tablename__ = "m14_risk_attribution_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    configuration_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("m14_risk_attribution_configurations.id", ondelete="SET NULL"), nullable=True, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reporting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valuation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_measure: Mapped[RiskMeasureType] = mapped_column(SQLEnum(RiskMeasureType), nullable=False)
    authoritative_risk_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    risk_measure_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="ANNUALIZED_PERCENTAGE")
    risk_methodology: Mapped[str] = mapped_column(String(64), nullable=False, default="COVARIANCE_EULER")
    
    # Portfolio Decomposition
    systematic_risk: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    idiosyncratic_risk: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    residual_risk: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    
    # Statuses
    generation_status: Mapped[ReportGenerationStatus] = mapped_column(SQLEnum(ReportGenerationStatus), nullable=False, default=ReportGenerationStatus.COMPLETED)
    reconciliation_status: Mapped[ReconciliationStatusType] = mapped_column(SQLEnum(ReconciliationStatusType), nullable=False, default=ReconciliationStatusType.EXACT_RECONCILIATION)
    
    # Model & Provenance
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    factor_model_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    classification_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    report_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    report_schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    
    # Manifests
    source_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    methodology_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    coverage_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")

    configuration: Mapped[Optional[RiskAttributionReportConfiguration]] = relationship("RiskAttributionReportConfiguration", back_populates="runs")
    security_contributions: Mapped[List["RiskAttributionSecurityContribution"]] = relationship("RiskAttributionSecurityContribution", back_populates="run", cascade="all, delete-orphan")
    group_contributions: Mapped[List["RiskAttributionGroupContribution"]] = relationship("RiskAttributionGroupContribution", back_populates="run", cascade="all, delete-orphan")
    factor_contributions: Mapped[List["RiskAttributionFactorContribution"]] = relationship("RiskAttributionFactorContribution", back_populates="run", cascade="all, delete-orphan")
    reconciliations: Mapped[List["RiskAttributionReconciliation"]] = relationship("RiskAttributionReconciliation", back_populates="run", cascade="all, delete-orphan")
    caveats: Mapped[List["RiskAttributionCaveat"]] = relationship("RiskAttributionCaveat", back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[List["RiskAttributionReportArtifact"]] = relationship("RiskAttributionReportArtifact", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_m14_attr_run_port_date", "portfolio_id", "reporting_date"),
    )


class RiskAttributionSecurityContribution(Base):
    """
    Individual security component and marginal risk contribution.
    """
    __tablename__ = "m14_risk_attribution_security_contributions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_risk_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sector: Mapped[str] = mapped_column(String(64), nullable=False, default="UNCLASSIFIED")
    industry: Mapped[str] = mapped_column(String(64), nullable=False, default="UNCLASSIFIED")
    position_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    position_weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    position_side: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG, SHORT
    standalone_volatility: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8), nullable=True)
    marginal_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    component_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    contribution_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    contribution_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False, default="M07.09")
    contribution_status: Mapped[AttributionContributionStatus] = mapped_column(SQLEnum(AttributionContributionStatus), nullable=False, default=AttributionContributionStatus.ACTIVE)

    run: Mapped[RiskAttributionReportRun] = relationship("RiskAttributionReportRun", back_populates="security_contributions")


class RiskAttributionGroupContribution(Base):
    """
    Aggregated sector or industry risk contribution.
    """
    __tablename__ = "m14_risk_attribution_group_contributions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_risk_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    group_type: Mapped[AttributionGroupType] = mapped_column(SQLEnum(AttributionGroupType), nullable=False)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    security_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    total_weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=Decimal("0"))
    component_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    contribution_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    group_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    classification_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    contribution_status: Mapped[AttributionContributionStatus] = mapped_column(SQLEnum(AttributionContributionStatus), nullable=False, default=AttributionContributionStatus.ACTIVE)

    run: Mapped[RiskAttributionReportRun] = relationship("RiskAttributionReportRun", back_populates="group_contributions")


class RiskAttributionFactorContribution(Base):
    """
    Systematic factor risk contribution and exposure.
    """
    __tablename__ = "m14_risk_attribution_factor_contributions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_risk_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_category: Mapped[str] = mapped_column(String(32), nullable=False, default="STYLE")
    factor_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    marginal_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    component_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    contribution_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    factor_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    factor_model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False, default="M08.05")
    contribution_status: Mapped[AttributionContributionStatus] = mapped_column(SQLEnum(AttributionContributionStatus), nullable=False, default=AttributionContributionStatus.ACTIVE)

    run: Mapped[RiskAttributionReportRun] = relationship("RiskAttributionReportRun", back_populates="factor_contributions")


class RiskAttributionReconciliation(Base):
    """
    Audit reconciliation record between granular contributions and authoritative portfolio totals.
    """
    __tablename__ = "m14_risk_attribution_reconciliations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_risk_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    attribution_level: Mapped[AttributionGranularity] = mapped_column(SQLEnum(AttributionGranularity), nullable=False)
    risk_measure: Mapped[RiskMeasureType] = mapped_column(SQLEnum(RiskMeasureType), nullable=False)
    authoritative_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    contribution_sum: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    residual: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    absolute_difference: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    relative_difference: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    absolute_tolerance: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    relative_tolerance: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    reconciliation_status: Mapped[ReconciliationStatusType] = mapped_column(SQLEnum(ReconciliationStatusType), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[RiskAttributionReportRun] = relationship("RiskAttributionReportRun", back_populates="reconciliations")


class RiskAttributionCaveat(Base):
    """
    Auditable caveat, limitation, or data quality note affecting the report.
    """
    __tablename__ = "m14_risk_attribution_caveats"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_risk_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    caveat_category: Mapped[CaveatCategory] = mapped_column(SQLEnum(CaveatCategory), nullable=False)
    severity: Mapped[CaveatSeverity] = mapped_column(SQLEnum(CaveatSeverity), nullable=False)
    affected_entity: Mapped[str] = mapped_column(String(64), nullable=False)
    affected_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    affects_completeness: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    run: Mapped[RiskAttributionReportRun] = relationship("RiskAttributionReportRun", back_populates="caveats")


class RiskAttributionReportArtifact(Base):
    """
    Rendered durable report artifact (PDF, HTML, CSV) with cryptographic verification.
    """
    __tablename__ = "m14_risk_attribution_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_risk_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type: Mapped[ReportArtifactType] = mapped_column(SQLEnum(ReportArtifactType), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run: Mapped[RiskAttributionReportRun] = relationship("RiskAttributionReportRun", back_populates="artifacts")


class RiskAttributionReportVersion(Base):
    """
    Immutable version lineage tracking for regenerated reports.
    """
    __tablename__ = "m14_risk_attribution_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_risk_attribution_runs.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    version_reason: Mapped[str] = mapped_column(String(256), nullable=False, default="Initial generation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")

    __table_args__ = (
        Index("ix_m14_attr_ver_port_date_ver", "portfolio_id", "report_date", "version_number", unique=True),
    )
