"""Stories router for story generation and management.

Endpoints for creating and managing audio stories using the services-first architecture:

    Frontend → FastAPI → Backend Services (prepare context) → Agent (creative work)

Uses BackgroundTasks for async pipeline execution and SSE for progress updates.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from codestory.api.deps import DBSession, SupabaseUser

# Security scheme for extracting token
security = HTTPBearer()
from codestory.api.exceptions import NotFoundError
from codestory.api.routers.sse import publish_completion, publish_error, publish_progress
from codestory.models.story import (
    NarrativeStyle,
    Repository,
    Story,
    StoryChapter,
    StoryStatus,
)
# Import StoryPipeline (with actual Claude SDK integration) instead of PipelineService (TODOs)
from codestory.pipeline.orchestrator import (
    StoryPipeline,
    PipelineEvent,
    PipelineEventType,
)
from codestory.agents.base import PipelineStage as AgentPipelineStage
# Keep StoryGenerationRequest for backwards compatibility (may be needed elsewhere)
from codestory.services import StoryGenerationRequest

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class StoryCreateRequest(BaseModel):
    """Request to create a new story."""

    repository_url: HttpUrl = Field(..., description="GitHub repository URL")
    title: str = Field(..., min_length=1, max_length=255)
    narrative_style: NarrativeStyle = Field(default=NarrativeStyle.EDUCATIONAL)
    focus_areas: list[str] = Field(default_factory=list, max_length=10)
    user_intent: str = Field(
        default="Explain the architecture and key components",
        description="What the user wants to learn about the repository",
    )


class ChapterResponse(BaseModel):
    """Chapter information response."""

    id: int
    order: int
    title: str
    script: str
    audio_url: str | None
    start_time: float
    duration_seconds: float | None

    class Config:
        from_attributes = True


class StoryResponse(BaseModel):
    """Story information response."""

    id: int
    title: str
    status: StoryStatus
    narrative_style: NarrativeStyle
    focus_areas: list[str]
    repository_url: str
    audio_url: str | None
    transcript: str | None
    duration_seconds: float | None
    error_message: str | None
    chapters: list[ChapterResponse]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class StoryListResponse(BaseModel):
    """Paginated list of stories."""

    items: list[StoryResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class StoryStatusResponse(BaseModel):
    """Story status with progress."""

    id: int
    status: StoryStatus
    progress_percent: int
    current_step: str
    error_message: str | None


# =============================================================================
# Background Task: Pipeline Execution
# =============================================================================


async def run_story_pipeline(
    story_id: int,
    repo_url: str,
    user_intent: str,
    style: str,
    focus_areas: list[str],
    db_url: str,
) -> None:
    """Execute story generation pipeline in background.

    This function uses the SERVICES-FIRST architecture:

        1. Backend Services (deterministic):
           - RepositoryService: Package repo with Repomix CLI
           - AnalysisService: Analyze structure and patterns

        2. Agent (creative work):
           - Receives prepared context
           - Generates narrative

    Publishes SSE events for real-time progress tracking.

    Args:
        story_id: Database ID of the story
        repo_url: GitHub repository URL
        user_intent: User's learning goals (maps to intent_category)
        style: Narrative style (documentary, tutorial, etc.)
        focus_areas: Areas to focus on in the story
        db_url: Database connection URL for background context
    """
    from codestory.models.database import get_engine
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    # Get a fresh database session for background task
    engine = get_engine()
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    story_id_str = str(story_id)

    async with async_session() as db:
        try:
            # Verify story exists
            result = await db.execute(select(Story).where(Story.id == story_id))
            story = result.scalar_one_or_none()
            if not story:
                await publish_error(story_id_str, "Story not found")
                return

            # Create StoryPipeline (with actual Claude SDK integration)
            # This uses ClaudeSDKClient to invoke the 4-agent pipeline
            pipeline = StoryPipeline()

            # Map AgentPipelineStage (from base.py) to StoryStatus
            stage_status_map = {
                AgentPipelineStage.INTENT: StoryStatus.PENDING,
                AgentPipelineStage.ANALYSIS: StoryStatus.ANALYZING,
                AgentPipelineStage.NARRATIVE: StoryStatus.GENERATING,
                AgentPipelineStage.SYNTHESIS: StoryStatus.SYNTHESIZING,
                AgentPipelineStage.COMPLETE: StoryStatus.COMPLETE,
                AgentPipelineStage.FAILED: StoryStatus.FAILED,
            }

            # Map AgentPipelineStage to SSE status strings
            sse_status_map = {
                AgentPipelineStage.INTENT: "pending",
                AgentPipelineStage.ANALYSIS: "analyzing",
                AgentPipelineStage.NARRATIVE: "generating",
                AgentPipelineStage.SYNTHESIS: "synthesizing",
                AgentPipelineStage.COMPLETE: "complete",
                AgentPipelineStage.FAILED: "failed",
            }

            # Run the 4-agent pipeline with actual Claude SDK invocation
            async for event in pipeline.run(
                repo_url=repo_url,
                user_message=user_intent,
                style=style,
            ):
                # Update story status based on pipeline stage
                new_status = stage_status_map.get(event.stage)
                if new_status and story.status != new_status:
                    story.status = new_status
                    await db.commit()

                # Publish SSE event for real-time progress
                await publish_progress(
                    story_id_str,
                    sse_status_map.get(event.stage, "analyzing"),
                    event.progress_percent,
                    event.message,
                )

                # Handle completion (type is PipelineEventType.COMPLETED)
                if event.type == PipelineEventType.COMPLETED:
                    story.status = StoryStatus.COMPLETE
                    story.completed_at = datetime.utcnow()
                    story.duration_seconds = event.data.get("duration_seconds", 0)

                    # Get result data from the pipeline
                    audio_url = event.data.get("audio_url", "")
                    chapters_count = event.data.get("chapters", 0)

                    if audio_url:
                        story.audio_url = audio_url

                    await db.commit()
                    await publish_completion(
                        story_id_str,
                        audio_url=audio_url,
                        duration_seconds=story.duration_seconds or 0,
                        chapters=chapters_count,
                    )
                    return

                # Handle failure (type is PipelineEventType.FAILED)
                if event.type == PipelineEventType.FAILED:
                    story.status = StoryStatus.FAILED
                    story.error_message = event.error or event.message
                    await db.commit()
                    await publish_error(story_id_str, event.error or event.message)
                    return

        except Exception as e:
            # Update story with error
            try:
                result = await db.execute(select(Story).where(Story.id == story_id))
                story = result.scalar_one_or_none()
                if story:
                    story.status = StoryStatus.FAILED
                    story.error_message = str(e)
                    await db.commit()
            except Exception:
                pass  # Best effort error recording
            await publish_error(story_id_str, str(e))


def _map_intent(user_intent: str) -> str:
    """Map user intent text to intent category."""
    intent_lower = user_intent.lower()
    if any(word in intent_lower for word in ["onboard", "new", "getting started"]):
        return "onboarding"
    if any(word in intent_lower for word in ["architect", "design", "structure"]):
        return "architecture"
    if any(word in intent_lower for word in ["feature", "function", "capability"]):
        return "feature"
    if any(word in intent_lower for word in ["debug", "fix", "issue", "bug"]):
        return "debugging"
    if any(word in intent_lower for word in ["review", "audit", "check"]):
        return "review"
    return "architecture"  # Default


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "",
    response_model=StoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new story",
    description="""
    Create a new audio story from a repository.

    The story generation process:
    1. Repository is cloned and analyzed via Repomix
    2. Code structure and patterns are identified
    3. Narrative outline is generated based on style
    4. Chapters are created with appropriate depth
    5. Audio is synthesized using ElevenLabs

    **Webhook Events**: `story.created`, `story.analyzing`, `story.generating`, `story.completed`

    Use the SSE endpoint `/api/sse/stories/{story_id}` to track real-time progress.
    """,
    response_description="The created story with PENDING status",
    responses={
        201: {
            "description": "Story created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "title": "Understanding My API",
                        "status": "pending",
                        "narrative_style": "educational",
                        "focus_areas": ["architecture"],
                        "repository_url": "https://github.com/user/repo",
                        "created_at": "2025-01-15T10:30:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid repository URL or parameters",
            "content": {
                "application/json": {"example": {"detail": "Invalid GitHub repository URL"}}
            },
        },
        402: {
            "description": "Story quota exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "error": "Daily quota exceeded",
                            "quota_info": {"daily": {"used": 2, "limit": 2}},
                        }
                    }
                }
            },
        },
    },
)
async def create_story(
    request: StoryCreateRequest,
    background_tasks: BackgroundTasks,
    user: SupabaseUser,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    http_request: Request,
) -> StoryResponse:
    """Create a new story and start generation pipeline.

    Creates the story record and kicks off the Claude Agent SDK pipeline
    in a background task. Use SSE endpoint to track progress.

    Args:
        request: Story creation parameters
        background_tasks: FastAPI background tasks
        user: Authenticated user
        credentials: Bearer token for Supabase auth
        http_request: FastAPI request for app state access

    Returns:
        Created story with PENDING status
    """
    from codestory.core.supabase import get_supabase_client

    supabase = get_supabase_client()
    # Set auth header to use user's permissions (RLS)
    supabase.postgrest.auth(credentials.credentials)
    repo_url = str(request.repository_url)
    user_id = user["id"]

    # Find or create repository record
    repo_result = supabase.table("repositories").select("*").eq("url", repo_url).execute()

    if repo_result.data:
        repository = repo_result.data[0]
    else:
        # Parse owner/name from URL
        parts = repo_url.rstrip("/").split("/")
        owner = parts[-2] if len(parts) >= 2 else "unknown"
        name = parts[-1] if parts else "unknown"

        insert_result = supabase.table("repositories").insert({
            "url": repo_url,
            "owner": owner,
            "name": name,
        }).execute()
        repository = insert_result.data[0]

    # Create story record
    story_result = supabase.table("stories").insert({
        "user_id": user_id,
        "repository_id": repository["id"],
        "title": request.title,
        "narrative_style": request.narrative_style.value,
        "focus_areas": request.focus_areas,
        "status": "pending",
    }).execute()
    story = story_result.data[0]

    # Get settings for background task
    from codestory.core.config import get_settings
    settings = get_settings()

    # Start pipeline in background
    background_tasks.add_task(
        run_story_pipeline,
        story_id=story["id"],
        repo_url=repo_url,
        user_intent=request.user_intent,
        style=request.narrative_style.value,
        focus_areas=request.focus_areas,
        db_url=settings.async_database_url,
    )

    # Return response
    return StoryResponse(
        id=story["id"],
        title=story["title"],
        status=StoryStatus(story["status"]),
        narrative_style=NarrativeStyle(story["narrative_style"]),
        focus_areas=story.get("focus_areas") or [],
        repository_url=repository.get("url", ""),
        audio_url=story.get("audio_url"),
        transcript=story.get("transcript"),
        duration_seconds=story.get("duration_seconds"),
        error_message=story.get("error_message"),
        chapters=[],
        created_at=story["created_at"],
        updated_at=story["updated_at"],
        completed_at=story.get("completed_at"),
    )


@router.get(
    "",
    response_model=StoryListResponse,
    summary="List user's stories",
    description="""
    List all stories for the authenticated user with pagination.

    Supports filtering by:
    - Status (pending, analyzing, generating, completed, failed)

    Results are paginated and sorted by creation date (newest first).
    """,
)
async def list_stories(
    user: SupabaseUser,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page (max 100)")] = 20,
    status_filter: Annotated[StoryStatus | None, Query(description="Filter by story status")] = None,
) -> StoryListResponse:
    """List stories for the current user.

    Args:
        user: Authenticated user
        page: Page number (1-indexed)
        page_size: Items per page
        status_filter: Optional status filter

    Returns:
        Paginated list of stories
    """
    from codestory.core.supabase import get_supabase_client

    supabase = get_supabase_client()
    user_id = user["id"]

    # Build query using Supabase client
    query = supabase.table("stories").select("*, repositories(*), story_chapters(*)").eq("user_id", user_id)

    if status_filter:
        query = query.eq("status", status_filter.value)

    # Get total count
    count_response = supabase.table("stories").select("id", count="exact").eq("user_id", user_id)
    if status_filter:
        count_response = count_response.eq("status", status_filter.value)
    count_result = count_response.execute()
    total = count_result.count or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)

    # Execute query
    result = query.execute()
    stories_data = result.data or []

    # Convert to response format
    items = []
    for story in stories_data:
        repo = story.get("repositories") or {}
        chapters = story.get("story_chapters") or []
        items.append(StoryResponse(
            id=story["id"],
            title=story["title"],
            status=StoryStatus(story["status"]),
            narrative_style=NarrativeStyle(story["narrative_style"]),
            focus_areas=story.get("focus_areas") or [],
            repository_url=repo.get("url", ""),
            audio_url=story.get("audio_url"),
            transcript=story.get("transcript"),
            duration_seconds=story.get("duration_seconds"),
            error_message=story.get("error_message"),
            chapters=[ChapterResponse(
                id=c["id"],
                order=c["order"],
                title=c["title"],
                script=c["script"],
                audio_url=c.get("audio_url"),
                start_time=c.get("start_time", 0.0),
                duration_seconds=c.get("duration_seconds"),
            ) for c in chapters],
            created_at=story["created_at"],
            updated_at=story["updated_at"],
            completed_at=story.get("completed_at"),
        ))

    return StoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(stories_data)) < total,
    )


@router.get(
    "/{story_id}",
    response_model=StoryResponse,
    summary="Get story details",
    description="""
    Retrieve detailed information about a specific story.

    Includes:
    - Story metadata and status
    - List of chapters with durations
    - Audio URLs (if completed)
    - Error message (if failed)
    """,
    responses={
        200: {"description": "Story details with chapters"},
        404: {"description": "Story not found or not owned by user"},
    },
)
async def get_story(
    story_id: Annotated[int, Path(description="Unique story identifier")],
    user: SupabaseUser,
) -> StoryResponse:
    """Get a specific story by ID.

    Args:
        story_id: Story database ID
        user: Authenticated user

    Returns:
        Story details with chapters

    Raises:
        NotFoundError: If story doesn't exist or user doesn't own it
    """
    from codestory.core.supabase import get_supabase_client

    supabase = get_supabase_client()
    user_id = user["id"]

    # Query story with related data
    result = supabase.table("stories").select(
        "*, repositories(*), story_chapters(*)"
    ).eq("id", story_id).eq("user_id", user_id).execute()

    if not result.data:
        raise NotFoundError("Story", str(story_id))

    story = result.data[0]
    repo = story.get("repositories") or {}
    chapters = story.get("story_chapters") or []

    return StoryResponse(
        id=story["id"],
        title=story["title"],
        status=StoryStatus(story["status"]),
        narrative_style=NarrativeStyle(story["narrative_style"]),
        focus_areas=story.get("focus_areas") or [],
        repository_url=repo.get("url", ""),
        audio_url=story.get("audio_url"),
        transcript=story.get("transcript"),
        duration_seconds=story.get("duration_seconds"),
        error_message=story.get("error_message"),
        chapters=[ChapterResponse(
            id=c["id"],
            order=c["order"],
            title=c["title"],
            script=c["script"],
            audio_url=c.get("audio_url"),
            start_time=c.get("start_time", 0.0),
            duration_seconds=c.get("duration_seconds"),
        ) for c in chapters],
        created_at=story["created_at"],
        updated_at=story["updated_at"],
        completed_at=story.get("completed_at"),
    )


@router.get(
    "/{story_id}/status",
    response_model=StoryStatusResponse,
    summary="Get story status",
    description="""
    Lightweight endpoint for polling generation status.

    Returns current status, progress percentage, and current step.
    For real-time updates, use the SSE endpoint `/api/sse/stories/{story_id}`.
    """,
)
async def get_story_status(
    story_id: Annotated[int, Path(description="Unique story identifier")],
    user: SupabaseUser,
    db: DBSession,
) -> StoryStatusResponse:
    """Get story generation status.

    Lighter endpoint for polling status without full story data.
    For real-time updates, use the SSE endpoint.

    Args:
        story_id: Story database ID
        user: Authenticated user
        db: Database session

    Returns:
        Current status and progress

    Raises:
        NotFoundError: If story doesn't exist or user doesn't own it
    """
    result = await db.execute(
        select(Story).where(Story.id == story_id, Story.user_id == user["id"])
    )
    story = result.scalar_one_or_none()

    if not story:
        raise NotFoundError("Story", str(story_id))

    # Map status to progress
    progress_map = {
        StoryStatus.PENDING: (0, "Waiting to start..."),
        StoryStatus.ANALYZING: (25, "Analyzing repository..."),
        StoryStatus.GENERATING: (50, "Generating narrative..."),
        StoryStatus.SYNTHESIZING: (75, "Synthesizing audio..."),
        StoryStatus.COMPLETE: (100, "Complete!"),
        StoryStatus.FAILED: (0, "Failed"),
    }
    progress, step = progress_map.get(story.status, (0, "Unknown"))

    return StoryStatusResponse(
        id=story.id,
        status=story.status,
        progress_percent=progress,
        current_step=step,
        error_message=story.error_message,
    )


@router.delete(
    "/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a story",
    description="Permanently delete a story and all its chapters.",
    responses={
        204: {"description": "Story deleted successfully"},
        404: {"description": "Story not found"},
    },
)
async def delete_story(
    story_id: Annotated[int, Path(description="Unique story identifier")],
    user: SupabaseUser,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> None:
    """Delete a story.

    Deletes the story and all associated chapters. Audio files in
    external storage should be cleaned up separately.

    Args:
        story_id: Story database ID
        user: Authenticated user
        credentials: Bearer token for Supabase auth

    Raises:
        NotFoundError: If story doesn't exist or user doesn't own it
    """
    from codestory.core.supabase import get_supabase_client

    supabase = get_supabase_client()
    supabase.postgrest.auth(credentials.credentials)
    user_id = user["id"]

    # Check story exists and belongs to user
    result = supabase.table("stories").select("id").eq("id", story_id).eq("user_id", user_id).execute()
    if not result.data:
        raise NotFoundError("Story", str(story_id))

    # Delete chapters first (cascade)
    supabase.table("story_chapters").delete().eq("story_id", story_id).execute()

    # Delete story
    supabase.table("stories").delete().eq("id", story_id).eq("user_id", user_id).execute()


@router.post(
    "/{story_id}/retry",
    response_model=StoryResponse,
    summary="Retry failed story",
    description="""
    Retry generation for a failed story.

    Only works for stories in FAILED status. Resets the status
    to PENDING and restarts the Claude Agent SDK pipeline.
    """,
    responses={
        200: {"description": "Story retry initiated"},
        400: {"description": "Story is not in FAILED status"},
        404: {"description": "Story not found"},
    },
)
async def retry_story(
    story_id: Annotated[int, Path(description="Unique story identifier")],
    background_tasks: BackgroundTasks,
    user: SupabaseUser,
    db: DBSession,
) -> Story:
    """Retry a failed story generation.

    Resets the story status and restarts the pipeline.
    Only works for stories in FAILED status.

    Args:
        story_id: Story database ID
        background_tasks: FastAPI background tasks
        user: Authenticated user
        db: Database session

    Returns:
        Story with reset status

    Raises:
        NotFoundError: If story doesn't exist
        HTTPException: If story is not in FAILED status
    """
    result = await db.execute(
        select(Story)
        .options(selectinload(Story.repository))
        .where(Story.id == story_id, Story.user_id == user["id"])
    )
    story = result.scalar_one_or_none()

    if not story:
        raise NotFoundError("Story", str(story_id))

    if story.status != StoryStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only retry failed stories. Current status: {story.status.value}",
        )

    # Reset story state
    story.status = StoryStatus.PENDING
    story.error_message = None
    story.audio_url = None
    story.transcript = None
    story.duration_seconds = None
    story.completed_at = None

    # Delete old chapters
    from sqlalchemy import delete
    await db.execute(delete(StoryChapter).where(StoryChapter.story_id == story_id))
    await db.commit()

    # Get settings for background task
    from codestory.core.config import get_settings
    settings = get_settings()

    # Restart pipeline
    background_tasks.add_task(
        run_story_pipeline,
        story_id=story.id,
        repo_url=story.repository.url,
        user_intent="Retry generation",  # Original intent not stored
        style=story.narrative_style.value,
        focus_areas=story.focus_areas,
        db_url=settings.async_database_url,
    )

    story.chapters = []
    return story
