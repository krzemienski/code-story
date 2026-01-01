"""Rate limiting middleware for API key authenticated requests.

Uses a sliding window algorithm with in-memory storage (Redis recommended for production).
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass
class RateLimitEntry:
    """Track rate limit usage for a single API key."""

    requests: list[float] = field(default_factory=list)
    limit: int = 1000  # Default requests per hour


class RateLimiter:
    """In-memory rate limiter using sliding window algorithm.

    For production, replace with Redis-backed implementation.
    """

    def __init__(self, window_seconds: int = 3600):
        """Initialize rate limiter.

        Args:
            window_seconds: Time window for rate limiting (default: 1 hour)
        """
        self.window_seconds = window_seconds
        self._entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)

    def is_allowed(self, key: str, limit: int | None = None) -> tuple[bool, dict]:
        """Check if request is allowed under rate limit.

        Args:
            key: Unique identifier (API key or user ID)
            limit: Custom rate limit (uses default if None)

        Returns:
            Tuple of (is_allowed, headers_dict with rate limit info)
        """
        now = time.time()
        window_start = now - self.window_seconds

        entry = self._entries[key]
        if limit is not None:
            entry.limit = limit

        # Remove expired requests
        entry.requests = [ts for ts in entry.requests if ts > window_start]

        # Calculate remaining
        remaining = entry.limit - len(entry.requests)
        reset_time = int(window_start + self.window_seconds)

        headers = {
            "X-RateLimit-Limit": str(entry.limit),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(reset_time),
        }

        if remaining <= 0:
            headers["Retry-After"] = str(int(reset_time - now))
            return False, headers

        # Record this request
        entry.requests.append(now)
        headers["X-RateLimit-Remaining"] = str(remaining - 1)
        return True, headers

    def get_usage(self, key: str) -> dict:
        """Get current usage stats for a key."""
        now = time.time()
        window_start = now - self.window_seconds

        entry = self._entries[key]
        entry.requests = [ts for ts in entry.requests if ts > window_start]

        return {
            "requests_used": len(entry.requests),
            "limit": entry.limit,
            "remaining": entry.limit - len(entry.requests),
            "reset_at": int(window_start + self.window_seconds),
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting API key requests."""

    def __init__(self, app: Callable, exempt_paths: list[str] | None = None):
        """Initialize middleware.

        Args:
            app: FastAPI application
            exempt_paths: List of path prefixes to exempt from rate limiting
        """
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/api/docs",
            "/api/redoc",
            "/api/openapi.json",
            "/api/health",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for exempt paths
        path = request.url.path
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return await call_next(request)

        # Check for API key in header
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            # No API key - use bearer token or skip rate limiting
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                # For JWT auth, use a default rate limit per user
                # This would need to extract user ID from token in production
                return await call_next(request)
            # No auth - let the endpoint handle it
            return await call_next(request)

        # For API key requests, apply rate limiting
        # In production, look up the rate limit from database
        # For now, use a default
        is_allowed, headers = rate_limiter.is_allowed(api_key, limit=1000)

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "type": "rate_limit_error",
                    "retry_after": headers.get("Retry-After"),
                },
                headers=headers,
            )

        # Process request and add rate limit headers to response
        response = await call_next(request)
        for key, value in headers.items():
            response.headers[key] = value

        return response


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return rate_limiter
