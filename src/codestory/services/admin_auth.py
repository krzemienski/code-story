"""Admin authentication service with 2FA and session management.

Provides secure admin authentication including:
- Password verification via Supabase
- TOTP-based 2FA
- Session creation and management
- Audit logging for all actions
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.models.admin import (
    AdminRole,
    AdminSession,
    AdminUser,
    AuditLog,
    Permission,
)
from codestory.models.user import User

if TYPE_CHECKING:
    from fastapi import Request


class AdminAuthService:
    """Service for admin authentication with SDK integration."""

    # Configuration
    SESSION_DURATION = timedelta(hours=8)
    MAX_SESSIONS = 3
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    async def authenticate(
        self,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str | None = None,
    ) -> tuple[AdminUser | None, str | None]:
        """Authenticate admin and return admin user or error.

        Args:
            email: Admin email
            password: Admin password
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Tuple of (AdminUser, None) on success or (None, error_message) on failure
        """
        # Find user by email
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None, "Invalid credentials"

        # Verify password via passlib/bcrypt
        if not self._verify_password(password, user.hashed_password):
            return None, "Invalid credentials"

        # Check for admin profile
        result = await self.db.execute(
            select(AdminUser).where(
                AdminUser.user_id == user.id,
                AdminUser.is_active == True,
            )
        )
        admin = result.scalar_one_or_none()

        if not admin:
            return None, "Not authorized for admin access"

        # Check if account is locked
        if admin.locked_until and admin.locked_until > datetime.utcnow():
            remaining = (admin.locked_until - datetime.utcnow()).seconds // 60
            return None, f"Account locked. Try again in {remaining} minutes"

        # Reset failed attempts on successful auth
        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.last_login_at = datetime.utcnow()
        admin.last_login_ip = ip_address

        await self.db.commit()

        return admin, None

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash.

        Args:
            plain_password: Plain text password
            hashed_password: Bcrypt hash

        Returns:
            True if password matches
        """
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.verify(plain_password, hashed_password)

    async def record_failed_login(
        self,
        email: str,
        ip_address: str,
        reason: str,
    ) -> None:
        """Record a failed login attempt.

        Args:
            email: Attempted email
            ip_address: Client IP
            reason: Failure reason
        """
        # Find admin by email if exists
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user:
            result = await self.db.execute(
                select(AdminUser).where(AdminUser.user_id == user.id)
            )
            admin = result.scalar_one_or_none()

            if admin:
                admin.failed_login_attempts += 1

                # Lock after max attempts
                if admin.failed_login_attempts >= self.MAX_LOGIN_ATTEMPTS:
                    admin.locked_until = datetime.utcnow() + self.LOCKOUT_DURATION

                await self.db.commit()

        # Log the attempt
        await self.create_audit_log(
            admin_id=None,
            actor_email=email,
            action="admin_login_failed",
            category="authentication",
            status="failure",
            error_message=reason,
            ip_address=ip_address,
        )

    def verify_totp(self, admin: AdminUser, code: str) -> bool:
        """Verify TOTP code for 2FA.

        Args:
            admin: Admin user
            code: TOTP code from authenticator app

        Returns:
            True if code is valid
        """
        if not admin.totp_enabled or not admin.totp_secret:
            return True  # 2FA not enabled

        totp = pyotp.TOTP(admin.totp_secret)
        # Allow 1 period window for clock skew
        return totp.verify(code, valid_window=1)

    async def create_admin_session(
        self,
        admin: AdminUser,
        ip_address: str,
        user_agent: str | None = None,
    ) -> str:
        """Create admin session and return JWT token.

        Args:
            admin: Authenticated admin
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            JWT access token
        """
        # Enforce max sessions - revoke oldest if needed
        result = await self.db.execute(
            select(AdminSession)
            .where(
                AdminSession.admin_id == admin.id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > datetime.utcnow(),
            )
            .order_by(AdminSession.created_at.asc())
        )
        active_sessions = list(result.scalars().all())

        if len(active_sessions) >= self.MAX_SESSIONS:
            oldest = active_sessions[0]
            oldest.revoked_at = datetime.utcnow()

        # Create JWT token
        from codestory.core.security import create_access_token

        token_data = {
            "sub": str(admin.user_id),
            "admin_id": admin.id,
            "role": admin.role,
            "permissions": [p.value for p in admin.get_permissions()],
            "type": "admin",
        }
        token = create_access_token(
            data=token_data,
            expires_delta=self.SESSION_DURATION,
        )

        # Store session
        session = AdminSession(
            admin_id=admin.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + self.SESSION_DURATION,
        )
        self.db.add(session)
        await self.db.commit()

        return token

    async def validate_session(self, token: str) -> AdminSession | None:
        """Validate admin session token.

        Args:
            token: JWT token

        Returns:
            AdminSession if valid, None otherwise
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        result = await self.db.execute(
            select(AdminSession).where(
                AdminSession.token_hash == token_hash,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > datetime.utcnow(),
            )
        )
        session = result.scalar_one_or_none()

        if session:
            session.last_activity_at = datetime.utcnow()
            await self.db.commit()

        return session

    async def revoke_session(self, session_id: int, admin_id: int) -> bool:
        """Revoke a specific admin session.

        Args:
            session_id: Session to revoke
            admin_id: Admin who owns the session

        Returns:
            True if session was revoked
        """
        result = await self.db.execute(
            select(AdminSession).where(
                AdminSession.id == session_id,
                AdminSession.admin_id == admin_id,
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            return False

        session.revoked_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def revoke_all_sessions(self, admin_id: int) -> int:
        """Revoke all sessions for an admin.

        Args:
            admin_id: Admin whose sessions to revoke

        Returns:
            Number of sessions revoked
        """
        result = await self.db.execute(
            select(AdminSession).where(
                AdminSession.admin_id == admin_id,
                AdminSession.revoked_at.is_(None),
            )
        )
        sessions = list(result.scalars().all())

        for session in sessions:
            session.revoked_at = datetime.utcnow()

        await self.db.commit()
        return len(sessions)

    def setup_totp(self, admin: AdminUser) -> str:
        """Generate TOTP secret for 2FA setup.

        Args:
            admin: Admin user

        Returns:
            Provisioning URI for QR code
        """
        secret = pyotp.random_base32()
        admin.totp_secret = secret

        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=admin.user.email,
            issuer_name="Code Story Admin",
        )

    async def enable_totp(self, admin: AdminUser, code: str) -> bool:
        """Enable 2FA after verifying setup code.

        Args:
            admin: Admin user
            code: Verification code from authenticator

        Returns:
            True if 2FA was enabled
        """
        if not admin.totp_secret:
            return False

        totp = pyotp.TOTP(admin.totp_secret)
        if totp.verify(code):
            admin.totp_enabled = True
            await self.db.commit()
            return True

        return False

    async def disable_totp(self, admin: AdminUser) -> None:
        """Disable 2FA for an admin.

        Args:
            admin: Admin user
        """
        admin.totp_enabled = False
        admin.totp_secret = None
        await self.db.commit()

    async def create_audit_log(
        self,
        admin_id: int | None,
        actor_email: str,
        action: str,
        category: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict | None = None,
        status: str = "success",
        error_message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry.

        Args:
            admin_id: Admin who performed action
            actor_email: Email of actor
            action: Action name
            category: Action category
            target_type: Type of target resource
            target_id: ID of target resource
            details: Additional details
            status: success/failure
            error_message: Error if failed
            ip_address: Client IP
            user_agent: Client user agent
            request_id: Request correlation ID

        Returns:
            Created AuditLog entry
        """
        log = AuditLog(
            admin_id=admin_id,
            actor_email=actor_email,
            action=action,
            category=category,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            status=status,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        self.db.add(log)
        await self.db.commit()

        return log

    async def get_admin_by_id(self, admin_id: int) -> AdminUser | None:
        """Get admin by ID.

        Args:
            admin_id: Admin ID

        Returns:
            AdminUser or None
        """
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.id == admin_id)
        )
        return result.scalar_one_or_none()

    async def require_permission(
        self,
        admin: AdminUser,
        permission: Permission,
    ) -> bool:
        """Check if admin has required permission.

        Args:
            admin: Admin user
            permission: Required permission

        Returns:
            True if admin has permission

        Raises:
            PermissionError: If admin lacks permission
        """
        if not admin.has_permission(permission):
            raise PermissionError(
                f"Permission denied: {permission.value} required"
            )
        return True
