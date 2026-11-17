"""
SQLAlchemy ORM models for M13.05 — Correlation Dashboard.

Defines persistence for:
1. correlation_dashboard_preferences: User/portfolio default lookback, frequency, methodology
2. correlation_saved_universes: Named saved universes (portfolio subset, watchlist, factors)
3. correlation_saved_universe_members: Constituent instrument / factor mappings
4. correlation_investigations: User investigation notes on unusual / changing correlation pairs
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


class CorrelationDashboardPreference(Base):
    """Stores user or system default preferences for the Correlation Dashboard."""
    __tablename__ = "correlation_dashboard_preferences"

    id = Column(String(64), primary_key=True, default=lambda: f"cdpref_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    dashboard_name = Column(String(100), nullable=False, default="Default Correlation Dashboard")
    default_portfolio_id = Column(String(64), nullable=True, index=True)
    default_universe_type = Column(String(32), nullable=False, default="PORTFOLIO_HOLDINGS")
    
    # Estimation & Display Configuration
    default_lookback_days = Column(Integer, nullable=False, default=60)
    sampling_frequency = Column(String(32), nullable=False, default="DAILY")
    correlation_method = Column(String(32), nullable=False, default="PEARSON")
    return_definition = Column(String(32), nullable=False, default="LOGARITHMIC")
    min_observations = Column(Integer, nullable=False, default=20)
    
    # UI Layout & Heatmap Settings (Palette, Clustered view, etc.)
    display_configuration = Column(JSON, nullable=True, default=dict)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "dashboard_name", name="uq_corr_user_dashboard_pref"),
    )


class CorrelationSavedUniverse(Base):
    """Named collections of instruments or factors for correlation analysis."""
    __tablename__ = "correlation_saved_universes"

    id = Column(String(64), primary_key=True, default=lambda: f"cuniv_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    universe_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    universe_type = Column(String(32), nullable=False, default="CUSTOM_SECURITIES") # PORTFOLIO_HOLDINGS, SECTOR_GROUP, CUSTOM_SECURITIES, RISK_FACTORS
    portfolio_id = Column(String(64), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    members = relationship(
        "CorrelationSavedUniverseMember",
        back_populates="universe",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "universe_name", name="uq_corr_user_universe_name"),
    )


class CorrelationSavedUniverseMember(Base):
    """Constituent instruments or factors in a saved universe."""
    __tablename__ = "correlation_saved_universe_members"

    id = Column(String(64), primary_key=True, default=lambda: f"cumem_{uuid.uuid4().hex[:12]}")
    universe_id = Column(String(64), ForeignKey("correlation_saved_universes.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    member_type = Column(String(32), nullable=False, default="SECURITY") # SECURITY, FACTOR
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    universe = relationship("CorrelationSavedUniverse", back_populates="members")

    __table_args__ = (
        UniqueConstraint("universe_id", "instrument_id", name="uq_corr_univ_instrument"),
    )


class CorrelationInvestigation(Base):
    """Operational records of user annotations and investigation into anomalous correlation relationships."""
    __tablename__ = "correlation_investigations"

    id = Column(String(64), primary_key=True, default=lambda: f"cinv_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=False, index=True)
    portfolio_id = Column(String(64), nullable=True, index=True)
    instrument_a_id = Column(String(64), nullable=False, index=True)
    instrument_b_id = Column(String(64), nullable=False, index=True)
    
    # Statistical Context at time of investigation
    correlation_value = Column(Numeric(10, 4), nullable=False)
    previous_correlation = Column(Numeric(10, 4), nullable=True)
    correlation_method = Column(String(32), nullable=False, default="PEARSON")
    lookback_days = Column(Integer, nullable=False)
    sampling_frequency = Column(String(32), nullable=False, default="DAILY")
    observation_count = Column(Integer, nullable=False)
    
    detection_reason = Column(String(64), nullable=False) # HIGH_CORRELATION, NEGATIVE_CORRELATION, LARGE_CHANGE, SIGN_REVERSAL, REGIME_BREAK
    source_result_reference = Column(String(128), nullable=True)
    user_notes = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="OPEN") # OPEN, UNDER_REVIEW, RESOLVED, DISMISSED
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_corr_inv_pair", "instrument_a_id", "instrument_b_id"),
        Index("idx_corr_inv_created", "created_at"),
    )
