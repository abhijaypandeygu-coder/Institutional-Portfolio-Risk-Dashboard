"""
SQLAlchemy 2.x Database Models for M04.02 Security Classification.
Includes:
- Classification schemes and releases
- Hierarchical classification nodes (Sectors, Industries)
- Asset categories
- Bitemporal instrument classification assignments
- Analytical asset category assignments
- Sources, evidence, import batches, and review cases
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Numeric, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# 1. Classification Scheme Registry
class ClassificationScheme(Base):
    __tablename__ = "m04_classification_schemes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    scheme_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    scheme_type: Mapped[str] = mapped_column(String(32), default="INTERNAL_PROPRIETARY", nullable=False)
    applicable_market_scope: Mapped[str] = mapped_column(String(64), default="GLOBAL", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_primary_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 2. Scheme Taxonomy Versions (e.g. GICS 2023, Internal V1.2)
class ClassificationSchemeVersion(Base):
    __tablename__ = "m04_classification_scheme_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m04_classification_schemes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version_description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("scheme_id", "version_code", name="uq_scheme_version"),
    )


# 3. Hierarchical Classification Nodes (Sectors, Industries)
class ClassificationNode(Base):
    __tablename__ = "m04_classification_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"NOD_{uuid.uuid4().hex[:12].upper()}"
    )
    scheme_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m04_classification_schemes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheme_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m04_classification_scheme_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # e.g. "45" (Tech) or "4510" (Software)
    node_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    node_description: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)  # SECTOR, INDUSTRY
    parent_node_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1=Sector, 2=Industry

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    node_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)

    __table_args__ = (
        UniqueConstraint("scheme_id", "scheme_version_id", "node_code", name="uq_scheme_node_code"),
    )


# 4. Analytical Asset Category Registry
class AssetCategory(Base):
    __tablename__ = "m04_asset_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    category_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_asset_class: Mapped[str] = mapped_column(String(32), default="EQUITY", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# 5. Bitemporal Instrument Sector/Industry Classification Assignment
class InstrumentClassificationAssignment(Base):
    __tablename__ = "m04_instrument_classification_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ASN_{uuid.uuid4().hex[:12].upper()}"
    )
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheme_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m04_classification_schemes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheme_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m04_classification_scheme_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sector_node_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    industry_node_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    assignment_status: Mapped[str] = mapped_column(String(32), default="CLASSIFIED", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False, index=True)
    assignment_source: Mapped[str] = mapped_column(String(64), default="INTERNAL_RESEARCH", nullable=False)
    assignment_reason: Mapped[str] = mapped_column(Text, nullable=False)
    assignment_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Bitemporal Valid Time (market applicability)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Bitemporal Transaction Time (platform recording)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)


# 6. Instrument Asset Category Assignment
class InstrumentAssetCategoryAssignment(Base):
    __tablename__ = "m04_instrument_asset_category_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ACA_{uuid.uuid4().hex[:12].upper()}"
    )
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    assignment_status: Mapped[str] = mapped_column(String(32), default="CLASSIFIED", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    assignment_source: Mapped[str] = mapped_column(String(64), default="M04_01_INHERITED", nullable=False)
    assignment_reason: Mapped[str] = mapped_column(Text, nullable=False)

    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)


# 7. Classification Review Cases (Conflicts & Ambiguities)
class ClassificationReviewCase(Base):
    __tablename__ = "m04_classification_review_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"CRV_{uuid.uuid4().hex[:12].upper()}"
    )
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scheme_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_decision: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# 8. Append-Only Classification Audit Events
class ClassificationAuditEvent(Base):
    __tablename__ = "m04_classification_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: f"CLA_{uuid.uuid4().hex[:12].upper()}"
    )
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_state: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    new_state: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

