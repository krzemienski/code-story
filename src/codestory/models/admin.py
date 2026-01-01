"""Admin role, permission, and session models.

Implements RBAC with role-based permissions, 2FA support,
and session management for admin users.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base

if TYPE_CHECKING:
    from .user import User


class AdminRole(str, Enum):
    """Admin role levels with increasing privileges."""

    SUPER_ADMIN = "super_admin"  # Full system access, can manage other admins
    ADMIN = "admin"              # User and content management
    SUPPORT = "support"          # Read-only access, limited actions


class Permission(str, Enum):
    """Granular permissions for admin actions."""

    # User management
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    MANAGE_QUOTAS = "manage_quotas"
    IMPERSONATE_USERS = "impersonate_users"

    # Content management
    VIEW_STORIES = "view_stories"
    DELETE_STORIES = "delete_stories"

    # API key management
    VIEW_API_KEYS = "view_api_keys"
    REVOKE_API_KEYS = "revoke_api_keys"

    # Analytics
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"

    # System administration
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_ADMINS = "manage_admins"
    SYSTEM_SETTINGS = "system_settings"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[AdminRole, list[Permission]] = {
    AdminRole.SUPER_ADMIN: list(Permission),  # All permissions
    AdminRole.ADMIN: [
        Permission.VIEW_USERS,
        Permission.EDIT_USERS,
        Permission.MANAGE_QUOTAS,
        Permission.VIEW_STORIES,
        Permission.DELETE_STORIES,
        Permission.VIEW_API_KEYS,
        Permission.REVOKE_API_KEYS,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_DATA,
        Permission.VIEW_AUDIT_LOGS,
    ],
    AdminRole.SUPPORT: [
        Permission.VIEW_USERS,
        Permission.VIEW_STORIES,
        Permission.VIEW_API_KEYS,
        Permission.VIEW_ANALYTICS,
    ],
}


class AdminUser(Base):
    """Admin user with elevated privileges and 2FA support.

    Extends regular user accounts with admin-specific features:
    - Role-based access control
    - Two-factor authentication (TOTP)
    - Session tracking and management
    """

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default=AdminRole.SUPPORT.value,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id"),
        nullable=True,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Two-factor authentication
    totp_secret: Mapped[str | None] = mapped_column(String(32), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Login tracking
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="admin_profile")
    sessions: Mapped[list[AdminSession]] = relationship(
        "AdminSession",
        back_populates="admin",
        lazy="selectin",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog",
        back_populates="admin",
        lazy="selectin",
    )

    @property
    def admin_role(self) -> AdminRole:
        """Get role as enum."""
        return AdminRole(self.role)

    def has_permission(self, permission: Permission) -> bool:
        """Check if admin has a specific permission.

        Args:
            permission: Permission to check

        Returns:
            True if admin has the permission and is active
        """
        if not self.is_active:
            return False
        return permission in ROLE_PERMISSIONS.get(self.admin_role, [])

    def get_permissions(self) -> list[Permission]:
        """Get all permissions for this admin.

        Returns:
            List of permissions based on role
        """
        if not self.is_active:
            return []
        return ROLE_PERMISSIONS.get(self.admin_role, [])

    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, role='{self.role}')>"


class AdminSession(Base):
    """Track admin sessions for security and audit.

    Stores session metadata for:
    - Concurrent session limiting
    - Session revocation
    - Activity tracking
    """

    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        index=True,
    )

    # Session identification
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Client info
    ip_address: Mapped[str] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Activity
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    admin: Mapped[AdminUser] = relationship("AdminUser", back_populates="sessions")

    @property
    def is_valid(self) -> bool:
        """Check if session is still valid."""
        now = datetime.utcnow()
        return (
            self.revoked_at is None
            and self.expires_at > now
        )

    def __repr__(self) -> str:
        return f"<AdminSession(id={self.id}, admin_id={self.admin_id})>"


class AuditLog(Base):
    """Comprehensive audit log for admin actions.

    Tracks all admin operations for security and compliance:
    - Who performed the action
    - What action was performed
    - What was affected
    - When and from where
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Actor
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_email: Mapped[str] = mapped_column(String(255))

    # Action
    action: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)

    # Target
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Details
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    # Relationships
    admin: Mapped[AdminUser | None] = relationship(
        "AdminUser",
        back_populates="audit_logs",
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}')>"
