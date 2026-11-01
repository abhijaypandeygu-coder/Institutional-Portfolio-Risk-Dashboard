"""
M06.02 Net Exposure Models.
Database models for net exposure policies, calculation runs, results,
position contributions, breakdowns, snapshots, and directional threshold events.
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
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


class DirectionalState(str, Enum):
    NET_LONG = "NET_LONG"
    NET_SHORT = "NET_SHORT"
    APPROX_NEUTRAL = "APPROX_NEUTRAL"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class NeutralityThresholdType(str, Enum):
    ABSOLUTE = "ABSOLUTE"
    RELATIVE = "RELATIVE"
    COMBINED_AND = "COMBINED_AND"
    COMBINED_OR = "COMBINED_OR"


class NetDenominatorType(str, Enum):
    NAV = "NAV"
    TOTAL_EQUITY = "TOTAL_EQUITY"
    RISK_CAPITAL = "RISK_CAPITAL"
    CUSTOM_CAPITAL = "CUSTOM_CAPITAL"


class NetExposureScope(str, Enum):
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_GROUP = "PORTFOLIO_GROUP"
    ACCOUNT = "ACCOUNT"
    INSTRUMENT = "INSTRUMENT"


class NetRunStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class NetRatioStatus(str, Enum):
    VALID = "VALID"
    INVALID_ZERO_DENOMINATOR = "INVALID_ZERO_DENOMINATOR"
    INVALID_NEGATIVE_DENOMINATOR = "INVALID_NEGATIVE_DENOMINATOR"
    DENOMINATOR_UNAVAILABLE = "DENOMINATOR_UNAVAILABLE"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    STALE_DENOMINATOR = "STALE_DENOMINATOR"


class NetThresholdStatus(str, Enum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    WARNING = "WARNING"
    BREACH = "BREACH"
    APPROX_NEUTRAL = "APPROX_NEUTRAL"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class NetExposurePolicy(Base):
    """
    Versioned policy for directional net exposure, neutrality thresholds, and limits.
    """
    __tablename__ = "m06_net_exposure_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    denominator_type: Mapped[str] = mapped_column(String(32), default=NetDenominatorType.NAV.value, nullable=False)
    
    # Neutrality settings
    neutrality_threshold_type: Mapped[str] = mapped_column(
        String(32), default=NeutralityThresholdType.RELATIVE.value, nullable=False
    )
    absolute_neutrality_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    relative_neutrality_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), default=Decimal("0.020000"), nullable=True) # e.g. 2%
    combined_threshold_semantics: Mapped[str] = mapped_column(String(16), default="AND", nullable=False)
    
    # Directional Limits (e.g. +100% max net long, -50% max net short)
    max_net_long_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    max_net_short_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    warning_buffer_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), default=Decimal("5.0"), nullable=True)

    effective_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NetExposureCalculationRun(Base):
    """
    Audit execution record for a Net Exposure calculation.
    """
    __tablename__ = "m06_net_exposure_calculation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    calculation_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    denominator_type: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="M06.02-v1", nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), default=NetRunStatus.COMPLETED.value, nullable=False)
    input_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NetExposureResult(Base):
    """
    Authoritative aggregated net exposure result and directional classification.
    """
    __tablename__ = "m06_net_exposure_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_net_exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    # Fundamental Aggregations
    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    absolute_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Denominator & Ratios
    denominator_type: Mapped[str] = mapped_column(String(32), nullable=False)
    denominator_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    denominator_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    net_exposure_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    net_exposure_ratio_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    ratio_status: Mapped[str] = mapped_column(String(32), default=NetRatioStatus.VALID.value, nullable=False)
    
    # Directional Classification & Neutrality
    directional_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    neutrality_threshold_type: Mapped[str] = mapped_column(String(32), nullable=False)
    neutrality_threshold_applied: Mapped[str] = mapped_column(String(128), nullable=False)
    threshold_status: Mapped[str] = mapped_column(String(32), default=NetThresholdStatus.WITHIN_LIMIT.value, nullable=False)
    
    # Lineage & Audit
    completeness_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    eligible_position_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    excluded_position_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    audit_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NetExposureContribution(Base):
    """
    Granular signed source position contribution to net market value.
    """
    __tablename__ = "m06_net_exposure_contributions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_net_exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_side: Mapped[str] = mapped_column(String(16), nullable=False)
    
    # Signed Quantities and Values
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    signed_market_value_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    native_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    # FX Conversion
    fx_rate_reference: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False)
    converted_signed_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    # Lineage references
    position_snapshot_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    valuation_snapshot_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    eligibility_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NetExposureBreakdown(Base):
    """
    Dimensional slice breakdown of directional net exposure.
    """
    __tablename__ = "m06_net_exposure_breakdowns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_net_exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    breakdown_type: Mapped[str] = mapped_column(String(32), nullable=False) # INSTRUMENT, ACCOUNT, CURRENCY, SECTOR, PORTFOLIO
    breakdown_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    absolute_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    contribution_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    directional_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DirectionalThresholdEvent(Base):
    """
    Audit log of directional limit or neutrality breach/warning events.
    """
    __tablename__ = "m06_directional_threshold_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_net_exposure_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    threshold_type: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    observed_net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    observed_net_exposure_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    event_level: Mapped[str] = mapped_column(String(16), nullable=False) # WARNING, BREACH
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
