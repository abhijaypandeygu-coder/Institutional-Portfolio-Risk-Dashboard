import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class KeyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    REVOKED = "REVOKED"


class SecretStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class EncryptionKeyRecord(Base):
    """Registry of Data Encryption Keys (DEKs) wrapped by Key Encryption Keys (KEK).
    Plaintext key material is NEVER stored directly.
    """
    __tablename__ = "sec_encryption_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_id = Column(String(64), unique=True, nullable=False, index=True) # e.g. key-dek-2026-v1
    key_version = Column(Integer, nullable=False, default=1, index=True)
    key_purpose = Column(String(64), nullable=False, default="FIELD_ENCRYPTION")
    algorithm = Column(String(32), nullable=False, default="AES-256-GCM")
    wrapped_key_payload = Column(Text, nullable=False) # JSON/Base64 of encrypted DEK using master KEK
    kek_identifier = Column(String(64), nullable=False, default="MASTER_KEK_V1")
    status = Column(SQLEnum(KeyStatus), nullable=False, default=KeyStatus.ACTIVE, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    retired_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class ManagedSecretRecord(Base):
    """Metadata registry of application secrets (API keys, integration credentials, tokens).
    Secret values are encrypted at rest with AES-256-GCM using active DEK.
    """
    __tablename__ = "sec_managed_secrets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    secret_id = Column(String(64), unique=True, nullable=False, index=True) # e.g. sec-alpha-vantage-api-key
    secret_name = Column(String(128), nullable=False)
    secret_type = Column(String(64), nullable=False) # API_KEY, DB_CREDENTIAL, OAUTH_TOKEN, WEBHOOK_SECRET
    owner_module = Column(String(64), nullable=False) # e.g. M01_FEED_REGISTRY, M12_ALERTS
    current_version = Column(Integer, nullable=False, default=1)
    status = Column(SQLEnum(SecretStatus), nullable=False, default=SecretStatus.ACTIVE, index=True)
    ciphertext_payload = Column(Text, nullable=False) # Versioned encrypted payload
    key_id = Column(String(64), ForeignKey("sec_encryption_keys.key_id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    last_rotated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    key = relationship("EncryptionKeyRecord")


class SecretVersionHistoryRecord(Base):
    """Historical versions of secrets preserved for rollback or rotation verification."""
    __tablename__ = "sec_secret_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    history_id = Column(String(64), unique=True, nullable=False, index=True)
    secret_id = Column(String(64), ForeignKey("sec_managed_secrets.secret_id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    ciphertext_payload = Column(Text, nullable=False)
    key_id = Column(String(64), nullable=False)
    status = Column(SQLEnum(SecretStatus), nullable=False, default=SecretStatus.DEPRECATED)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    retired_at = Column(DateTime, nullable=True)


class EncryptionPolicyRecord(Base):
    """Encryption policy definitions controlling classification and minimum algorithms."""
    __tablename__ = "sec_encryption_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(String(64), unique=True, nullable=False, index=True)
    policy_name = Column(String(128), nullable=False)
    classification = Column(String(32), nullable=False, default="RESTRICTED") # PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
    algorithm = Column(String(32), nullable=False, default="AES-256-GCM")
    key_rotation_days = Column(Integer, nullable=False, default=90)
    enforce_aad = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class SecurityAuditEventRecord(Base):
    """Cryptographic security events (key rotation, secret access denial, decryption failures)."""
    __tablename__ = "sec_encryption_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True) # KEY_ROTATION, SECRET_ROTATED, DECRYPTION_FAILED, etc.
    severity = Column(String(32), nullable=False, default="INFO", index=True) # INFO, WARNING, CRITICAL, EMERGENCY
    resource_id = Column(String(128), nullable=True, index=True)
    details = Column(JSON, nullable=True)
    source_ip = Column(String(64), nullable=True)
    actor_id = Column(String(64), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
