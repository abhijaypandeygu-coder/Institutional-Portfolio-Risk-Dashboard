"""
SQLAlchemy ORM models for M13.07 — Stress Testing Dashboard.

Defines persistence for:
1. stress_dashboard_preferences: User/desk default scenarios, layout, lookback, and comparison options
2. stress_saved_views: Named custom views and scenario comparison sets
3. stress_scenario_annotations: Risk officer notes, investigation records, and sign-offs on stress outcomes
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


class StressDashboardPreference(Base):
    """Stores user or desk default preferences for the Stress Testing Dashboard."""
    __tablename__ = "stress_dashboard_preferences"

    id = Column(String(64), primary_key=True, default=lambda: f"sdpref_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    dashboard_name = Column(String(100), nullable=False, default="Default Stress Testing Dashboard")
    default_portfolio_id = Column(String(64), nullable=True, index=True)
    
    # Filter and display defaults
    default_scenario_category = Column(String(50), nullable=False, default="ALL")  # ALL, HISTORICAL, HYPOTHETICAL, MARKET_CRASH, SECTOR_SHOCK, MONTE_CARLO
    preferred_currency_display = Column(String(8), nullable=False, default="BASE")  # BASE, USD, INR
    default_comparison_limit = Column(Integer, nullable=False, default=5)
    default_quantile_selection = Column(JSON, nullable=True, default=lambda: ["p01", "p05", "p50", "p95", "p99"])
    
    # UI Customizations / Color Scales / Layout
    display_configuration = Column(JSON, nullable=True, default=dict)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "dashboard_name", name="uq_stress_user_dashboard_pref"),
    )


class StressSavedView(Base):
    """Stores saved scenario comparison views and filter sets."""
    __tablename__ = "stress_saved_views"

    id = Column(String(64), primary_key=True, default=lambda: f"sview_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    view_name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    portfolio_id = Column(String(64), nullable=True, index=True)
    
    # Scenarios selected for side-by-side comparison
    selected_scenario_ids = Column(JSON, nullable=False, default=list)
    selected_calculation_ids = Column(JSON, nullable=True, default=list)
    filter_configuration = Column(JSON, nullable=True, default=dict)
    display_configuration = Column(JSON, nullable=True, default=dict)
    
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "view_name", name="uq_stress_user_view_name"),
    )


class StressScenarioAnnotation(Base):
    """Stores risk analyst annotations, investigation notes, and sign-offs on stress outcomes."""
    __tablename__ = "stress_scenario_annotations"

    id = Column(String(64), primary_key=True, default=lambda: f"sanno_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    portfolio_id = Column(String(64), nullable=True, index=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    calculation_id = Column(String(64), nullable=True, index=True)
    
    annotation_type = Column(String(32), nullable=False, default="INVESTIGATION")  # INVESTIGATION, EXTREME_LOSS_CAVEAT, ASSUMPTION_OVERRIDE, AUDIT_NOTE, SIGN_OFF
    severity = Column(String(16), nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(32), nullable=False, default="OPEN")  # OPEN, IN_REVIEW, RESOLVED, SIGNED_OFF
    
    title = Column(String(200), nullable=False)
    notes = Column(Text, nullable=False)
    metrics_snapshot = Column(JSON, nullable=True, default=dict)
    
    signoff_by = Column(String(64), nullable=True)
    signoff_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
