"""
Module M07.04: Drawdown Analytics Models.
Defines data structures for:
1. DrawdownConfig: Configurations for scope (portfolio / instrument), value series type,
   corporate action policy, high-water-mark policy, and recovery tolerances.
2. DrawdownSeriesResult: Point-in-time time series of running high-water mark, signed & positive drawdown.
3. DrawdownEpisode: Discrete drawdown episode with peak, trough, recovery, durations, and state.
4. MaximumDrawdownResult: Largest historical peak-to-trough decline over lookback windows.
5. DrawdownRecoveryStatistics: Aggregate statistics on recovery duration, underwater duration, and episode counts.
6. DrawdownDiagnostic: Continuity, corporate-action, and data freshness audit records.
"""
from datetime import datetime, timezone, date
from decimal import Decimal
import enum
from typing import Optional, List, Dict, Any
import uuid
from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Date,
    Boolean,
    Text,
    Enum as SAEnum,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DrawdownScopeType(str, enum.Enum):
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_GROUP = "PORTFOLIO_GROUP"
    INSTRUMENT = "INSTRUMENT"


class DrawdownValueSeriesType(str, enum.Enum):
    PORTFOLIO_NAV_SERIES = "PORTFOLIO_NAV_SERIES"
    FLOW_ADJUSTED_EQUITY_CURVE = "FLOW_ADJUSTED_EQUITY_CURVE"
    SPLIT_ADJUSTED_PRICE_SERIES = "SPLIT_ADJUSTED_PRICE_SERIES"
    RAW_PRICE_SERIES = "RAW_PRICE_SERIES"
    TOTAL_RETURN_PRICE_SERIES = "TOTAL_RETURN_PRICE_SERIES"


class HighWaterMarkPolicy(str, enum.Enum):
    FULL_HISTORY_HIGH_WATER_MARK = "FULL_HISTORY_HIGH_WATER_MARK"
    WINDOW_RELATIVE_PEAK = "WINDOW_RELATIVE_PEAK"


class DrawdownEpisodeStatus(str, enum.Enum):
    RECOVERED = "RECOVERED"
    ONGOING = "ONGOING"
    DATA_INTERRUPTED = "DATA_INTERRUPTED"
    PARTIALLY_OBSERVED = "PARTIALLY_OBSERVED"


class CurrentDrawdownStatus(str, enum.Enum):
    AT_HIGH_WATER_MARK = "AT_HIGH_WATER_MARK"
    CURRENTLY_UNDERWATER = "CURRENTLY_UNDERWATER"
    RECOVERED = "RECOVERED"
    STALE_VALUE = "STALE_VALUE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DrawdownDataQualityStatus(str, enum.Enum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INCOMPLETE_HISTORY = "INCOMPLETE_HISTORY"
    DATA_GAP = "DATA_GAP"
    STALE_SERIES = "STALE_SERIES"
    INVALID_VALUE_SERIES = "INVALID_VALUE_SERIES"


class DrawdownConfig(Base):
    """
    Configuration specification for Drawdown and Recovery analysis.
    """
    __tablename__ = "m07_drawdown_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"DDCONF_{uuid.uuid4().hex[:12].upper()}"
    )
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[DrawdownScopeType] = mapped_column(
        SAEnum(DrawdownScopeType, native_enum=False), default=DrawdownScopeType.PORTFOLIO, nullable=False
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    value_series_type: Mapped[DrawdownValueSeriesType] = mapped_column(
        SAEnum(DrawdownValueSeriesType, native_enum=False), default=DrawdownValueSeriesType.PORTFOLIO_NAV_SERIES, nullable=False
    )
    high_water_mark_policy: Mapped[HighWaterMarkPolicy] = mapped_column(
        SAEnum(HighWaterMarkPolicy, native_enum=False), default=HighWaterMarkPolicy.FULL_HISTORY_HIGH_WATER_MARK, nullable=False
    )
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    recovery_tolerance: Mapped[Decimal] = mapped_column(Numeric(10, 8), default=Decimal("0.00000001"), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DrawdownEpisode(Base):
    """
    Distinct drawdown episode starting at a running high-water mark peak,
    descending to a trough, and either recovering or remaining ongoing.
    """
    __tablename__ = "m07_drawdown_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"DDEP_{uuid.uuid4().hex[:12].upper()}"
    )
    series_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    scope_type: Mapped[DrawdownScopeType] = mapped_column(SAEnum(DrawdownScopeType, native_enum=False), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    peak_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    peak_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trough_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    trough_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recovery_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    recovery_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Magnitude metrics
    drawdown_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)  # positive percentage e.g. 15.50%
    signed_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)       # negative return e.g. -0.1550
    absolute_drawdown_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Durations
    peak_to_trough_days: Mapped[int] = mapped_column(Integer, nullable=False)
    trough_to_recovery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    underwater_duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    trading_sessions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)

    episode_status: Mapped[DrawdownEpisodeStatus] = mapped_column(
        SAEnum(DrawdownEpisodeStatus, native_enum=False), default=DrawdownEpisodeStatus.ONGOING, nullable=False
    )
    as_of_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_dd_ep_series_status", "series_id", "episode_status"),
        Index("ix_m07_dd_ep_port_time", "portfolio_id", "peak_timestamp"),
    )


class DrawdownSeriesResult(Base):
    """
    Time series records capturing running high-water mark and drawdown progression.
    """
    __tablename__ = "m07_drawdown_series_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    observation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    selected_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    running_high_water_mark: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high_water_mark_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    signed_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    drawdown_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    absolute_drawdown_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    episode_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    episode_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    data_quality_status: Mapped[str] = mapped_column(String(64), default="VALID", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_dd_series_time", "series_id", "observation_timestamp"),
    )


class MaximumDrawdownResult(Base):
    """
    Authoritative maximum peak-to-trough decline within a configured lookback window.
    """
    __tablename__ = "m07_maximum_drawdown_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"MDD_{uuid.uuid4().hex[:12].upper()}"
    )
    series_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    lookback_window_name: Mapped[str] = mapped_column(String(64), default="SINCE_INCEPTION", nullable=False)
    lookback_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    maximum_drawdown_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    signed_maximum_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    maximum_drawdown_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    peak_episode_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    peak_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    peak_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trough_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    trough_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recovery_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    peak_to_trough_days: Mapped[int] = mapped_column(Integer, nullable=False)
    trough_to_recovery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    underwater_duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    recovery_status: Mapped[DrawdownEpisodeStatus] = mapped_column(
        SAEnum(DrawdownEpisodeStatus, native_enum=False), default=DrawdownEpisodeStatus.RECOVERED, nullable=False
    )

    data_quality_status: Mapped[str] = mapped_column(String(64), default="VALID", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DrawdownRecoveryStatistics(Base):
    """
    Summary recovery diagnostics across completed and ongoing episodes.
    """
    __tablename__ = "m07_drawdown_recovery_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    total_episodes_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_episodes_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ongoing_episodes_count: Mapped[int] = mapped_column(Integer, nullable=False)

    average_recovery_days: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    median_recovery_days: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    longest_recovery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shortest_recovery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    average_peak_to_trough_days: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    average_underwater_days: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    longest_underwater_days: Mapped[int] = mapped_column(Integer, nullable=False)

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DrawdownDiagnostic(Base):
    """
    Data quality and continuity diagnostics for drawdown analysis.
    """
    __tablename__ = "m07_drawdown_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    episode_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    diagnostic_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="INFO", nullable=False)
    diagnostic_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

