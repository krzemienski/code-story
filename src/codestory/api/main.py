"""FastAPI application entry point with Claude Agent SDK integration.

Main application configuration, middleware, and startup lifecycle.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from codestory.core.config import get_settings
from codestory.models.database import init_db, close_db
from codestory.tools import create_codestory_server

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler with SDK initialization.

    Startup:
    - Initialize database connection pool
    - Create Claude Agent SDK MCP server

    Shutdown:
    - Close database connections
    """
    settings = get_settings()

    # Initialize database
    logger.info("Initializing database connection...")
    init_db(
        settings.async_database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    logger.info("Database initialized")

    # Initialize Claude Agent SDK MCP server
    logger.info("Initializing Claude Agent SDK MCP server...")
    app.state.sdk_server = create_codestory_server()
    # SDK server returns dict with 'name' and 'instance' keys
    server_name = app.state.sdk_server.get("name", "codestory")
    logger.info(f"SDK server '{server_name}' initialized")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with Claude Agent SDK.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()
    is_production = settings.environment == "production"

    app = FastAPI(
        title="Code Story API",
        description="Transform code repositories into audio narratives using Claude Agent SDK",
        version=settings.app_version,
        docs_url="/api/docs" if not is_production else None,
        redoc_url="/api/redoc" if not is_production else None,
        openapi_url="/api/openapi.json" if not is_production else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Vite dev server
            "http://localhost:5173",  # Vite default
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ] if not is_production else ["https://codestory.dev"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add compression for responses > 1KB
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Import and register routers
    from codestory.api.routers import auth, auth_supabase, stories, users
    from codestory.api.routers import health, sse

    app.include_router(health.router, prefix="/api", tags=["health"])
    # Supabase Auth (primary) - uses Supabase Auth service
    app.include_router(auth_supabase.router, prefix="/api/auth", tags=["auth"])
    # Legacy auth (kept for migration) - uses custom JWT
    app.include_router(auth.router, prefix="/api/auth/legacy", tags=["auth-legacy"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(stories.router, prefix="/api/stories", tags=["stories"])
    app.include_router(sse.router, prefix="/api/sse", tags=["sse"])

    # Register exception handlers
    from codestory.api.exceptions import register_exception_handlers
    register_exception_handlers(app)

    return app


# Application instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "codestory.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        workers=settings.workers if settings.environment == "production" else 1,
    )
