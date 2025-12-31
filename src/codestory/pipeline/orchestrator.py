"""Story Generation Pipeline Orchestrator.

Implements the 4-agent pipeline using Claude Agent SDK:
- Sequential agent execution via Task tool delegation
- Progress tracking with WebSocket-compatible events
- Error recovery with configurable retries
- State persistence for resumption

The orchestrator coordinates the SDK client to execute agents in order,
passing results between stages and emitting progress events.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    TextBlock,
    ToolUseBlock,
)

from codestory.agents import (
    CodeStoryClient,
    PipelineStage,
    PipelineState,
    StoryResult,
    create_codestory_options,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger("codestory.pipeline")


# =============================================================================
# Pipeline Configuration
# =============================================================================


@dataclass
class PipelineConfig:
    """Configuration for story generation pipeline.

    Attributes:
        max_retries: Maximum retry attempts per stage
        retry_delay_seconds: Initial delay between retries (exponential backoff)
        timeout_seconds: Maximum time per stage before timeout
        enable_caching: Cache intermediate results for resumption
        parallel_analysis: Run independent analysis tools in parallel
        voice_enabled: Enable audio synthesis (disable for text-only)
        max_turns: Maximum SDK conversation turns per stage
    """

    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 300.0
    enable_caching: bool = True
    parallel_analysis: bool = True
    voice_enabled: bool = True
    max_turns: int = 50


# =============================================================================
# Pipeline Events
# =============================================================================


class PipelineEventType(str, Enum):
    """Types of pipeline events for progress tracking."""

    STARTED = "started"
    STAGE_STARTED = "stage_started"
    STAGE_PROGRESS = "stage_progress"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    STAGE_RETRYING = "stage_retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineEvent:
    """Event emitted during pipeline execution.

    Compatible with WebSocket streaming and SSE.
    """

    type: PipelineEventType
    stage: PipelineStage
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    progress_percent: int = 0
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "type": self.type.value,
            "stage": self.stage.value,
            "timestamp": self.timestamp,
            "progress_percent": self.progress_percent,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


# =============================================================================
# Pipeline Orchestrator
# =============================================================================


class StoryPipeline:
    """Orchestrates the 4-agent story generation pipeline.

    Uses Claude Agent SDK's Task tool for subagent delegation,
    with progress events for real-time UI updates.

    Example:
        pipeline = StoryPipeline()

        async for event in pipeline.run(
            repo_url="https://github.com/anthropics/claude-code",
            user_message="Explain the architecture",
        ):
            print(f"{event.stage}: {event.progress_percent}%")

        print(f"Result: {pipeline.result}")
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        on_event: Callable[[PipelineEvent], None] | None = None,
    ) -> None:
        """Initialize pipeline.

        Args:
            config: Pipeline configuration
            on_event: Optional callback for events (in addition to yielding)
        """
        self.config = config or PipelineConfig()
        self.on_event = on_event
        self.state = PipelineState(stage=PipelineStage.INTENT)
        self.result: StoryResult | None = None
        self.session_id: str = str(uuid4())
        self._cancelled = False

    def _emit(self, event: PipelineEvent) -> None:
        """Emit event to callback if configured."""
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                logger.warning(f"Event callback error: {e}")

    async def run(
        self,
        repo_url: str,
        user_message: str,
        style: str = "documentary",
    ) -> AsyncIterator[PipelineEvent]:
        """Execute the full story generation pipeline.

        Args:
            repo_url: GitHub repository URL
            user_message: User's description of what they want to learn
            style: Narrative style (fiction, documentary, tutorial, podcast, technical)

        Yields:
            PipelineEvent objects for progress tracking

        Returns:
            Final StoryResult is stored in self.result
        """
        start_event = PipelineEvent(
            type=PipelineEventType.STARTED,
            stage=PipelineStage.INTENT,
            progress_percent=0,
            message="Starting story generation pipeline",
            data={"repo_url": repo_url, "style": style, "session_id": self.session_id},
        )
        self._emit(start_event)
        yield start_event

        try:
            # Execute pipeline using CodeStoryClient
            options = create_codestory_options(max_turns=self.config.max_turns)

            async with CodeStoryClient(options=options) as client:
                async for update in client.generate_story(
                    repo_url=repo_url,
                    user_intent=user_message,
                    style=style,
                ):
                    # Map SDK updates to pipeline events
                    stage = PipelineStage(update.get("stage", "intent"))
                    progress = update.get("progress", 0)

                    event = PipelineEvent(
                        type=PipelineEventType.STAGE_PROGRESS,
                        stage=stage,
                        progress_percent=progress,
                        message=self._get_stage_message(stage, progress),
                        data={"update": str(update.get("message", ""))[:200]},
                    )
                    self._emit(event)
                    yield event

                    # Check for cancellation
                    if self._cancelled:
                        cancel_event = PipelineEvent(
                            type=PipelineEventType.CANCELLED,
                            stage=stage,
                            message="Pipeline cancelled by user",
                        )
                        self._emit(cancel_event)
                        yield cancel_event
                        return

                    # Check for result
                    if "result" in update:
                        self.result = update["result"]

            # Pipeline completed successfully
            if self.result and self.result.success:
                complete_event = PipelineEvent(
                    type=PipelineEventType.COMPLETED,
                    stage=PipelineStage.COMPLETE,
                    progress_percent=100,
                    message="Story generation complete!",
                    data={
                        "audio_url": self.result.audio_url,
                        "chapters": len(self.result.chapters),
                        "duration_seconds": self.result.duration_seconds,
                    },
                )
                self._emit(complete_event)
                yield complete_event
            else:
                # Pipeline failed
                error_msg = self.result.error if self.result else "Unknown error"
                fail_event = PipelineEvent(
                    type=PipelineEventType.FAILED,
                    stage=self.state.stage,
                    progress_percent=0,
                    message="Pipeline failed",
                    error=error_msg,
                )
                self._emit(fail_event)
                yield fail_event

        except Exception as e:
            logger.exception("Pipeline execution error")
            error_event = PipelineEvent(
                type=PipelineEventType.FAILED,
                stage=self.state.stage,
                progress_percent=0,
                message="Pipeline error",
                error=str(e),
            )
            self._emit(error_event)
            yield error_event
            self.result = StoryResult(success=False, error=str(e))

    def cancel(self) -> None:
        """Request pipeline cancellation."""
        self._cancelled = True
        logger.info(f"Pipeline {self.session_id} cancellation requested")

    def _get_stage_message(self, stage: PipelineStage, progress: int) -> str:
        """Get human-readable message for stage progress."""
        messages = {
            PipelineStage.INTENT: "Understanding your learning goals...",
            PipelineStage.ANALYSIS: "Analyzing repository structure and patterns...",
            PipelineStage.NARRATIVE: "Crafting your story narrative...",
            PipelineStage.SYNTHESIS: "Generating audio narration...",
            PipelineStage.COMPLETE: "Story complete!",
            PipelineStage.FAILED: "An error occurred",
        }
        return messages.get(stage, f"Processing... ({progress}%)")


# =============================================================================
# Convenience Function
# =============================================================================


async def run_story_pipeline(
    repo_url: str,
    user_message: str,
    style: str = "documentary",
    config: PipelineConfig | None = None,
) -> StoryResult:
    """Run the story generation pipeline and return the result.

    Convenience function that handles async iteration internally.

    Args:
        repo_url: GitHub repository URL
        user_message: User's learning intent
        style: Narrative style
        config: Optional pipeline configuration

    Returns:
        StoryResult with success/failure and audio URL if successful
    """
    pipeline = StoryPipeline(config=config)

    async for event in pipeline.run(repo_url, user_message, style):
        logger.info(f"[{event.stage.value}] {event.progress_percent}%: {event.message}")

    return pipeline.result or StoryResult(success=False, error="No result generated")


# =============================================================================
# Stage Runners (for granular control)
# =============================================================================


async def run_intent_stage(
    user_message: str,
    repo_url: str,
) -> dict[str, Any]:
    """Run only the intent analysis stage.

    Useful for testing or multi-step UIs.
    """
    options = create_codestory_options(max_turns=20)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            f"""Analyze user intent for Code Story.

Repository: {repo_url}
User message: {user_message}

Use the Task tool to delegate to intent-agent with prompt:
"Analyze the user's learning goals and preferred style for this repository."

Return structured JSON with intent_category, expertise_level, focus_areas, and recommended_style.
"""
        )

        result: dict[str, Any] = {}
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        result["response"] = block.text

        return result


async def run_analysis_stage(
    repo_url: str,
    intent_result: dict[str, Any],
) -> dict[str, Any]:
    """Run only the repository analysis stage.

    Useful for testing or multi-step UIs.
    """
    focus_areas = intent_result.get("focus_areas", [])

    options = create_codestory_options(max_turns=30)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            f"""Analyze repository for Code Story.

Repository: {repo_url}
Focus areas: {', '.join(focus_areas) if focus_areas else 'general overview'}

Use the Task tool to delegate to repo-analyzer with prompt:
"Analyze the repository structure, architecture patterns, and key components."

Return structured JSON with architecture_pattern, key_components, design_patterns, and dependencies.
"""
        )

        result: dict[str, Any] = {}
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        result["analysis"] = block.text

        return result
