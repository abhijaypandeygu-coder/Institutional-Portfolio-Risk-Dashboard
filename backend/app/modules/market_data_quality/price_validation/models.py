"""
Module 03.02: Price Validation - SQLAlchemy 2.x Database Models.
Tables:
- price_validation_rules: Configurable versioned rules with priority and enforcement action.
- price_validation_results: Validation decisions per observation with overall status and severity.
- price_validation_evidence: Granular evidence payload supporting each rule evaluation.
- price_anomaly_incidents: Material anomalies with deduplication keys and resolution lifecycle.
- price_reference_snapshots: Authoritative reference prices (previous close, official exchange band).
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    JSON,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RuleCategory(str, Enum):
    STRUCTURAL = "STRUCTURAL"
    ZERO_PRICE = "ZERO_PRICE"
    PRICE_RANGE = "PRICE_RANGE"
    TICK_SIZE = "TICK_SIZE"
    EXTREME_MOVEMENT = "EXTREME_MOVEMENT"
    EXCHANGE_BAND = "EXCHANGE_BAND"
    REFERENCE_COMPARISON = "REFERENCE_COMPARISON"


class EnforcementAction(str, Enum):
    REJECT = "REJECT"
    WARN = "WARN"
    QUARANTINE = "QUARANTINE"


class ValidationSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ValidationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_WARNING = "ACCEPTED_WITH_WARNING"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AnomalyIncidentStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class PriceValidationRule(Base):
    """Stores configurable, versioned validation rules."""
    __tablename__ = "price_validation_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(128))
    rule_category: Mapped[RuleCategory] = mapped_column(SQLEnum(RuleCategory), index=True)
    observation_type: Mapped[str] = mapped_column(String(32), default="ALL")  # TICK, OHLCV, TRADE, ALL
    price_field: Mapped[str] = mapped_column(String(32), default="ALL")        # last_traded_price, close, open, etc.
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(32), default="ALL", index=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    
    threshold_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # PERCENTAGE, ABSOLUTE, Z_SCORE
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    severity: Mapped[ValidationSeverity] = mapped_column(SQLEnum(ValidationSeverity), default=ValidationSeverity.MEDIUM)
    enforcement_action: Mapped[EnforcementAction] = mapped_column(SQLEnum(EnforcementAction), default=EnforcementAction.WARN)
    rule_parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    priority: Mapped[int] = mapped_column(Integer, default=100)
    version: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PriceValidationResult(Base):
    """Stores the final validation decision and summary for an individual observation."""
    __tablename__ = "price_validation_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    observation_id: Mapped[str] = mapped_column(String(64), index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True)
    feed_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    observation_type: Mapped[str] = mapped_column(String(32))
    price_field: Mapped[str] = mapped_column(String(32))
    
    original_price_value: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parsed_price_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    validation_status: Mapped[ValidationStatus] = mapped_column(SQLEnum(ValidationStatus), index=True)
    overall_severity: Mapped[ValidationSeverity] = mapped_column(SQLEnum(ValidationSeverity), default=ValidationSeverity.INFO)
    
    failed_rule_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    rule_version_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    evidence_items: Mapped[List["PriceValidationEvidence"]] = relationship(
        "PriceValidationEvidence", back_populates="validation_result", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_pvr_inst_time", "instrument_id", "validation_timestamp"),
        Index("ix_pvr_feed_status", "feed_id", "validation_status"),
    )


class PriceValidationEvidence(Base):
    """Detailed evidence supporting every material rule outcome."""
    __tablename__ = "price_validation_evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    validation_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("price_validation_results.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("price_validation_rules.id"), nullable=True)
    rule_code: Mapped[str] = mapped_column(String(64))
    evidence_type: Mapped[str] = mapped_column(String(64))
    
    observed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    reference_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    calculated_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    calculated_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[ValidationStatus] = mapped_column(SQLEnum(ValidationStatus))
    evidence_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    validation_result: Mapped["PriceValidationResult"] = relationship(
        "PriceValidationResult", back_populates="evidence_items"
    )


class PriceAnomalyIncident(Base):
    """Tracks material price anomalies with lifecycle management."""
    __tablename__ = "price_anomaly_incidents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True)
    feed_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(64), index=True)
    
    observed_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    reference_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    absolute_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    percentage_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    applicable_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    
    severity: Mapped[ValidationSeverity] = mapped_column(SQLEnum(ValidationSeverity), default=ValidationSeverity.HIGH)
    incident_status: Mapped[AnomalyIncidentStatus] = mapped_column(
        SQLEnum(AnomalyIncidentStatus), default=AnomalyIncidentStatus.OPEN, index=True
    )
    
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class PriceReferenceSnapshot(Base):
    """Authoritative snapshots of reference prices (previous close, official price bands)."""
    __tablename__ = "price_reference_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    reference_type: Mapped[str] = mapped_column(String(64), index=True)  # PREVIOUS_CLOSE, OFFICIAL_REFERENCE, etc.
    reference_value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    
    source_provider: Mapped[str] = mapped_column(String(64), default="EXCHANGE")
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    retrieval_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    adjustment_basis: Mapped[str] = mapped_column(String(32), default="UNADJUSTED")
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_prs_inst_ref_type", "instrument_id", "reference_type", "effective_date"),
    )
