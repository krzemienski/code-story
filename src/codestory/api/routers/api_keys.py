"""API Keys management endpoints for Phase 10."""
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import Client

from ..deps import get_current_user, get_supabase

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class APIKeyCreate(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(..., min_length=1, max_length=100, description="Name for the API key")
    permissions: list[str] = Field(
        default=["read"],
        description="Permissions for this key (read, write, admin)",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until expiration (null = never)",
    )
    rate_limit: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Requests per hour limit",
    )


class APIKeyResponse(BaseModel):
    """Response body for API key operations."""

    id: int
    name: str
    permissions: list[str]
    rate_limit: int
    is_active: bool
    created_at: str
    expires_at: str | None
    last_used_at: str | None


class APIKeyCreated(APIKeyResponse):
    """Response when creating a new API key (includes the actual key)."""

    key: str = Field(..., description="The API key (only shown once)")


class APIKeyList(BaseModel):
    """Response body for listing API keys."""

    keys: list[APIKeyResponse]
    total: int


@router.post("", response_model=APIKeyCreated, status_code=201)
async def create_api_key(
    body: APIKeyCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
) -> APIKeyCreated:
    """Create a new API key for the authenticated user.

    The returned key is only shown once and cannot be retrieved later.
    Store it securely.
    """
    from ...core.security import create_api_key_hash, generate_api_key

    # Generate a new API key
    api_key = generate_api_key()
    key_hash = create_api_key_hash(api_key)

    # Calculate expiration
    expires_at = None
    if body.expires_in_days:
        expires_at = (datetime.now(UTC) + timedelta(days=body.expires_in_days)).isoformat()

    # Create in database
    result = supabase.table("api_keys").insert(
        {
            "user_id": current_user["id"],
            "name": body.name,
            "key_hash": key_hash,
            "permissions": body.permissions,
            "rate_limit": body.rate_limit,
            "expires_at": expires_at,
            "is_active": True,
        }
    ).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create API key")

    created = result.data[0]
    return APIKeyCreated(
        id=created["id"],
        name=created["name"],
        permissions=created["permissions"],
        rate_limit=created["rate_limit"],
        is_active=created["is_active"],
        created_at=created["created_at"],
        expires_at=created["expires_at"],
        last_used_at=created["last_used_at"],
        key=api_key,
    )


@router.get("", response_model=APIKeyList)
async def list_api_keys(
    current_user: Annotated[dict, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
    active_only: bool = Query(default=True, description="Only return active keys"),
) -> APIKeyList:
    """List all API keys for the authenticated user."""
    query = supabase.table("api_keys").select("*").eq("user_id", current_user["id"])

    if active_only:
        query = query.eq("is_active", True)

    result = query.order("created_at", desc=True).execute()

    keys = [
        APIKeyResponse(
            id=k["id"],
            name=k["name"],
            permissions=k["permissions"],
            rate_limit=k["rate_limit"],
            is_active=k["is_active"],
            created_at=k["created_at"],
            expires_at=k["expires_at"],
            last_used_at=k["last_used_at"],
        )
        for k in result.data
    ]

    return APIKeyList(keys=keys, total=len(keys))


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
) -> APIKeyResponse:
    """Get details of a specific API key."""
    result = (
        supabase.table("api_keys")
        .select("*")
        .eq("id", key_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="API key not found")

    k = result.data
    return APIKeyResponse(
        id=k["id"],
        name=k["name"],
        permissions=k["permissions"],
        rate_limit=k["rate_limit"],
        is_active=k["is_active"],
        created_at=k["created_at"],
        expires_at=k["expires_at"],
        last_used_at=k["last_used_at"],
    )


@router.patch("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
    name: str | None = None,
    is_active: bool | None = None,
    rate_limit: int | None = None,
) -> APIKeyResponse:
    """Update an API key (name, active status, or rate limit)."""
    # First verify ownership
    check = (
        supabase.table("api_keys")
        .select("id")
        .eq("id", key_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not check.data:
        raise HTTPException(status_code=404, detail="API key not found")

    # Build update payload
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if is_active is not None:
        update_data["is_active"] = is_active
    if rate_limit is not None:
        if rate_limit < 10 or rate_limit > 10000:
            raise HTTPException(status_code=400, detail="Rate limit must be between 10 and 10000")
        update_data["rate_limit"] = rate_limit

    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")

    result = (
        supabase.table("api_keys")
        .update(update_data)
        .eq("id", key_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update API key")

    k = result.data[0]
    return APIKeyResponse(
        id=k["id"],
        name=k["name"],
        permissions=k["permissions"],
        rate_limit=k["rate_limit"],
        is_active=k["is_active"],
        created_at=k["created_at"],
        expires_at=k["expires_at"],
        last_used_at=k["last_used_at"],
    )


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
) -> None:
    """Delete an API key (permanently)."""
    # Verify ownership and delete
    result = (
        supabase.table("api_keys")
        .delete()
        .eq("id", key_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="API key not found")


@router.post("/{key_id}/regenerate", response_model=APIKeyCreated)
async def regenerate_api_key(
    key_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
) -> APIKeyCreated:
    """Regenerate an API key (invalidates the old key)."""
    from ...core.security import create_api_key_hash, generate_api_key

    # Verify ownership
    check = (
        supabase.table("api_keys")
        .select("*")
        .eq("id", key_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )

    if not check.data:
        raise HTTPException(status_code=404, detail="API key not found")

    # Generate new key
    api_key = generate_api_key()
    key_hash = create_api_key_hash(api_key)

    # Update in database
    result = (
        supabase.table("api_keys")
        .update({"key_hash": key_hash})
        .eq("id", key_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to regenerate API key")

    k = result.data[0]
    return APIKeyCreated(
        id=k["id"],
        name=k["name"],
        permissions=k["permissions"],
        rate_limit=k["rate_limit"],
        is_active=k["is_active"],
        created_at=k["created_at"],
        expires_at=k["expires_at"],
        last_used_at=k["last_used_at"],
        key=api_key,
    )
