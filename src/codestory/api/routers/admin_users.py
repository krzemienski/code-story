"""Admin user management endpoints.

Provides endpoints for admin user management:
- List and search users
- View user details
- Update user profiles and quotas
- Suspend/unsuspend accounts
- Create impersonation tokens
- Manage user API keys
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field

from codestory.api.deps import DBSession
from codestory.api.routers.admin_auth import CurrentAdmin, require_permission
from codestory.models.admin import AdminUser, Permission
from codestory.services.admin_auth import AdminAuthService
from codestory.tools.user_management import UserManagementService

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class UserListItem(BaseModel):
    """User in list view."""

    id: int
    email: str
    is_active: bool
    subscription_tier: str
    usage_quota: int
    created_at: str | None


class UserListResponse(BaseModel):
    """Paginated user list."""

    users: list[UserListItem]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserStats(BaseModel):
    """User statistics."""

    story_count: int
    api_key_count: int
    active_api_keys: int


class UserDetailResponse(BaseModel):
    """Detailed user information."""

    id: int
    email: str
    is_active: bool
    is_superuser: bool
    subscription_tier: str
    usage_quota: int
    preferences: dict
    created_at: str | None
    updated_at: str | None
    is_admin: bool
    stats: UserStats


class UpdateUserRequest(BaseModel):
    """Update user profile request."""

    email: EmailStr | None = None
    subscription_tier: str | None = Field(None, pattern="^(free|pro|enterprise)$")
    usage_quota: int | None = Field(None, ge=0)
    preferences: dict | None = None


class UpdateUserResponse(BaseModel):
    """Update user response with changes."""

    user_id: int
    changes: dict
    updated_at: str | None


class SuspendUserRequest(BaseModel):
    """Suspend user request."""

    reason: str = Field(..., min_length=10, max_length=500)


class SuspendUserResponse(BaseModel):
    """Suspend user response."""

    user_id: int
    was_active: bool
    is_active: bool
    reason: str


class UnsuspendUserResponse(BaseModel):
    """Unsuspend user response."""

    user_id: int
    is_active: bool


class DeleteUserResponse(BaseModel):
    """Delete user response."""

    user_id: int
    deleted: bool
    type: str


class ImpersonationResponse(BaseModel):
    """Impersonation token response."""

    token: str
    user_id: int
    user_email: str
    expires_in: int
    impersonated_by: str
    warning: str = "This action is logged for audit purposes"


class APIKeyItem(BaseModel):
    """API key item."""

    id: int
    name: str
    is_active: bool
    rate_limit: int
    permissions: dict
    last_used_at: str | None
    expires_at: str | None
    created_at: str | None


class RevokeKeyResponse(BaseModel):
    """Revoke API key response."""

    key_id: int
    user_id: int
    revoked: bool


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=UserListResponse)
async def list_users(
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.VIEW_USERS))],
    search: str | None = Query(None, description="Search in email"),
    user_status: str | None = Query(None, alias="status", pattern="^(active|inactive)$"),
    plan: str | None = Query(None, pattern="^(free|pro|enterprise)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> UserListResponse:
    """List and search users with pagination.

    Args:
        request: FastAPI request
        db: Database session
        admin: Current admin (requires VIEW_USERS permission)
        search: Search term for email
        user_status: Filter by active/inactive
        plan: Filter by subscription tier
        page: Page number
        per_page: Results per page

    Returns:
        Paginated user list
    """
    service = UserManagementService(db)
    result = await service.search_users(
        search=search,
        status=user_status,
        plan=plan,
        page=page,
        per_page=per_page,
    )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_list_users",
        category="user_management",
        details={
            "search": search,
            "status": user_status,
            "plan": plan,
            "page": page,
            "result_count": len(result["users"]),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UserListResponse(**result)


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.VIEW_USERS))],
) -> UserDetailResponse:
    """Get detailed user information.

    Args:
        user_id: User ID
        request: FastAPI request
        db: Database session
        admin: Current admin (requires VIEW_USERS permission)

    Returns:
        Detailed user information

    Raises:
        HTTPException: If user not found
    """
    service = UserManagementService(db)
    result = await service.get_user_details(user_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_view_user",
        category="user_management",
        target_type="user",
        target_id=str(user_id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UserDetailResponse(**result)


@router.patch("/{user_id}", response_model=UpdateUserResponse)
async def update_user(
    user_id: int,
    data: UpdateUserRequest,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.EDIT_USERS))],
) -> UpdateUserResponse:
    """Update user profile.

    Args:
        user_id: User ID
        data: Update data
        request: FastAPI request
        db: Database session
        admin: Current admin (requires EDIT_USERS permission)

    Returns:
        Update result with changes

    Raises:
        HTTPException: If user not found
    """
    service = UserManagementService(db)
    result = await service.update_user(
        user_id=user_id,
        email=data.email,
        subscription_tier=data.subscription_tier,
        usage_quota=data.usage_quota,
        preferences=data.preferences,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_update_user",
        category="user_management",
        target_type="user",
        target_id=str(user_id),
        details=result["changes"],
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UpdateUserResponse(**result)


@router.patch("/{user_id}/quotas", response_model=UpdateUserResponse)
async def update_user_quotas(
    user_id: int,
    usage_quota: int = Query(..., ge=0),
    request: Request = None,
    db: DBSession = None,
    admin: AdminUser = Depends(require_permission(Permission.MANAGE_QUOTAS)),
) -> UpdateUserResponse:
    """Update user quotas.

    Args:
        user_id: User ID
        usage_quota: New usage quota
        request: FastAPI request
        db: Database session
        admin: Current admin (requires MANAGE_QUOTAS permission)

    Returns:
        Update result

    Raises:
        HTTPException: If user not found
    """
    service = UserManagementService(db)
    result = await service.update_user(
        user_id=user_id,
        usage_quota=usage_quota,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_update_quotas",
        category="user_management",
        target_type="user",
        target_id=str(user_id),
        details=result["changes"],
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UpdateUserResponse(**result)


@router.post("/{user_id}/suspend", response_model=SuspendUserResponse)
async def suspend_user(
    user_id: int,
    data: SuspendUserRequest,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.EDIT_USERS))],
) -> SuspendUserResponse:
    """Suspend a user account.

    Args:
        user_id: User ID
        data: Suspension details
        request: FastAPI request
        db: Database session
        admin: Current admin (requires EDIT_USERS permission)

    Returns:
        Suspension result

    Raises:
        HTTPException: If user not found
    """
    service = UserManagementService(db)
    result = await service.suspend_user(user_id, data.reason)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_suspend_user",
        category="user_management",
        target_type="user",
        target_id=str(user_id),
        details={"reason": data.reason},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return SuspendUserResponse(**result)


@router.post("/{user_id}/unsuspend", response_model=UnsuspendUserResponse)
async def unsuspend_user(
    user_id: int,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.EDIT_USERS))],
) -> UnsuspendUserResponse:
    """Remove suspension from user account.

    Args:
        user_id: User ID
        request: FastAPI request
        db: Database session
        admin: Current admin (requires EDIT_USERS permission)

    Returns:
        Unsuspension result

    Raises:
        HTTPException: If user not found
    """
    service = UserManagementService(db)
    result = await service.unsuspend_user(user_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_unsuspend_user",
        category="user_management",
        target_type="user",
        target_id=str(user_id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UnsuspendUserResponse(**result)


@router.delete("/{user_id}", response_model=DeleteUserResponse)
async def delete_user(
    user_id: int,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.DELETE_USERS))],
    hard_delete: bool = Query(False, description="Permanently delete user"),
) -> DeleteUserResponse:
    """Delete user account.

    Args:
        user_id: User ID
        request: FastAPI request
        db: Database session
        admin: Current admin (requires DELETE_USERS permission)
        hard_delete: If True, permanently delete; if False, soft delete

    Returns:
        Deletion result

    Raises:
        HTTPException: If user not found
    """
    service = UserManagementService(db)
    result = await service.delete_user(user_id, hard_delete)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_delete_user",
        category="user_management",
        target_type="user",
        target_id=str(user_id),
        details={"hard_delete": hard_delete},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return DeleteUserResponse(**result)


@router.post("/{user_id}/impersonate", response_model=ImpersonationResponse)
async def impersonate_user(
    user_id: int,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.IMPERSONATE_USERS))],
) -> ImpersonationResponse:
    """Create impersonation token for support.

    SECURITY: This action is always audit logged.

    Args:
        user_id: User ID to impersonate
        request: FastAPI request
        db: Database session
        admin: Current admin (requires IMPERSONATE_USERS permission)

    Returns:
        Impersonation token details

    Raises:
        HTTPException: If user not found
    """
    service = UserManagementService(db)
    result = await service.create_impersonation_token(user_id, admin)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # CRITICAL: Always audit log impersonation
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_impersonate_user",
        category="security",
        target_type="user",
        target_id=str(user_id),
        details={
            "user_email": result["user_email"],
            "expires_in": result["expires_in"],
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return ImpersonationResponse(**result)


@router.get("/{user_id}/api-keys", response_model=list[APIKeyItem])
async def get_user_api_keys(
    user_id: int,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.VIEW_API_KEYS))],
) -> list[APIKeyItem]:
    """Get all API keys for a user.

    Args:
        user_id: User ID
        request: FastAPI request
        db: Database session
        admin: Current admin (requires VIEW_API_KEYS permission)

    Returns:
        List of API keys
    """
    service = UserManagementService(db)
    keys = await service.get_user_api_keys(user_id)

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_view_api_keys",
        category="user_management",
        target_type="user",
        target_id=str(user_id),
        details={"key_count": len(keys)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return [APIKeyItem(**k) for k in keys]


@router.delete("/{user_id}/api-keys/{key_id}", response_model=RevokeKeyResponse)
async def revoke_user_api_key(
    user_id: int,
    key_id: int,
    request: Request,
    db: DBSession,
    admin: Annotated[AdminUser, Depends(require_permission(Permission.REVOKE_API_KEYS))],
) -> RevokeKeyResponse:
    """Revoke a specific API key.

    Args:
        user_id: User ID
        key_id: API key ID
        request: FastAPI request
        db: Database session
        admin: Current admin (requires REVOKE_API_KEYS permission)

    Returns:
        Revocation result

    Raises:
        HTTPException: If key not found
    """
    service = UserManagementService(db)
    result = await service.revoke_user_api_key(user_id, key_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    # Audit log
    auth_service = AdminAuthService(db)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="admin_revoke_api_key",
        category="user_management",
        target_type="api_key",
        target_id=str(key_id),
        details={"user_id": user_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return RevokeKeyResponse(**result)
