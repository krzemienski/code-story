"""Admin authentication endpoints with 2FA and session management.

Provides secure admin authentication:
- Login with optional 2FA
- Logout and session management
- 2FA setup and verification
- Audit logging of all actions
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.api.deps import DBSession
from codestory.models.admin import AdminUser, Permission
from codestory.services.admin_auth import AdminAuthService

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class AdminLoginRequest(BaseModel):
    """Admin login request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    totp_code: str | None = Field(None, min_length=6, max_length=6)


class AdminLoginResponse(BaseModel):
    """Admin login response."""

    access_token: str | None = None
    token_type: str = "bearer"
    admin_id: int | None = None
    role: str | None = None
    permissions: list[str] = []
    requires_2fa: bool = False
    message: str | None = None


class AdminTOTPSetup(BaseModel):
    """2FA setup response with secret and QR URI."""

    secret: str
    provisioning_uri: str


class AdminTOTPVerify(BaseModel):
    """2FA verification request."""

    code: str = Field(..., min_length=6, max_length=6)


class AdminSessionInfo(BaseModel):
    """Admin session information."""

    id: int
    ip_address: str
    user_agent: str | None
    created_at: datetime
    last_activity_at: datetime
    is_current: bool = False


class AdminProfileResponse(BaseModel):
    """Current admin profile."""

    id: int
    user_id: int
    email: str
    role: str
    permissions: list[str]
    totp_enabled: bool
    last_login_at: datetime | None
    last_login_ip: str | None


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# =============================================================================
# Dependencies
# =============================================================================


async def get_current_admin(
    request: Request,
    db: DBSession,
) -> AdminUser:
    """Get current authenticated admin from token.

    Args:
        request: FastAPI request
        db: Database session

    Returns:
        Authenticated AdminUser

    Raises:
        HTTPException: If not authenticated or not admin
    """
    from codestory.core.security import decode_access_token

    # Get token from header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ")[1]

    # Decode and validate token
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if admin token
    if payload.get("type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Validate session
    service = AdminAuthService(db)
    session = await service.validate_session(token)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get admin
    admin = await service.get_admin_by_id(payload.get("admin_id"))

    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account inactive",
        )

    # Store session ID for logout
    request.state.admin_session = session
    request.state.admin_token = token

    return admin


def require_permission(permission: Permission):
    """Dependency to require a specific permission.

    Args:
        permission: Required permission

    Returns:
        Dependency that validates permission
    """
    async def check_permission(
        admin: Annotated[AdminUser, Depends(get_current_admin)],
    ) -> AdminUser:
        if not admin.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required",
            )
        return admin

    return check_permission


# Type aliases
CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    request: Request,
    login_data: AdminLoginRequest,
    db: DBSession,
) -> AdminLoginResponse:
    """Authenticate admin user with optional 2FA.

    Args:
        request: FastAPI request
        login_data: Login credentials
        db: Database session

    Returns:
        Login response with token or 2FA requirement
    """
    service = AdminAuthService(db)

    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    # Authenticate
    admin, error = await service.authenticate(
        email=login_data.email,
        password=login_data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if error:
        # Log failed attempt
        await service.record_failed_login(
            email=login_data.email,
            ip_address=ip_address,
            reason=error,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
        )

    # Check 2FA if enabled
    if admin.totp_enabled:
        if not login_data.totp_code:
            return AdminLoginResponse(
                requires_2fa=True,
                message="2FA code required",
            )

        if not service.verify_totp(admin, login_data.totp_code):
            await service.record_failed_login(
                email=login_data.email,
                ip_address=ip_address,
                reason="Invalid 2FA code",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )

    # Create session
    token = await service.create_admin_session(admin, ip_address, user_agent)

    # Audit log
    await service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_login",
        category="authentication",
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return AdminLoginResponse(
        access_token=token,
        token_type="bearer",
        admin_id=admin.id,
        role=admin.role,
        permissions=[p.value for p in admin.get_permissions()],
    )


@router.post("/logout", response_model=MessageResponse)
async def admin_logout(
    request: Request,
    admin: CurrentAdmin,
    db: DBSession,
) -> MessageResponse:
    """Logout current admin session.

    Args:
        request: FastAPI request
        admin: Current admin
        db: Database session

    Returns:
        Success message
    """
    service = AdminAuthService(db)

    # Revoke current session
    session = request.state.admin_session
    await service.revoke_session(session.id, admin.id)

    # Audit log
    await service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_logout",
        category="authentication",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return MessageResponse(message="Logged out successfully")


@router.post("/logout/all", response_model=MessageResponse)
async def admin_logout_all(
    request: Request,
    admin: CurrentAdmin,
    db: DBSession,
) -> MessageResponse:
    """Logout all admin sessions.

    Args:
        request: FastAPI request
        admin: Current admin
        db: Database session

    Returns:
        Success message with count
    """
    service = AdminAuthService(db)

    count = await service.revoke_all_sessions(admin.id)

    # Audit log
    await service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_logout_all",
        category="authentication",
        details={"sessions_revoked": count},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return MessageResponse(message=f"Logged out of {count} sessions")


@router.get("/me", response_model=AdminProfileResponse)
async def get_current_admin_info(
    admin: CurrentAdmin,
) -> AdminProfileResponse:
    """Get current admin profile.

    Args:
        admin: Current admin

    Returns:
        Admin profile information
    """
    return AdminProfileResponse(
        id=admin.id,
        user_id=admin.user_id,
        email=admin.user.email,
        role=admin.role,
        permissions=[p.value for p in admin.get_permissions()],
        totp_enabled=admin.totp_enabled,
        last_login_at=admin.last_login_at,
        last_login_ip=admin.last_login_ip,
    )


@router.get("/sessions", response_model=list[AdminSessionInfo])
async def list_admin_sessions(
    request: Request,
    admin: CurrentAdmin,
    db: DBSession,
) -> list[AdminSessionInfo]:
    """List all active sessions for current admin.

    Args:
        request: FastAPI request
        admin: Current admin
        db: Database session

    Returns:
        List of active sessions
    """
    from codestory.models.admin import AdminSession

    result = await db.execute(
        select(AdminSession).where(
            AdminSession.admin_id == admin.id,
            AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > datetime.utcnow(),
        ).order_by(AdminSession.created_at.desc())
    )
    sessions = result.scalars().all()

    current_session = request.state.admin_session

    return [
        AdminSessionInfo(
            id=s.id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at,
            last_activity_at=s.last_activity_at,
            is_current=s.id == current_session.id,
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_admin_session(
    session_id: int,
    request: Request,
    admin: CurrentAdmin,
    db: DBSession,
) -> MessageResponse:
    """Revoke a specific session.

    Args:
        session_id: Session to revoke
        request: FastAPI request
        admin: Current admin
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If session not found or not owned
    """
    service = AdminAuthService(db)

    success = await service.revoke_session(session_id, admin.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Audit log
    await service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_revoke_session",
        category="authentication",
        details={"session_id": session_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return MessageResponse(message="Session revoked")


@router.post("/2fa/setup", response_model=AdminTOTPSetup)
async def setup_2fa(
    request: Request,
    admin: CurrentAdmin,
    db: DBSession,
) -> AdminTOTPSetup:
    """Generate 2FA setup with secret and QR code URI.

    Args:
        request: FastAPI request
        admin: Current admin
        db: Database session

    Returns:
        TOTP secret and provisioning URI

    Raises:
        HTTPException: If 2FA already enabled
    """
    if admin.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA already enabled",
        )

    service = AdminAuthService(db)
    provisioning_uri = service.setup_totp(admin)
    await db.commit()

    # Audit log
    await service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_2fa_setup",
        category="security",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return AdminTOTPSetup(
        secret=admin.totp_secret,
        provisioning_uri=provisioning_uri,
    )


@router.post("/2fa/verify", response_model=MessageResponse)
async def verify_2fa(
    request: Request,
    data: AdminTOTPVerify,
    admin: CurrentAdmin,
    db: DBSession,
) -> MessageResponse:
    """Verify 2FA code and enable 2FA.

    Args:
        request: FastAPI request
        data: Verification code
        admin: Current admin
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If code invalid
    """
    service = AdminAuthService(db)

    if not await service.enable_totp(admin, data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    # Audit log
    await service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_2fa_enabled",
        category="security",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return MessageResponse(message="2FA enabled successfully")


@router.delete("/2fa", response_model=MessageResponse)
async def disable_2fa(
    request: Request,
    admin: CurrentAdmin,
    db: DBSession,
) -> MessageResponse:
    """Disable 2FA for current admin.

    Args:
        request: FastAPI request
        admin: Current admin
        db: Database session

    Returns:
        Success message
    """
    service = AdminAuthService(db)
    await service.disable_totp(admin)

    # Audit log
    await service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_2fa_disabled",
        category="security",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return MessageResponse(message="2FA disabled")
