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


class AssignmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ScopeType(str, enum.Enum):
    GLOBAL = "GLOBAL"
    PORTFOLIO = "PORTFOLIO"
    MODULE = "MODULE"
    RESOURCE = "RESOURCE"


class AuthDecisionType(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class Role(Base):
    """Institutional Role registry defining RBAC groups and permission profiles."""
    __tablename__ = "auth_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(String(64), unique=True, nullable=False, index=True)
    role_code = Column(String(64), unique=True, nullable=False, index=True) # VIEWER, ANALYST, OPERATOR, ADMINISTRATOR
    role_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    is_system_role = Column(Boolean, nullable=False, default=False)
    status = Column(String(32), nullable=False, default="ACTIVE")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    user_assignments = relationship("UserRoleAssignment", back_populates="role", cascade="all, delete-orphan")


class Permission(Base):
    """Granular permission definition following <module>.<resource>.<action> convention."""
    __tablename__ = "auth_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    permission_id = Column(String(64), unique=True, nullable=False, index=True)
    permission_code = Column(String(128), unique=True, nullable=False, index=True) # e.g. portfolio.positions.read
    permission_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    module = Column(String(64), nullable=False, index=True) # e.g. portfolio, risk, alerts, admin
    resource_type = Column(String(64), nullable=False, index=True) # e.g. portfolio, position, report, role
    action = Column(String(64), nullable=False, index=True) # e.g. read, create, update, delete, execute, export
    category = Column(String(64), nullable=False, default="STANDARD")
    status = Column(String(32), nullable=False, default="ACTIVE")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class RolePermission(Base):
    """Mapping between roles and granular permissions."""
    __tablename__ = "auth_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_permission_id = Column(String(64), unique=True, nullable=False, index=True)
    role_id = Column(String(64), ForeignKey("auth_roles.role_id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(String(64), ForeignKey("auth_permissions.permission_id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(64), nullable=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="role_permissions")


class UserRoleAssignment(Base):
    """Assignment of a role to a user with optional scope, effective dates, and audit trail."""
    __tablename__ = "auth_user_role_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    role_id = Column(String(64), ForeignKey("auth_roles.role_id", ondelete="CASCADE"), nullable=False, index=True)
    scope_type = Column(SQLEnum(ScopeType), nullable=False, default=ScopeType.GLOBAL)
    scope_id = Column(String(128), nullable=True, index=True) # e.g. portfolio ID if portfolio-scoped
    status = Column(SQLEnum(AssignmentStatus), nullable=False, default=AssignmentStatus.ACTIVE, index=True)
    effective_from = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    assigned_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    role = relationship("Role", back_populates="user_assignments")


class ResourceAccessAssignment(Base):
    """Resource-level access grants (e.g. Portfolio isolation grants)."""
    __tablename__ = "auth_resource_access_assignments"
    __table_args__ = (
        Index("ix_res_assign_lookup", "user_id", "resource_type", "resource_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, default="PORTFOLIO", index=True)
    resource_id = Column(String(128), nullable=False, index=True) # Specific portfolio_id or resource identifier
    access_level = Column(String(32), nullable=False, default="READ") # READ, WRITE, ADMIN
    status = Column(SQLEnum(AssignmentStatus), nullable=False, default=AssignmentStatus.ACTIVE, index=True)
    effective_from = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    assigned_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class AuthorizationDecisionRecord(Base):
    """Structured, immutable audit record of an evaluated authorization decision."""
    __tablename__ = "auth_decision_records"
    __table_args__ = (
        Index("ix_auth_dec_user_time", "user_id", "evaluated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(128), nullable=True, index=True)
    module = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    decision = Column(SQLEnum(AuthDecisionType), nullable=False, index=True)
    reason_code = Column(String(64), nullable=False)
    policy_version = Column(Integer, nullable=False, default=1)
    correlation_id = Column(String(64), nullable=True)
    evaluated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
