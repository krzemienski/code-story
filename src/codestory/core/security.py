"""Security utilities for authentication and authorization."""
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from .config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    # Bcrypt requires bytes and has 72-byte limit
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Previously hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = plain_password.encode("utf-8")[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        subject: The subject of the token (typically user ID)
        expires_delta: Optional custom expiration time
        extra_claims: Additional claims to include in the token

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    encoded: str = jwt.encode(
        to_encode,
        settings.effective_jwt_secret,
        algorithm=settings.effective_jwt_algorithm,
    )
    return encoded


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=[settings.effective_jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


def create_refresh_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token.

    Args:
        subject: The subject of the token (typically user ID)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }

    encoded: str = jwt.encode(
        to_encode,
        settings.effective_jwt_secret,
        algorithm=settings.effective_jwt_algorithm,
    )
    return encoded


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT refresh token.

    Args:
        token: The JWT refresh token string

    Returns:
        Decoded token payload or None if invalid/not a refresh token
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=[settings.effective_jwt_algorithm],
        )
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


def create_api_key_hash(api_key: str) -> str:
    """Create a hash of an API key for storage.

    Uses the same bcrypt hashing as passwords for security.

    Args:
        api_key: Plain text API key

    Returns:
        Hashed API key string
    """
    return hash_password(api_key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its stored hash.

    Args:
        plain_key: Plain text API key to verify
        hashed_key: Previously hashed API key

    Returns:
        True if API key matches, False otherwise
    """
    return verify_password(plain_key, hashed_key)


def generate_api_key() -> str:
    """Generate a new random API key.

    Returns:
        A secure random API key string with 'cs_' prefix (32 bytes, hex encoded)
    """
    return f"cs_{secrets.token_hex(32)}"


# Alias for backward compatibility with common naming convention
get_password_hash = hash_password
