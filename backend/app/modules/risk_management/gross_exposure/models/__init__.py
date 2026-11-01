"""
M06.01 Gross Exposure Models.
Database models for gross exposure calculation runs, exposure results, position contributions,
breakdowns, denominator references, and threshold events.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


class DenominatorType(str, Enum):
    NAV = "NAV"
    TOTAL_EQUITY = "TOTAL_EQUITY"
    RISK_CAPITAL = "RISK_CAPITAL"
    CUSTOM_BENCHMARK = "CUSTOM_BENCHMARK"


class ExposureCalculationScope(str, Enum):
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_GROUP = "PORTFOLIO_GROUP"


class ExposureRunStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class RatioStatus(str, Enum):
    VALID = "VALID"
    INVALID_ZERO_DENOMINATOR = "INVALID_ZERO_DENOMINATOR"
    INVALID_NEGATIVE_DENOMINATOR = "INVALID_NEGATIVE_DENOMINATOR"
    DENOMINATOR_UNAVAILABLE = "DENOMINATOR_UNAVAILABLE"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    STALE_DENOMINATOR = "STALE_DENOMINATOR"


class ThresholdStatus(str, Enum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    WARNING = "WARNING"
    BREACH = "BREACH"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ExposurePolicy(Base):
    """
    Approved gross exposure calculation and threshold policy.
    """
    __tablename__ = "exposure_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    denominator_type: Mapped[str] = mapped_column(String(32), default=DenominatorType.NAV.value, nullable=False)
    denominator_source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    currency_policy: Mapped[str] = mapped_column(String(32), default="BASE_OR_REPORTING", nullable=False)
    valuation_freshness_policy: Mapped[str] = mapped_column(String(64), default="EOD_STRICT", nullable=False)
    timestamp_alignment_policy: Mapped[str] = mapped_column(String(64), default="SAME_SESSION", nullable=False)
    
    exposure_threshold_warning: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    exposure_threshold_hard: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    
    policy_version: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ExposureCalculationRun(Base):
    """
    Execution header record for an exposure calculation run.
    """
    __tablename__ = "exposure_calculation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    calculation_scope: Mapped[str] = mapped_column(String(32), nullable=False)  # PORTFOLIO / PORTFOLIO_GROUP
    
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    denominator_type: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), default="EXP-POL-V1", nullable=False)
    calculation_version: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), default=ExposureRunStatus.COMPLETED.value, nullable=False)
    input_manifest_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    result: Mapped[Optional["ExposureResult"]] = relationship("ExposureResult", back_populates="calculation_run", uselist=False, cascade="all, delete-orphan")
    contributions: Mapped[List["ExposureContribution"]] = relationship("ExposureContribution", back_populates="calculation_run", cascade="all, delete-orphan")
    breakdowns: Mapped[List["ExposureBreakdown"]] = relationship("ExposureBreakdown", back_populates="calculation_run", cascade="all, delete-orphan")
    threshold_events: Mapped[List["ExposureThresholdEvent"]] = relationship("ExposureThresholdEvent", back_populates="calculation_run", cascade="all, delete-orphan")


class ExposureResult(Base):
    """
    Primary aggregate gross exposure metrics and ratio against denominator.
    """
    __tablename__ = "exposure_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)  # Supplementary only
    
    denominator_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    denominator_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    denominator_type: Mapped[str] = mapped_column(String(32), nullable=False)
    denominator_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    gross_exposure_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)  # Multiple e.g. 1.40x
    exposure_ratio_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)  # Percentage e.g. 140.0%
    ratio_status: Mapped[str] = mapped_column(String(48), default=RatioStatus.VALID.value, nullable=False)
    completeness_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    
    eligible_position_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    excluded_position_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    calculation_run: Mapped["ExposureCalculationRun"] = relationship("ExposureCalculationRun", back_populates="result")


class ExposureContribution(Base):
    """
    Position-level line item preserving source lineage, native market value, and absolute gross contribution.
    """
    __tablename__ = "exposure_contributions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    position_side: Mapped[str] = mapped_column(String(16), nullable=False)  # LONG / SHORT
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    signed_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    absolute_exposure_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    native_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    converted_exposure_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    position_snapshot_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    valuation_snapshot_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    price_observation_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fx_observation_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    eligibility_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    calculation_run: Mapped["ExposureCalculationRun"] = relationship("ExposureCalculationRun", back_populates="contributions")


class ExposureBreakdown(Base):
    """
    Subtotal breakdowns by dimension (Instrument, Sector, Industry, Account, Portfolio, Currency).
    """
    __tablename__ = "exposure_breakdowns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    breakdown_type: Mapped[str] = mapped_column(String(32), nullable=False)  # INSTRUMENT, SECTOR, CURRENCY, PORTFOLIO, ACCOUNT
    breakdown_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    
    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    contribution_percentage: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    calculation_run: Mapped["ExposureCalculationRun"] = relationship("ExposureCalculationRun", back_populates="breakdowns")


class ExposureThresholdEvent(Base):
    """
    Threshold monitoring evaluations for warning and hard limits.
    """
    __tablename__ = "exposure_threshold_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    threshold_type: Mapped[str] = mapped_column(String(32), nullable=False)  # WARNING / HARD / ABSOLUTE
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # WITHIN_LIMIT / WARNING / BREACH
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    calculation_run: Mapped["ExposureCalculationRun"] = relationship("ExposureCalculationRun", back_populates="threshold_events")

