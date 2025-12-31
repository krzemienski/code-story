"""Server-Sent Events (SSE) endpoints for real-time progress updates.

Provides SSE streams for story generation progress, allowing clients
to receive real-time updates during the pipeline execution.
"""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from codestory.api.deps import CurrentUser

router = APIRouter()

# In-memory event queues per story_id
# In production, use Redis pub/sub for multi-instance support
_event_queues: dict[str, asyncio.Queue] = {}


async def _event_generator(
    story_id: str,
    request: Request,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a story.

    Args:
        story_id: Story to subscribe to
        request: FastAPI request for disconnect detection

    Yields:
        SSE formatted event strings
    """
    queue = _event_queues.get(story_id)
    if queue is None:
        queue = asyncio.Queue()
        _event_queues[story_id] = queue

    try:
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                break

            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"

                # Check for completion events
                if event.get("type") in ("completed", "failed", "cancelled"):
                    break

            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"

    finally:
        # Cleanup empty queues
        if story_id in _event_queues and _event_queues[story_id].empty():
            del _event_queues[story_id]


@router.get("/stories/{story_id}/progress")
async def story_progress_stream(
    story_id: str,
    request: Request,
    user: CurrentUser,
) -> StreamingResponse:
    """Stream story generation progress via SSE.

    Args:
        story_id: Story ID to subscribe to
        request: FastAPI request
        user: Authenticated user

    Returns:
        SSE stream of progress events
    """
    return StreamingResponse(
        _event_generator(story_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def publish_event(story_id: str, event: dict) -> None:
    """Publish an event to SSE subscribers.

    Args:
        story_id: Story ID to publish to
        event: Event data to send
    """
    queue = _event_queues.get(story_id)
    if queue is not None:
        await queue.put(event)


async def publish_progress(
    story_id: str,
    status: str,
    progress_percent: int,
    current_step: str,
    data: dict | None = None,
) -> None:
    """Publish a progress update event.

    Args:
        story_id: Story ID
        status: Current status string
        progress_percent: Progress 0-100
        current_step: Human readable step description
        data: Optional additional data
    """
    from datetime import datetime

    event = {
        "type": "progress",
        "timestamp": datetime.utcnow().isoformat(),
        "story_id": story_id,
        "status": status,
        "progress_percent": progress_percent,
        "current_step": current_step,
        **(data or {}),
    }
    await publish_event(story_id, event)


async def publish_completion(
    story_id: str,
    audio_url: str,
    duration_seconds: float,
    chapters: int,
) -> None:
    """Publish a completion event.

    Args:
        story_id: Story ID
        audio_url: URL to generated audio
        duration_seconds: Audio duration
        chapters: Number of chapters
    """
    from datetime import datetime

    event = {
        "type": "completed",
        "timestamp": datetime.utcnow().isoformat(),
        "story_id": story_id,
        "audio_url": audio_url,
        "duration_seconds": duration_seconds,
        "chapters": chapters,
    }
    await publish_event(story_id, event)


async def publish_error(
    story_id: str,
    error: str,
    details: dict | None = None,
) -> None:
    """Publish an error event.

    Args:
        story_id: Story ID
        error: Error message
        details: Optional error details
    """
    from datetime import datetime

    event = {
        "type": "failed",
        "timestamp": datetime.utcnow().isoformat(),
        "story_id": story_id,
        "error": error,
        **({"details": details} if details else {}),
    }
    await publish_event(story_id, event)
