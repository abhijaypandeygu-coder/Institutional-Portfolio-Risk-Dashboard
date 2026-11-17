"""
SQLAlchemy ORM models for M13.10 — Custom Views.

Provides persistent storage for:
1. `dashboard_custom_views`: User-created customized dashboard workspaces with layout, widgets, filters, and sharing.
2. `dashboard_view_versions`: Immutable version snapshots of view layouts when modified or restored.
3. `dashboard_view_shares`: Explicit sharing permissions (VIEW, EDIT, DUPLICATE, MANAGE) to groups or users.
4. `dashboard_user_view_preferences`: User default view and presentation preferences.
5. `dashboard_view_audit_logs`: Institutional audit logs tracking view lifecycle (creation, updates, sharing, restores, deletion).
"""

from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DashboardCustomView(Base):
    """
    Main saved view definition representing a personal or group-shared dashboard workspace.
    """
    __tablename__ = "dashboard_custom_views"

    view_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"VIEW_{uuid.uuid4().hex[:12].upper()}")
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Visibility: 'PERSONAL' or 'GROUP'
    visibility: Mapped[str] = mapped_column(String(32), default="PERSONAL", nullable=False)
    owner_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    # Structured JSON configurations
    layout_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    widget_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    filter_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    time_range_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    # Versioning & Status
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_custom_views_owner", "owner_user_id"),
        Index("idx_custom_views_visibility", "visibility"),
        Index("idx_custom_views_group", "owner_group_id"),
        Index("idx_custom_views_archived", "is_archived"),
    )


class DashboardViewVersion(Base):
    """
    Immutable version history for saved dashboard layouts and widget configurations.
    """
    __tablename__ = "dashboard_view_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"VER_{uuid.uuid4().hex[:12].upper()}")
    view_id: Mapped[str] = mapped_column(String(64), ForeignKey("dashboard_custom_views.view_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_view_versions_lookup", "view_id", "version_number"),
    )


class DashboardViewShare(Base):
    """
    Fine-grained view sharing permissions for users or groups.
    Permissions can be: 'VIEW', 'EDIT', 'DUPLICATE', 'MANAGE'
    """
    __tablename__ = "dashboard_view_shares"

    share_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"SHR_{uuid.uuid4().hex[:12].upper()}")
    view_id: Mapped[str] = mapped_column(String(64), ForeignKey("dashboard_custom_views.view_id", ondelete="CASCADE"), nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(String(32), default="GROUP", nullable=False) # 'USER' or 'GROUP'
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    permission: Mapped[str] = mapped_column(String(32), default="VIEW", nullable=False)
    granted_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_view_shares_principal", "principal_type", "principal_id"),
        Index("idx_view_shares_view", "view_id"),
    )


class DashboardUserViewPreference(Base):
    """
    User-specific preferences including default view selection and responsive layout behavior.
    """
    __tablename__ = "dashboard_user_view_preferences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"UVPREF_{uuid.uuid4().hex[:12].upper()}")
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    default_view_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    preferred_timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    density_mode: Mapped[str] = mapped_column(String(32), default="COMFORTABLE", nullable=False) # 'COMPACT', 'COMFORTABLE'
    auto_refresh_sec: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    theme_preference: Mapped[str] = mapped_column(String(32), default="DARK", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DashboardViewAuditLog(Base):
    """
    Institutional audit logging for custom view operations.
    """
    __tablename__ = "dashboard_view_audit_logs"

    log_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"VALOG_{uuid.uuid4().hex[:12].upper()}")
    view_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    version_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    version_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_view_audit_view", "view_id"),
        Index("idx_view_audit_user", "user_id"),
        Index("idx_view_audit_created", "created_at"),
    )
