"""SQLAlchemy Models for M05.01 - Portfolio Creation."""
from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Boolean,
    Integer,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Enum as SAEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class PortfolioLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


class PortfolioTypeEnum(str, Enum):
    DISCRETIONARY = "DISCRETIONARY"
    NON_DISCRETIONARY = "NON_DISCRETIONARY"
    PROPRIETARY = "PROPRIETARY"
    MODEL_PORTFOLIO = "MODEL_PORTFOLIO"
    RESEARCH_PORTFOLIO = "RESEARCH_PORTFOLIO"
    PAPER_PORTFOLIO = "PAPER_PORTFOLIO"
    SIMULATED_PORTFOLIO = "SIMULATED_PORTFOLIO"
    CLIENT_PORTFOLIO = "CLIENT_PORTFOLIO"
    INSTITUTIONAL_PORTFOLIO = "INSTITUTIONAL_PORTFOLIO"
    AGGREGATE_PORTFOLIO = "AGGREGATE_PORTFOLIO"


class CreationSourceEnum(str, Enum):
    MANUAL_ADMINISTRATION = "MANUAL_ADMINISTRATION"
    INTERNAL_API = "INTERNAL_API"
    APPROVED_IMPORT = "APPROVED_IMPORT"
    SYSTEM_GENERATION = "SYSTEM_GENERATION"
    TEMPLATE_CLONING = "TEMPLATE_CLONING"
    OTHER_APPROVED_SOURCE = "OTHER_APPROVED_SOURCE"


class MarketScopeEnum(str, Enum):
    INDIA = "INDIA"
    UNITED_STATES = "UNITED_STATES"
    INDIA_AND_US = "INDIA_AND_US"
    OTHER_SUPPORTED_MARKETS = "OTHER_SUPPORTED_MARKETS"


class OwnershipTypeEnum(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    TEAM = "TEAM"
    DESK = "DESK"
    ORGANIZATION = "ORGANIZATION"
    LEGAL_ENTITY = "LEGAL_ENTITY"
    CLIENT_OR_ACCOUNT = "CLIENT_OR_ACCOUNT"
    SYSTEM_OWNED = "SYSTEM_OWNED"


class HierarchyTypeEnum(str, Enum):
    PARENT_PORTFOLIO = "PARENT_PORTFOLIO"
    AGGREGATE_PORTFOLIO = "AGGREGATE_PORTFOLIO"
    SLEEVE = "SLEEVE"
    STRATEGY_GROUP = "STRATEGY_GROUP"
    SUB_PORTFOLIO = "SUB_PORTFOLIO"
    STANDALONE_PORTFOLIO = "STANDALONE_PORTFOLIO"


class BenchmarkTypeEnum(str, Enum):
    PRIMARY_BENCHMARK = "PRIMARY_BENCHMARK"
    SECONDARY_BENCHMARK = "SECONDARY_BENCHMARK"
    STRATEGY_BENCHMARK = "STRATEGY_BENCHMARK"
    MARKET_BENCHMARK = "MARKET_BENCHMARK"
    CUSTOM_BENCHMARK = "CUSTOM_BENCHMARK"
    COMPOSITE_BENCHMARK = "COMPOSITE_BENCHMARK"
    NO_BENCHMARK = "NO_BENCHMARK"


class ValuationFrequencyEnum(str, Enum):
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    CUSTOM = "CUSTOM"


class AccountingBasisEnum(str, Enum):
    TRADE_DATE = "TRADE_DATE"
    SETTLEMENT_DATE = "SETTLEMENT_DATE"
    CONFIGURABLE_POLICY = "CONFIGURABLE_POLICY"


class CostBasisMethodEnum(str, Enum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    WEIGHTED_AVERAGE = "WEIGHTED_AVERAGE"
    SPECIFIC_IDENTIFICATION = "SPECIFIC_IDENTIFICATION"
    OTHER_APPROVED_METHOD = "OTHER_APPROVED_METHOD"


class DividendAccrualMethodEnum(str, Enum):
    CASH_ON_PAYMENT = "CASH_ON_PAYMENT"
    ACCRUAL_ON_ENTITLEMENT = "ACCRUAL_ON_ENTITLEMENT"
    ACCRUAL_ON_APPROVED_DATE = "ACCRUAL_ON_APPROVED_DATE"
    OTHER_APPROVED_METHOD = "OTHER_APPROVED_METHOD"


class LimitCategoryEnum(str, Enum):
    MAX_SINGLE_INSTRUMENT_EXPOSURE = "MAX_SINGLE_INSTRUMENT_EXPOSURE"
    MAX_SECTOR_EXPOSURE = "MAX_SECTOR_EXPOSURE"
    MAX_INDUSTRY_EXPOSURE = "MAX_INDUSTRY_EXPOSURE"
    MAX_MARKET_EXPOSURE = "MAX_MARKET_EXPOSURE"
    MAX_ASSET_CATEGORY_EXPOSURE = "MAX_ASSET_CATEGORY_EXPOSURE"
    MAX_CURRENCY_EXPOSURE = "MAX_CURRENCY_EXPOSURE"
    MAX_GROSS_EXPOSURE = "MAX_GROSS_EXPOSURE"
    MAX_NET_EXPOSURE = "MAX_NET_EXPOSURE"
    MAX_LEVERAGE = "MAX_LEVERAGE"
    MAX_CONCENTRATION = "MAX_CONCENTRATION"
    MAX_POSITION_SIZE = "MAX_POSITION_SIZE"
    MINIMUM_LIQUIDITY = "MINIMUM_LIQUIDITY"
    MAX_PORTFOLIO_DRAWDOWN = "MAX_PORTFOLIO_DRAWDOWN"
    MAX_TURNOVER = "MAX_TURNOVER"
    MAX_SHORT_EXPOSURE = "MAX_SHORT_EXPOSURE"


class LimitScopeEnum(str, Enum):
    PORTFOLIO_LEVEL = "PORTFOLIO_LEVEL"
    INSTRUMENT_LEVEL = "INSTRUMENT_LEVEL"
    SECTOR_LEVEL = "SECTOR_LEVEL"
    INDUSTRY_LEVEL = "INDUSTRY_LEVEL"
    MARKET_LEVEL = "MARKET_LEVEL"
    CURRENCY_LEVEL = "CURRENCY_LEVEL"
    ASSET_CATEGORY_LEVEL = "ASSET_CATEGORY_LEVEL"
    STRATEGY_LEVEL = "STRATEGY_LEVEL"
    CUSTOM_SCOPE = "CUSTOM_SCOPE"


class LimitThresholdTypeEnum(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    ABSOLUTE_AMOUNT = "ABSOLUTE_AMOUNT"
    MULTIPLE = "MULTIPLE"
    COUNT = "COUNT"
    RATIO = "RATIO"
    CURRENCY_AMOUNT = "CURRENCY_AMOUNT"
    CUSTOM_SUPPORTED_UNIT = "CUSTOM_SUPPORTED_UNIT"


class LimitStatusEnum(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# CORE PORTFOLIO MASTER TABLE
# ---------------------------------------------------------------------------
class Portfolio(Base):
    """
    Authoritative institutional portfolio master registry.
    """
    __tablename__ = "m05_portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    portfolio_type: Mapped[PortfolioTypeEnum] = mapped_column(
        SAEnum(PortfolioTypeEnum, native_enum=False), default=PortfolioTypeEnum.DISCRETIONARY, nullable=False
    )
    lifecycle_status: Mapped[PortfolioLifecycleStatus] = mapped_column(
        SAEnum(PortfolioLifecycleStatus, native_enum=False), default=PortfolioLifecycleStatus.DRAFT, nullable=False, index=True
    )
    creation_source: Mapped[CreationSourceEnum] = mapped_column(
        SAEnum(CreationSourceEnum, native_enum=False), default=CreationSourceEnum.MANUAL_ADMINISTRATION, nullable=False
    )
    
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True) # ISO-4217, e.g. 'USD', 'INR'
    market_scope: Mapped[MarketScopeEnum] = mapped_column(
        SAEnum(MarketScopeEnum, native_enum=False), default=MarketScopeEnum.INDIA_AND_US, nullable=False
    )
    asset_class_scope: Mapped[str] = mapped_column(String(64), default="EQUITIES", nullable=False)
    
    current_configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    strategy_assignments: Mapped[List["PortfolioStrategyAssignment"]] = relationship(
        "PortfolioStrategyAssignment", back_populates="portfolio", cascade="all, delete-orphan"
    )
    mandate_assignments: Mapped[List["PortfolioMandateAssignment"]] = relationship(
        "PortfolioMandateAssignment", back_populates="portfolio", cascade="all, delete-orphan"
    )
    benchmarks: Mapped[List["PortfolioBenchmark"]] = relationship(
        "PortfolioBenchmark", back_populates="portfolio", cascade="all, delete-orphan"
    )
    ownerships: Mapped[List["PortfolioOwnership"]] = relationship(
        "PortfolioOwnership", back_populates="portfolio", cascade="all, delete-orphan"
    )
    valuation_settings: Mapped[List["PortfolioValuationSettings"]] = relationship(
        "PortfolioValuationSettings", back_populates="portfolio", cascade="all, delete-orphan"
    )
    accounting_settings: Mapped[List["PortfolioAccountingSettings"]] = relationship(
        "PortfolioAccountingSettings", back_populates="portfolio", cascade="all, delete-orphan"
    )
    limits: Mapped[List["PortfolioLimit"]] = relationship(
        "PortfolioLimit", back_populates="portfolio", cascade="all, delete-orphan"
    )
    configuration_versions: Mapped[List["PortfolioConfigurationVersion"]] = relationship(
        "PortfolioConfigurationVersion", back_populates="portfolio", cascade="all, delete-orphan"
    )
    lifecycle_events: Mapped[List["PortfolioLifecycleEvent"]] = relationship(
        "PortfolioLifecycleEvent", back_populates="portfolio", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["PortfolioAuditEvent"]] = relationship(
        "PortfolioAuditEvent", back_populates="portfolio", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# STRATEGY & MANDATE TABLES
# ---------------------------------------------------------------------------
class PortfolioStrategy(Base):
    """Catalog of investment strategies."""
    __tablename__ = "m05_portfolio_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_family: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. QUANTITATIVE, FUNDAMENTAL
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supported_asset_classes: Mapped[str] = mapped_column(String(128), default="EQUITIES", nullable=False)
    supported_markets: Mapped[str] = mapped_column(String(128), default="INDIA_AND_US", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PortfolioStrategyAssignment(Base):
    """Associates portfolio with one or more strategies."""
    __tablename__ = "m05_portfolio_strategy_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assignment_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="strategy_assignments")


class PortfolioMandate(Base):
    """Formal investment mandate constraints and terms."""
    __tablename__ = "m05_portfolio_mandates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mandate_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    mandate_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mandate_type: Mapped[str] = mapped_column(String(64), default="LONG_ONLY_EQUITY", nullable=False)
    investment_objective: Mapped[str] = mapped_column(Text, nullable=False)
    permitted_markets: Mapped[str] = mapped_column(String(128), default="INDIA_AND_US", nullable=False)
    permitted_asset_classes: Mapped[str] = mapped_column(String(128), default="EQUITIES", nullable=False)
    short_selling_permitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    leverage_permitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    configuration_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON of structured limits
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PortfolioMandateAssignment(Base):
    """Associates portfolio with an investment mandate."""
    __tablename__ = "m05_portfolio_mandate_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    mandate_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="mandate_assignments")


# ---------------------------------------------------------------------------
# BENCHMARK ASSOCIATIONS
# ---------------------------------------------------------------------------
class PortfolioBenchmark(Base):
    """Benchmark associations with weights and primary/secondary designations."""
    __tablename__ = "m05_portfolio_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    association_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    benchmark_reference_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # e.g. 'NIFTY50', 'SP500'
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False)
    benchmark_type: Mapped[BenchmarkTypeEnum] = mapped_column(
        SAEnum(BenchmarkTypeEnum, native_enum=False), default=BenchmarkTypeEnum.PRIMARY_BENCHMARK, nullable=False
    )
    benchmark_currency: Mapped[str] = mapped_column(String(3), nullable=False) # e.g. 'USD', 'INR'
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    benchmark_weight: Mapped[float] = mapped_column(Numeric(6, 4), default=1.0000, nullable=False) # 1.0 = 100%
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="benchmarks")


# ---------------------------------------------------------------------------
# OWNERSHIP AND ORGANIZATIONAL METADATA
# ---------------------------------------------------------------------------
class PortfolioOwnership(Base):
    """Tracks owner, manager, desk, and team associations with historical preservation."""
    __tablename__ = "m05_portfolio_ownerships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ownership_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    ownership_type: Mapped[OwnershipTypeEnum] = mapped_column(
        SAEnum(OwnershipTypeEnum, native_enum=False), default=OwnershipTypeEnum.INDIVIDUAL, nullable=False
    )
    owner_entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # user_id, team_id, desk_id
    owner_name: Mapped[str] = mapped_column(String(128), nullable=False)
    ownership_role: Mapped[str] = mapped_column(String(64), default="PORTFOLIO_MANAGER", nullable=False)
    is_primary_owner: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="ownerships")


# ---------------------------------------------------------------------------
# PORTFOLIO HIERARCHY AND SLEEVES
# ---------------------------------------------------------------------------
class PortfolioHierarchy(Base):
    """Parent, child, sleeve, and strategy group relationships."""
    __tablename__ = "m05_portfolio_hierarchies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relationship_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    parent_portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id"), nullable=False, index=True
    )
    child_portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id"), nullable=False, index=True
    )
    relationship_type: Mapped[HierarchyTypeEnum] = mapped_column(
        SAEnum(HierarchyTypeEnum, native_enum=False), default=HierarchyTypeEnum.SLEEVE, nullable=False
    )
    allocation_weight: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True) # e.g. 0.4000 = 40%
    aggregation_method: Mapped[str] = mapped_column(String(64), default="PRO_RATA_WEIGHTED", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# VALUATION & ACCOUNTING SETTINGS
# ---------------------------------------------------------------------------
class PortfolioValuationSettings(Base):
    """Valuation calendar, frequency, cutoff time, and policy references."""
    __tablename__ = "m05_portfolio_valuation_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    valuation_calendar_id: Mapped[str] = mapped_column(String(64), default="DEFAULT_DAILY_CALENDAR", nullable=False)
    valuation_frequency: Mapped[ValuationFrequencyEnum] = mapped_column(
        SAEnum(ValuationFrequencyEnum, native_enum=False), default=ValuationFrequencyEnum.DAILY, nullable=False
    )
    cutoff_time: Mapped[str] = mapped_column(String(8), default="16:00:00", nullable=False) # HH:MM:SS
    cutoff_timezone: Mapped[str] = mapped_column(String(32), default="UTC", nullable=False)
    price_selection_policy_id: Mapped[str] = mapped_column(String(64), default="OFFICIAL_CLOSE_FALLBACK_PREV", nullable=False)
    currency_conversion_policy_id: Mapped[str] = mapped_column(String(64), default="DAILY_OFFICIAL_FX", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="valuation_settings")


class PortfolioAccountingSettings(Base):
    """Trade/settlement date basis, cost-basis, and dividend accrual policies."""
    __tablename__ = "m05_portfolio_accounting_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_accounting_basis: Mapped[AccountingBasisEnum] = mapped_column(
        SAEnum(AccountingBasisEnum, native_enum=False), default=AccountingBasisEnum.TRADE_DATE, nullable=False
    )
    cost_basis_method: Mapped[CostBasisMethodEnum] = mapped_column(
        SAEnum(CostBasisMethodEnum, native_enum=False), default=CostBasisMethodEnum.FIFO, nullable=False
    )
    dividend_accrual_method: Mapped[DividendAccrualMethodEnum] = mapped_column(
        SAEnum(DividendAccrualMethodEnum, native_enum=False), default=DividendAccrualMethodEnum.ACCRUAL_ON_ENTITLEMENT, nullable=False
    )
    corporate_action_policy_id: Mapped[str] = mapped_column(String(64), default="STANDARD_ADJUSTMENT_FACTOR", nullable=False)
    rounding_precision_places: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="accounting_settings")


# ---------------------------------------------------------------------------
# PORTFOLIO LIMITS
# ---------------------------------------------------------------------------
class PortfolioLimit(Base):
    """Applicable risk, concentration, and mandate limit configurations."""
    __tablename__ = "m05_portfolio_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    limit_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    limit_category: Mapped[LimitCategoryEnum] = mapped_column(
        SAEnum(LimitCategoryEnum, native_enum=False), nullable=False
    )
    limit_scope: Mapped[LimitScopeEnum] = mapped_column(
        SAEnum(LimitScopeEnum, native_enum=False), default=LimitScopeEnum.PORTFOLIO_LEVEL, nullable=False
    )
    scope_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True) # e.g. Sector code 'FINANCIALS'
    comparison_operator: Mapped[str] = mapped_column(String(8), default="<=", nullable=False) # '<=', '>=', '<', '>', '=='
    threshold_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    threshold_unit: Mapped[LimitThresholdTypeEnum] = mapped_column(
        SAEnum(LimitThresholdTypeEnum, native_enum=False), default=LimitThresholdTypeEnum.PERCENTAGE, nullable=False
    )
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    warning_threshold: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    hard_threshold: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    limit_status: Mapped[LimitStatusEnum] = mapped_column(
        SAEnum(LimitStatusEnum, native_enum=False), default=LimitStatusEnum.ACTIVE, nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="limits")


# ---------------------------------------------------------------------------
# CONFIGURATION SNAPSHOTS & AUDIT LOGS
# ---------------------------------------------------------------------------
class PortfolioConfigurationVersion(Base):
    """Point-in-time reproducible configuration snapshot."""
    __tablename__ = "m05_portfolio_configuration_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False) # JSON serialization of configuration
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    approval_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="configuration_versions")


class PortfolioLifecycleEvent(Base):
    """Tracks state machine transitions."""
    __tablename__ = "m05_portfolio_lifecycle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_status: Mapped[PortfolioLifecycleStatus] = mapped_column(
        SAEnum(PortfolioLifecycleStatus, native_enum=False), nullable=False
    )
    new_status: Mapped[PortfolioLifecycleStatus] = mapped_column(
        SAEnum(PortfolioLifecycleStatus, native_enum=False), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    approval_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="lifecycle_events")


class PortfolioAuditEvent(Base):
    """Immutable audit action trail for compliance and tracking."""
    __tablename__ = "m05_portfolio_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. CREATE, UPDATE_SETTINGS, ASSIGN_BENCHMARK
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False) # PORTFOLIO, LIMIT, BENCHMARK, HIERARCHY
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="audit_events")
