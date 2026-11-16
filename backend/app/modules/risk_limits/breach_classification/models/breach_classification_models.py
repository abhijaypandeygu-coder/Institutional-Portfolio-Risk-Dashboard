"""
SQLAlchemy ORM models for M11.07 — Breach Classification.

Database schemas:
1. `classification_policies`: Governed master classification policy entities.
2. `classification_policy_versions`: Immutable versioned rules and severity mappings.
3. `classification_rules`: Configurable rules translating metrics/magnitudes to WARNING, CRITICAL, EMERGENCY.
4. `breach_classifications`: Record of each breach severity determination.
5. `classification_evidence`: Immutable evidence snapshot supporting each classification.
6. `classification_history`: Audit trail of reclassifications and severity transitions.
7. `classification_events`: Immutable events published downstream to M11.08.
8. `classification_audit_events`: Administrative and governance audit log.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Text,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


class ClassificationPolicy(Base):
    """
    Parent policy governing breach classification.
    """
    __tablename__ = "classification_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_type: Mapped[str] = mapped_column(String(32), default="ALL")  # ALL, PORTFOLIO, ASSET_CLASS
    scope_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    risk_category: Mapped[str] = mapped_column(String(64), default="ALL")  # MARKET, LIQUIDITY, CONCENTRATION
    priority: Mapped[int] = mapped_column(Integer, default=100)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)  # DRAFT, SUBMITTED, APPROVED, ACTIVE, SUSPENDED, RETIRED
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    versions: Mapped[List["ClassificationPolicyVersion"]] = relationship(
        "ClassificationPolicyVersion", back_populates="policy", cascade="all, delete-orphan", order_by="desc(ClassificationPolicyVersion.version_number)"
    )


class ClassificationPolicyVersion(Base):
    """
    Immutable version of a classification policy containing rules.
    """
    __tablename__ = "classification_policy_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("classification_policies.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    severity_mapping: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    precedence_configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    materiality_configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    persistence_configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    emergency_rules: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    approval_status: Mapped[str] = mapped_column(String(32), default="DRAFT")  # DRAFT, APPROVED, SUPERSEDED
    
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    policy: Mapped["ClassificationPolicy"] = relationship("ClassificationPolicy", back_populates="versions")
    rules: Mapped[List["ClassificationRule"]] = relationship(
        "ClassificationRule", back_populates="version", cascade="all, delete-orphan"
    )


class ClassificationRule(Base):
    """
    Individual rule translating breach characteristics to WARNING, CRITICAL, or EMERGENCY.
    """
    __tablename__ = "classification_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("classification_policy_versions.id", ondelete="CASCADE"), index=True)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_metric_code: Mapped[str] = mapped_column(String(64), default="ALL", index=True)
    target_limit_type: Mapped[str] = mapped_column(String(32), default="ALL")
    
    # Rule Evaluation
    condition_operator: Mapped[str] = mapped_column(String(32), default="GREATER_THAN")  # GREATER_THAN, GREATER_EQUAL, BETWEEN, etc.
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    upper_threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="PERCENT")
    target_severity: Mapped[str] = mapped_column(String(16), nullable=False)  # WARNING, CRITICAL, EMERGENCY
    priority: Mapped[int] = mapped_column(Integer, default=100)
    
    # Special triggers
    persistence_requirement: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # TRANSIENT, PERSISTENT
    immediate_classification: Mapped[bool] = mapped_column(Boolean, default=False)
    materiality_requirement: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    version: Mapped["ClassificationPolicyVersion"] = relationship("ClassificationPolicyVersion", back_populates="rules")


class BreachClassification(Base):
    """
    Classification record linking a breach event to its evaluated severity.
    """
    __tablename__ = "breach_classifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    classification_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    breach_event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    breach_episode_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_limit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO")
    target_entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Classification Decision
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # WARNING, CRITICAL, EMERGENCY
    classification_status: Mapped[str] = mapped_column(String(32), default="CLASSIFIED")  # CLASSIFIED, RECLASSIFIED, UNAVAILABLE
    classification_reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Metric Evidence Snapshot
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    applied_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    breach_magnitude: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    utilization: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    persistence_status: Mapped[str] = mapped_column(String(32), default="TRANSIENT")
    materiality_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    materiality_status: Mapped[str] = mapped_column(String(32), default="NOT_EVALUATED")
    effective_limit_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    classified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    evidence: Mapped[List["ClassificationEvidence"]] = relationship(
        "ClassificationEvidence", back_populates="classification", cascade="all, delete-orphan"
    )
    history: Mapped[List["ClassificationHistory"]] = relationship(
        "ClassificationHistory", back_populates="classification", cascade="all, delete-orphan"
    )
    events: Mapped[List["ClassificationEvent"]] = relationship(
        "ClassificationEvent", back_populates="classification", cascade="all, delete-orphan"
    )


class ClassificationEvidence(Base):
    """
    Immutable evidence payload supporting a classification decision.
    """
    __tablename__ = "classification_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    classification_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_classifications.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="PERCENT")
    source_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    evidence_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    classification: Mapped["BreachClassification"] = relationship("BreachClassification", back_populates="evidence")


class ClassificationHistory(Base):
    """
    Audit log of reclassifications and severity transitions.
    """
    __tablename__ = "classification_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    classification_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_classifications.id", ondelete="CASCADE"), index=True)
    previous_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    new_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), default="REEVALUATION")  # UPGRADE, DOWNGRADE, POLICY_CHANGE, REEVALUATION
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    triggering_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    changed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    classification: Mapped["BreachClassification"] = relationship("BreachClassification", back_populates="history")


class ClassificationEvent(Base):
    """
    Structured event published downstream to M11.08.
    """
    __tablename__ = "classification_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    classification_id: Mapped[str] = mapped_column(String(64), ForeignKey("breach_classifications.id", ondelete="CASCADE"), index=True)
    breach_event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # WARNING_CLASSIFIED, CRITICAL_CLASSIFIED, EMERGENCY_CLASSIFIED, SEVERITY_UPGRADED, etc.
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    previous_severity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_limit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    classification: Mapped["BreachClassification"] = relationship("BreachClassification", back_populates="events")


class ClassificationAuditEvent(Base):
    """
    Administrative audit trail for policy lifecycle transitions.
    """
    __tablename__ = "classification_audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # POLICY, VERSION, CLASSIFICATION
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)   # POLICY_CREATED, APPROVED, ACTIVATED, SUSPENDED
    previous_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

