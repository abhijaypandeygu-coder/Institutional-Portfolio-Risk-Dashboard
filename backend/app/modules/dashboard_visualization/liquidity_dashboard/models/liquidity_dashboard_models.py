"""
SQLAlchemy ORM models for M13.06 — Liquidity Dashboard.

Defines persistence for:
1. liquidity_dashboard_preferences: User/portfolio default lookback, depth levels, participation rate
2. liquidity_saved_views: Named saved views and portfolio filters
3. liquidity_investigations: User investigation notes on spread blowouts, depth drops, or liquidation stress
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


class LiquidityDashboardPreference(Base):
    """Stores user or system default preferences for the Liquidity Dashboard."""
    __tablename__ = "liquidity_dashboard_preferences"

    id = Column(String(64), primary_key=True, default=lambda: f"ldpref_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    dashboard_name = Column(String(100), nullable=False, default="Default Liquidity Dashboard")
    default_portfolio_id = Column(String(64), nullable=True, index=True)
    
    # Spread & Depth display settings
    spread_unit = Column(String(16), nullable=False, default="BPS")  # BPS, RELATIVE, ABSOLUTE
    depth_levels_count = Column(Integer, nullable=False, default=5)
    default_lookback_days = Column(Integer, nullable=False, default=30)
    
    # Liquidation simulation defaults
    default_participation_rate = Column(Numeric(10, 4), nullable=False, default=0.10)  # 10%
    default_liquidation_scenario = Column(String(32), nullable=False, default="MODERATE")  # CONSERVATIVE, MODERATE, AGGRESSIVE
    default_target_percentage = Column(Numeric(10, 4), nullable=False, default=1.0)  # 100% full liquidation
    
    # UI Customizations / Color Scales / Warning Thresholds
    display_configuration = Column(JSON, nullable=True, default=dict)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "dashboard_name", name="uq_liq_user_dashboard_pref"),
    )


class LiquiditySavedView(Base):
    """Stores saved liquidity dashboard configurations and watchlists."""
    __tablename__ = "liquidity_saved_views"

    id = Column(String(64), primary_key=True, default=lambda: f"lview_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    view_name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    portfolio_id = Column(String(64), nullable=True, index=True)
    
    # Filter configurations (e.g. min_score, max_spread_bps, asset_classes)
    filters = Column(JSON, nullable=False, default=dict)
    selected_instrument_ids = Column(JSON, nullable=True, default=list)
    
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "view_name", name="uq_liq_user_view_name"),
    )


class LiquidityInvestigation(Base):
    """Stores risk analyst notes and investigations regarding liquidity anomalies."""
    __tablename__ = "liquidity_investigations"

    id = Column(String(64), primary_key=True, default=lambda: f"linv_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    portfolio_id = Column(String(64), nullable=True, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    
    investigation_type = Column(String(32), nullable=False)  # SPREAD_BLOWOUT, DEPTH_DROP, HIGH_LIQUIDATION_COST, SCORE_DEGRADATION
    severity = Column(String(16), nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(32), nullable=False, default="OPEN")  # OPEN, IN_REVIEW, RESOLVED, DISMISSED
    
    title = Column(String(200), nullable=False)
    notes = Column(Text, nullable=False)
    metrics_snapshot = Column(JSON, nullable=True, default=dict)
    
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
