"""User and API key models.

SQLAlchemy models for user authentication and API key management.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base

if TYPE_CHECKING:
    from .admin import AdminUser
    from .story import Story


class User(Base):
    """User account model.

    Stores user credentials, subscription info, and preferences.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_tier: Mapped[str] = mapped_column(String(50), default="free")
    usage_quota: Mapped[int] = mapped_column(Integer, default=10)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    stories: Mapped[list[Story]] = relationship(
        "Story",
        back_populates="user",
        lazy="selectin",
    )
    api_keys: Mapped[list[APIKey]] = relationship(
        "APIKey",
        back_populates="user",
        lazy="selectin",
    )
    admin_profile: Mapped[AdminUser | None] = relationship(
        "AdminUser",
        back_populates="user",
        uselist=False,
        lazy="selectin",
    )

    @property
    def is_admin(self) -> bool:
        """Check if user has an active admin profile."""
        return self.admin_profile is not None and self.admin_profile.is_active

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"


class APIKey(Base):
    """API key model for programmatic access.

    Stores hashed API keys with permissions and rate limits.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    rate_limit: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name='{self.name}')>"
