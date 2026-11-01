"""
SQLAlchemy 2.x Database Models for M06.08 Exposure Limits.

Includes:
- ExposureLimitConfig: Effective-dated risk limit definitions across instrument, sector,
  industry, portfolio gross/net, country, and region.
- ExposureLimitEvaluation: Measured exposures, limit utilization percentage, headroom, and status.
- ExposureLimitBreachHistory: Traceable audit log of breach lifecycle transitions.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Numeric, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey, Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExposureLimitCategory(str, enum.Enum):
    INSTRUMENT_LIMIT = "INSTRUMENT_LIMIT"
    SECTOR_LIMIT = "SECTOR_LIMIT"
    INDUSTRY_LIMIT = "INDUSTRY_LIMIT"
    PORTFOLIO_GROSS_LIMIT = "PORTFOLIO_GROSS_LIMIT"
    PORTFOLIO_NET_LIMIT = "PORTFOLIO_NET_LIMIT"
    COUNTRY_LIMIT = "COUNTRY_LIMIT"
    REGION_LIMIT = "REGION_LIMIT"


class ExposureMeasurementBasis(str, enum.Enum):
    GROSS_MARKET_VALUE = "GROSS_MARKET_VALUE"
    LONG_MARKET_VALUE = "LONG_MARKET_VALUE"
    SHORT_MARKET_VALUE = "SHORT_MARKET_VALUE"
    NET_MARKET_VALUE = "NET_MARKET_VALUE"
    ABSOLUTE_NET_MARKET_VALUE = "ABSOLUTE_NET_MARKET_VALUE"
    NAV_PERCENTAGE = "NAV_PERCENTAGE"
    GROSS_CONTRIBUTION_PERCENTAGE = "GROSS_CONTRIBUTION_PERCENTAGE"


class ExposureLimitDirection(str, enum.Enum):
    MAXIMUM = "MAXIMUM"
    MINIMUM = "MINIMUM"
    UPPER_BOUND = "UPPER_BOUND"
    LOWER_BOUND = "LOWER_BOUND"


class ExposureLimitDenominatorType(str, enum.Enum):
    ABSOLUTE_AMOUNT = "ABSOLUTE_AMOUNT"
    PORTFOLIO_NAV = "PORTFOLIO_NAV"
    PORTFOLIO_GROSS_EXPOSURE = "PORTFOLIO_GROSS_EXPOSURE"
    PORTFOLIO_LONG_EXPOSURE = "PORTFOLIO_LONG_EXPOSURE"
    PORTFOLIO_SHORT_EXPOSURE = "PORTFOLIO_SHORT_EXPOSURE"


class ExposureLimitStatus(str, enum.Enum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    APPROACHING_LIMIT = "APPROACHING_LIMIT"
    WARNING = "WARNING"
    BREACHED = "BREACHED"
    SEVERELY_BREACHED = "SEVERELY_BREACHED"
    PENDING_EVALUATION = "PENDING_EVALUATION"
    EVALUATION_UNAVAILABLE = "EVALUATION_UNAVAILABLE"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"
    ZERO_LIMIT_BREACH = "ZERO_LIMIT_BREACH"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ExposureBreachEventType(str, enum.Enum):
    NEW_WARNING = "NEW_WARNING"
    NEW_BREACH = "NEW_BREACH"
    BREACH_CONTINUING = "BREACH_CONTINUING"
    BREACH_WORSENED = "BREACH_WORSENED"
    BREACH_IMPROVED = "BREACH_IMPROVED"
    BREACH_RESOLVED = "BREACH_RESOLVED"
    WARNING_RESOLVED = "WARNING_RESOLVED"
    EVALUATION_UNAVAILABLE = "EVALUATION_UNAVAILABLE"


class ExposureLimitConfig(Base):
    """
    Effective-dated limit configuration rule.
    Defines exposure boundary, measurement basis, denominator, warning and severe breach thresholds.
    """
    __tablename__ = "m06_exposure_limit_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    limit_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"LIM_{uuid.uuid4().hex[:12].upper()}"
    )
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)

    limit_category: Mapped[ExposureLimitCategory] = mapped_column(
        Enum(ExposureLimitCategory, name="exposure_limit_category_enum", native_enum=False),
        nullable=False,
        index=True
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    target_entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    target_entity_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    exposure_basis: Mapped[ExposureMeasurementBasis] = mapped_column(
        Enum(ExposureMeasurementBasis, name="exposure_measurement_basis_enum", native_enum=False),
        default=ExposureMeasurementBasis.GROSS_MARKET_VALUE,
        nullable=False
    )
    limit_direction: Mapped[ExposureLimitDirection] = mapped_column(
        Enum(ExposureLimitDirection, name="exposure_limit_direction_enum", native_enum=False),
        default=ExposureLimitDirection.MAXIMUM,
        nullable=False
    )
    denominator_type: Mapped[ExposureLimitDenominatorType] = mapped_column(
        Enum(ExposureLimitDenominatorType, name="exposure_limit_denominator_enum", native_enum=False),
        default=ExposureLimitDenominatorType.PORTFOLIO_NAV,
        nullable=False
    )

    limit_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    warning_threshold_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.850000"), nullable=False)  # 85% utilization
    severe_breach_threshold_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.100000"), nullable=False)  # 110% utilization

    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    evaluations: Mapped[List["ExposureLimitEvaluation"]] = relationship(
        "ExposureLimitEvaluation", back_populates="limit_config", cascade="all, delete-orphan"
    )


class ExposureLimitEvaluation(Base):
    """
    Evaluated limit state for a specific calculation run or snapshot.
    Stores measured exposure, denominator value, utilization percentage, headroom, and breach status.
    """
    __tablename__ = "m06_exposure_limit_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"EVAL_{uuid.uuid4().hex[:12].upper()}"
    )
    limit_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_exposure_limit_configs.limit_id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    measured_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    denominator_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    limit_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    utilization_percentage: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    headroom: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    shortfall: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    status: Mapped[ExposureLimitStatus] = mapped_column(
        Enum(ExposureLimitStatus, name="exposure_limit_status_enum", native_enum=False),
        default=ExposureLimitStatus.WITHIN_LIMIT,
        nullable=False,
        index=True
    )
    data_completeness_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    limit_config: Mapped["ExposureLimitConfig"] = relationship("ExposureLimitConfig", back_populates="evaluations")

    __table_args__ = (
        Index("ix_eval_port_stat", "portfolio_id", "status"),
        Index("ix_eval_grp_stat", "portfolio_group_id", "status"),
    )


class ExposureLimitBreachHistory(Base):
    """
    Immutable audit history recording limit status transitions and breach lifecycles.
    """
    __tablename__ = "m06_exposure_limit_breach_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"BREVT_{uuid.uuid4().hex[:12].upper()}"
    )
    limit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    target_entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    previous_status: Mapped[Optional[ExposureLimitStatus]] = mapped_column(
        Enum(ExposureLimitStatus, name="exposure_limit_status_enum", native_enum=False),
        nullable=True
    )
    new_status: Mapped[ExposureLimitStatus] = mapped_column(
        Enum(ExposureLimitStatus, name="exposure_limit_status_enum", native_enum=False),
        nullable=False
    )
    event_type: Mapped[ExposureBreachEventType] = mapped_column(
        Enum(ExposureBreachEventType, name="exposure_breach_event_type_enum", native_enum=False),
        nullable=False,
        index=True
    )

    measured_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    limit_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    headroom: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    details: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
