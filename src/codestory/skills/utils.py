"""Shared utilities for Code Story skills.

Provides common functionality used across all skill modules:
- HTTP client with retry logic and rate limit handling
- Custom exceptions for skill errors
- Data parsing and validation utilities
- Text processing helpers
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, TypeVar

import httpx

T = TypeVar("T")


# =============================================================================
# Exceptions
# =============================================================================


class SkillError(Exception):
    """Base exception for skill errors.

    Provides structured error information for debugging and user feedback.

    Args:
        message: Human-readable error message
        code: Machine-readable error code for programmatic handling
        details: Additional context about the error
    """

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class RateLimitError(SkillError):
    """Raised when an API rate limit is hit.

    Contains retry_after information when available.
    """

    pass


class APIError(SkillError):
    """Raised when an external API returns an error.

    Contains HTTP status code and response body in details.
    """

    pass


class ValidationError(SkillError):
    """Raised when input validation fails.

    Contains field-level validation errors in details.
    """

    pass


# =============================================================================
# HTTP Client
# =============================================================================


class HTTPClient:
    """Async HTTP client with retry and rate limiting support.

    Provides a robust HTTP client for skill integrations with:
    - Automatic retry on transient failures
    - Rate limit detection and backoff
    - Configurable timeouts and headers
    - Connection pooling via httpx

    Args:
        base_url: Base URL for all requests (optional)
        headers: Default headers for all requests
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        retry_delay: Base delay between retries (exponential backoff)

    Example:
        ```python
        client = HTTPClient(
            base_url="https://api.github.com",
            headers={"Authorization": "Bearer token"},
        )
        async with client:
            data = await client.get("/repos/owner/repo")
        ```
    """

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HTTPClient":
        """Support async context manager."""
        await self._get_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close client on context exit."""
        await self.close()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.default_headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release connections."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: URL path (will be joined with base_url)
            **kwargs: Additional arguments passed to httpx.request

        Returns:
            Parsed JSON response as dict, or {"content": text} for non-JSON

        Raises:
            APIError: If the request fails after retries
            RateLimitError: If rate limited and retries exhausted
        """
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await client.request(method, path, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get("Retry-After", self.retry_delay * 2)
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        f"Rate limited on {path}",
                        code="RATE_LIMITED",
                        details={"retry_after": retry_after},
                    )

                # Handle errors
                if response.status_code >= 400:
                    error_body: Any = response.text
                    try:
                        error_body = response.json()
                    except json.JSONDecodeError:
                        pass

                    raise APIError(
                        f"API error {response.status_code} on {path}",
                        code=f"HTTP_{response.status_code}",
                        details={"response": error_body, "status_code": response.status_code},
                    )

                # Parse response
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("application/json"):
                    return response.json()  # type: ignore[no-any-return]
                return {"content": response.text}

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

        raise APIError(
            f"Request failed after {self.max_retries} retries: {last_error}",
            code="CONNECTION_FAILED",
        )

    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make a GET request."""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make a POST request."""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make a PUT request."""
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make a DELETE request."""
        return await self.request("DELETE", path, **kwargs)


# =============================================================================
# Data Parsing Utilities
# =============================================================================


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub URL to extract owner and repo.

    Supports multiple URL formats:
    - https://github.com/owner/repo
    - git@github.com:owner/repo.git
    - owner/repo (shorthand)

    Args:
        url: GitHub repository URL or shorthand

    Returns:
        Tuple of (owner, repo_name)

    Raises:
        ValidationError: If URL is not a valid GitHub URL
    """
    patterns = [
        r"github\.com[:/]([^/]+)/([^/\.]+)",  # HTTPS or SSH
        r"^([^/]+)/([^/]+)$",  # owner/repo format
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            owner, repo = match.groups()
            repo = repo.rstrip(".git")
            return owner, repo

    raise ValidationError(
        f"Invalid GitHub URL: {url}",
        code="INVALID_GITHUB_URL",
        details={"url": url},
    )


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to a maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: String to append when truncating

    Returns:
        Truncated text with suffix if truncated
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def safe_json_parse(text: str, default: T | None = None) -> dict[str, Any] | list[Any] | T | None:
    """Safely parse JSON text with fallback.

    Args:
        text: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        return default


def format_timestamp(dt: datetime | None = None) -> str:
    """Format a datetime as ISO 8601 string in UTC.

    Args:
        dt: Datetime to format (defaults to now)

    Returns:
        ISO 8601 formatted string with Z suffix
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        # Assume UTC for naive datetimes
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================================================================
# Text Processing Utilities
# =============================================================================


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in text.

    Uses a simple heuristic of ~4 characters per token.
    This is an approximation; actual token counts vary by model.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    return len(text) // 4


def chunk_text(text: str, max_tokens: int = 4000) -> list[str]:
    """Split text into chunks that fit within token limits.

    Attempts to split on paragraph boundaries for cleaner chunks.
    Falls back to character-based splitting for long paragraphs.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk

    Returns:
        List of text chunks
    """
    max_chars = max_tokens * 4  # Approximate 4 chars per token
    chunks: list[str] = []

    # Try to split on paragraph boundaries
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chars:
            if current_chunk:
                current_chunk += "\n\n"
            current_chunk += para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If single paragraph exceeds limit, force split
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars):
                    chunks.append(para[i : i + max_chars])
                current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def chunk_text_for_synthesis(
    text: str,
    max_chars: int = 5000,
    overlap_sentences: int = 1,
) -> list[str]:
    """Split text into chunks suitable for voice synthesis.

    Preserves sentence boundaries and optionally overlaps
    sentences for continuity in audio synthesis.

    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk
        overlap_sentences: Number of sentences to overlap between chunks

    Returns:
        List of text chunks with sentence boundaries preserved
    """
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_length + sentence_len > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep overlap for continuity
            if overlap_sentences:
                current_chunk = current_chunk[-overlap_sentences:]
                current_length = sum(len(s) for s in current_chunk)
            else:
                current_chunk = []
                current_length = 0

        current_chunk.append(sentence)
        current_length += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# =============================================================================
# Decorator Utilities
# =============================================================================


def handle_skill_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle and wrap skill errors consistently.

    Wraps unexpected exceptions in SkillError for consistent error handling.
    SkillError subclasses are re-raised as-is.

    Usage:
        ```python
        @handle_skill_errors
        async def my_skill_method(self, ...):
            ...
        ```
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except SkillError:
            raise  # Re-raise skill errors as-is
        except Exception as e:
            raise SkillError(
                f"Unexpected error in {func.__name__}: {e!s}",
                code="UNEXPECTED_ERROR",
                details={"original_error": str(e), "error_type": type(e).__name__},
            ) from e

    return wrapper
