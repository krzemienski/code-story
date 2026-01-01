"""Authentication router for login and registration.

Endpoints for user authentication, registration, and token management.
Uses JWT tokens with access/refresh token pattern.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from codestory.api.deps import CurrentUser, DBSession
from codestory.core.config import get_settings
from codestory.models.user import User

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# =============================================================================
# Schemas
# =============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    # Note: 'name' not stored in User model - kept for API compatibility


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class UserResponse(BaseModel):
    """User info response."""

    id: int
    email: str
    is_active: bool
    is_superuser: bool
    subscription_tier: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# =============================================================================
# Token Helpers
# =============================================================================


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    settings = get_settings()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(to_encode, settings.effective_jwt_secret, algorithm=settings.effective_jwt_algorithm)


def create_refresh_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create JWT refresh token."""
    settings = get_settings()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=settings.refresh_token_expire_days))
    to_encode = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(to_encode, settings.effective_jwt_secret, algorithm=settings.effective_jwt_algorithm)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    return pwd_context.hash(password)


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: DBSession,
) -> TokenResponse:
    """Register a new user.

    Args:
        request: Registration data
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If email already exists
    """
    settings = get_settings()

    # Check if email exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: DBSession,
) -> TokenResponse:
    """Login with email and password.

    Args:
        request: Login credentials
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    settings = get_settings()

    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    # Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: DBSession,
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        request: Refresh token
        db: Database session

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            request.refresh_token,
            settings.effective_jwt_secret,
            algorithms=[settings.effective_jwt_algorithm],
        )
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Generate new tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: CurrentUser,
) -> UserResponse:
    """Get current authenticated user info.

    Args:
        user: Current user from token

    Returns:
        User information
    """
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    user: CurrentUser,
) -> MessageResponse:
    """Logout current user.

    Note: Since we use stateless JWTs, this is mainly for client-side
    token invalidation. For full invalidation, use a token blacklist.

    Args:
        user: Current user

    Returns:
        Logout confirmation
    """
    # In a production system, you would add the token to a blacklist here
    # For now, we just return success and expect client to discard tokens
    return MessageResponse(message="Successfully logged out")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    current_password: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8, max_length=128)],
    user: CurrentUser,
    db: DBSession,
) -> MessageResponse:
    """Change current user's password.

    Args:
        current_password: Current password for verification
        new_password: New password
        user: Current user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If current password is wrong
    """
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.password_hash = hash_password(new_password)
    await db.commit()

    return MessageResponse(message="Password changed successfully")
