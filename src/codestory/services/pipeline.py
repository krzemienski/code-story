"""Pipeline Service - Story Generation Orchestration.

This is the MAIN ORCHESTRATOR that implements the correct architecture:

    Frontend Button Press
           ↓
    FastAPI Endpoint (POST /api/stories)
           ↓
    PipelineService.generate_story()
           ↓
    ┌──────────────────────────────────────┐
    │  BACKEND CONTEXT PREPARATION         │
    │  (Deterministic, no agent needed)    │
    │                                      │
    │  1. RepositoryService.package()      │
    │     - Calls Repomix CLI              │
    │     - Returns packaged content       │
    │                                      │
    │  2. AnalysisService.analyze()        │
    │     - Parses structure               │
    │     - Detects patterns               │
    │     - Builds story components        │
    │                                      │
    │  3. Build Agent Context              │
    │     - Combine all analysis           │
    │     - Format for agent consumption   │
    └──────────────────────────────────────┘
           ↓
    ┌──────────────────────────────────────┐
    │  SPAWN STORY ARCHITECT AGENT         │
    │  (Creative work with prepared ctx)   │
    │                                      │
    │  Agent receives:                     │
    │  - Full AnalysisResult               │
    │  - StoryComponents                   │
    │  - User intent/preferences           │
    │                                      │
    │  Agent creates:                      │
    │  - Narrative structure               │
    │  - Chapter scripts                   │
    │  - Voice direction markers           │
    └──────────────────────────────────────┘
           ↓
    Return story to frontend

This is the CORRECT architecture per user feedback.
No MCP tools for infrastructure - that's backend work.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable

from ..models.contracts import (
    AnalysisResult,
    ChapterScript,
    IntentResult,
    NarrativeResult,
    validate_analysis_result,
)
from .analysis import AnalysisService
from .repository import RepositoryService


class PipelineStage(str, Enum):
    """Stages of the story generation pipeline."""

    VALIDATING = "validating"
    PACKAGING = "packaging"
    ANALYZING = "analyzing"
    PREPARING_CONTEXT = "preparing_context"
    GENERATING_NARRATIVE = "generating_narrative"
    SYNTHESIZING_AUDIO = "synthesizing_audio"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineEvent:
    """Event emitted during pipeline execution for progress tracking."""

    event_id: str
    stage: PipelineStage
    progress: int  # 0-100
    message: str
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization (SSE/WebSocket)."""
        return {
            "event_id": self.event_id,
            "stage": self.stage.value,
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp,
            "data": self.data,
            "error": self.error,
        }


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""

    # Timeouts
    package_timeout: int = 300  # 5 minutes for large repos
    analysis_timeout: int = 60  # 1 minute
    narrative_timeout: int = 120  # 2 minutes for agent

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0

    # Agent settings
    agent_model: str = "opus"  # opus for creative work
    max_narrative_turns: int = 10

    # Audio settings
    enable_audio: bool = True
    voice_id: str = ""  # ElevenLabs voice ID


@dataclass
class StoryGenerationRequest:
    """Request to generate a story from a repository."""

    github_url: str
    user_id: str | None = None

    # Intent (from chat or defaults)
    intent_category: str = "architecture"
    expertise_level: str = "intermediate"
    focus_areas: list[str] = field(default_factory=list)

    # Narrative preferences
    narrative_style: str = "documentary"
    target_duration_minutes: int = 10


@dataclass
class StoryGenerationResult:
    """Result of story generation."""

    success: bool
    story_id: str
    title: str = ""
    narrative: NarrativeResult | None = None
    analysis: AnalysisResult | None = None
    audio_url: str | None = None
    error: str | None = None
    duration_seconds: float = 0.0


class PipelineService:
    """Orchestrates the complete story generation pipeline.

    This is the main service called by FastAPI endpoints.
    It coordinates backend services and agent invocation.

    Usage:
        pipeline = PipelineService()

        # Stream progress events
        async for event in pipeline.generate_story_stream(request):
            await websocket.send_json(event.to_dict())

        # Or get final result
        result = await pipeline.generate_story(request)
    """

    def __init__(
        self,
        repository_service: RepositoryService | None = None,
        analysis_service: AnalysisService | None = None,
        config: PipelineConfig | None = None,
    ):
        """Initialize the pipeline service.

        Args:
            repository_service: Service for packaging repos (creates if not provided)
            analysis_service: Service for analyzing code (creates if not provided)
            config: Pipeline configuration
        """
        self.repository_service = repository_service or RepositoryService()
        self.analysis_service = analysis_service or AnalysisService()
        self.config = config or PipelineConfig()
        self._cancelled = False

    def _emit_event(
        self,
        stage: PipelineStage,
        progress: int,
        message: str,
        data: dict | None = None,
        error: str | None = None,
    ) -> PipelineEvent:
        """Create a pipeline event."""
        return PipelineEvent(
            event_id=str(uuid.uuid4()),
            stage=stage,
            progress=progress,
            message=message,
            timestamp=datetime.utcnow().isoformat() + "Z",
            data=data or {},
            error=error,
        )

    def cancel(self) -> None:
        """Cancel the pipeline execution."""
        self._cancelled = True

    async def generate_story_stream(
        self,
        request: StoryGenerationRequest,
    ) -> AsyncGenerator[PipelineEvent, None]:
        """Generate a story with streaming progress events.

        This is the preferred method for real-time UI updates.
        Events are yielded as each stage completes.

        Args:
            request: The story generation request

        Yields:
            PipelineEvent for each stage transition
        """
        story_id = str(uuid.uuid4())
        self._cancelled = False

        try:
            # Stage 1: Validation
            yield self._emit_event(
                PipelineStage.VALIDATING,
                5,
                "Validating GitHub URL...",
                {"github_url": request.github_url},
            )

            parsed = self.repository_service.parse_github_url(request.github_url)
            if not parsed:
                yield self._emit_event(
                    PipelineStage.FAILED,
                    0,
                    "Invalid GitHub URL",
                    error=f"Could not parse: {request.github_url}",
                )
                return

            owner, repo = parsed

            if self._cancelled:
                yield self._emit_event(
                    PipelineStage.FAILED, 0, "Pipeline cancelled"
                )
                return

            # Stage 2: Package Repository (BACKEND - no agent)
            yield self._emit_event(
                PipelineStage.PACKAGING,
                10,
                f"Packaging {owner}/{repo} with Repomix...",
                {"repository": f"{owner}/{repo}"},
            )

            package_result = await self.repository_service.package(
                github_url=request.github_url,
                output_format="markdown",
            )

            if not package_result.success:
                yield self._emit_event(
                    PipelineStage.FAILED,
                    0,
                    "Repository packaging failed",
                    error=package_result.error,
                )
                return

            yield self._emit_event(
                PipelineStage.PACKAGING,
                30,
                f"Packaged {package_result.file_count} files ({package_result.estimated_tokens:,} tokens)",
                {
                    "file_count": package_result.file_count,
                    "estimated_tokens": package_result.estimated_tokens,
                    "artifact_path": package_result.artifact_path,
                },
            )

            if self._cancelled:
                yield self._emit_event(
                    PipelineStage.FAILED, 0, "Pipeline cancelled"
                )
                return

            # Stage 3: Analyze Repository (BACKEND - no agent)
            yield self._emit_event(
                PipelineStage.ANALYZING,
                40,
                "Analyzing code structure and patterns...",
            )

            analysis_result = self.analysis_service.analyze(
                packaged_content=package_result.packaged_content,
                github_url=request.github_url,
                focus_areas=request.focus_areas,
            )

            # Validate analysis
            is_valid, error_msg = validate_analysis_result(analysis_result)
            if not is_valid:
                yield self._emit_event(
                    PipelineStage.FAILED,
                    0,
                    "Analysis validation failed",
                    error=error_msg,
                )
                return

            yield self._emit_event(
                PipelineStage.ANALYZING,
                55,
                f"Found {len(analysis_result.frameworks)} frameworks, {len(analysis_result.design_patterns)} patterns",
                {
                    "primary_language": analysis_result.primary_language,
                    "frameworks": analysis_result.frameworks,
                    "patterns": analysis_result.design_patterns,
                    "chapters": len(analysis_result.story_components.chapters),
                },
            )

            if self._cancelled:
                yield self._emit_event(
                    PipelineStage.FAILED, 0, "Pipeline cancelled"
                )
                return

            # Stage 4: Prepare Agent Context (BACKEND)
            yield self._emit_event(
                PipelineStage.PREPARING_CONTEXT,
                60,
                "Preparing context for Story Architect...",
            )

            agent_context = self._build_agent_context(
                request=request,
                analysis=analysis_result,
            )

            yield self._emit_event(
                PipelineStage.PREPARING_CONTEXT,
                65,
                "Context prepared, ready for narrative generation",
                {"context_size": len(agent_context)},
            )

            # Stage 5: Generate Narrative (AGENT - creative work)
            yield self._emit_event(
                PipelineStage.GENERATING_NARRATIVE,
                70,
                "Story Architect generating narrative...",
            )

            # This is where we spawn the agent with prepared context
            narrative_result = await self._generate_narrative(
                context=agent_context,
                analysis=analysis_result,
                request=request,
            )

            yield self._emit_event(
                PipelineStage.GENERATING_NARRATIVE,
                90,
                f"Generated {len(narrative_result.chapters)} chapters",
                {
                    "title": narrative_result.title,
                    "chapters": len(narrative_result.chapters),
                    "duration_seconds": narrative_result.estimated_duration_seconds,
                },
            )

            # Stage 6: Audio Synthesis (optional)
            audio_url = None
            if self.config.enable_audio and narrative_result.chapters:
                yield self._emit_event(
                    PipelineStage.SYNTHESIZING_AUDIO,
                    92,
                    "Synthesizing audio narration...",
                )
                # TODO: Implement audio synthesis via Voice Director agent
                # For now, skip audio
                yield self._emit_event(
                    PipelineStage.SYNTHESIZING_AUDIO,
                    98,
                    "Audio synthesis skipped (not implemented yet)",
                )

            # Stage 7: Complete
            yield self._emit_event(
                PipelineStage.COMPLETED,
                100,
                "Story generation complete!",
                {
                    "story_id": story_id,
                    "title": narrative_result.title,
                    "chapters": len(narrative_result.chapters),
                    "total_duration_seconds": narrative_result.estimated_duration_seconds,
                },
            )

        except Exception as e:
            yield self._emit_event(
                PipelineStage.FAILED,
                0,
                f"Pipeline error: {type(e).__name__}",
                error=str(e),
            )

    async def generate_story(
        self,
        request: StoryGenerationRequest,
    ) -> StoryGenerationResult:
        """Generate a story and return the final result.

        This is simpler than streaming but doesn't provide progress updates.

        Args:
            request: The story generation request

        Returns:
            StoryGenerationResult with narrative and metadata
        """
        story_id = str(uuid.uuid4())
        last_event: PipelineEvent | None = None

        async for event in self.generate_story_stream(request):
            last_event = event

            if event.stage == PipelineStage.FAILED:
                return StoryGenerationResult(
                    success=False,
                    story_id=story_id,
                    error=event.error or event.message,
                )

        if not last_event or last_event.stage != PipelineStage.COMPLETED:
            return StoryGenerationResult(
                success=False,
                story_id=story_id,
                error="Pipeline did not complete",
            )

        # Reconstruct result from final event
        return StoryGenerationResult(
            success=True,
            story_id=story_id,
            title=last_event.data.get("title", "Untitled Story"),
            duration_seconds=last_event.data.get("total_duration_seconds", 0),
        )

    def _build_agent_context(
        self,
        request: StoryGenerationRequest,
        analysis: AnalysisResult,
    ) -> str:
        """Build the context string to pass to Story Architect agent.

        This prepares ALL the information the agent needs so it can focus
        purely on creative narrative generation.

        The agent receives this as input and doesn't need to call ANY
        infrastructure tools - all that work is already done.
        """
        summary = self.analysis_service.generate_summary(analysis)

        context_parts = [
            "# Story Generation Context\n",
            "You have been provided with a complete analysis of a GitHub repository.",
            "Your task is to create an engaging narrative story about this codebase.",
            "All analysis is complete - focus on creative storytelling.\n",
            "## User Request\n",
            f"- **Repository**: {request.github_url}",
            f"- **Intent**: {request.intent_category}",
            f"- **Expertise Level**: {request.expertise_level}",
            f"- **Narrative Style**: {request.narrative_style}",
            f"- **Target Duration**: {request.target_duration_minutes} minutes",
        ]

        if request.focus_areas:
            context_parts.append(f"- **Focus Areas**: {', '.join(request.focus_areas)}")

        context_parts.append("\n" + summary)

        # Add story components
        if analysis.story_components.chapters:
            context_parts.append("\n## Suggested Chapter Structure\n")
            for chapter in analysis.story_components.chapters:
                context_parts.append(f"### {chapter.title}")
                context_parts.append(f"{chapter.description}")
                if chapter.key_files:
                    context_parts.append(f"Key files: {', '.join(chapter.key_files[:3])}")
                context_parts.append("")

        # Add narrative arc
        if analysis.story_components.narrative_arc:
            context_parts.append(f"\n## Narrative Arc\n{analysis.story_components.narrative_arc}")

        # Add characters
        if analysis.story_components.characters:
            context_parts.append("\n## Code Characters\n")
            for char in analysis.story_components.characters:
                context_parts.append(f"- **{char.name}** ({char.role}): {char.description}")

        return "\n".join(context_parts)

    async def _generate_narrative(
        self,
        context: str,
        analysis: AnalysisResult,
        request: StoryGenerationRequest,
    ) -> NarrativeResult:
        """Generate narrative using Story Architect agent.

        This is where we actually invoke Claude with the prepared context.
        The agent only needs creative tools, not infrastructure tools.

        TODO: Replace with actual Claude Agent SDK invocation.
        For now, generates a placeholder narrative based on analysis.
        """
        # For now, create narrative directly from analysis
        # TODO: Actually invoke Story Architect agent with context

        chapters = []
        for i, chapter_suggestion in enumerate(analysis.story_components.chapters, 1):
            # Create script placeholder
            script = f"""
[CONVERSATIONAL] Welcome to {chapter_suggestion.title}.

{chapter_suggestion.description}

[PAUSE]

In this chapter, we'll explore how the code brings this to life.

[EMPHASIS] The developers made thoughtful choices here.

[SLOW] Let's trace through the key concepts: {', '.join(chapter_suggestion.code_concepts[:3])}.

[CONVERSATIONAL] By the end, you'll understand why this matters.
""".strip()

            chapters.append(
                ChapterScript(
                    chapter_number=i,
                    title=chapter_suggestion.title,
                    script=script,
                    estimated_seconds=request.target_duration_minutes * 60 // len(analysis.story_components.chapters) if analysis.story_components.chapters else 120,
                    transition_out="fade" if i < len(analysis.story_components.chapters) else "silence",
                )
            )

        # Create title based on analysis
        # Extract repo name from URL
        parsed = self.repository_service.parse_github_url(analysis.repo_url)
        repo_name = f"{parsed[0]}/{parsed[1]}" if parsed else "this codebase"

        if analysis.frameworks:
            title = f"The Story of {repo_name}: A {analysis.frameworks[0]} Journey"
        else:
            title = f"Inside {repo_name}: A Code Story"

        return NarrativeResult(
            title=title,
            style=request.narrative_style,  # type: ignore
            chapters=chapters,
            estimated_duration_seconds=sum(c.estimated_seconds for c in chapters),
            voice_profile_recommendation="",  # Will be set by Voice Director
        )

    @property
    def repository_name(self) -> str:
        """Helper to get repository name from analysis."""
        return ""  # Placeholder
