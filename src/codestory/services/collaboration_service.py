"""Collaboration service for story sharing and comments.

Provides business logic for:
- Story collaborator management (add, remove, update roles)
- Comments and threaded replies
- Activity logging for audit trail
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from codestory.models.story import Story
from codestory.models.collaboration import (
    CollaboratorRole,
    ActivityType,
    CommentStatus,
    StoryCollaborator,
    StoryComment,
    StoryActivity,
)


class CollaborationError(Exception):
    """Base exception for collaboration errors."""
    pass


class StoryNotFoundError(CollaborationError):
    """Story not found."""
    pass


class CollaboratorNotFoundError(CollaborationError):
    """Collaborator not found."""
    pass


class CommentNotFoundError(CollaborationError):
    """Comment not found."""
    pass


class PermissionDeniedError(CollaborationError):
    """User lacks required permission."""
    pass


class CollaborationService:
    """Service for managing story collaboration."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Story Access
    # =========================================================================

    async def get_story_with_access_check(
        self,
        story_id: int,
        user_id: str,
        required_role: Optional[CollaboratorRole] = None,
    ) -> Story:
        """Get a story and verify user has access.

        Args:
            story_id: Story ID
            user_id: User requesting access
            required_role: Minimum role required (None = any access)

        Returns:
            Story if user has access

        Raises:
            StoryNotFoundError: If story doesn't exist
            PermissionDeniedError: If user lacks access
        """
        result = await self.db.execute(
            select(Story)
            .options(selectinload(Story.collaborators))
            .where(Story.id == story_id)
        )
        story = result.scalar_one_or_none()

        if not story:
            raise StoryNotFoundError(f"Story {story_id} not found")

        # Check if user is owner
        if story.user_id == user_id:
            return story

        # Check if user is collaborator
        collaborator = next(
            (c for c in story.collaborators if c.user_id == user_id and c.accepted),
            None,
        )

        if not collaborator:
            raise PermissionDeniedError("You don't have access to this story")

        # Check role if required
        if required_role:
            role_hierarchy = {
                CollaboratorRole.VIEWER: 0,
                CollaboratorRole.COMMENTER: 1,
                CollaboratorRole.EDITOR: 2,
                CollaboratorRole.OWNER: 3,
            }
            if role_hierarchy.get(collaborator.role, 0) < role_hierarchy.get(required_role, 0):
                raise PermissionDeniedError(
                    f"Requires {required_role.value} role or higher"
                )

        return story

    async def get_accessible_stories(
        self,
        user_id: str,
        team_id: Optional[str] = None,
        include_owned: bool = True,
        include_shared: bool = True,
    ) -> list[Story]:
        """Get all stories accessible to a user.

        Args:
            user_id: User ID
            team_id: Filter by team (optional)
            include_owned: Include stories owned by user
            include_shared: Include stories shared with user

        Returns:
            List of accessible stories
        """
        conditions = []

        if include_owned:
            conditions.append(Story.user_id == user_id)

        if include_shared:
            # Stories shared via collaborator
            shared_query = (
                select(StoryCollaborator.story_id)
                .where(
                    StoryCollaborator.user_id == user_id,
                    StoryCollaborator.accepted == True,
                )
            )
            conditions.append(Story.id.in_(shared_query))

        if not conditions:
            return []

        query = select(Story).where(or_(*conditions))

        if team_id:
            query = query.where(Story.team_id == team_id)

        result = await self.db.execute(query.order_by(Story.created_at.desc()))
        return list(result.scalars().all())

    # =========================================================================
    # Collaborator Management
    # =========================================================================

    async def add_collaborator(
        self,
        story_id: int,
        user_id: str,
        collaborator_user_id: str,
        role: CollaboratorRole = CollaboratorRole.VIEWER,
    ) -> StoryCollaborator:
        """Add a collaborator to a story.

        Args:
            story_id: Story ID
            user_id: User adding the collaborator (must be owner/editor)
            collaborator_user_id: User to add as collaborator
            role: Role to assign

        Returns:
            Created collaborator record

        Raises:
            PermissionDeniedError: If user can't add collaborators
        """
        story = await self.get_story_with_access_check(
            story_id, user_id, CollaboratorRole.EDITOR
        )

        # Check if already a collaborator
        existing = await self.db.execute(
            select(StoryCollaborator).where(
                StoryCollaborator.story_id == story_id,
                StoryCollaborator.user_id == collaborator_user_id,
            )
        )
        if existing.scalar_one_or_none():
            raise CollaborationError("User is already a collaborator")

        # Can't add story owner as collaborator
        if story.user_id == collaborator_user_id:
            raise CollaborationError("Cannot add story owner as collaborator")

        collaborator = StoryCollaborator(
            id=str(uuid.uuid4()),
            story_id=story_id,
            user_id=collaborator_user_id,
            role=role,
            invited_by_id=user_id,
            invited_at=datetime.utcnow(),
            accepted=True,  # Auto-accept for now
            accepted_at=datetime.utcnow(),
        )
        self.db.add(collaborator)

        # Log activity
        await self._log_activity(
            story_id=story_id,
            user_id=user_id,
            activity_type=ActivityType.COLLABORATOR_ADDED,
            description=f"Added collaborator with {role.value} role",
            target_user_id=collaborator_user_id,
        )

        await self.db.commit()
        await self.db.refresh(collaborator)

        return collaborator

    async def update_collaborator_role(
        self,
        story_id: int,
        user_id: str,
        collaborator_user_id: str,
        new_role: CollaboratorRole,
    ) -> StoryCollaborator:
        """Update a collaborator's role.

        Args:
            story_id: Story ID
            user_id: User updating (must be owner)
            collaborator_user_id: Collaborator to update
            new_role: New role to assign

        Returns:
            Updated collaborator

        Raises:
            CollaboratorNotFoundError: If collaborator doesn't exist
            PermissionDeniedError: If user isn't owner
        """
        story = await self.get_story_with_access_check(story_id, user_id)

        # Only story owner can change roles
        if story.user_id != user_id:
            raise PermissionDeniedError("Only story owner can change roles")

        result = await self.db.execute(
            select(StoryCollaborator).where(
                StoryCollaborator.story_id == story_id,
                StoryCollaborator.user_id == collaborator_user_id,
            )
        )
        collaborator = result.scalar_one_or_none()

        if not collaborator:
            raise CollaboratorNotFoundError(
                f"Collaborator {collaborator_user_id} not found"
            )

        old_role = collaborator.role
        collaborator.role = new_role

        await self._log_activity(
            story_id=story_id,
            user_id=user_id,
            activity_type=ActivityType.COLLABORATOR_ROLE_CHANGED,
            description=f"Changed role from {old_role.value} to {new_role.value}",
            target_user_id=collaborator_user_id,
        )

        await self.db.commit()
        await self.db.refresh(collaborator)

        return collaborator

    async def remove_collaborator(
        self,
        story_id: int,
        user_id: str,
        collaborator_user_id: str,
    ) -> None:
        """Remove a collaborator from a story.

        Args:
            story_id: Story ID
            user_id: User removing (must be owner or self)
            collaborator_user_id: Collaborator to remove
        """
        story = await self.get_story_with_access_check(story_id, user_id)

        # Can remove self, or owner can remove anyone
        if user_id != collaborator_user_id and story.user_id != user_id:
            raise PermissionDeniedError(
                "Only story owner can remove other collaborators"
            )

        result = await self.db.execute(
            select(StoryCollaborator).where(
                StoryCollaborator.story_id == story_id,
                StoryCollaborator.user_id == collaborator_user_id,
            )
        )
        collaborator = result.scalar_one_or_none()

        if not collaborator:
            raise CollaboratorNotFoundError(
                f"Collaborator {collaborator_user_id} not found"
            )

        await self.db.delete(collaborator)

        await self._log_activity(
            story_id=story_id,
            user_id=user_id,
            activity_type=ActivityType.COLLABORATOR_REMOVED,
            description="Removed collaborator",
            target_user_id=collaborator_user_id,
        )

        await self.db.commit()

    async def get_story_collaborators(
        self,
        story_id: int,
        user_id: str,
    ) -> list[StoryCollaborator]:
        """Get all collaborators for a story.

        Args:
            story_id: Story ID
            user_id: User requesting (must have access)

        Returns:
            List of collaborators
        """
        await self.get_story_with_access_check(story_id, user_id)

        result = await self.db.execute(
            select(StoryCollaborator)
            .where(StoryCollaborator.story_id == story_id)
            .order_by(StoryCollaborator.invited_at)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Comments
    # =========================================================================

    async def add_comment(
        self,
        story_id: int,
        user_id: str,
        content: str,
        parent_id: Optional[str] = None,
        chapter_id: Optional[int] = None,
        timestamp_seconds: Optional[int] = None,
    ) -> StoryComment:
        """Add a comment to a story.

        Args:
            story_id: Story ID
            user_id: User adding comment
            content: Comment text
            parent_id: Parent comment ID (for replies)
            chapter_id: Chapter ID (for chapter-specific comments)
            timestamp_seconds: Audio timestamp (for time-based comments)

        Returns:
            Created comment

        Raises:
            PermissionDeniedError: If user can't comment
        """
        await self.get_story_with_access_check(
            story_id, user_id, CollaboratorRole.COMMENTER
        )

        # Validate parent if provided
        if parent_id:
            parent_result = await self.db.execute(
                select(StoryComment).where(
                    StoryComment.id == parent_id,
                    StoryComment.story_id == story_id,
                )
            )
            if not parent_result.scalar_one_or_none():
                raise CommentNotFoundError(f"Parent comment {parent_id} not found")

        comment = StoryComment(
            id=str(uuid.uuid4()),
            story_id=story_id,
            user_id=user_id,
            content=content,
            parent_id=parent_id,
            chapter_id=chapter_id,
            timestamp_seconds=timestamp_seconds,
            status=CommentStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(comment)

        await self._log_activity(
            story_id=story_id,
            user_id=user_id,
            activity_type=ActivityType.COMMENT_ADDED,
            description="Added comment" if not parent_id else "Added reply",
            activity_metadata=json.dumps({"comment_id": comment.id}),
        )

        await self.db.commit()
        await self.db.refresh(comment)

        return comment

    async def update_comment(
        self,
        comment_id: str,
        user_id: str,
        content: str,
    ) -> StoryComment:
        """Update a comment's content.

        Args:
            comment_id: Comment ID
            user_id: User updating (must be author)
            content: New content

        Returns:
            Updated comment
        """
        result = await self.db.execute(
            select(StoryComment).where(StoryComment.id == comment_id)
        )
        comment = result.scalar_one_or_none()

        if not comment:
            raise CommentNotFoundError(f"Comment {comment_id} not found")

        if comment.user_id != user_id:
            raise PermissionDeniedError("Only comment author can edit")

        comment.content = content
        comment.updated_at = datetime.utcnow()

        await self._log_activity(
            story_id=comment.story_id,
            user_id=user_id,
            activity_type=ActivityType.COMMENT_UPDATED,
            description="Updated comment",
            activity_metadata=json.dumps({"comment_id": comment_id}),
        )

        await self.db.commit()
        await self.db.refresh(comment)

        return comment

    async def delete_comment(
        self,
        comment_id: str,
        user_id: str,
    ) -> None:
        """Soft-delete a comment.

        Args:
            comment_id: Comment ID
            user_id: User deleting (must be author or story owner)
        """
        result = await self.db.execute(
            select(StoryComment)
            .options(selectinload(StoryComment.story))
            .where(StoryComment.id == comment_id)
        )
        comment = result.scalar_one_or_none()

        if not comment:
            raise CommentNotFoundError(f"Comment {comment_id} not found")

        # Author or story owner can delete
        if comment.user_id != user_id and comment.story.user_id != user_id:
            raise PermissionDeniedError("Only author or story owner can delete")

        comment.status = CommentStatus.DELETED
        comment.updated_at = datetime.utcnow()

        await self._log_activity(
            story_id=comment.story_id,
            user_id=user_id,
            activity_type=ActivityType.COMMENT_DELETED,
            description="Deleted comment",
            activity_metadata=json.dumps({"comment_id": comment_id}),
        )

        await self.db.commit()

    async def resolve_comment(
        self,
        comment_id: str,
        user_id: str,
    ) -> StoryComment:
        """Mark a comment as resolved.

        Args:
            comment_id: Comment ID
            user_id: User resolving (must have edit access)

        Returns:
            Updated comment
        """
        result = await self.db.execute(
            select(StoryComment).where(StoryComment.id == comment_id)
        )
        comment = result.scalar_one_or_none()

        if not comment:
            raise CommentNotFoundError(f"Comment {comment_id} not found")

        # Verify user has edit access to story
        await self.get_story_with_access_check(
            comment.story_id, user_id, CollaboratorRole.EDITOR
        )

        comment.status = CommentStatus.RESOLVED
        comment.resolved_by_id = user_id
        comment.resolved_at = datetime.utcnow()

        await self._log_activity(
            story_id=comment.story_id,
            user_id=user_id,
            activity_type=ActivityType.COMMENT_RESOLVED,
            description="Resolved comment",
            activity_metadata=json.dumps({"comment_id": comment_id}),
        )

        await self.db.commit()
        await self.db.refresh(comment)

        return comment

    async def get_story_comments(
        self,
        story_id: int,
        user_id: str,
        include_resolved: bool = False,
    ) -> list[StoryComment]:
        """Get all comments for a story.

        Args:
            story_id: Story ID
            user_id: User requesting
            include_resolved: Include resolved comments

        Returns:
            List of comments (top-level, with replies loaded)
        """
        await self.get_story_with_access_check(story_id, user_id)

        query = (
            select(StoryComment)
            .where(
                StoryComment.story_id == story_id,
                StoryComment.parent_id.is_(None),  # Top-level only
            )
        )

        if not include_resolved:
            query = query.where(StoryComment.status == CommentStatus.ACTIVE)

        result = await self.db.execute(query.order_by(StoryComment.created_at.desc()))
        return list(result.scalars().all())

    # =========================================================================
    # Activity Log
    # =========================================================================

    async def _log_activity(
        self,
        story_id: int,
        user_id: Optional[str],
        activity_type: ActivityType,
        description: str,
        target_user_id: Optional[str] = None,
        activity_metadata: Optional[str] = None,
    ) -> StoryActivity:
        """Log a collaboration activity.

        Args:
            story_id: Story ID
            user_id: User performing action (None for system)
            activity_type: Type of activity
            description: Human-readable description
            target_user_id: Target user (for user-related activities)
            activity_metadata: JSON string with extra data

        Returns:
            Created activity record
        """
        activity = StoryActivity(
            id=str(uuid.uuid4()),
            story_id=story_id,
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            target_user_id=target_user_id,
            activity_metadata=activity_metadata,
            created_at=datetime.utcnow(),
        )
        self.db.add(activity)
        return activity

    async def get_story_activity(
        self,
        story_id: int,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StoryActivity]:
        """Get activity log for a story.

        Args:
            story_id: Story ID
            user_id: User requesting
            limit: Max records to return
            offset: Pagination offset

        Returns:
            List of activities (newest first)
        """
        await self.get_story_with_access_check(story_id, user_id)

        result = await self.db.execute(
            select(StoryActivity)
            .where(StoryActivity.story_id == story_id)
            .order_by(StoryActivity.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


__all__ = [
    "CollaborationService",
    "CollaborationError",
    "StoryNotFoundError",
    "CollaboratorNotFoundError",
    "CommentNotFoundError",
    "PermissionDeniedError",
]
