"""
Microstructure Monitoring SQLAlchemy Models (M09.09).

Tables:
1. microstructure_monitoring_configs
2. microstructure_spread_monitoring
3. microstructure_depth_monitoring
4. microstructure_depth_events
5. microstructure_update_intensity
6. microstructure_feed_freshness
7. microstructure_anomaly_rules
8. microstructure_anomaly_models
9. microstructure_anomaly_events
10. microstructure_anomaly_evidence
11. microstructure_anomaly_transitions
12. microstructure_anomaly_episodes
13. microstructure_monitoring_baselines
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Index,
    Boolean,
    Integer,
    Text,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class MicrostructureMonitoringConfig(Base):
    __tablename__ = "microstructure_monitoring_configs"

    id = Column(String(50), primary_key=True)
    config_name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    market_scope = Column(String(50), nullable=False, default="ALL")
    venue_scope = Column(String(50), nullable=False, default="ALL")
    feed_scope = Column(String(50), nullable=False, default="ALL")
    instrument_scope = Column(String(50), nullable=False, default="ALL")
    monitoring_mode = Column(String(50), nullable=False, default="HYBRID") # STREAMING, POLLING, SNAPSHOT, HYBRID
    spread_window_seconds = Column(Integer, nullable=False, default=60)
    depth_window_seconds = Column(Integer, nullable=False, default=60)
    update_rate_window_seconds = Column(Integer, nullable=False, default=10)
    maximum_spread_age_ms = Column(Integer, nullable=False, default=3000)
    maximum_book_age_ms = Column(Integer, nullable=False, default=5000)
    expected_update_cadence_ms = Column(Integer, nullable=False, default=1000)
    minimum_sample_count = Column(Integer, nullable=False, default=5)
    minimum_coverage = Column(Numeric(5, 4), nullable=False, default=0.80)
    version = Column(String(20), nullable=False, default="1.0.0")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MicrostructureSpreadMonitoring(Base):
    __tablename__ = "microstructure_spread_monitoring"

    id = Column(String(50), primary_key=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    source_feed_id = Column(String(50), nullable=False)
    observation_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    calculation_timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    absolute_spread = Column(Numeric(18, 8), nullable=False)
    relative_spread = Column(Numeric(12, 6), nullable=True)
    spread_bps = Column(Numeric(12, 4), nullable=True)
    spread_change = Column(Numeric(18, 8), nullable=True)
    spread_change_percentage = Column(Numeric(12, 4), nullable=True)
    rolling_mean_spread = Column(Numeric(18, 8), nullable=True)
    rolling_stddev_spread = Column(Numeric(18, 8), nullable=True)
    spread_cv = Column(Numeric(12, 4), nullable=True)
    spread_range = Column(Numeric(18, 8), nullable=True)
    time_weighted_spread = Column(Numeric(18, 8), nullable=True)
    historical_percentile = Column(Numeric(6, 2), nullable=True)
    
    valid_observation_count = Column(Integer, nullable=False, default=1)
    coverage_ratio = Column(Numeric(5, 4), nullable=False, default=1.0)
    quality_status = Column(String(50), nullable=False, default="VALID")
    config_id = Column(String(50), nullable=True)
    config_version = Column(String(20), nullable=False, default="1.0.0")
    calculation_version = Column(String(20), nullable=False, default="1.0.0")


class MicrostructureDepthMonitoring(Base):
    __tablename__ = "microstructure_depth_monitoring"

    id = Column(String(50), primary_key=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    source_book_snapshot_id = Column(String(50), nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    calculation_timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    side = Column(String(10), nullable=False) # BID, ASK, BOTH
    depth_measure = Column(String(50), nullable=False, default="TOP_5_CUMULATIVE")
    depth_level_count = Column(Integer, nullable=False, default=5)
    baseline_depth = Column(Numeric(24, 4), nullable=True)
    current_depth = Column(Numeric(24, 4), nullable=False)
    absolute_depth_change = Column(Numeric(24, 4), nullable=False, default=0)
    relative_depth_change = Column(Numeric(12, 4), nullable=True)
    depth_stddev = Column(Numeric(24, 4), nullable=True)
    depth_cv = Column(Numeric(12, 4), nullable=True)
    
    depletion_amount = Column(Numeric(24, 4), nullable=False, default=0)
    depletion_rate = Column(Numeric(24, 4), nullable=True) # per second
    replenishment_amount = Column(Numeric(24, 4), nullable=False, default=0)
    recovery_ratio = Column(Numeric(12, 4), nullable=True)
    
    quality_status = Column(String(50), nullable=False, default="VALID")
    config_id = Column(String(50), nullable=True)
    config_version = Column(String(20), nullable=False, default="1.0.0")


class MicrostructureDepthEvent(Base):
    __tablename__ = "microstructure_depth_events"

    id = Column(String(50), primary_key=True)
    source_event_id = Column(String(100), nullable=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    source_feed_id = Column(String(50), nullable=False)
    
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    receive_timestamp = Column(DateTime(timezone=True), nullable=False)
    sequence_number = Column(Integer, nullable=True)
    event_type = Column(String(50), nullable=False) # ADD, MODIFY, CANCEL, EXECUTION, SNAPSHOT, OBSERVED_CHANGE
    side = Column(String(10), nullable=False) # BID, ASK
    price = Column(Numeric(18, 8), nullable=True)
    quantity_change = Column(Numeric(24, 4), nullable=False)
    notional_change = Column(Numeric(24, 4), nullable=True)
    order_reference = Column(String(100), nullable=True)
    
    classification_source = Column(String(50), nullable=False, default="FEED_MESSAGE") # FEED_MESSAGE, SNAPSHOT_DIFF
    classification_status = Column(String(50), nullable=False, default="EXPLICIT_EVENT") # EXPLICIT_EVENT, DERIVED_AGGREGATE_CHANGE
    source_book_snapshot_id = Column(String(50), nullable=True)
    quality_status = Column(String(50), nullable=False, default="VALID")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MicrostructureUpdateIntensity(Base):
    __tablename__ = "microstructure_update_intensity"

    id = Column(String(50), primary_key=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    source_feed_id = Column(String(50), nullable=False)
    
    interval_start = Column(DateTime(timezone=True), nullable=False)
    interval_end = Column(DateTime(timezone=True), nullable=False, index=True)
    source_mode = Column(String(50), nullable=False, default="STREAMING") # STREAMING, POLLING, SNAPSHOT
    
    total_message_count = Column(Integer, nullable=False, default=0)
    valid_message_count = Column(Integer, nullable=False, default=0)
    unique_event_count = Column(Integer, nullable=True)
    book_update_count = Column(Integer, nullable=False, default=0)
    trade_message_count = Column(Integer, nullable=False, default=0)
    add_event_count = Column(Integer, nullable=False, default=0)
    modify_event_count = Column(Integer, nullable=False, default=0)
    cancel_event_count = Column(Integer, nullable=False, default=0)
    snapshot_count = Column(Integer, nullable=False, default=0)
    heartbeat_count = Column(Integer, nullable=False, default=0)
    duplicate_message_count = Column(Integer, nullable=False, default=0)
    invalid_message_count = Column(Integer, nullable=False, default=0)

    message_rate = Column(Numeric(12, 4), nullable=False, default=0) # msgs/sec
    book_change_rate = Column(Numeric(12, 4), nullable=False, default=0) # updates/sec
    baseline_message_rate = Column(Numeric(12, 4), nullable=True)
    intensity_ratio = Column(Numeric(12, 4), nullable=True)
    robust_standardized_rate = Column(Numeric(12, 4), nullable=True)
    quality_status = Column(String(50), nullable=False, default="VALID")
    calculation_version = Column(String(20), nullable=False, default="1.0.0")


class MicrostructureFeedFreshness(Base):
    __tablename__ = "microstructure_feed_freshness"

    id = Column(String(50), primary_key=True)
    source_feed_id = Column(String(50), nullable=False, index=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    
    monitoring_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    last_source_event_timestamp = Column(DateTime(timezone=True), nullable=False)
    last_receive_timestamp = Column(DateTime(timezone=True), nullable=False)
    last_valid_book_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    observation_age_ms = Column(Integer, nullable=False)
    receive_latency_ms = Column(Integer, nullable=False)
    expected_update_cadence_ms = Column(Integer, nullable=False, default=1000)
    actual_update_cadence_ms = Column(Integer, nullable=True)
    
    feed_status = Column(String(50), nullable=False, default="FRESH") # FRESH, AGING, STALE, FEED_UNAVAILABLE
    book_status = Column(String(50), nullable=False, default="ACTIVE") # ACTIVE, UNCHANGED, STALE
    sequence_status = Column(String(50), nullable=False, default="IN_SEQUENCE") # IN_SEQUENCE, GAP_DETECTED, RECOVERING
    recovery_status = Column(String(50), nullable=False, default="NORMAL") # NORMAL, RECOVERY_IN_PROGRESS
    quality_status = Column(String(50), nullable=False, default="VALID")
    calculation_version = Column(String(20), nullable=False, default="1.0.0")


class MicrostructureAnomalyRule(Base):
    __tablename__ = "microstructure_anomaly_rules"

    id = Column(String(50), primary_key=True)
    rule_name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    anomaly_category = Column(String(50), nullable=False)
    metric_name = Column(String(50), nullable=False)
    comparison_method = Column(String(50), nullable=False) # MULTIPLIER, ABSOLUTE, ROBUST_Z, PERCENTILE
    threshold_value = Column(Numeric(18, 8), nullable=True)
    threshold_multiplier = Column(Numeric(12, 4), nullable=True)
    minimum_duration_seconds = Column(Integer, nullable=False, default=0)
    minimum_observation_count = Column(Integer, nullable=False, default=1)
    evaluation_window_seconds = Column(Integer, nullable=False, default=60)
    recovery_threshold = Column(Numeric(18, 8), nullable=True)
    severity = Column(String(20), nullable=False, default="MEDIUM") # INFO, LOW, MEDIUM, HIGH, CRITICAL
    market_scope = Column(String(50), nullable=False, default="ALL")
    venue_scope = Column(String(50), nullable=False, default="ALL")
    feed_scope = Column(String(50), nullable=False, default="ALL")
    version = Column(String(20), nullable=False, default="1.0.0")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MicrostructureAnomalyModel(Base):
    __tablename__ = "microstructure_anomaly_models"

    id = Column(String(50), primary_key=True)
    model_name = Column(String(100), nullable=False, unique=True)
    model_type = Column(String(50), nullable=False) # ROBUST_MAD, EWMA_CUSUM, ISOLATION_FOREST
    feature_schema = Column(Text, nullable=False) # JSON description of input features
    reference_period = Column(String(50), nullable=False, default="30D")
    training_period_start = Column(DateTime(timezone=True), nullable=True)
    training_period_end = Column(DateTime(timezone=True), nullable=True)
    training_sample_count = Column(Integer, nullable=False, default=0)
    validation_metrics = Column(Text, nullable=True)
    threshold_parameters = Column(Text, nullable=True)
    model_artifact_reference = Column(String(255), nullable=True)
    model_status = Column(String(50), nullable=False, default="TRAINED") # TRAINED, ACTIVE, RETIRED
    model_version = Column(String(20), nullable=False, default="1.0.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime(timezone=True), nullable=True)


class MicrostructureAnomalyEvent(Base):
    __tablename__ = "microstructure_anomaly_events"

    id = Column(String(50), primary_key=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    source_feed_id = Column(String(50), nullable=False)
    
    anomaly_category = Column(String(50), nullable=False, index=True)
    anomaly_description = Column(String(255), nullable=False)
    severity = Column(String(20), nullable=False, index=True) # INFO, LOW, MEDIUM, HIGH, CRITICAL
    detected_metric = Column(String(50), nullable=False)
    observed_value = Column(Numeric(24, 8), nullable=False)
    baseline_value = Column(Numeric(24, 8), nullable=True)
    threshold_value = Column(Numeric(24, 8), nullable=True)
    deviation_magnitude = Column(Numeric(24, 8), nullable=True)
    
    event_start_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    detection_timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_observed_timestamp = Column(DateTime(timezone=True), nullable=False)
    event_end_timestamp = Column(DateTime(timezone=True), nullable=True)
    
    affected_side = Column(String(10), nullable=True) # BID, ASK, BOTH
    affected_level_count = Column(Integer, nullable=True)
    detection_method = Column(String(50), nullable=False, default="DETERMINISTIC_RULE") # DETERMINISTIC_RULE, STATISTICAL_MODEL
    rule_id = Column(String(50), nullable=True)
    rule_version = Column(String(20), nullable=True)
    model_id = Column(String(50), nullable=True)
    model_version = Column(String(20), nullable=True)
    source_reference = Column(String(100), nullable=True)
    quality_status = Column(String(50), nullable=False, default="VALID")
    lifecycle_status = Column(String(50), nullable=False, default="DETECTED", index=True) # DETECTED, ACTIVE, ACKNOWLEDGED, RECOVERING, RESOLVED, CLOSED, SUPPRESSED
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    evidence = relationship("MicrostructureAnomalyEvidence", back_populates="anomaly_event", cascade="all, delete-orphan")
    transitions = relationship("MicrostructureAnomalyTransition", back_populates="anomaly_event", cascade="all, delete-orphan")


class MicrostructureAnomalyEvidence(Base):
    __tablename__ = "microstructure_anomaly_evidence"

    id = Column(String(50), primary_key=True)
    anomaly_event_id = Column(String(50), ForeignKey("microstructure_anomaly_events.id"), nullable=False, index=True)
    evidence_type = Column(String(50), nullable=False) # SPREAD_OBSERVATION, DEPTH_SNAPSHOT, MESSAGE_BURST, GAP_INFO
    source_reference_id = Column(String(100), nullable=True)
    source_snapshot_id = Column(String(50), nullable=True)
    source_event_id = Column(String(100), nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    observed_value = Column(Numeric(24, 8), nullable=True)
    baseline_value = Column(Numeric(24, 8), nullable=True)
    threshold_value = Column(Numeric(24, 8), nullable=True)
    evidence_description = Column(String(255), nullable=False)
    quality_status = Column(String(50), nullable=False, default="VALID")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    anomaly_event = relationship("MicrostructureAnomalyEvent", back_populates="evidence")


class MicrostructureAnomalyTransition(Base):
    __tablename__ = "microstructure_anomaly_transitions"

    id = Column(String(50), primary_key=True)
    anomaly_event_id = Column(String(50), ForeignKey("microstructure_anomaly_events.id"), nullable=False, index=True)
    previous_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    transition_timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    transition_reason = Column(String(255), nullable=False)
    actor_id = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    policy_version = Column(String(20), nullable=False, default="1.0.0")

    anomaly_event = relationship("MicrostructureAnomalyEvent", back_populates="transitions")


class MicrostructureAnomalyEpisode(Base):
    __tablename__ = "microstructure_anomaly_episodes"

    id = Column(String(50), primary_key=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    episode_category = Column(String(50), nullable=False) # COMPOUND_LIQUIDITY_ANOMALY, SPREAD_EPISODE, WITHDRAWAL_EPISODE
    episode_severity = Column(String(20), nullable=False, default="MEDIUM")
    episode_start = Column(DateTime(timezone=True), nullable=False, index=True)
    episode_end = Column(DateTime(timezone=True), nullable=True)
    related_event_count = Column(Integer, nullable=False, default=1)
    primary_anomaly_event_id = Column(String(50), nullable=False)
    episode_status = Column(String(50), nullable=False, default="ACTIVE") # ACTIVE, RECOVERED, CLOSED
    grouping_policy_version = Column(String(20), nullable=False, default="1.0.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MicrostructureMonitoringBaseline(Base):
    __tablename__ = "microstructure_monitoring_baselines"

    id = Column(String(50), primary_key=True)
    instrument_id = Column(String(50), nullable=False, index=True)
    listing_id = Column(String(50), nullable=False, index=True)
    venue_id = Column(String(50), nullable=False, index=True)
    source_feed_id = Column(String(50), nullable=False)
    metric_name = Column(String(50), nullable=False)
    baseline_method = Column(String(50), nullable=False, default="ROBUST_MAD") # ROBUST_MAD, TIME_OF_DAY_BUCKET, PERCENTILES
    baseline_period_start = Column(DateTime(timezone=True), nullable=False)
    baseline_period_end = Column(DateTime(timezone=True), nullable=False)
    time_of_day_bucket = Column(String(50), nullable=True) # OPEN, MIDDAY, CLOSE
    market_regime = Column(String(50), nullable=True)
    
    mean_value = Column(Numeric(24, 8), nullable=True)
    median_value = Column(Numeric(24, 8), nullable=True)
    stddev_value = Column(Numeric(24, 8), nullable=True)
    mad_value = Column(Numeric(24, 8), nullable=True)
    percentile_values = Column(Text, nullable=True) # JSON: {"p50": ..., "p90": ..., "p95": ..., "p99": ...}
    sample_count = Column(Integer, nullable=False, default=0)
    coverage_ratio = Column(Numeric(5, 4), nullable=False, default=1.0)
    baseline_version = Column(String(20), nullable=False, default="1.0.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
