"""
SQLAlchemy ORM models for M13.08 — Alerts Dashboard.

Persistence layer for:
1. `alerts_dashboard_preferences`: User-specific alert & breach view preferences (severities, categories, page sizes, quiet display rules).
2. `alerts_saved_views`: Named custom filtered views across active breaches and alerts.
3. `alerts_dashboard_audit_logs`: Audit log tracking dashboard-initiated operational workflows.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertsDashboardPreference(Base):
    """Stores user/desk default preferences and settings for the Alerts Dashboard."""
    __tablename__ = "alerts_dashboard_preferences"

    id = Column(String(64), primary_key=True, default=lambda: f"adpref_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    dashboard_name = Column(String(100), nullable=False, default="Default Alerts Dashboard")
    default_portfolio_id = Column(String(64), nullable=True, index=True)
    
    # Filter preferences
    default_severity_selection = Column(JSON, nullable=False, default=lambda: ["WARNING", "CRITICAL", "EMERGENCY"])
    default_alert_category_selection = Column(JSON, nullable=False, default=lambda: ["ALL"])
    default_time_range_preset = Column(String(32), nullable=False, default="LAST_24_HOURS")
    
    # View configuration & pagination
    breaches_page_size = Column(Integer, nullable=False, default=25)
    alerts_page_size = Column(Integer, nullable=False, default=50)
    auto_refresh_interval_seconds = Column(Integer, nullable=False, default=30)
    sound_alerts_enabled = Column(Boolean, nullable=False, default=False)
    
    # UI Customizations & Layout
    display_configuration = Column(JSON, nullable=True, default=dict)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "dashboard_name", name="uq_alerts_user_dashboard_pref"),
    )


class AlertsSavedView(Base):
    """Stores named custom view configurations for rapid switching between breach/alert sets."""
    __tablename__ = "alerts_saved_views"

    id = Column(String(64), primary_key=True, default=lambda: f"aview_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    view_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    portfolio_id = Column(String(64), nullable=True, index=True)
    selected_severities = Column(JSON, nullable=False, default=lambda: ["CRITICAL", "EMERGENCY"])
    selected_categories = Column(JSON, nullable=False, default=lambda: ["ALL"])
    selected_statuses = Column(JSON, nullable=False, default=lambda: ["OPEN", "ACKNOWLEDGED", "INVESTIGATING"])
    time_range_preset = Column(String(32), nullable=False, default="LAST_24_HOURS")
    
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_alerts_saved_views_user_name", "user_id", "view_name"),
    )


class AlertsDashboardAuditLog(Base):
    """Tracks consequential user actions initiated from M13.08 (acknowledgements, assignments, closures)."""
    __tablename__ = "alerts_dashboard_audit_logs"

    id = Column(String(64), primary_key=True, default=lambda: f"adlog_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    action_type = Column(String(64), nullable=False, index=True)  # ACKNOWLEDGE_ALERT, ASSIGN_ALERT, CLOSE_ALERT, REOPEN_ALERT, ACKNOWLEDGE_BREACH
    target_type = Column(String(32), nullable=False, index=True)  # ALERT, BREACH
    target_id = Column(String(64), nullable=False, index=True)
    
    previous_state = Column(String(64), nullable=True)
    new_state = Column(String(64), nullable=False)
    comment = Column(Text, nullable=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    request_metadata = Column(JSON, nullable=True, default=dict)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
