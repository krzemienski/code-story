"""Supabase Authentication router.

Handles authentication using Supabase Auth service instead of custom JWT.
This replaces the legacy auth.py router with Supabase-native authentication.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from codestory.core.config import get_settings
from codestory.core.supabase import (
    get_current_user,
    get_current_user_id,
    get_supabase_client,
)
from fastapi import Depends

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Supabase token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: int | None = None
    user: dict | None = None


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class UserResponse(BaseModel):
    """User info response from Supabase."""

    id: str
    email: str
    name: str = ""
    is_active: bool = True
    is_superuser: bool = False
    subscription_tier: str = "free"
    created_at: datetime | None = None


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""

    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    """Password update request."""

    new_password: str = Field(..., min_length=8, max_length=128)


class OAuthRequest(BaseModel):
    """OAuth provider login request."""

    provider: str = Field(..., pattern="^(github|google|apple|discord)$")
    redirect_to: str | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest) -> TokenResponse:
    """Register a new user with Supabase Auth.

    Args:
        request: Registration data with email, password, and optional name.

    Returns:
        Access and refresh tokens from Supabase.

    Raises:
        HTTPException: If registration fails.
    """
    client = get_supabase_client()

    try:
        # Sign up with Supabase Auth
        response = client.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "name": request.name,
                }
            }
        })

        if response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed. Email may already be registered.",
            )

        # Check if email confirmation is required
        if response.session is None:
            return TokenResponse(
                access_token="",
                refresh_token="",
                expires_in=0,
                user={"id": response.user.id, "email": response.user.email},
            )

        return TokenResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in or 3600,
            expires_at=response.session.expires_at,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "name": request.name,
            },
        )

    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {error_msg}",
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Login with email and password via Supabase Auth.

    Args:
        request: Login credentials.

    Returns:
        Access and refresh tokens from Supabase.

    Raises:
        HTTPException: If credentials are invalid.
    """
    client = get_supabase_client()

    try:
        response = client.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })

        if response.session is None or response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in or 3600,
            expires_at=response.session.expires_at,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name", ""),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        request: Refresh token.

    Returns:
        New access and refresh tokens.

    Raises:
        HTTPException: If refresh token is invalid.
    """
    client = get_supabase_client()

    try:
        response = client.auth.refresh_session(request.refresh_token)

        if response.session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user_data = None
        if response.user:
            user_data = {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name", ""),
            }

        return TokenResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in or 3600,
            expires_at=response.session.expires_at,
            user=user_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to refresh token",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: dict = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user info from Supabase.

    Args:
        user: Current user from token.

    Returns:
        User information.
    """
    # Fetch profile from Supabase profiles table
    client = get_supabase_client()

    try:
        response = client.table("profiles").select("*").eq("id", user["id"]).single().execute()
        profile = response.data if response.data else {}
    except Exception:
        profile = {}

    return UserResponse(
        id=user["id"],
        email=user.get("email", ""),
        name=user.get("user_metadata", {}).get("name", profile.get("name", "")),
        is_active=True,
        is_superuser=profile.get("is_superuser", False),
        subscription_tier=profile.get("subscription_tier", "free"),
        created_at=user.get("created_at"),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Logout current user from Supabase.

    Args:
        user: Current user.

    Returns:
        Logout confirmation.
    """
    client = get_supabase_client()

    try:
        client.auth.sign_out()
    except Exception:
        pass  # Sign out is best-effort

    return MessageResponse(message="Successfully logged out")


@router.post("/password/reset", response_model=MessageResponse)
async def request_password_reset(request: PasswordResetRequest) -> MessageResponse:
    """Request password reset email.

    Args:
        request: Email to send reset link to.

    Returns:
        Confirmation message.
    """
    settings = get_settings()
    client = get_supabase_client()

    try:
        # Use a configurable redirect URL for the reset link
        redirect_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/verify"
        client.auth.reset_password_for_email(
            request.email,
            {"redirect_to": redirect_url},
        )
    except Exception as e:
        # Don't reveal if email exists or not for security
        pass

    return MessageResponse(
        message="If an account exists with this email, a password reset link has been sent."
    )


@router.post("/password/update", response_model=MessageResponse)
async def update_password(
    request: PasswordUpdateRequest,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Update password for authenticated user.

    Args:
        request: New password.
        user: Current user.

    Returns:
        Success message.
    """
    client = get_supabase_client()

    try:
        client.auth.update_user({"password": request.new_password})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update password: {e}",
        )

    return MessageResponse(message="Password updated successfully")


@router.get("/oauth/{provider}")
async def get_oauth_url(
    provider: str,
    redirect_to: str | None = None,
) -> dict[str, str]:
    """Get OAuth authorization URL for a provider.

    Args:
        provider: OAuth provider (github, google, apple, discord).
        redirect_to: URL to redirect after auth.

    Returns:
        Authorization URL.
    """
    valid_providers = {"github", "google", "apple", "discord"}
    if provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}",
        )

    client = get_supabase_client()

    try:
        options = {}
        if redirect_to:
            options["redirect_to"] = redirect_to

        response = client.auth.sign_in_with_oauth({
            "provider": provider,
            "options": options,
        })

        return {"url": response.url}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate OAuth URL: {e}",
        )
