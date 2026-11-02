"""
M08.01 Factor Definition Database Models and Enums.
Establishes the quantitative factor registry, immutable versioning,
characteristic definitions, construction specifications, source mappings,
factor models, pinned memberships, and governance audit trails.
"""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


# ============================================================================
# 1. ENUMERATIONS
# ============================================================================

class FactorFamily(str, Enum):
    MARKET = "MARKET"
    SIZE = "SIZE"
    VALUE = "VALUE"
    MOMENTUM = "MOMENTUM"
    QUALITY = "QUALITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    CUSTOM = "CUSTOM"


class FactorType(str, Enum):
    MARKET_RETURN_FACTOR = "MARKET_RETURN_FACTOR"
    LONG_SHORT_PORTFOLIO_FACTOR = "LONG_SHORT_PORTFOLIO_FACTOR"
    CHARACTERISTIC_FACTOR = "CHARACTERISTIC_FACTOR"
    EXTERNAL_FACTOR_SERIES = "EXTERNAL_FACTOR_SERIES"
    COMPOSITE_FACTOR = "COMPOSITE_FACTOR"
    CUSTOM_FACTOR = "CUSTOM_FACTOR"


class ConstructionType(str, Enum):
    INTERNALLY_CONSTRUCTED = "INTERNALLY_CONSTRUCTED"
    EXTERNALLY_SOURCED = "EXTERNALLY_SOURCED"
    HYBRID = "HYBRID"


class FactorLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class CharacteristicDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class StandardizationMethod(str, Enum):
    NONE = "NONE"
    CROSS_SECTIONAL_Z_SCORE = "CROSS_SECTIONAL_Z_SCORE"
    ROBUST_Z_SCORE = "ROBUST_Z_SCORE"
    PERCENTILE_RANK = "PERCENTILE_RANK"
    SECTOR_RELATIVE_Z_SCORE = "SECTOR_RELATIVE_Z_SCORE"


class WeightingMethodology(str, Enum):
    EQUAL_WEIGHTED = "EQUAL_WEIGHTED"
    MARKET_CAP_WEIGHTED = "MARKET_CAP_WEIGHTED"
    FREE_FLOAT_MARKET_CAP_WEIGHTED = "FREE_FLOAT_MARKET_CAP_WEIGHTED"
    SCORE_WEIGHTED = "SCORE_WEIGHTED"


class RebalancingFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"


class MarketScope(str, Enum):
    INDIA = "INDIA"
    UNITED_STATES = "UNITED_STATES"
    GLOBAL = "GLOBAL"
    CUSTOM = "CUSTOM"


# ============================================================================
# 2. FACTOR REGISTRY & VERSIONING MODELS
# ============================================================================

class FactorDefinition(Base):
    """
    Stable identity table for equity factors.
    Factor identity persists across revisions and version changes.
    """
    __tablename__ = "m08_01_factor_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factor_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    factor_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)  # e.g., MKT, SMB, HML, MOM, QMJ
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    factor_family: Mapped[FactorFamily] = mapped_column(SQLEnum(FactorFamily), nullable=False, index=True)
    factor_type: Mapped[FactorType] = mapped_column(SQLEnum(FactorType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    economic_interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    construction_type: Mapped[ConstructionType] = mapped_column(SQLEnum(ConstructionType), nullable=False)
    
    current_version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lifecycle_status: Mapped[FactorLifecycleStatus] = mapped_column(
        SQLEnum(FactorLifecycleStatus), default=FactorLifecycleStatus.DRAFT, nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versions: Mapped[List["FactorDefinitionVersion"]] = relationship(
        "FactorDefinitionVersion",
        back_populates="factor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class FactorDefinitionVersion(Base):
    """
    Immutable versioned analytical contract specifying how a factor is sourced or constructed.
    Any material change (e.g., benchmark, weighting, formation window) mandates a new version.
    """
    __tablename__ = "m08_01_factor_definition_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    factor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m08_01_factor_definitions.factor_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Core currency, frequency, and market scope
    market_scope: Mapped[MarketScope] = mapped_column(SQLEnum(MarketScope), default=MarketScope.INDIA, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)  # ISO 4217
    frequency: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    return_type: Mapped[str] = mapped_column(String(32), default="LOGARITHMIC", nullable=False)
    return_direction: Mapped[str] = mapped_column(String(32), default="LONG_MINUS_SHORT", nullable=False)  # or TOTAL_MARKET, EXCESS_MARKET

    # Full construction and source specification manifests (typed JSON)
    construction_specification: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Deterministic SHA256 cryptographic recipe hash
    definition_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Lifecycle and governance
    approval_status: Mapped[FactorLifecycleStatus] = mapped_column(
        SQLEnum(FactorLifecycleStatus), default=FactorLifecycleStatus.DRAFT, nullable=False, index=True
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    change_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    factor: Mapped["FactorDefinition"] = relationship("FactorDefinition", back_populates="versions")
    characteristics: Mapped[List["FactorCharacteristic"]] = relationship(
        "FactorCharacteristic",
        back_populates="version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("factor_id", "version_number", name="uq_m08_factor_version"),
        Index("idx_m08_factor_version_status", "factor_id", "approval_status"),
    )


class FactorCharacteristic(Base):
    """
    Deconstructed characteristic definitions for multi-attribute factors (Value, Quality).
    Tracks formula, direction, weight, standardization, and outlier rules.
    """
    __tablename__ = "m08_01_factor_characteristics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    characteristic_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m08_01_factor_definition_versions.version_id", ondelete="CASCADE"), nullable=False, index=True
    )
    characteristic_code: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g., ROE, DEBT_TO_EQUITY, BOOK_TO_MARKET
    characteristic_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_field_reference: Mapped[str] = mapped_column(String(128), nullable=False)  # accounting or market data source column
    formula_specification: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="RATIO", nullable=False)
    
    characteristic_direction: Mapped[CharacteristicDirection] = mapped_column(
        SQLEnum(CharacteristicDirection), default=CharacteristicDirection.HIGHER_IS_BETTER, nullable=False
    )
    standardization_method: Mapped[StandardizationMethod] = mapped_column(
        SQLEnum(StandardizationMethod), default=StandardizationMethod.CROSS_SECTIONAL_Z_SCORE, nullable=False
    )
    winsorization_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0100"), nullable=False)  # 1% tails
    component_weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1.0000"), nullable=False)
    missing_data_policy: Mapped[str] = mapped_column(String(64), default="EXCLUDE_OR_AVERAGE_REMAINING", nullable=False)

    version: Mapped["FactorDefinitionVersion"] = relationship("FactorDefinitionVersion", back_populates="characteristics")


# ============================================================================
# 3. FACTOR MODEL REGISTRY & MEMBERSHIP
# ============================================================================

class FactorModel(Base):
    """
    Canonical factor model identity (e.g., Fama-French 3-Factor, Carhart 4-Factor, Fama-French 5-Factor + Momentum).
    """
    __tablename__ = "m08_01_factor_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    model_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    market_scope: Mapped[MarketScope] = mapped_column(SQLEnum(MarketScope), default=MarketScope.INDIA, nullable=False)
    currency_basis: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    return_frequency: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    lifecycle_status: Mapped[FactorLifecycleStatus] = mapped_column(
        SQLEnum(FactorLifecycleStatus), default=FactorLifecycleStatus.DRAFT, nullable=False, index=True
    )
    current_version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    model_versions: Mapped[List["FactorModelVersion"]] = relationship(
        "FactorModelVersion",
        back_populates="model",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class FactorModelVersion(Base):
    """
    Immutable versioned collection of exact pinned factor definition versions.
    Enforces deterministic factor ordering (k = 1, ..., K).
    """
    __tablename__ = "m08_01_factor_model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m08_01_factor_models.model_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Deterministic hash of factor members, versions, order, and currencies
    model_definition_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    approval_status: Mapped[FactorLifecycleStatus] = mapped_column(
        SQLEnum(FactorLifecycleStatus), default=FactorLifecycleStatus.DRAFT, nullable=False, index=True
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    change_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    model: Mapped["FactorModel"] = relationship("FactorModel", back_populates="model_versions")
    memberships: Mapped[List["FactorModelMembership"]] = relationship(
        "FactorModelMembership",
        back_populates="model_version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("model_id", "version_number", name="uq_m08_model_version"),
    )


class FactorModelMembership(Base):
    """
    Explicit ordered factor membership within a factor model version.
    """
    __tablename__ = "m08_01_factor_model_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m08_01_factor_model_versions.model_version_id", ondelete="CASCADE"), nullable=False, index=True
    )
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # Pinned exact version!
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_position: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, ..., K
    
    model_version: Mapped["FactorModelVersion"] = relationship("FactorModelVersion", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("model_version_id", "factor_position", name="uq_m08_model_factor_pos"),
        UniqueConstraint("model_version_id", "factor_id", name="uq_m08_model_factor_id"),
    )
