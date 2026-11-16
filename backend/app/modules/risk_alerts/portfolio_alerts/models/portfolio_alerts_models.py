"""
SQLAlchemy ORM models for M12.04 Portfolio Alerts.

Tables:
1. `portfolio_alert_rules`: Master rule configurations for loss, concentration, positions, cash, and breaks.
2. `portfolio_alert_rule_versions`: Immutable version records for audit and replay reproducibility.
3. `portfolio_alert_events`: Master detected portfolio events.
4. `portfolio_alert_evidence`: Granular metric evidence records per portfolio event.
5. `portfolio_alert_occurrences`: Repetition and aggregation log per alert instance.
6. `portfolio_alert_baselines`: Reference portfolio baselines (start-of-day NAV, baseline weights).
7. `portfolio_alert_rule_evaluations`: Evaluation execution logs and data-quality status.
8. `portfolio_alert_reconciliation_links`: Explicit links to M05.06 reconciliation breaks.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Text,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class PortfolioAlertRule(Base):
    """
    Master portfolio alert rule configuration entity.
    """
    __tablename__ = "portfolio_alert_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # PORTFOLIO_LOSS, CONCENTRATION, POSITION_MOVEMENT, CASH_MOVEMENT, RECONCILIATION_BREAK
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # INTRADAY_LOSS, PERIOD_LOSS, INSTRUMENT_CONCENTRATION, SECTOR_CONCENTRATION, UNUSUAL_POSITION_CHANGE, CASH_WITHDRAWAL, RECONCILIATION_BREAK
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[str] = mapped_column(String(16), default="GTE")  # GTE, LTE, GT, LT, EQ
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_currency: Mapped[str] = mapped_column(String(16), default="INR")
    threshold_unit: Mapped[str] = mapped_column(String(32), default="PERCENT_NAV")  # PERCENT_NAV, CURRENCY, PERCENT_POINTS, SHARES
    baseline_type: Mapped[str] = mapped_column(String(32), default="PREVIOUS_CLOSE")  # PREVIOUS_CLOSE, START_OF_DAY, ROLLING_7D
    evaluation_interval: Mapped[str] = mapped_column(String(16), default="5m")
    persistence_count: Mapped[int] = mapped_column(Integer, default=1)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    severity_preference: Mapped[str] = mapped_column(String(16), default="HIGH")

    rule_version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    versions: Mapped[List["PortfolioAlertRuleVersion"]] = relationship(
        "PortfolioAlertRuleVersion", back_populates="rule", cascade="all, delete-orphan", order_by="desc(PortfolioAlertRuleVersion.version_number)"
    )
    evaluations: Mapped[List["PortfolioAlertRuleEvaluation"]] = relationship(
        "PortfolioAlertRuleEvaluation", back_populates="rule"
    )


class PortfolioAlertRuleVersion(Base):
    """
    Immutable versioned snapshot of portfolio alert rule configuration.
    """
    __tablename__ = "portfolio_alert_rule_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_alert_rules.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    change_reason: Mapped[str] = mapped_column(String(255), default="Initial configuration")
    changed_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rule: Mapped["PortfolioAlertRule"] = relationship("PortfolioAlertRule", back_populates="versions")
    events: Mapped[List["PortfolioAlertEvent"]] = relationship("PortfolioAlertEvent", back_populates="rule_version")


class PortfolioAlertEvent(Base):
    """
    Primary detected portfolio alert event.
    """
    __tablename__ = "portfolio_alert_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    delta_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="INR")
    source_module: Mapped[str] = mapped_column(String(32), default="M05.03")  # M05.03, M06, M05.02, M05.04, M05.06
    source_record_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    event_state: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # ACTIVE, RECOVERING, RESOLVED, CLOSED
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID")
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), index=True)
    rule_version_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("portfolio_alert_rule_versions.id"), nullable=True)

    rule_version: Mapped[Optional["PortfolioAlertRuleVersion"]] = relationship("PortfolioAlertRuleVersion", back_populates="events")
    evidence_items: Mapped[List["PortfolioAlertEvidence"]] = relationship(
        "PortfolioAlertEvidence", back_populates="portfolio_event", cascade="all, delete-orphan"
    )
    occurrences: Mapped[List["PortfolioAlertOccurrence"]] = relationship(
        "PortfolioAlertOccurrence", back_populates="portfolio_event", cascade="all, delete-orphan"
    )
    reconciliation_links: Mapped[List["PortfolioAlertReconciliationLink"]] = relationship(
        "PortfolioAlertReconciliationLink", back_populates="portfolio_event", cascade="all, delete-orphan"
    )


class PortfolioAlertEvidence(Base):
    """
    Granular evidence metrics supporting each detected portfolio alert.
    """
    __tablename__ = "portfolio_alert_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_alert_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_alert_events.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # INTRADAY_LOSS, PERIOD_LOSS, LOSS_ATTRIBUTION, CONCENTRATION_WEIGHT, POSITION_MOVEMENT, CASH_FLOW, RECONCILIATION_BREAK
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="PERCENT")
    currency: Mapped[str] = mapped_column(String(16), default="INR")
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(32), default="v1.0.0")
    evidence_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    portfolio_event: Mapped["PortfolioAlertEvent"] = relationship("PortfolioAlertEvent", back_populates="evidence_items")


class PortfolioAlertOccurrence(Base):
    """
    Occurrence repetition logs for deduplicated events.
    """
    __tablename__ = "portfolio_alert_occurrences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_alert_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_alert_events.id", ondelete="CASCADE"), index=True)
    occurrence_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    occurrence_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    portfolio_event: Mapped["PortfolioAlertEvent"] = relationship("PortfolioAlertEvent", back_populates="occurrences")


class PortfolioAlertBaseline(Base):
    """
    Reference portfolio baselines for change detection.
    """
    __tablename__ = "portfolio_alert_baselines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    baseline_type: Mapped[str] = mapped_column(String(32), nullable=False)  # START_OF_DAY, PREVIOUS_CLOSE, ROLLING_7D
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="INR")
    reference_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    source_snapshot_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(32), default="v1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PortfolioAlertRuleEvaluation(Base):
    """
    Evaluation execution logs for auditing detector runs.
    """
    __tablename__ = "portfolio_alert_rule_evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_alert_rules.id", ondelete="CASCADE"), index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    observed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    evaluation_result: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # TRIGGERED, NOT_TRIGGERED, SUPPRESSED
    eligibility_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE")  # ELIGIBLE, STALE_DATA, MISSING_VALUATION
    suppression_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_snapshot_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    rule: Mapped["PortfolioAlertRule"] = relationship("PortfolioAlertRule", back_populates="evaluations")


class PortfolioAlertReconciliationLink(Base):
    """
    Explicit links to authoritative M05.06 reconciliation breaks.
    """
    __tablename__ = "portfolio_alert_reconciliation_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_alert_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_alert_events.id", ondelete="CASCADE"), index=True)
    reconciliation_break_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    break_category: Mapped[str] = mapped_column(String(64), default="POSITION_QUANTITY")
    break_magnitude: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), default="PRIMARY")
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    portfolio_event: Mapped["PortfolioAlertEvent"] = relationship("PortfolioAlertEvent", back_populates="reconciliation_links")

