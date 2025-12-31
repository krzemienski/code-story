"""Supabase client management for FastAPI.

Provides typed Supabase clients for database operations and authentication.
Uses the anon key for client operations and service role key for admin operations.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from supabase import Client, create_client

from codestory.core.config import get_settings

if TYPE_CHECKING:
    from supabase.lib.client_options import ClientOptions

logger = logging.getLogger(__name__)

# Module-level client instances
_supabase_client: Client | None = None
_supabase_admin: Client | None = None


def get_supabase_client() -> Client:
    """Get the Supabase client using anon key.

    This client respects RLS policies and is safe for user-facing operations.
    JWTs from Supabase Auth should be passed in requests to authenticate users.

    Returns:
        Supabase Client configured with anon key.

    Raises:
        RuntimeError: If Supabase is not configured.
    """
    global _supabase_client

    if _supabase_client is None:
        settings = get_settings()
        if not settings.has_supabase_config():
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY."
            )
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key,
        )
        logger.info("Supabase client initialized with anon key")

    return _supabase_client


def get_supabase_admin() -> Client:
    """Get the Supabase admin client using service role key.

    WARNING: This client bypasses RLS policies. Use only for:
    - Background jobs that need to access all data
    - Admin operations
    - Webhook handlers

    Returns:
        Supabase Client configured with service role key.

    Raises:
        RuntimeError: If Supabase admin is not configured.
    """
    global _supabase_admin

    if _supabase_admin is None:
        settings = get_settings()
        if not settings.has_supabase_admin():
            raise RuntimeError(
                "Supabase admin not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        _supabase_admin = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        logger.info("Supabase admin client initialized with service role key")

    return _supabase_admin


@lru_cache
def get_supabase_url() -> str:
    """Get the Supabase project URL.

    Returns:
        The Supabase URL.

    Raises:
        RuntimeError: If Supabase is not configured.
    """
    settings = get_settings()
    if not settings.supabase_url:
        raise RuntimeError("Supabase URL not configured.")
    return settings.supabase_url


async def verify_supabase_jwt(token: str) -> dict | None:
    """Verify a Supabase JWT and extract user info.

    Args:
        token: The JWT access token from Supabase Auth.

    Returns:
        User data dict if valid, None if invalid.
    """
    try:
        client = get_supabase_client()
        # Get user from token
        response = client.auth.get_user(token)
        if response and response.user:
            return {
                "id": response.user.id,
                "email": response.user.email,
                "role": response.user.role,
                "aud": response.user.aud,
                "created_at": response.user.created_at,
                "app_metadata": response.user.app_metadata,
                "user_metadata": response.user.user_metadata,
            }
    except Exception as e:
        logger.warning(f"JWT verification failed: {e}")
    return None


def close_supabase_clients() -> None:
    """Close Supabase client connections.

    Should be called during application shutdown.
    """
    global _supabase_client, _supabase_admin

    # Supabase Python client doesn't require explicit cleanup,
    # but we reset the module-level instances
    _supabase_client = None
    _supabase_admin = None
    logger.info("Supabase clients closed")


# FastAPI dependency helpers
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """FastAPI dependency to get the current authenticated user.

    Args:
        credentials: Bearer token from Authorization header.

    Returns:
        User data dict from Supabase.

    Raises:
        HTTPException: If not authenticated or token invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await verify_supabase_jwt(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """FastAPI dependency to optionally get the current user.

    Returns None if not authenticated instead of raising an exception.

    Args:
        credentials: Bearer token from Authorization header.

    Returns:
        User data dict or None if not authenticated.
    """
    if not credentials:
        return None

    return await verify_supabase_jwt(credentials.credentials)


async def get_current_user_id(
    user: dict = Depends(get_current_user),
) -> str:
    """FastAPI dependency to get just the current user's ID.

    Args:
        user: User dict from get_current_user.

    Returns:
        The user's UUID as string.
    """
    return user["id"]
