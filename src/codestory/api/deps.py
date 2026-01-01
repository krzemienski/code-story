"""FastAPI dependencies for dependency injection.

Provides reusable dependencies for authentication, database sessions,
and other common patterns across endpoints.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.core.config import get_settings
from codestory.models.database import get_session
from codestory.models.user import User

# Security scheme
security = HTTPBearer(auto_error=False)

# Settings dependency
Settings = Annotated[type, Depends(get_settings)]

# Database session dependency
DBSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict:
    """Get the current authenticated user from Supabase JWT token.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User dict from Supabase

    Raises:
        HTTPException: If authentication fails
    """
    from codestory.core.supabase import verify_supabase_jwt

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user_data = await verify_supabase_jwt(token)

    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_data


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict | None:
    """Get current user if authenticated, None otherwise.

    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def require_admin_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the current user to be an admin.

    Args:
        user: Current authenticated user

    Returns:
        Admin user

    Raises:
        HTTPException: If user is not an admin
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    db: DBSession = None,
) -> str | None:
    """Get and validate API key from header.

    Args:
        x_api_key: API key from X-API-Key header
        db: Database session

    Returns:
        Validated API key or None
    """
    if x_api_key is None:
        return None

    # Validate API key exists in database
    from codestory.models.user import APIKey
    from sqlalchemy import select

    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == APIKey.hash_key(x_api_key),
            APIKey.is_active == True,
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Update last used timestamp
    from datetime import datetime

    api_key.last_used_at = datetime.utcnow()
    await db.commit()

    return x_api_key


# Type aliases for dependency injection (legacy SQLAlchemy-based)
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
AdminUser = Annotated[User, Depends(require_admin_user)]
ValidAPIKey = Annotated[str | None, Depends(get_api_key)]

# Supabase-based dependencies (preferred for new code)
from codestory.core.supabase import (
    get_current_user as get_supabase_user,
    get_current_user_optional as get_supabase_user_optional,
    get_current_user_id as get_supabase_user_id,
    get_supabase_admin,
)
from supabase import Client as SupabaseClient


def get_supabase() -> SupabaseClient:
    """Get the Supabase admin client for database operations.

    Returns:
        Configured Supabase client with service role key
    """
    return get_supabase_admin()


# Supabase client dependency
Supabase = Annotated[SupabaseClient, Depends(get_supabase)]

# Supabase user dict (id, email, role, metadata)
SupabaseUser = Annotated[dict, Depends(get_supabase_user)]
SupabaseUserOptional = Annotated[dict | None, Depends(get_supabase_user_optional)]
SupabaseUserId = Annotated[str, Depends(get_supabase_user_id)]
