"""
M05.07 - Portfolio History Models.
Institutional bitemporal portfolio history, snapshot storage, change timeline, and risk run manifests.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


class SnapshotType(str, Enum):
    EOD = "EOD"
    INTRADAY = "INTRADAY"
    MANUAL = "MANUAL"
    RESTATED = "RESTATED"


class ChangeEventCategory(str, Enum):
    TRADE = "TRADE"
    POSITION_ADJUSTMENT = "POSITION_ADJUSTMENT"
    CASH_TRANSFER = "CASH_TRANSFER"
    DIVIDEND_CASH = "DIVIDEND_CASH"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    RECONCILIATION_CORRECTION = "RECONCILIATION_CORRECTION"
    SETTLEMENT = "SETTLEMENT"
    VALUATION_UPDATE = "VALUATION_UPDATE"
    SYSTEM_RESTATED = "SYSTEM_RESTATED"


class ReconstructionMode(str, Enum):
    EXACT_SNAPSHOT = "EXACT_SNAPSHOT"
    SOURCE_AS_OF = "SOURCE_AS_OF"
    SNAPSHOT_REPLAY = "SNAPSHOT_REPLAY"


class PortfolioBookSnapshot(Base):
    """
    Header record representing an authoritative snapshot of a portfolio book.
    Maintains dual temporal semantics (effective_as_of vs knowledge_as_of).
    """
    __tablename__ = "portfolio_book_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(String(32), nullable=False, default=SnapshotType.EOD.value)
    
    # Bitemporal timestamps
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Versioning & Restatement
    snapshot_version: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    is_restated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    superseded_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("portfolio_book_snapshots.snapshot_id"), nullable=True)
    restatement_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Aggregates & Integrity
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_positions_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    total_market_value_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_cash_value_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_nav_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    
    # Relationships
    positions: Mapped[List["HistoricalPositionSnapshot"]] = relationship("HistoricalPositionSnapshot", back_populates="snapshot", cascade="all, delete-orphan")
    cash_balances: Mapped[List["HistoricalCashSnapshot"]] = relationship("HistoricalCashSnapshot", back_populates="snapshot", cascade="all, delete-orphan")
    valuations: Mapped[List["HistoricalValuationSnapshot"]] = relationship("HistoricalValuationSnapshot", back_populates="snapshot", cascade="all, delete-orphan")
    source_manifests: Mapped[List["SnapshotSourceManifest"]] = relationship("SnapshotSourceManifest", back_populates="snapshot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_port_history_eff_know", "portfolio_id", "effective_as_of", "knowledge_as_of"),
    )


class HistoricalPositionSnapshot(Base):
    """
    Point-in-time security holding captured within a PortfolioBookSnapshot.
    """
    __tablename__ = "historical_position_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_book_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Quantities
    net_signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_long_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_short_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    settled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unsettled_buy_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unsettled_sell_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    # Cost & Valuation reference
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cost_basis_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    cost_basis_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    market_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    market_value_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unrealized_pnl_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)

    # Temporal context
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    snapshot: Mapped["PortfolioBookSnapshot"] = relationship("PortfolioBookSnapshot", back_populates="positions")

    __table_args__ = (
        Index("idx_hist_pos_port_inst", "portfolio_id", "instrument_id", "effective_as_of"),
    )


class HistoricalCashSnapshot(Base):
    """
    Point-in-time cash balance captured within a PortfolioBookSnapshot.
    """
    __tablename__ = "historical_cash_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_book_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    # Cash Breakdown
    settled_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unsettled_receivables: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unsettled_payables: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    reserved_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    restricted_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    available_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False)
    available_cash_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    # Temporal context
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    snapshot: Mapped["PortfolioBookSnapshot"] = relationship("PortfolioBookSnapshot", back_populates="cash_balances")


class HistoricalValuationSnapshot(Base):
    """
    Captured valuation metrics associated with a historical portfolio snapshot.
    """
    __tablename__ = "historical_valuation_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_book_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    price_source: Mapped[str] = mapped_column(String(64), nullable=False)
    price_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    market_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False)
    
    market_value_local: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    market_value_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_basis_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unrealized_pnl_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    snapshot: Mapped["PortfolioBookSnapshot"] = relationship("PortfolioBookSnapshot", back_populates="valuations")


class SnapshotSourceManifest(Base):
    """
    Tracks authoritative upstream module versions and event watermarks used to construct a snapshot.
    """
    __tablename__ = "snapshot_source_manifests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_book_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. M05.02_POSITIONS, M05.04_CASH
    event_watermark_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_watermark_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    records_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    snapshot: Mapped["PortfolioBookSnapshot"] = relationship("PortfolioBookSnapshot", back_populates="source_manifests")


class PortfolioChangeRecord(Base):
    """
    Chronological timeline entry recording an atomic change to the portfolio state.
    """
    __tablename__ = "portfolio_change_records"

    change_record_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Numeric(14, 0), nullable=False, index=True)
    
    event_category: Mapped[str] = mapped_column(String(48), nullable=False)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Bitemporal
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # Affected entities
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    account_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Impact summary
    quantity_delta: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    cash_delta: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    
    change_description: Mapped[str] = mapped_column(String(500), nullable=False)
    change_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("portfolio_id", "sequence_number", name="uq_port_hist_seq"),
        Index("idx_change_eff_rec", "portfolio_id", "effective_at", "recorded_at"),
    )


class RiskRunInputManifest(Base):
    """
    Immutable risk run input package that captures exact historical state references,
    partition IDs, market data reference versions, and policies for fully reproducible risk calculations.
    """
    __tablename__ = "risk_run_input_manifests"

    manifest_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Snapshot bound to
    snapshot_id: Mapped[str] = mapped_column(String(64), ForeignKey("portfolio_book_snapshots.snapshot_id"), nullable=False)
    effective_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Environmental & Dependency Fingerprints
    market_data_partition_id: Mapped[str] = mapped_column(String(128), nullable=False)
    pricing_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    fx_rate_table_version: Mapped[str] = mapped_column(String(64), nullable=False)
    corporate_action_version: Mapped[str] = mapped_column(String(64), nullable=False)
    
    positions_count: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    total_nav_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    manifest_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    manifest_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

