"""Users router for profile and settings management.

Endpoints for user profile, preferences, and API key management.
"""

from datetime import datetime
from typing import Annotated
import secrets

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select

from codestory.api.deps import AdminUser, CurrentUser, DBSession
from codestory.api.exceptions import NotFoundError

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class UserProfileResponse(BaseModel):
    """User profile response."""

    id: int
    email: str
    name: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login_at: datetime | None

    class Config:
        from_attributes = True


class UserProfileUpdateRequest(BaseModel):
    """Request to update user profile."""

    name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None


class APIKeyResponse(BaseModel):
    """API key response (key shown only on creation)."""

    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    is_active: bool


class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=100)


class APIKeyCreatedResponse(BaseModel):
    """Response with full API key (only shown once)."""

    id: int
    name: str
    key: str  # Full key, only shown on creation
    prefix: str
    created_at: datetime


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# =============================================================================
# Profile Endpoints
# =============================================================================


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(user: CurrentUser) -> UserProfileResponse:
    """Get current user's profile.

    Args:
        user: Authenticated user

    Returns:
        User profile information
    """
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    request: UserProfileUpdateRequest,
    user: CurrentUser,
    db: DBSession,
) -> UserProfileResponse:
    """Update current user's profile.

    Args:
        request: Fields to update
        user: Authenticated user
        db: Database session

    Returns:
        Updated user profile
    """
    if request.name is not None:
        user.name = request.name

    if request.email is not None:
        # Check email not already taken
        from codestory.models.user import User
        result = await db.execute(
            select(User).where(User.email == request.email, User.id != user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        user.email = request.email

    await db.commit()
    await db.refresh(user)

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


# =============================================================================
# API Key Endpoints
# =============================================================================


@router.get("/me/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    user: CurrentUser,
    db: DBSession,
) -> list[APIKeyResponse]:
    """List user's API keys.

    Args:
        user: Authenticated user
        db: Database session

    Returns:
        List of API keys (without the full key)
    """
    from codestory.models.user import APIKey

    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user.id)
        .order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            prefix=key.key_prefix,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            is_active=key.is_active,
        )
        for key in keys
    ]


@router.post("/me/api-keys", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreateRequest,
    user: CurrentUser,
    db: DBSession,
) -> APIKeyCreatedResponse:
    """Create a new API key.

    The full key is only returned once on creation.
    Store it securely - it cannot be retrieved again.

    Args:
        request: API key creation parameters
        user: Authenticated user
        db: Database session

    Returns:
        Created API key with full key visible
    """
    from codestory.models.user import APIKey

    # Generate a secure random key
    raw_key = f"cs_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:8]

    api_key = APIKey(
        user_id=user.id,
        name=request.name,
        key_prefix=prefix,
        key_hash=APIKey.hash_key(raw_key),
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return APIKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,  # Only time we return the full key!
        prefix=prefix,
        created_at=api_key.created_at,
    )


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete an API key.

    Args:
        key_id: API key ID to delete
        user: Authenticated user
        db: Database session

    Raises:
        NotFoundError: If key doesn't exist or user doesn't own it
    """
    from codestory.models.user import APIKey

    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise NotFoundError("API Key", str(key_id))

    await db.delete(api_key)
    await db.commit()


# =============================================================================
# Admin Endpoints
# =============================================================================


@router.get("", response_model=list[UserProfileResponse])
async def list_users(
    admin: AdminUser,
    db: DBSession,
) -> list[UserProfileResponse]:
    """List all users (admin only).

    Args:
        admin: Authenticated admin user
        db: Database session

    Returns:
        List of all users
    """
    from codestory.models.user import User

    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    return [
        UserProfileResponse(
            id=u.id,
            email=u.email,
            name=u.name,
            is_active=u.is_active,
            is_admin=u.is_admin,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.patch("/{user_id}/status", response_model=MessageResponse)
async def update_user_status(
    user_id: int,
    is_active: bool,
    admin: AdminUser,
    db: DBSession,
) -> MessageResponse:
    """Enable or disable a user (admin only).

    Args:
        user_id: Target user ID
        is_active: New active status
        admin: Authenticated admin user
        db: Database session

    Returns:
        Success message

    Raises:
        NotFoundError: If user doesn't exist
        HTTPException: If trying to modify own account
    """
    from codestory.models.user import User

    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account status",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User", str(user_id))

    user.is_active = is_active
    await db.commit()

    status_text = "enabled" if is_active else "disabled"
    return MessageResponse(message=f"User {user.email} has been {status_text}")
