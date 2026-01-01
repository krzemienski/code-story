"""Collaboration models for team story sharing.

Provides models for:
- StoryCollaborator: Shared access to stories within teams
- StoryComment: Comments and feedback on stories
- StoryActivity: Activity log for collaboration tracking
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, ForeignKey,
    Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped

from codestory.models.database import Base

if TYPE_CHECKING:
    from codestory.models.user import User
    from codestory.models.story import Story


class CollaboratorRole(str, Enum):
    """Roles for story collaborators."""
    OWNER = "owner"       # Full control, can transfer ownership
    EDITOR = "editor"     # Can edit story, add comments
    COMMENTER = "commenter"  # Can add comments only
    VIEWER = "viewer"     # View-only access


class ActivityType(str, Enum):
    """Types of collaboration activities."""
    # Story lifecycle
    STORY_CREATED = "story_created"
    STORY_UPDATED = "story_updated"
    STORY_COMPLETED = "story_completed"
    STORY_FAILED = "story_failed"
    STORY_DELETED = "story_deleted"
    STORY_SHARED = "story_shared"
    STORY_UNSHARED = "story_unshared"

    # Collaboration
    COLLABORATOR_ADDED = "collaborator_added"
    COLLABORATOR_REMOVED = "collaborator_removed"
    COLLABORATOR_ROLE_CHANGED = "collaborator_role_changed"

    # Comments
    COMMENT_ADDED = "comment_added"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    COMMENT_RESOLVED = "comment_resolved"

    # Team
    TRANSFERRED_TO_TEAM = "transferred_to_team"
    REMOVED_FROM_TEAM = "removed_from_team"


class StoryCollaborator(Base):
    """Junction table for story collaborators.

    Allows sharing stories with specific users at different permission levels.
    """
    __tablename__ = "story_collaborators"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(
        Integer,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Role
    role = Column(
        SQLEnum(CollaboratorRole),
        default=CollaboratorRole.VIEWER,
        nullable=False,
    )

    # Invitation tracking
    invited_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    invited_at = Column(DateTime, default=datetime.utcnow)

    # Status
    accepted = Column(Boolean, default=True)  # True if user accepted invite
    accepted_at = Column(DateTime, nullable=True)

    # Activity
    last_accessed_at = Column(DateTime, nullable=True)

    # Relationships
    story: Mapped["Story"] = relationship(
        "Story",
        backref="collaborators",
        foreign_keys=[story_id],
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    invited_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[invited_by_id],
    )

    def can_edit(self) -> bool:
        """Check if collaborator can edit the story."""
        return self.role in (CollaboratorRole.OWNER, CollaboratorRole.EDITOR)

    def can_comment(self) -> bool:
        """Check if collaborator can add comments."""
        return self.role in (
            CollaboratorRole.OWNER,
            CollaboratorRole.EDITOR,
            CollaboratorRole.COMMENTER,
        )


class CommentStatus(str, Enum):
    """Status of story comments."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    DELETED = "deleted"


class StoryComment(Base):
    """Comments on stories for collaboration feedback.

    Supports threaded comments with chapter-specific or time-based anchoring.
    """
    __tablename__ = "story_comments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(
        Integer,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Comment content
    content = Column(Text, nullable=False)

    # Threading (optional - for replies)
    parent_id = Column(
        String(36),
        ForeignKey("story_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Anchoring (optional - for specific locations)
    chapter_id = Column(
        Integer,
        ForeignKey("story_chapters.id", ondelete="CASCADE"),
        nullable=True,
    )
    timestamp_seconds = Column(Integer, nullable=True)  # Audio timestamp

    # Status
    status = Column(
        SQLEnum(CommentStatus),
        default=CommentStatus.ACTIVE,
        nullable=False,
    )
    resolved_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    story: Mapped["Story"] = relationship(
        "Story",
        backref="comments",
        foreign_keys=[story_id],
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    parent: Mapped[Optional["StoryComment"]] = relationship(
        "StoryComment",
        remote_side="StoryComment.id",
        backref="replies",
        foreign_keys=[parent_id],
    )
    resolved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[resolved_by_id],
    )

    @property
    def is_reply(self) -> bool:
        """Check if this is a reply to another comment."""
        return self.parent_id is not None

    @property
    def reply_count(self) -> int:
        """Count of replies to this comment."""
        return len([r for r in self.replies if r.status == CommentStatus.ACTIVE])


class StoryActivity(Base):
    """Activity log for collaboration tracking.

    Records all significant actions on a story for audit and notification purposes.
    """
    __tablename__ = "story_activities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(
        Integer,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Can be null for system actions
    )

    # Activity details
    activity_type = Column(SQLEnum(ActivityType), nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Additional context (JSON-serializable data)
    activity_metadata = Column(Text, nullable=True)  # JSON string for extra data

    # Target user (for collaborator activities)
    target_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    story: Mapped["Story"] = relationship(
        "Story",
        backref="activities",
        foreign_keys=[story_id],
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    target_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[target_user_id],
    )


__all__ = [
    "CollaboratorRole",
    "ActivityType",
    "CommentStatus",
    "StoryCollaborator",
    "StoryComment",
    "StoryActivity",
]
