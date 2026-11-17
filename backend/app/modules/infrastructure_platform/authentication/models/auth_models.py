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
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"
    SUSPENDED = "SUSPENDED"


class SessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class AuthEventType(str, enum.Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_UNLOCKED = "ACCOUNT_UNLOCKED"


class UserIdentity(Base):
    """Authoritative user identity record for institutional authentication."""
    __tablename__ = "auth_user_identities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    login_identifier = Column(String(128), unique=True, nullable=False, index=True)
    normalized_login_identifier = Column(String(128), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="OPERATOR")
    account_status = Column(SQLEnum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE, index=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    credential = relationship("UserCredential", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserCredential(Base):
    """Secure credential record with scrypt/Argon2 adaptive salt and work factor."""
    __tablename__ = "auth_user_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    credential_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("auth_user_identities.user_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
    hash_algorithm = Column(String(32), nullable=False, default="scrypt")
    credential_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("UserIdentity", back_populates="credential")


class UserSession(Base):
    """Server-side opaque session token registry with idle and absolute expiration."""
    __tablename__ = "auth_user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("auth_user_identities.user_id", ondelete="CASCADE"), nullable=False, index=True)
    session_token_hash = Column(String(128), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE, index=True)
    authentication_method = Column(String(32), nullable=False, default="LOCAL_PASSWORD")
    user_agent = Column(String(256), nullable=True)
    ip_address = Column(String(64), nullable=True)
    last_activity_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserIdentity", back_populates="sessions")


class AuthenticationEventRecord(Base):
    """Persistent audit-integrated authentication security event."""
    __tablename__ = "auth_security_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    event_type = Column(SQLEnum(AuthEventType), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    login_identifier_snapshot = Column(String(128), nullable=True)
    session_id = Column(String(64), nullable=True)
    outcome = Column(String(32), nullable=False) # SUCCESS vs FAILURE
    failure_reason = Column(String(128), nullable=True)
    source_ip = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
