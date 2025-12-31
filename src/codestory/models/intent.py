"""Story intent model for conversation tracking.

SQLAlchemy model for tracking user intent during story creation.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base

if TYPE_CHECKING:
    from .story import Story


class StoryIntent(Base):
    """Story intent model.

    Tracks conversation history and intent during story creation.
    """

    __tablename__ = "story_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    repository_url: Mapped[str] = mapped_column(String(500))

    # Conversation and intent tracking
    conversation_history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    identified_goals: Mapped[list[str]] = mapped_column(JSONB, default=list)
    generated_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
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
    story: Mapped[Story | None] = relationship(
        "Story",
        back_populates="intent",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<StoryIntent(id={self.id}, repository_url='{self.repository_url}')>"
