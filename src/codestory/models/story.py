"""Story and chapter models.

SQLAlchemy models for stories, repositories, and chapters.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base

if TYPE_CHECKING:
    from .intent import StoryIntent
    from .user import User
    from .team import Team


class StoryStatus(str, Enum):
    """Status of story generation pipeline."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"


class NarrativeStyle(str, Enum):
    """Available narrative styles for stories."""

    TECHNICAL = "technical"
    STORYTELLING = "storytelling"
    EDUCATIONAL = "educational"
    CASUAL = "casual"
    EXECUTIVE = "executive"


class Repository(Base):
    """Repository model for caching analysis.

    Stores repository metadata and cached analysis results.
    """

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str] = mapped_column(String(255))
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_cache: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    stories: Mapped[list[Story]] = relationship(
        "Story",
        back_populates="repository",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Repository(id={self.id}, url='{self.url}')>"


class Story(Base):
    """Story model - the main audio narrative entity.

    Represents a complete audio story generated from a repository.
    """

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
    )
    intent_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_intents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Team ownership (optional - None means personal story)
    team_id: Mapped[str | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[StoryStatus] = mapped_column(
        SQLEnum(StoryStatus, name="story_status"),
        default=StoryStatus.PENDING,
        index=True,
    )
    narrative_style: Mapped[NarrativeStyle] = mapped_column(
        SQLEnum(NarrativeStyle, name="narrative_style"),
        default=NarrativeStyle.EDUCATIONAL,
    )
    focus_areas: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audio output
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="stories")
    repository: Mapped[Repository] = relationship("Repository", back_populates="stories")
    intent: Mapped[StoryIntent | None] = relationship(
        "StoryIntent",
        back_populates="story",
    )
    chapters: Mapped[list[StoryChapter]] = relationship(
        "StoryChapter",
        back_populates="story",
        order_by="StoryChapter.order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    team: Mapped[Team | None] = relationship(
        "Team",
        back_populates="stories",
        foreign_keys=[team_id],
    )

    def __repr__(self) -> str:
        return f"<Story(id={self.id}, title='{self.title}', status={self.status})>"


class StoryChapter(Base):
    """Story chapter model.

    Represents a single chapter/segment of an audio story.
    """

    __tablename__ = "story_chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"),
        index=True,
    )

    order: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(255))
    script: Mapped[str] = mapped_column(Text)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_time: Mapped[float] = mapped_column(Float, default=0.0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    story: Mapped[Story] = relationship("Story", back_populates="chapters")

    def __repr__(self) -> str:
        return f"<StoryChapter(id={self.id}, order={self.order}, title='{self.title}')>"
