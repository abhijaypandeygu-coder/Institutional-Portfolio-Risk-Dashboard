"""
M07.09 Risk Contribution Database Models and Enums.
Defines persistent entities and enumerations for portfolio risk decomposition,
marginal and component risk contributions, group attributions, and Euler reconciliation.
"""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List
import uuid

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class RiskContributionStatus(str, Enum):
    VALID = "VALID"
    DEGENERATE_PORTFOLIO_ZERO_RISK = "DEGENERATE_PORTFOLIO_ZERO_RISK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    ALIGNMENT_FAILURE = "ALIGNMENT_FAILURE"
    FAILED = "FAILED"


class ReconciliationStatus(str, Enum):
    RECONCILED = "RECONCILED"
    RECONCILIATION_WARNING = "RECONCILIATION_WARNING"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"


class WeightBasis(str, Enum):
    MARKET_VALUE = "MARKET_VALUE"
    NAV = "NAV"
    GROSS_EXPOSURE = "GROSS_EXPOSURE"
    CUSTOM = "CUSTOM"


class GroupingDimension(str, Enum):
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    GEOGRAPHY = "GEOGRAPHY"
    STRATEGY_SLEEVE = "STRATEGY_SLEEVE"
    ASSET_CLASS = "ASSET_CLASS"


class RiskContributionCalculationRun(Base):
    """
    Header record representing an execution of the Risk Contribution decomposition
    for a portfolio at a specific as-of date.
    """
    __tablename__ = "m07_09_risk_contribution_runs"

    calculation_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    portfolio_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Configuration & Method details
    weight_basis: Mapped[WeightBasis] = mapped_column(
        SQLEnum(WeightBasis), default=WeightBasis.MARKET_VALUE, nullable=False
    )
    covariance_matrix_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    covariance_estimator: Mapped[str] = mapped_column(String(50), default="SAMPLE", nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("252.0"), nullable=False
    )

    # Portfolio Totals
    portfolio_total_value: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0.0"), nullable=False
    )
    portfolio_gross_exposure: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0.0"), nullable=False
    )
    portfolio_net_exposure: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0.0"), nullable=False
    )
    portfolio_variance: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("0.0"), nullable=False
    )
    portfolio_volatility: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("0.0"), nullable=False
    )
    annualized_portfolio_volatility: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("0.0"), nullable=False
    )

    # Euler Variance & Volatility Reconciliation Metrics
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        SQLEnum(ReconciliationStatus), default=ReconciliationStatus.RECONCILED, nullable=False
    )
    sum_component_variance: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("0.0"), nullable=False
    )
    variance_residual: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("0.0"), nullable=False
    )
    sum_component_volatility: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("0.0"), nullable=False
    )
    volatility_residual: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), default=Decimal("0.0"), nullable=False
    )
    relative_residual: Mapped[Decimal] = mapped_column(
        Numeric(12, 8), default=Decimal("0.0"), nullable=False
    )

    # Execution status & metadata
    status: Mapped[RiskContributionStatus] = mapped_column(
        SQLEnum(RiskContributionStatus), default=RiskContributionStatus.VALID, nullable=False
    )
    num_assets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finite_difference_max_error: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 10), nullable=True
    )
    calculation_lineage: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    holding_contributions: Mapped[List["HoldingRiskContributionResult"]] = relationship(
        "HoldingRiskContributionResult",
        back_populates="calculation_run",
        cascade="all, delete-orphan",
    )
    group_contributions: Mapped[List["GroupRiskContributionResult"]] = relationship(
        "GroupRiskContributionResult",
        back_populates="calculation_run",
        cascade="all, delete-orphan",
    )


class HoldingRiskContributionResult(Base):
    """
    Decomposition details for an individual holding / instrument within a calculation run.
    Stores Marginal Risk Contribution (MRC), Component Risk Contribution (CRC),
    Component Contribution to Variance (CCV), and percentage shares.
    """
    __tablename__ = "m07_09_holding_risk_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calculation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("m07_09_risk_contribution_runs.calculation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # Position Attributes
    market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    portfolio_weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    standalone_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)

    # Marginal Risk Metrics
    # MRC = d(sigma_p) / d(w_i) = (Sigma w)_i / sigma_p
    # MCV = d(sigma_p^2) / d(w_i) = 2 (Sigma w)_i
    marginal_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    marginal_variance_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)

    # Component Risk Metrics
    # CRC_i = w_i * MRC_i
    # CCV_i = w_i * (Sigma w)_i
    component_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    component_variance_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)

    # Percentage Share of Total Risk: CRC_i / sigma_p * 100
    percentage_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    percentage_variance_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)

    # Correlation with total portfolio return: rho(r_i, r_p) = (Sigma w)_i / (sigma_i * sigma_p)
    correlation_with_portfolio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)

    # Classification & Group Context
    sector: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    geography: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    strategy_sleeve: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Numerical Check
    finite_difference_mrc: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)

    calculation_run: Mapped["RiskContributionCalculationRun"] = relationship(
        "RiskContributionCalculationRun", back_populates="holding_contributions"
    )

    __table_args__ = (
        Index("idx_m07_09_holding_calc_inst", "calculation_id", "instrument_id"),
    )


class GroupRiskContributionResult(Base):
    """
    Aggregated Component Risk Contribution across a classification dimension
    (e.g. Sector, Industry, Geography, Sleeve).
    """
    __tablename__ = "m07_09_group_risk_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calculation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("m07_09_risk_contribution_runs.calculation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dimension: Mapped[GroupingDimension] = mapped_column(
        SQLEnum(GroupingDimension), nullable=False
    )
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)

    holding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    total_weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)

    # Sum of component contributions of all member holdings
    component_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    component_variance_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    percentage_risk_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    percentage_variance_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)

    calculation_run: Mapped["RiskContributionCalculationRun"] = relationship(
        "RiskContributionCalculationRun", back_populates="group_contributions"
    )

    __table_args__ = (
        Index("idx_m07_09_group_calc_dim", "calculation_id", "dimension"),
    )
