"""
M13.09 - Historical Analytics Models.
SQLAlchemy models for user preferences, saved historical views, and audit logging.
Strictly does not duplicate authoritative portfolio, valuation, risk, or event data.
"""

from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HistoricalAnalyticsPreference(Base):
    """
    User-specific preferences for the Historical Analytics workspace.
    """
    __tablename__ = "historical_analytics_preferences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"HAP_{uuid.uuid4().hex[:12].upper()}")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dashboard_name: Mapped[str] = mapped_column(String(128), default="Default Historical Analytics", nullable=False)
    default_portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    default_lookback_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    default_frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    default_historical_mode: Mapped[str] = mapped_column(String(32), default="AS_KNOWN_AT_TIME", nullable=False)
    default_timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    enabled_event_overlays: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["ALERTS", "BREACHES", "TRADES", "SCENARIOS"], nullable=False)
    downsample_threshold: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_hist_pref_user", "user_id"),
    )


class HistoricalAnalyticsSavedView(Base):
    """
    Saved custom historical workspace views, supporting multi-metric comparisons and time ranges.
    """
    __tablename__ = "historical_analytics_saved_views"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"HSV_{uuid.uuid4().hex[:12].upper()}")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    view_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    portfolio_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    historical_mode: Mapped[str] = mapped_column(String(32), default="AS_KNOWN_AT_TIME", nullable=False)
    selected_metrics: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["NAV", "DAILY_PNL", "VAR_99_1D"], nullable=False)
    event_overlay_filters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_hist_view_user", "user_id"),
    )


class HistoricalAnalyticsAuditLog(Base):
    """
    Immutable audit trail for historical queries, point-in-time state reconstructions, and data exports.
    """
    __tablename__ = "historical_analytics_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"HAL_{uuid.uuid4().hex[:12].upper()}")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # POINT_IN_TIME_RECONSTRUCT, EXPORT, VERSION_COMPARE, QUERY
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    knowledge_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    historical_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("idx_hist_audit_user_ts", "user_id", "timestamp"),
    )
