"""Stories router for story generation and management.

Endpoints for creating and managing audio stories using the Claude Agent SDK pipeline.
Uses BackgroundTasks for async pipeline execution and SSE for progress updates.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from codestory.agents import CodeStoryClient, PipelineStage
from codestory.api.deps import CurrentUser, DBSession
from codestory.api.exceptions import NotFoundError
from codestory.api.routers.sse import publish_completion, publish_error, publish_progress
from codestory.models.story import (
    NarrativeStyle,
    Repository,
    Story,
    StoryChapter,
    StoryStatus,
)

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
    db_url: str,
) -> None:
    """Execute story generation pipeline in background.

    This function runs the Claude Agent SDK pipeline and updates the story
    record as it progresses through stages. Publishes SSE events for real-time
    progress tracking.

    Args:
        story_id: Database ID of the story
        repo_url: GitHub repository URL
        user_intent: User's learning goals
        style: Narrative style (documentary, tutorial, etc.)
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
            # Update status to analyzing
            result = await db.execute(select(Story).where(Story.id == story_id))
            story = result.scalar_one_or_none()
            if not story:
                await publish_error(story_id_str, "Story not found")
                return

            story.status = StoryStatus.ANALYZING
            await db.commit()
            await publish_progress(story_id_str, "analyzing", 10, "Starting repository analysis...")

            # Run the Claude Agent SDK pipeline
            def on_progress(stage: PipelineStage, message: str, percent: int) -> None:
                """Progress callback - note: this is sync, SSE publish is async."""
                import asyncio
                # Schedule SSE publish in event loop
                try:
                    loop = asyncio.get_event_loop()
                    status_map = {
                        PipelineStage.INTENT: "analyzing",
                        PipelineStage.ANALYSIS: "analyzing",
                        PipelineStage.NARRATIVE: "generating",
                        PipelineStage.SYNTHESIS: "synthesizing",
                        PipelineStage.COMPLETE: "complete",
                        PipelineStage.FAILED: "failed",
                    }
                    loop.create_task(
                        publish_progress(story_id_str, status_map.get(stage, "analyzing"), percent, message)
                    )
                except RuntimeError:
                    pass  # No event loop, skip SSE

            async with CodeStoryClient(on_progress=on_progress) as client:
                final_result = None

                async for update in client.generate_story(
                    repo_url=repo_url,
                    user_intent=user_intent,
                    style=style,
                ):
                    stage = update.get("stage", "")
                    progress = update.get("progress", 0)

                    # Map pipeline stages to story status
                    if stage in ("intent", "analysis"):
                        story.status = StoryStatus.ANALYZING
                    elif stage == "narrative":
                        story.status = StoryStatus.GENERATING
                    elif stage == "synthesis":
                        story.status = StoryStatus.SYNTHESIZING
                    await db.commit()

                    # Capture final result
                    if "result" in update:
                        final_result = update["result"]

                    # Handle errors
                    if stage == "failed":
                        error_msg = update.get("error", "Unknown pipeline error")
                        story.status = StoryStatus.FAILED
                        story.error_message = error_msg
                        await db.commit()
                        await publish_error(story_id_str, error_msg)
                        return

            # Process successful result
            if final_result and final_result.success:
                story.status = StoryStatus.COMPLETE
                story.audio_url = final_result.audio_url
                story.duration_seconds = final_result.duration_seconds
                story.completed_at = datetime.utcnow()

                # Create chapters from result
                for i, chapter_data in enumerate(final_result.chapters):
                    chapter = StoryChapter(
                        story_id=story_id,
                        order=i + 1,
                        title=chapter_data.get("title", f"Chapter {i + 1}"),
                        script=chapter_data.get("content", ""),
                        audio_url=chapter_data.get("audio_url"),
                        start_time=chapter_data.get("start_time", 0.0),
                        duration_seconds=chapter_data.get("duration_seconds"),
                    )
                    db.add(chapter)

                await db.commit()

                await publish_completion(
                    story_id_str,
                    audio_url=final_result.audio_url or "",
                    duration_seconds=final_result.duration_seconds,
                    chapters=len(final_result.chapters),
                )
            else:
                error_msg = final_result.error if final_result else "Pipeline produced no result"
                story.status = StoryStatus.FAILED
                story.error_message = error_msg
                await db.commit()
                await publish_error(story_id_str, error_msg)

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


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    request: StoryCreateRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: DBSession,
    http_request: Request,
) -> Story:
    """Create a new story and start generation pipeline.

    Creates the story record and kicks off the Claude Agent SDK pipeline
    in a background task. Use SSE endpoint to track progress.

    Args:
        request: Story creation parameters
        background_tasks: FastAPI background tasks
        user: Authenticated user
        db: Database session
        http_request: FastAPI request for app state access

    Returns:
        Created story with PENDING status
    """
    repo_url = str(request.repository_url)

    # Find or create repository record
    result = await db.execute(select(Repository).where(Repository.url == repo_url))
    repository = result.scalar_one_or_none()

    if not repository:
        # Parse owner/name from URL
        parts = repo_url.rstrip("/").split("/")
        owner = parts[-2] if len(parts) >= 2 else "unknown"
        name = parts[-1] if parts else "unknown"

        repository = Repository(
            url=repo_url,
            owner=owner,
            name=name,
        )
        db.add(repository)
        await db.flush()  # Get repository ID

    # Create story record
    story = Story(
        user_id=user.id,
        repository_id=repository.id,
        title=request.title,
        narrative_style=request.narrative_style,
        focus_areas=request.focus_areas,
        status=StoryStatus.PENDING,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    # Get settings for background task
    from codestory.core.config import get_settings
    settings = get_settings()

    # Start pipeline in background
    background_tasks.add_task(
        run_story_pipeline,
        story_id=story.id,
        repo_url=repo_url,
        user_intent=request.user_intent,
        style=request.narrative_style.value,
        db_url=settings.async_database_url,
    )

    # Load relationships for response
    story.repository = repository
    story.chapters = []

    return story


@router.get("", response_model=StoryListResponse)
async def list_stories(
    user: CurrentUser,
    db: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: StoryStatus | None = None,
) -> StoryListResponse:
    """List stories for the current user.

    Args:
        user: Authenticated user
        db: Database session
        page: Page number (1-indexed)
        page_size: Items per page
        status_filter: Optional status filter

    Returns:
        Paginated list of stories
    """
    # Build query
    query = select(Story).where(Story.user_id == user.id)
    if status_filter:
        query = query.where(Story.status == status_filter)

    # Count total
    from sqlalchemy import func as sql_func
    count_query = select(sql_func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get page
    offset = (page - 1) * page_size
    query = (
        query.options(selectinload(Story.repository), selectinload(Story.chapters))
        .order_by(Story.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    stories = result.scalars().all()

    # Convert to response format
    items = []
    for story in stories:
        items.append(StoryResponse(
            id=story.id,
            title=story.title,
            status=story.status,
            narrative_style=story.narrative_style,
            focus_areas=story.focus_areas,
            repository_url=story.repository.url if story.repository else "",
            audio_url=story.audio_url,
            transcript=story.transcript,
            duration_seconds=story.duration_seconds,
            error_message=story.error_message,
            chapters=[ChapterResponse.model_validate(c) for c in story.chapters],
            created_at=story.created_at,
            updated_at=story.updated_at,
            completed_at=story.completed_at,
        ))

    return StoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(stories)) < total,
    )


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: int,
    user: CurrentUser,
    db: DBSession,
) -> Story:
    """Get a specific story by ID.

    Args:
        story_id: Story database ID
        user: Authenticated user
        db: Database session

    Returns:
        Story details with chapters

    Raises:
        NotFoundError: If story doesn't exist or user doesn't own it
    """
    result = await db.execute(
        select(Story)
        .options(selectinload(Story.repository), selectinload(Story.chapters))
        .where(Story.id == story_id, Story.user_id == user.id)
    )
    story = result.scalar_one_or_none()

    if not story:
        raise NotFoundError("Story", str(story_id))

    return story


@router.get("/{story_id}/status", response_model=StoryStatusResponse)
async def get_story_status(
    story_id: int,
    user: CurrentUser,
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
        select(Story).where(Story.id == story_id, Story.user_id == user.id)
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


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    story_id: int,
    user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a story.

    Deletes the story and all associated chapters. Audio files in
    external storage should be cleaned up separately.

    Args:
        story_id: Story database ID
        user: Authenticated user
        db: Database session

    Raises:
        NotFoundError: If story doesn't exist or user doesn't own it
    """
    result = await db.execute(
        select(Story).where(Story.id == story_id, Story.user_id == user.id)
    )
    story = result.scalar_one_or_none()

    if not story:
        raise NotFoundError("Story", str(story_id))

    await db.delete(story)
    await db.commit()


@router.post("/{story_id}/retry", response_model=StoryResponse)
async def retry_story(
    story_id: int,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
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
        .where(Story.id == story_id, Story.user_id == user.id)
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
        db_url=settings.async_database_url,
    )

    story.chapters = []
    return story
