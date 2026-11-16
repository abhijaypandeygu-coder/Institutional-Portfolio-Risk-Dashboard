"""
SQLAlchemy ORM models for M12.02 Market Alerts.

Tables:
1. `market_alert_rules`: Master rule configurations for price, volatility, bands, halts, and market-wide events.
2. `market_alert_rule_versions`: Immutable version records for audit and replay reproducibility.
3. `market_event_observations`: Snapshot of market observations that triggered evaluations.
4. `market_alert_evaluations`: Evaluation execution records (rule, window, values, triggered).
5. `market_events`: Primary detected market events (anomaly, spike, halt, resumption, market-wide).
6. `market_event_evidence`: Granular metric evidence records per market event.
7. `market_event_status_history`: State transition history of market events.
8. `market_halt_events`: Authoritative halt and suspension tracking with resumption linking.
9. `market_wide_events`: Aggregated market-wide events (index return, breadth, anomaly counts).
10. `market_event_portfolio_impacts`: Mapping of detected events to affected portfolios and positions.
11. `market_alert_review_labels`: Governance / false-positive review labels.
12. `market_detection_processing_log`: Operational latency and health logging.
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
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class MarketAlertRule(Base):
    """
    Master market alert rule configuration entity.
    """
    __tablename__ = "market_alert_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # ABNORMAL_PRICE_MOVEMENT, HISTORICAL_DEVIATION, MARKET_BAND, VOLATILITY_SPIKE, TRADING_HALT, MARKET_WIDE
    market: Mapped[str] = mapped_column(String(32), default="INDIA", index=True)  # INDIA, US
    exchange: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # NSE, BSE, NYSE, NASDAQ
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    observation_horizon_seconds: Mapped[int] = mapped_column(Integer, default=900)  # e.g., 900s = 15m
    reference_window_seconds: Mapped[int] = mapped_column(Integer, default=86400 * 20)  # 20 sessions default
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(32), default="PERCENT")  # PERCENT, RATIO, CURRENCY, Z_SCORE
    percentile_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    persistence_seconds: Mapped[int] = mapped_column(Integer, default=0)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=5)
    minimum_coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.8000"))
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    recovery_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")

    versions: Mapped[List["MarketAlertRuleVersion"]] = relationship(
        "MarketAlertRuleVersion", back_populates="rule", cascade="all, delete-orphan", order_by="desc(MarketAlertRuleVersion.version_number)"
    )
    evaluations: Mapped[List["MarketAlertEvaluation"]] = relationship(
        "MarketAlertEvaluation", back_populates="rule"
    )


class MarketAlertRuleVersion(Base):
    """
    Immutable versioned snapshot of market alert rule configuration.
    """
    __tablename__ = "market_alert_rule_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("market_alert_rules.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    change_reason: Mapped[str] = mapped_column(String(255), default="Initial configuration")
    changed_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    approval_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rule: Mapped["MarketAlertRule"] = relationship("MarketAlertRule", back_populates="versions")
    events: Mapped[List["MarketEvent"]] = relationship("MarketEvent", back_populates="rule_version")


class MarketEventObservation(Base):
    """
    Minimum market observation snapshot supporting calculation reproducibility.
    """
    __tablename__ = "market_event_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    price_type: Mapped[str] = mapped_column(String(32), default="LAST")  # LAST, MID, BID, ASK, CLOSE
    price_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="INR")
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    source_feed_id: Mapped[str] = mapped_column(String(64), default="FEED_PRIMARY")
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quality_state: Mapped[str] = mapped_column(String(32), default="VALID", index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class MarketAlertEvaluation(Base):
    """
    Evaluation execution records for auditing detector runs.
    """
    __tablename__ = "market_alert_evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("market_alert_rules.id", ondelete="CASCADE"), index=True)
    rule_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    observation_window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    observation_window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    evaluation_status: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # SUCCESS, FAILED, INSUFFICIENT_DATA, STALE
    triggered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    observed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    reference_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    deviation_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    calculation_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rule: Mapped["MarketAlertRule"] = relationship("MarketAlertRule", back_populates="evaluations")


class MarketEvent(Base):
    """
    Primary detected market events (anomaly, volatility spike, band breach, halt, market-wide).
    """
    __tablename__ = "market_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # ABNORMAL_PRICE_MOVEMENT, HISTORICAL_DEVIATION, MARKET_BAND_BREACH, VOLATILITY_SPIKE, TRADING_HALT, TRADING_RESUMPTION, MARKET_WIDE_EVENT
    event_scope: Mapped[str] = mapped_column(String(32), default="INSTRUMENT")  # INSTRUMENT, INDEX, MARKET
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # INDIA, US
    exchange: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # NSE, BSE, NYSE, NASDAQ
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    index_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    direction: Mapped[str] = mapped_column(String(16), default="NO_DIRECTION")  # UPWARD, DOWNWARD, NO_DIRECTION, UNAVAILABLE
    
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    source_event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    event_state: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # ACTIVE, CONFIRMED, RECOVERING, RECOVERED, CLOSED
    event_fingerprint: Mapped[str] = mapped_column(String(64), index=True)  # Idempotency hash
    
    rule_version_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("market_alert_rule_versions.id"), nullable=True)
    detection_algorithm_version: Mapped[str] = mapped_column(String(32), default="v1.0.0")
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)

    rule_version: Mapped[Optional["MarketAlertRuleVersion"]] = relationship("MarketAlertRuleVersion", back_populates="events")
    evidence_items: Mapped[List["MarketEventEvidence"]] = relationship(
        "MarketEventEvidence", back_populates="market_event", cascade="all, delete-orphan"
    )
    status_history: Mapped[List["MarketEventStatusHistory"]] = relationship(
        "MarketEventStatusHistory", back_populates="market_event", cascade="all, delete-orphan"
    )
    portfolio_impacts: Mapped[List["MarketEventPortfolioImpact"]] = relationship(
        "MarketEventPortfolioImpact", back_populates="market_event", cascade="all, delete-orphan"
    )
    review_labels: Mapped[List["MarketAlertReviewLabel"]] = relationship(
        "MarketAlertReviewLabel", back_populates="market_event", cascade="all, delete-orphan"
    )


class MarketEventEvidence(Base):
    """
    Granular evidence metrics supporting each detected market alert.
    """
    __tablename__ = "market_event_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("market_events.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)  # PRICE_DELTA, RETURN_PCT, Z_SCORE, RV_SHORT, RV_BASELINE, SPIKE_RATIO, BAND_LIMIT, BREADTH
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="PERCENT")
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quality_state: Mapped[str] = mapped_column(String(32), default="VALID")
    evidence_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    evidence_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    market_event: Mapped["MarketEvent"] = relationship("MarketEvent", back_populates="evidence_items")


class MarketEventStatusHistory(Base):
    """
    State transition logs for market events.
    """
    __tablename__ = "market_event_status_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("market_events.id", ondelete="CASCADE"), index=True)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), nullable=False)
    transition_reason: Mapped[str] = mapped_column(String(255), default="State update")
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    market_event: Mapped["MarketEvent"] = relationship("MarketEvent", back_populates="status_history")


class MarketHaltEvent(Base):
    """
    Authoritative halt and suspension tracking entity.
    """
    __tablename__ = "market_halt_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_status_code: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # TRADING, HALTED, SUSPENDED, AUCTION_ONLY, RESTRICTED, RESUMED, NOT_SUPPORTED
    halt_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    halt_start_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expected_resumption_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_resumption_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    halt_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_feed_id: Mapped[str] = mapped_column(String(64), default="FEED_PRIMARY")
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quality_state: Mapped[str] = mapped_column(String(32), default="VALID")
    linked_resumption_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class MarketWideEvent(Base):
    """
    Aggregated market-wide events across indices and constituent breadth.
    """
    __tablename__ = "market_wide_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("market_events.id", ondelete="CASCADE"), index=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    index_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_classification: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # BROAD_MARKET_DECLINE, BROAD_MARKET_RALLY, MARKET_VOLATILITY_SPIKE, BROAD_SECTOR_DECLINE, MARKET_BREADTH_DETERIORATION
    index_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    realized_volatility: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    advance_count: Mapped[int] = mapped_column(Integer, default=0)
    decline_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    downside_anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    upside_anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    eligible_universe_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_universe_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    aggregation_window_seconds: Mapped[int] = mapped_column(Integer, default=900)


class MarketEventPortfolioImpact(Base):
    """
    Mapping of detected events to affected portfolios and position holdings.
    """
    __tablename__ = "market_event_portfolio_impacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("market_events.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    position_direction: Mapped[str] = mapped_column(String(16), default="LONG")  # LONG, SHORT
    movement_direction: Mapped[str] = mapped_column(String(16), default="DOWNWARD")  # UPWARD, DOWNWARD
    directional_impact: Mapped[str] = mapped_column(String(16), default="ADVERSE")  # ADVERSE, FAVORABLE, NEUTRAL
    exposure_reference: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(32), default="COMPLETE")  # COMPLETE, INCOMPLETE, MISSING_VALUATION
    effective_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    market_event: Mapped["MarketEvent"] = relationship("MarketEvent", back_populates="portfolio_impacts")


class MarketAlertReviewLabel(Base):
    """
    Post-event analyst review and false positive tracking.
    """
    __tablename__ = "market_alert_review_labels"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_event_id: Mapped[str] = mapped_column(String(64), ForeignKey("market_events.id", ondelete="CASCADE"), index=True)
    review_label: Mapped[str] = mapped_column(String(32), nullable=False)
    # VALID_EVENT, FALSE_POSITIVE, DATA_QUALITY_ISSUE, DUPLICATE, INSUFFICIENT_EVIDENCE, UNCLASSIFIED
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    market_event: Mapped["MarketEvent"] = relationship("MarketEvent", back_populates="review_labels")


class MarketDetectionProcessingLog(Base):
    """
    Operational latency, retry, and processing monitoring.
    """
    __tablename__ = "market_detection_processing_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_feed_id: Mapped[str] = mapped_column(String(64), default="FEED_PRIMARY")
    processing_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # SUCCESS, FAILED, RETRIED
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
