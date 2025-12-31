"""Async database connection management.

Provides SQLAlchemy async engine and session factory for PostgreSQL.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Module-level engine and session factory
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str, **engine_kwargs: Any) -> None:
    """Initialize database engine and session factory.

    Args:
        database_url: PostgreSQL async connection URL (postgresql+asyncpg://...)
        **engine_kwargs: Additional arguments passed to create_async_engine
    """
    global _engine, _session_factory

    # Set defaults for engine kwargs
    engine_kwargs.setdefault("echo", False)
    engine_kwargs.setdefault("pool_pre_ping", True)

    _engine = create_async_engine(database_url, **engine_kwargs)
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def get_engine() -> AsyncEngine:
    """Get the database engine.

    Returns:
        The async database engine.

    Raises:
        RuntimeError: If database not initialized.
    """
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db first.")
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI - yields async session.

    Yields:
        AsyncSession for database operations.

    Raises:
        RuntimeError: If database not initialized.
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Close database connections.

    Should be called during application shutdown.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
