"""Admin API key management endpoints.

Provides endpoints for:
- List all API keys across users with filtering
- Get detailed API key information
- Admin force-revoke API keys
- API key platform statistics

All endpoints require admin authentication with appropriate permissions.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.api.deps import get_session
from codestory.api.routers.admin_auth import require_permission
from codestory.models import AdminUser, APIKey, Permission, User
from codestory.services.admin_auth import AdminAuthService

router = APIRouter()


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class APIKeyListItem(BaseModel):
    """API key list item response."""

    id: int
    name: str
    key_prefix: str
    scopes: list[str]
    user_id: int
    user_email: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    request_count: int
    is_active: bool
    revoked_at: datetime | None


class APIKeyListResponse(BaseModel):
    """API key list response."""

    keys: list[APIKeyListItem]
    total: int
    page: int
    per_page: int


class APIKeyDetailResponse(BaseModel):
    """Detailed API key response."""

    key: dict[str, Any]
    user: dict[str, Any]
    stats: dict[str, Any]


class APIKeyStatsResponse(BaseModel):
    """Platform-wide API key statistics."""

    total_keys: int
    active_keys: int
    revoked_keys: int
    recently_active: int
    by_scope: dict[str, int]


class RevokeKeyRequest(BaseModel):
    """Request to revoke an API key."""

    reason: str = Field(..., min_length=1, max_length=500)


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get(
    "",
    response_model=APIKeyListResponse,
    summary="List all API keys",
    description="List all API keys across all users with filtering and pagination.",
)
async def list_api_keys(
    search: str | None = Query(None, description="Search by key name, prefix, or user email"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_API_KEYS)),
    session: AsyncSession = Depends(get_session),
) -> APIKeyListResponse:
    """List all API keys across all users."""
    # Build query
    query = (
        select(APIKey, User)
        .join(User, APIKey.user_id == User.id)
    )

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                APIKey.name.ilike(search_term),
                APIKey.key_prefix.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    if user_id is not None:
        query = query.where(APIKey.user_id == user_id)

    if is_active is not None:
        if is_active:
            query = query.where(
                and_(
                    APIKey.is_active == True,
                    APIKey.revoked_at.is_(None),
                )
            )
        else:
            query = query.where(
                or_(
                    APIKey.is_active == False,
                    APIKey.revoked_at.isnot(None),
                )
            )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(APIKey.created_at.desc()).offset(offset).limit(per_page)

    result = await session.execute(query)
    rows = result.all()

    keys = [
        APIKeyListItem(
            id=key.id,
            name=key.name,
            key_prefix=key.key_prefix,
            scopes=key.scopes.split(",") if key.scopes else [],
            user_id=key.user_id,
            user_email=user.email,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            request_count=key.request_count or 0,
            is_active=key.is_active and key.revoked_at is None,
            revoked_at=key.revoked_at,
        )
        for key, user in rows
    ]

    return APIKeyListResponse(
        keys=keys,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/stats",
    response_model=APIKeyStatsResponse,
    summary="Get API key statistics",
    description="Get platform-wide API key statistics.",
)
async def get_api_key_stats(
    admin: AdminUser = Depends(require_permission(Permission.VIEW_API_KEYS)),
    session: AsyncSession = Depends(get_session),
) -> APIKeyStatsResponse:
    """Get platform-wide API key statistics."""
    # Total keys
    total_result = await session.execute(select(func.count(APIKey.id)))
    total_keys = total_result.scalar() or 0

    # Active keys
    active_result = await session.execute(
        select(func.count(APIKey.id)).where(
            and_(
                APIKey.is_active == True,
                APIKey.revoked_at.is_(None),
            )
        )
    )
    active_keys = active_result.scalar() or 0

    # Recently active (used in last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_result = await session.execute(
        select(func.count(APIKey.id)).where(APIKey.last_used_at >= week_ago)
    )
    recently_active = recent_result.scalar() or 0

    # Keys by scope
    all_keys_result = await session.execute(select(APIKey.scopes))
    scope_counts: dict[str, int] = {}
    for (scopes,) in all_keys_result:
        if scopes:
            for scope in scopes.split(","):
                scope = scope.strip()
                if scope:
                    scope_counts[scope] = scope_counts.get(scope, 0) + 1

    return APIKeyStatsResponse(
        total_keys=total_keys,
        active_keys=active_keys,
        revoked_keys=total_keys - active_keys,
        recently_active=recently_active,
        by_scope=scope_counts,
    )


@router.get(
    "/{key_id}",
    response_model=APIKeyDetailResponse,
    summary="Get API key details",
    description="Get detailed information about a specific API key.",
)
async def get_api_key_details(
    key_id: int,
    admin: AdminUser = Depends(require_permission(Permission.VIEW_API_KEYS)),
    session: AsyncSession = Depends(get_session),
) -> APIKeyDetailResponse:
    """Get detailed info about an API key."""
    result = await session.execute(
        select(APIKey, User)
        .join(User, APIKey.user_id == User.id)
        .where(APIKey.id == key_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    key, user = row

    # Get usage stats (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    from codestory.models import APICallLog

    calls_result = await session.execute(
        select(func.count(APICallLog.id)).where(
            and_(
                APICallLog.user_id == key.user_id,
                APICallLog.created_at >= week_ago,
            )
        )
    )
    recent_calls = calls_result.scalar() or 0

    return APIKeyDetailResponse(
        key={
            "id": key.id,
            "name": key.name,
            "description": key.description,
            "key_prefix": key.key_prefix,
            "scopes": key.scopes.split(",") if key.scopes else [],
            "created_at": key.created_at.isoformat(),
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            "request_count": key.request_count or 0,
            "is_active": key.is_active,
            "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
        },
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "plan": user.plan if hasattr(user, "plan") else "free",
        },
        stats={
            "requests_last_7_days": recent_calls,
        },
    )


@router.post(
    "/{key_id}/revoke",
    summary="Revoke API key",
    description="Admin force-revoke an API key. This is a sensitive operation.",
)
async def revoke_api_key(
    key_id: int,
    request: RevokeKeyRequest,
    admin: AdminUser = Depends(require_permission(Permission.REVOKE_API_KEYS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Admin force-revoke an API key."""
    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id)
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is already revoked",
        )

    # Revoke the key
    key.revoked_at = datetime.utcnow()
    key.is_active = False

    # Create audit log
    auth_service = AdminAuthService(session)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="api_key_admin_revoked",
        category="api_key",
        target_type="api_key",
        target_id=str(key_id),
        details={
            "key_name": key.name,
            "key_prefix": key.key_prefix,
            "user_id": key.user_id,
            "reason": request.reason,
            "alert": "SENSITIVE_OPERATION",
        },
    )

    await session.commit()

    return {
        "status": "success",
        "message": f"API key {key_id} revoked successfully",
        "key_id": str(key_id),
    }


@router.post(
    "/{key_id}/reactivate",
    summary="Reactivate API key",
    description="Admin reactivate a revoked API key.",
)
async def reactivate_api_key(
    key_id: int,
    admin: AdminUser = Depends(require_permission(Permission.REVOKE_API_KEYS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Admin reactivate a revoked API key."""
    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id)
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if key.revoked_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is not revoked",
        )

    # Reactivate the key
    key.revoked_at = None
    key.is_active = True

    # Create audit log
    auth_service = AdminAuthService(session)
    await auth_service.create_audit_log(
        admin_id=admin.id,
        actor_email=admin.user.email,
        action="api_key_reactivated",
        category="api_key",
        target_type="api_key",
        target_id=str(key_id),
        details={
            "key_name": key.name,
            "key_prefix": key.key_prefix,
            "user_id": key.user_id,
        },
    )

    await session.commit()

    return {
        "status": "success",
        "message": f"API key {key_id} reactivated successfully",
        "key_id": str(key_id),
    }
