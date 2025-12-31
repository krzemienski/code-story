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
    db: DBSession,
) -> User:
    """Get the current authenticated user from JWT token.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        Authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    settings = get_settings()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=[settings.effective_jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type", "access")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: DBSession,
) -> User | None:
    """Get current user if authenticated, None otherwise.

    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials, db)
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
)

# Supabase user dict (id, email, role, metadata)
SupabaseUser = Annotated[dict, Depends(get_supabase_user)]
SupabaseUserOptional = Annotated[dict | None, Depends(get_supabase_user_optional)]
SupabaseUserId = Annotated[str, Depends(get_supabase_user_id)]
