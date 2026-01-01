"""Collaboration API router for story sharing and comments.

Provides endpoints for:
- Story collaborator management (add, update role, remove)
- Story comments with threading and chapter anchoring
- Activity feed for collaboration tracking
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from codestory.api.deps import DBSession, SupabaseUser
from codestory.models import (
    ActivityType,
    CollaboratorRole,
    CommentStatus,
)
from codestory.services import (
    CollaborationService,
    CollaborationError,
    StoryNotFoundError,
    CollaboratorNotFoundError,
    CommentNotFoundError,
)

router = APIRouter(prefix="/stories/{story_id}/collaboration", tags=["collaboration"])


# ============================================================================
# Pydantic Schemas (inline per project pattern)
# ============================================================================


class CollaboratorCreate(BaseModel):
    """Request to add a collaborator."""

    user_id: str = Field(..., description="ID of user to add as collaborator")
    role: CollaboratorRole = Field(
        default=CollaboratorRole.VIEWER,
        description="Role to assign",
    )


class CollaboratorUpdate(BaseModel):
    """Request to update collaborator role."""

    role: CollaboratorRole = Field(..., description="New role to assign")


class CollaboratorResponse(BaseModel):
    """Collaborator information."""

    id: str
    story_id: int
    user_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    role: CollaboratorRole
    invited_by_id: Optional[str] = None
    invited_at: datetime
    accepted: bool
    accepted_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    """Request to create a comment."""

    content: str = Field(..., min_length=1, max_length=10000, description="Comment content")
    parent_id: Optional[str] = Field(None, description="Parent comment ID for replies")
    chapter_id: Optional[int] = Field(None, description="Chapter to anchor comment to")
    timestamp_seconds: Optional[int] = Field(
        None,
        ge=0,
        description="Audio timestamp in seconds",
    )


class CommentUpdate(BaseModel):
    """Request to update a comment."""

    content: str = Field(..., min_length=1, max_length=10000, description="Updated content")


class CommentResponse(BaseModel):
    """Comment information."""

    id: str
    story_id: int
    user_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    content: str
    parent_id: Optional[str] = None
    chapter_id: Optional[int] = None
    timestamp_seconds: Optional[int] = None
    status: CommentStatus
    resolved_by_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reply_count: int = 0

    model_config = {"from_attributes": True}


class ActivityResponse(BaseModel):
    """Activity log entry."""

    id: str
    story_id: int
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    activity_type: ActivityType
    description: str
    activity_metadata: Optional[str] = None
    target_user_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CollaboratorListResponse(BaseModel):
    """List of collaborators."""

    collaborators: list[CollaboratorResponse]
    total: int


class CommentListResponse(BaseModel):
    """List of comments."""

    comments: list[CommentResponse]
    total: int


class ActivityListResponse(BaseModel):
    """List of activities."""

    activities: list[ActivityResponse]
    total: int


# ============================================================================
# Helper functions
# ============================================================================


def _collaborator_to_response(collab) -> CollaboratorResponse:
    """Convert collaborator model to response."""
    return CollaboratorResponse(
        id=collab.id,
        story_id=collab.story_id,
        user_id=collab.user_id,
        user_email=collab.user.email if collab.user else None,
        user_name=collab.user.full_name if collab.user else None,
        role=collab.role,
        invited_by_id=collab.invited_by_id,
        invited_at=collab.invited_at,
        accepted=collab.accepted,
        accepted_at=collab.accepted_at,
        last_accessed_at=collab.last_accessed_at,
    )


def _comment_to_response(comment) -> CommentResponse:
    """Convert comment model to response."""
    return CommentResponse(
        id=comment.id,
        story_id=comment.story_id,
        user_id=comment.user_id,
        user_email=comment.user.email if comment.user else None,
        user_name=comment.user.full_name if comment.user else None,
        content=comment.content,
        parent_id=comment.parent_id,
        chapter_id=comment.chapter_id,
        timestamp_seconds=comment.timestamp_seconds,
        status=comment.status,
        resolved_by_id=comment.resolved_by_id,
        resolved_at=comment.resolved_at,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        reply_count=comment.reply_count if hasattr(comment, "reply_count") else 0,
    )


def _activity_to_response(activity) -> ActivityResponse:
    """Convert activity model to response."""
    return ActivityResponse(
        id=activity.id,
        story_id=activity.story_id,
        user_id=activity.user_id,
        user_email=activity.user.email if activity.user else None,
        user_name=activity.user.full_name if activity.user else None,
        activity_type=activity.activity_type,
        description=activity.description,
        activity_metadata=activity.activity_metadata,
        target_user_id=activity.target_user_id,
        created_at=activity.created_at,
    )


# ============================================================================
# Collaborator Endpoints
# ============================================================================


@router.get("/collaborators", response_model=CollaboratorListResponse)
async def list_collaborators(
    story_id: int,
    db: DBSession,
    current_user: SupabaseUser,
) -> CollaboratorListResponse:
    """List all collaborators for a story.

    Requires at least viewer access to the story.
    """
    service = CollaborationService(db)

    try:
        collaborators = await service.get_collaborators(story_id, current_user["id"])
        return CollaboratorListResponse(
            collaborators=[_collaborator_to_response(c) for c in collaborators],
            total=len(collaborators),
        )
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "/collaborators",
    response_model=CollaboratorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_collaborator(
    story_id: int,
    data: CollaboratorCreate,
    db: DBSession,
    current_user: SupabaseUser,
) -> CollaboratorResponse:
    """Add a collaborator to a story.

    Requires owner or editor access to the story.
    """
    service = CollaborationService(db)

    try:
        collaborator = await service.add_collaborator(
            story_id=story_id,
            user_id=current_user["id"],
            collaborator_user_id=data.user_id,
            role=data.role,
        )
        return _collaborator_to_response(collaborator)
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch("/collaborators/{collaborator_user_id}", response_model=CollaboratorResponse)
async def update_collaborator_role(
    story_id: int,
    collaborator_user_id: str,
    data: CollaboratorUpdate,
    db: DBSession,
    current_user: SupabaseUser,
) -> CollaboratorResponse:
    """Update a collaborator's role.

    Only the story owner can change collaborator roles.
    """
    service = CollaborationService(db)

    try:
        collaborator = await service.update_collaborator_role(
            story_id=story_id,
            user_id=current_user["id"],
            collaborator_user_id=collaborator_user_id,
            new_role=data.role,
        )
        return _collaborator_to_response(collaborator)
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaboratorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.delete(
    "/collaborators/{collaborator_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_collaborator(
    story_id: int,
    collaborator_user_id: str,
    db: DBSession,
    current_user: SupabaseUser,
) -> None:
    """Remove a collaborator from a story.

    Story owner can remove anyone. Collaborators can remove themselves.
    """
    service = CollaborationService(db)

    try:
        await service.remove_collaborator(
            story_id=story_id,
            user_id=current_user["id"],
            collaborator_user_id=collaborator_user_id,
        )
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaboratorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============================================================================
# Comment Endpoints
# ============================================================================


@router.get("/comments", response_model=CommentListResponse)
async def list_comments(
    story_id: int,
    db: DBSession,
    current_user: SupabaseUser,
    chapter_id: Optional[int] = Query(None, description="Filter by chapter"),
    parent_id: Optional[str] = Query(None, description="Filter by parent comment"),
    include_resolved: bool = Query(False, description="Include resolved comments"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CommentListResponse:
    """List comments on a story.

    Requires at least viewer access to the story.
    """
    service = CollaborationService(db)

    try:
        comments = await service.get_comments(
            story_id=story_id,
            user_id=current_user["id"],
            chapter_id=chapter_id,
            parent_id=parent_id,
            include_resolved=include_resolved,
            limit=limit,
            offset=offset,
        )
        return CommentListResponse(
            comments=[_comment_to_response(c) for c in comments],
            total=len(comments),
        )
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    story_id: int,
    data: CommentCreate,
    db: DBSession,
    current_user: SupabaseUser,
) -> CommentResponse:
    """Create a comment on a story.

    Requires at least commenter access to the story.
    """
    service = CollaborationService(db)

    try:
        comment = await service.add_comment(
            story_id=story_id,
            user_id=current_user["id"],
            content=data.content,
            parent_id=data.parent_id,
            chapter_id=data.chapter_id,
            timestamp_seconds=data.timestamp_seconds,
        )
        return _comment_to_response(comment)
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CommentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent comment not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.get("/comments/{comment_id}", response_model=CommentResponse)
async def get_comment(
    story_id: int,
    comment_id: str,
    db: DBSession,
    current_user: SupabaseUser,
) -> CommentResponse:
    """Get a specific comment."""
    service = CollaborationService(db)

    try:
        # Verify access first
        await service.get_story_with_access_check(
            story_id=story_id,
            user_id=current_user["id"],
            required_role=CollaboratorRole.VIEWER,
        )

        # Get comment
        comments = await service.get_comments(
            story_id=story_id,
            user_id=current_user["id"],
            limit=1000,  # Get all to find by ID
            offset=0,
        )

        for comment in comments:
            if comment.id == comment_id:
                return _comment_to_response(comment)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    story_id: int,
    comment_id: str,
    data: CommentUpdate,
    db: DBSession,
    current_user: SupabaseUser,
) -> CommentResponse:
    """Update a comment.

    Only the comment author can update their comment.
    """
    service = CollaborationService(db)

    try:
        comment = await service.update_comment(
            story_id=story_id,
            comment_id=comment_id,
            user_id=current_user["id"],
            content=data.content,
        )
        return _comment_to_response(comment)
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CommentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    story_id: int,
    comment_id: str,
    db: DBSession,
    current_user: SupabaseUser,
) -> None:
    """Delete a comment.

    Comment author or story owner can delete comments.
    """
    service = CollaborationService(db)

    try:
        await service.delete_comment(
            story_id=story_id,
            comment_id=comment_id,
            user_id=current_user["id"],
        )
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CommentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post("/comments/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    story_id: int,
    comment_id: str,
    db: DBSession,
    current_user: SupabaseUser,
) -> CommentResponse:
    """Mark a comment as resolved.

    Requires at least editor access to the story.
    """
    service = CollaborationService(db)

    try:
        comment = await service.resolve_comment(
            story_id=story_id,
            comment_id=comment_id,
            user_id=current_user["id"],
        )
        return _comment_to_response(comment)
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CommentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============================================================================
# Activity Endpoints
# ============================================================================


@router.get("/activity", response_model=ActivityListResponse)
async def list_activity(
    story_id: int,
    db: DBSession,
    current_user: SupabaseUser,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ActivityListResponse:
    """Get activity feed for a story.

    Requires at least viewer access to the story.
    """
    service = CollaborationService(db)

    try:
        activities = await service.get_story_activity(
            story_id=story_id,
            user_id=current_user["id"],
            limit=limit,
            offset=offset,
        )
        return ActivityListResponse(
            activities=[_activity_to_response(a) for a in activities],
            total=len(activities),
        )
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============================================================================
# Transfer Ownership Endpoint
# ============================================================================


@router.post("/transfer-ownership/{new_owner_user_id}", response_model=CollaboratorResponse)
async def transfer_ownership(
    story_id: int,
    new_owner_user_id: str,
    db: DBSession,
    current_user: SupabaseUser,
) -> CollaboratorResponse:
    """Transfer story ownership to another collaborator.

    Only the current owner can transfer ownership.
    The new owner must already be a collaborator.
    """
    service = CollaborationService(db)

    try:
        collaborator = await service.transfer_ownership(
            story_id=story_id,
            current_owner_id=current_user["id"],
            new_owner_id=new_owner_user_id,
        )
        return _collaborator_to_response(collaborator)
    except StoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    except CollaboratorNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New owner is not a collaborator",
        )
    except CollaborationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
