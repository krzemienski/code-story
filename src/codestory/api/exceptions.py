"""Exception handlers for Code Story API."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found."""

    def __init__(self, resource: str, resource_id: str | None = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} '{resource_id}' not found"
        super().__init__(message, status_code=404)


class UnauthorizedError(APIError):
    """Authentication required."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class ForbiddenError(APIError):
    """Access denied."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403)


class ConflictError(APIError):
    """Resource conflict."""

    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class RateLimitError(APIError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            "Rate limit exceeded",
            status_code=429,
            details={"retry_after": retry_after},
        )


class SDKError(APIError):
    """Claude Agent SDK error."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            f"SDK error: {message}",
            status_code=500,
            details=details or {},
        )


class PipelineError(APIError):
    """Story generation pipeline error."""

    def __init__(self, stage: str, message: str, details: dict | None = None):
        super().__init__(
            f"Pipeline error in {stage}: {message}",
            status_code=500,
            details={"stage": stage, **(details or {})},
        )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "details": exc.details,
        },
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "details": exc.errors(),
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception("Unexpected error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": {},
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
