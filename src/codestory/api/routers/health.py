"""Health check endpoints."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    sdk_server: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Check application health status.

    Returns:
        Health status including SDK server and database connectivity.
    """
    from codestory.core.config import get_settings
    from codestory.models.database import get_engine

    settings = get_settings()

    # Check SDK server
    sdk_status = "healthy"
    try:
        sdk_server = getattr(request.app.state, "sdk_server", None)
        if sdk_server is None:
            sdk_status = "not initialized"
    except Exception:
        sdk_status = "error"

    # Check database
    db_status = "healthy"
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
    except RuntimeError:
        db_status = "not initialized"
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="healthy" if sdk_status == "healthy" and db_status == "healthy" else "degraded",
        version=settings.app_version,
        sdk_server=sdk_status,
        database=db_status,
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """Kubernetes readiness probe.

    Returns:
        Simple ready status.
    """
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe.

    Returns:
        Simple alive status.
    """
    return {"alive": True}
