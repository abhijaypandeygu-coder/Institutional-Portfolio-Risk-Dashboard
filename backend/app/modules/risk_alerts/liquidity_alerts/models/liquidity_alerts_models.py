"""
SQLAlchemy ORM models for M12.03 Liquidity Alerts.

Tables:
1. `liquidity_alert_rules`: Master rule configurations for spread, depth, score, and liquidation alerts.
2. `liquidity_alert_rule_versions`: Immutable version records for audit and replay reproducibility.
3. `liquidity_metric_observations`: Snapshot of liquidity observations triggering evaluations.
4. `liquidity_alert_evaluations`: Evaluation execution records (rule, window, values, triggered).
5. `liquidity_alert_events`: Master detected liquidity events.
6. `liquidity_alert_evidence`: Granular metric evidence records per liquidity event.
7. `liquidity_deterioration_state`: Detector-level state machine tracking persistence and hysteresis.
8. `liquidity_alert_portfolio_impacts`: Mapping of detected events to affected portfolios and positions.
9. `liquidity_alert_review_labels`: Post-event analyst review and false positive tracking.
10. `liquidity_alert_processing_log`: Operational latency, retry, and processing monitoring.
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


class LiquidityAlertRule(Base):
    """
    Master liquidity alert rule configuration entity.
    """
    __tablename__ = "liquidity_alert_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # SPREAD_WIDENING, DEPTH_DETERIORATION, LIQUIDITY_SCORE, LIQUIDATION_COST, LIQUIDATION_HORIZON
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # SPREAD_BPS, BID_DEPTH, ASK_DEPTH, COMPOSITE_SCORE, LIQUIDATION_COST_BPS, LIQUIDATION_TIME_MINUTES
    market: Mapped[str] = mapped_column(String(32), default="INDIA", index=True)  # INDIA, US
    exchange: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # NSE, BSE, NYSE, NASDAQ
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    observation_horizon_seconds: Mapped[int] = mapped_column(Integer, default=300)  # 5 min default
    baseline_window_seconds: Mapped[int] = mapped_column(Integer, default=86400 * 10)  # 10 trading sessions
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(32), default="BPS")  # BPS, PERCENT, SHARES, CURRENCY, MINUTES, SCORE
    persistence_seconds: Mapped[int] = mapped_column(Integer, default=60)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=3)
    minimum_coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.8000"))
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    recovery_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")

    versions: Mapped[List["LiquidityAlertRuleVersion"]] = relationship(
        "LiquidityAlertRuleVersion", back_populates="rule", cascade="all, delete-orphan", order_by="desc(LiquidityAlertRuleVersion.version_number)"
    )
    evaluations: Mapped[List["LiquidityAlertEvaluation"]] = relationship(
        "LiquidityAlertEvaluation", back_populates="rule"
    )


class LiquidityAlertRuleVersion(Base):
    """
    Immutable versioned snapshot of liquidity alert rule configuration.
    """
    __tablename__ = "liquidity_alert_rule_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("liquidity_alert_rules.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    change_reason: Mapped[str] = mapped_column(String(255), default="Initial configuration")
    changed_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    approval_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rule: Mapped["LiquidityAlertRule"] = relationship("LiquidityAlertRule", back_populates="versions")
    events: Mapped[List["LiquidityAlertEvent"]] = relationship("LiquidityAlertEvent", back_populates="rule_version")


class LiquidityMetricObservation(Base):
    """
    Snapshot of liquidity metric observations triggering evaluations.
    """
    __tablename__ = "liquidity_metric_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(32), default="BPS")
    metric_side: Mapped[str] = mapped_column(String(16), default="BOTH")  # BID, ASK, BOTH
    observation_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    source_metric_reference: Mapped[str] = mapped_column(String(128), default="M09_MICROSTRUCTURE")
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0.0")
    quality_state: Mapped[str] = mapped_column(String(32), default="VALID", index=True)
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class LiquidityAlertEvaluation(Base):
    """
    Evaluation execution records for auditing detector runs.
    """
    __tablename__ = "liquidity_alert_evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("liquidity_alert_rules.id", ondelete="CASCADE"), index=True)
    rule_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    observation_window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    observation_window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    observed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    reference_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    deviation_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    deviation_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, default=1)
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    evaluation_status: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # SUCCESS, REJECTED_STALE, INSUFFICIENT_DATA
    triggered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calculation_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    rule: Mapped["LiquidityAlertRule"] = relationship("LiquidityAlertRule", back_populates="evaluations")


class LiquidityAlertEvent(Base):
    """
    Primary detected liquidity deterioration event.
    """
    __tablename__ = "liquidity_alert_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # SPREAD_WIDENING, DEPTH_DETERIORATION, LOW_LIQUIDITY_SCORE, EXCESS_LIQUIDATION_COST, EXCESS_LIQUIDATION_HORIZON
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="DETERIORATING")
    
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    event_state: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # ACTIVE, RECOVERING, RECOVERED, CLOSED
    event_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    rule_version_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("liquidity_alert_rule_versions.id"), nullable=True)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_metric_reference: Mapped[str] = mapped_column(String(128), default="M09_MICROSTRUCTURE")

    rule_version: Mapped[Optional["LiquidityAlertRuleVersion"]] = relationship("LiquidityAlertRuleVersion", back_populates="events")
    evidence_items: Mapped[List["LiquidityAlertEvidence"]] = relationship(
        "LiquidityAlertEvidence", back_populates="liquidity_event", cascade="all, delete-orphan"
    )
    portfolio_impacts: Mapped[List["LiquidityAlertPortfolioImpact"]] = relationship(
        "LiquidityAlertPortfolioImpact", back_populates="liquidity_event", cascade="all, delete-orphan"
    )
    review_labels: Mapped[List["LiquidityAlertReviewLabel"]] = relationship(
        "LiquidityAlertReviewLabel", back_populates="liquidity_event", cascade="all, delete-orphan"
    )


class LiquidityAlertEvidence(Base):
    """
    Granular evidence metrics supporting each detected liquidity alert.
    """
    __tablename__ = "liquidity_alert_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    liquidity_alert_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("liquidity_alert_events.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)  # SPREAD_BPS, SPREAD_DELTA, DEPTH_QUANTITY, DEPTH_DECLINE_PCT, SCORE_CURRENT, LIQUIDATION_COST, LIQUIDATION_TIME
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="BPS")
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quality_state: Mapped[str] = mapped_column(String(32), default="VALID")
    evidence_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    evidence_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    liquidity_event: Mapped["LiquidityAlertEvent"] = relationship("LiquidityAlertEvent", back_populates="evidence_items")


class LiquidityDeteriorationState(Base):
    """
    Detector-level state machine tracking persistence, duration, and hysteresis.
    """
    __tablename__ = "liquidity_deterioration_state"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_side: Mapped[str] = mapped_column(String(16), default="BOTH")
    current_state: Mapped[str] = mapped_column(String(32), default="NORMAL", index=True)  # NORMAL, DETERIORATING, SEVERELY_DETERIORATED, RECOVERING
    first_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_recovery_candidate_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_valid_observation_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    current_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    consecutive_trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_recovery_count: Mapped[int] = mapped_column(Integer, default=0)
    state_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class LiquidityAlertPortfolioImpact(Base):
    """
    Mapping of detected events to affected portfolios and position holdings.
    """
    __tablename__ = "liquidity_alert_portfolio_impacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    liquidity_alert_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("liquidity_alert_events.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    position_direction: Mapped[str] = mapped_column(String(16), default="LONG")  # LONG, SHORT
    affected_liquidity_side: Mapped[str] = mapped_column(String(16), default="BID")  # BID, ASK, BOTH
    estimated_liquidation_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    estimated_liquidation_cost_unit: Mapped[str] = mapped_column(String(16), default="BPS")
    estimated_liquidation_horizon: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(32), default="COMPLETE")
    effective_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    liquidity_event: Mapped["LiquidityAlertEvent"] = relationship("LiquidityAlertEvent", back_populates="portfolio_impacts")


class LiquidityAlertReviewLabel(Base):
    """
    Post-event analyst review and false positive tracking.
    """
    __tablename__ = "liquidity_alert_review_labels"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    liquidity_alert_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("liquidity_alert_events.id", ondelete="CASCADE"), index=True)
    review_label: Mapped[str] = mapped_column(String(32), nullable=False)
    # VALID_LIQUIDITY_DETERIORATION, FALSE_POSITIVE, DATA_QUALITY_ISSUE, DUPLICATE, INSUFFICIENT_EVIDENCE, MODEL_LIMITATION
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    liquidity_event: Mapped["LiquidityAlertEvent"] = relationship("LiquidityAlertEvent", back_populates="review_labels")


class LiquidityAlertProcessingLog(Base):
    """
    Operational latency and processing health monitoring.
    """
    __tablename__ = "liquidity_alert_processing_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_metric_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    processing_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # SUCCESS, FAILED, RETRIED
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
