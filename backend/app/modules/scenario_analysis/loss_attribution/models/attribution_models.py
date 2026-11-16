"""
SQLAlchemy ORM models for M10.09 Stress Loss Attribution.
Strictly adheres to SQLAlchemy 2.0 type conventions using Mapped[Optional[T]].
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import uuid

from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    JSON,
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class StressLossAttribution(Base):
    """
    Attribution configuration master record.
    """
    __tablename__ = "m10_stress_loss_attributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    attribution_method: Mapped[str] = mapped_column(String(64), default="ARITHMETIC_EXACT", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="READY", nullable=False)
    completeness: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    runs: Mapped[List["StressLossAttributionRun"]] = relationship(
        "StressLossAttributionRun", back_populates="attribution", cascade="all, delete-orphan"
    )


class StressLossAttributionRun(Base):
    """
    Execution record of a stress loss attribution run.
    """
    __tablename__ = "m10_stress_loss_attribution_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_stress_loss_attributions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scenario_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    execution_status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    attribution_completeness: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    authoritative_total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    explained_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    residual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    loss_hhi: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    effective_contributor_count: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    input_manifest: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    attribution: Mapped["StressLossAttribution"] = relationship("StressLossAttribution", back_populates="runs")
    position_contributions: Mapped[List["StressPositionContribution"]] = relationship(
        "StressPositionContribution", back_populates="run", cascade="all, delete-orphan"
    )
    sector_contributions: Mapped[List["StressSectorContribution"]] = relationship(
        "StressSectorContribution", back_populates="run", cascade="all, delete-orphan"
    )
    industry_contributions: Mapped[List["StressIndustryContribution"]] = relationship(
        "StressIndustryContribution", back_populates="run", cascade="all, delete-orphan"
    )
    factor_contributions: Mapped[List["StressFactorContribution"]] = relationship(
        "StressFactorContribution", back_populates="run", cascade="all, delete-orphan"
    )
    interaction_effects: Mapped[List["StressInteractionEffect"]] = relationship(
        "StressInteractionEffect", back_populates="run", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["StressLossAttributionAuditLog"]] = relationship(
        "StressLossAttributionAuditLog", back_populates="run", cascade="all, delete-orphan"
    )


class StressPositionContribution(Base):
    """
    Position-level stressed P&L attribution and exact decomposition.
    """
    __tablename__ = "m10_stress_position_contributions"
    __table_args__ = (
        UniqueConstraint("attribution_run_id", "symbol", name="uq_run_position_symbol"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_stress_loss_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    position_direction: Mapped[str] = mapped_column(String(16), default="LONG", nullable=False)
    baseline_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fx_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    liquidity_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    other_adjustments: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    loss_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    contribution_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    sector: Mapped[str] = mapped_column(String(64), default="UNCLASSIFIED", nullable=False)
    industry: Mapped[str] = mapped_column(String(64), default="UNCLASSIFIED", nullable=False)

    # Relationships
    run: Mapped["StressLossAttributionRun"] = relationship("StressLossAttributionRun", back_populates="position_contributions")


class StressSectorContribution(Base):
    """
    Sector-level aggregated stress P&L contributions.
    """
    __tablename__ = "m10_stress_sector_contributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_stress_loss_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sector_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    loss_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    contribution_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    # Relationships
    run: Mapped["StressLossAttributionRun"] = relationship("StressLossAttributionRun", back_populates="sector_contributions")


class StressIndustryContribution(Base):
    """
    Industry-level aggregated stress P&L contributions.
    """
    __tablename__ = "m10_stress_industry_contributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_stress_loss_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    industry_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    loss_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    contribution_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    # Relationships
    run: Mapped["StressLossAttributionRun"] = relationship("StressLossAttributionRun", back_populates="industry_contributions")


class StressFactorContribution(Base):
    """
    Economic Factor Shock Attribution (View B).
    """
    __tablename__ = "m10_stress_factor_contributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_stress_loss_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    factor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_shock: Mapped[float] = mapped_column(Float, nullable=False)
    factor_exposure: Mapped[float] = mapped_column(Float, nullable=False)
    contribution_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    loss_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Relationships
    run: Mapped["StressLossAttributionRun"] = relationship("StressLossAttributionRun", back_populates="factor_contributions")


class StressInteractionEffect(Base):
    """
    Nonlinear interaction effect between multiple combined stress drivers.
    """
    __tablename__ = "m10_stress_interaction_effects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_stress_loss_attribution_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shock_driver_a: Mapped[str] = mapped_column(String(64), nullable=False)
    shock_driver_b: Mapped[str] = mapped_column(String(64), nullable=False)
    combined_effect: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    individual_effect_a: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    individual_effect_b: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    interaction_effect: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    interaction_method: Mapped[str] = mapped_column(String(32), default="COMBINED_SHOCK_DIFF", nullable=False)

    # Relationships
    run: Mapped["StressLossAttributionRun"] = relationship("StressLossAttributionRun", back_populates="interaction_effects")


class StressLossAttributionAuditLog(Base):
    """
    Audit log for attribution runs and configuration events.
    """
    __tablename__ = "m10_stress_attribution_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    attribution_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("m10_stress_loss_attribution_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    run: Mapped[Optional["StressLossAttributionRun"]] = relationship("StressLossAttributionRun", back_populates="audit_events")

