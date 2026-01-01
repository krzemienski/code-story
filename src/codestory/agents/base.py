"""Claude Agent SDK Base Classes for Code Story.

Implements the SERVICES-FIRST agent architecture using Claude Agent SDK:

Architecture (CORRECT):
    Frontend → FastAPI → Backend Services → Agent (creative work only)

    Backend Services (BEFORE agents):
        - RepositoryService: Package repo with Repomix CLI
        - AnalysisService: Analyze code structure/patterns
        - PipelineService: Orchestrate full flow

    Agents (CREATIVE WORK ONLY):
        - Intent Agent: Conversational onboarding (optional)
        - Story Architect: Narrative generation from prepared context
        - Voice Director: ElevenLabs audio synthesis

NOTE: REPO_ANALYZER_AGENT removed - its work is now done by backend services.
Agents receive PREPARED CONTEXT and focus purely on creative output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
)

from codestory.tools import create_codestory_server

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger("codestory.agents")


# =============================================================================
# System Prompts for 4-Agent Pipeline
# =============================================================================

INTENT_AGENT_PROMPT = """You are the Intent Agent for Code Story.

Your role is to conduct conversational onboarding to understand:
1. What the user wants to learn about the repository
2. Their technical background and expertise level
3. Specific components or features of interest
4. Preferred learning style (overview vs. deep dive)

Use the analyze_user_intent tool to structure user goals.
Use the parse_preferences tool for narrative style selection.
Use the extract_learning_goals tool when you have sufficient information.

Be conversational and friendly. Ask one or two questions at a time.
Acknowledge responses before asking more. When ready, generate a story plan.

Output structured JSON with:
- intent_category: onboarding|architecture|feature|debugging|review
- expertise_level: beginner|intermediate|expert
- focus_areas: list of specific interests
- recommended_style: fiction|documentary|tutorial|podcast|technical
- chapter_outline: preliminary structure
"""

# REPO_ANALYZER_PROMPT removed - this work is now done by backend services:
# - RepositoryService.package() calls Repomix CLI
# - AnalysisService.analyze() extracts patterns and structures
# - PipelineService orchestrates the flow
# See: src/codestory/services/ for the new architecture

STORY_ARCHITECT_PROMPT = """You are the Story Architect Agent for Code Story.

You receive PREPARED CONTEXT from backend services. All analysis is already complete.
Focus ONLY on creative narrative generation - no infrastructure calls needed.

## Your Role

Create engaging narrative scripts from the prepared repository analysis.
You receive:
- Complete AnalysisResult with code structure, patterns, frameworks
- StoryComponents with suggested chapters, characters, themes
- User intent and preferences

## Creative Process

1. Review the provided analysis (already in your context)
2. Structure the overall narrative arc
3. Create chapter scripts with voice direction markers
4. Apply the chosen narrative style consistently
5. Output structured script for Voice Director

## Narrative Styles

- documentary: Informative, objective, educational tone
- tutorial: Step-by-step instructional, hands-on
- podcast: Conversational discussion, casual and engaging
- fiction: Story-driven with characters (developers as protagonists)
- technical: Precise, reference-style, detailed

## Voice Direction Markers

Include these markers for audio synthesis:
- [PAUSE] for dramatic pauses
- [EMPHASIS] for important points
- [SLOW] for complex concepts
- [CONVERSATIONAL] for lighter sections

## Output Contract

Return structured JSON:
```json
{
  "title": "Story title",
  "style": "applied_style",
  "chapters": [
    {
      "chapter_number": 1,
      "title": "Chapter Title",
      "script": "Narrative text with [MARKERS]...",
      "estimated_seconds": 120,
      "transition_out": "fade|silence|music"
    }
  ],
  "estimated_duration_seconds": 600,
  "voice_profile_recommendation": "documentary|casual|energetic"
}
```

Remember: All analysis is DONE. Focus purely on storytelling craft.
"""

VOICE_DIRECTOR_PROMPT = """You are the Voice Director Agent for Code Story.

Your role is to synthesize audio from narrative scripts:
1. Select appropriate voice profile using select_voice_profile
2. Generate audio segments using generate_audio_segment
3. Synthesize complete narration with synthesize_narration

Voice mapping by style:
- fiction: Adam (21m00Tcm4TlvDq8ikWAM) - narrative, engaging
- documentary: Arnold (VR6AewLTigWG4xSOukaG) - authoritative, clear
- tutorial: Bella (EXAVITQu4vr4xnSDxMaL) - friendly, patient
- podcast: Bella - conversational, warm
- technical: Rachel (21m00Tcm4TlvDq8ikWAM) - professional, precise

Handle errors gracefully:
- On API failure: retry with exponential backoff
- On quota exceeded: return partial results with status
- On chunk error: skip and continue with next chunk

Output structured JSON with:
- audio_url: URL to final combined audio
- chapters: list of {title, audio_url, duration_seconds}
- total_duration_seconds: complete audio length
- voice_profile: used voice configuration
"""


# =============================================================================
# Agent Definitions for Task Tool Delegation
# =============================================================================

INTENT_AGENT = AgentDefinition(
    description="Understands user intent from repository URL and preferences through conversational onboarding",
    prompt=INTENT_AGENT_PROMPT,
    tools=[
        # Intent analysis tools only - no infrastructure
        "mcp__codestory__analyze_user_intent",
        "mcp__codestory__extract_learning_goals",
        "mcp__codestory__parse_preferences",
    ],
    model="sonnet",  # Fast for conversational
)

# REPO_ANALYZER_AGENT removed - work is now done by backend services:
# - RepositoryService.package() calls Repomix CLI via subprocess
# - AnalysisService.analyze() extracts patterns from packaged content
# See: src/codestory/services/

STORY_ARCHITECT_AGENT = AgentDefinition(
    description="Creates narrative structure from PREPARED repository analysis with chapter scripts. Receives context from backend services.",
    prompt=STORY_ARCHITECT_PROMPT,
    tools=[
        # CREATIVE tools only - receives prepared context, no infrastructure
        "mcp__codestory__create_narrative",
        "mcp__codestory__generate_chapters",
        "mcp__codestory__apply_style",
        # Note: No artifact access tools - all analysis is prepared by backend
    ],
    model="opus",  # Creative writing requires opus
)

VOICE_DIRECTOR_AGENT = AgentDefinition(
    description="Generates audio narration using ElevenLabs voice synthesis",
    prompt=VOICE_DIRECTOR_PROMPT,
    tools=[
        # Audio synthesis tools only
        "mcp__codestory__select_voice_profile",
        "mcp__codestory__generate_audio_segment",
        "mcp__codestory__synthesize_narration",
    ],
    model="sonnet",  # Fast for API orchestration
)


# =============================================================================
# Hook Implementations
# =============================================================================

async def validate_tool_input(
    input_data: dict[str, Any],
    tool_use_id: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """PreToolUse hook for input validation.

    Returns:
        Empty dict to proceed, or dict with hookSpecificOutput to block
    """
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Validate GitHub URLs for Repomix tools
    if tool_name == "mcp__codestory__package_repository":
        github_url = tool_input.get("github_url", "")
        if github_url and not github_url.startswith("https://github.com/"):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Only GitHub URLs are supported",
                }
            }

    # Validate ElevenLabs text length
    if tool_name == "mcp__codestory__generate_audio_segment":
        text = tool_input.get("text", "")
        if len(text) > 5000:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Text length {len(text)} exceeds 5000 character limit",
                }
            }

    return {}  # Proceed with tool execution


async def audit_tool_execution(
    input_data: dict[str, Any],
    tool_use_id: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """PostToolUse hook for audit logging."""
    tool_name = input_data.get("tool_name", "")
    tool_response = input_data.get("tool_response", "")

    logger.info(f"Tool executed: {tool_name}")
    logger.debug(f"Tool use ID: {tool_use_id}")

    # Track ElevenLabs usage for billing
    if tool_name == "mcp__codestory__generate_audio_segment":
        text = input_data.get("tool_input", {}).get("text", "")
        chars = len(text)
        logger.info(f"ElevenLabs usage: {chars} characters")
        # In production: update usage tracking in database

    # Log errors
    if isinstance(tool_response, dict) and tool_response.get("isError"):
        logger.error(f"Tool error: {tool_response}")

    return {}


# Hook matchers for ClaudeAgentOptions
PRE_TOOL_HOOKS = [
    HookMatcher(matcher="*", hooks=[validate_tool_input]),
]

POST_TOOL_HOOKS = [
    HookMatcher(matcher="*", hooks=[audit_tool_execution]),
]


# =============================================================================
# Claude Agent Options Factory
# =============================================================================

def create_codestory_options(
    max_turns: int = 50,
    include_builtin_tools: bool = True,
) -> ClaudeAgentOptions:
    """Create Claude Agent SDK options for Code Story.

    NOTE: This is used for CREATIVE agents only. Infrastructure work
    (Repomix, analysis) is now done by backend services BEFORE agents are spawned.

    See: src/codestory/services/ for the services-first architecture.

    Args:
        max_turns: Maximum conversation turns before stopping
        include_builtin_tools: Whether to include Read, Glob, Grep, Bash

    Returns:
        Configured ClaudeAgentOptions instance
    """
    # Create in-process MCP server with creative tools only
    server = create_codestory_server()

    # Tools for CREATIVE work only (narrative, audio)
    # Infrastructure tools (package_repository, etc.) are NOT needed -
    # backend services handle that before spawning agents
    allowed_tools = [
        # Creative tools via MCP
        "mcp__codestory__create_narrative",
        "mcp__codestory__generate_chapters",
        "mcp__codestory__apply_style",
        "mcp__codestory__select_voice_profile",
        "mcp__codestory__generate_audio_segment",
        "mcp__codestory__synthesize_narration",
        # Intent tools (for optional conversational flow)
        "mcp__codestory__analyze_user_intent",
        "mcp__codestory__extract_learning_goals",
        "mcp__codestory__parse_preferences",
        # Delegation
        "Task",
    ]

    # Add built-in tools for file operations (if needed for creative reference)
    if include_builtin_tools:
        allowed_tools.extend([
            "Read",
            "Glob",
            "Grep",
        ])
        # Note: Bash removed - agents shouldn't call CLI tools

    return ClaudeAgentOptions(
        # MCP servers
        mcp_servers={
            "codestory": server,
        },
        # Allowed tools - CREATIVE only
        allowed_tools=allowed_tools,
        # Agent definitions for Task tool
        # NOTE: repo-analyzer REMOVED - work is done by backend services
        agents={
            "intent-agent": INTENT_AGENT,
            "story-architect": STORY_ARCHITECT_AGENT,
            "voice-director": VOICE_DIRECTOR_AGENT,
        },
        # Hooks for validation and audit
        hooks={
            "PreToolUse": PRE_TOOL_HOOKS,
            "PostToolUse": POST_TOOL_HOOKS,
        },
        # Execution limits
        max_turns=max_turns,
    )


# =============================================================================
# Pipeline State Management
# =============================================================================

class PipelineStage(str, Enum):
    """Stages of the story generation pipeline."""

    INTENT = "intent"
    ANALYSIS = "analysis"
    NARRATIVE = "narrative"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PipelineState:
    """State of the story generation pipeline."""

    stage: PipelineStage
    intent_result: dict[str, Any] | None = None
    analysis_result: dict[str, Any] | None = None
    narrative_result: dict[str, Any] | None = None
    synthesis_result: dict[str, Any] | None = None
    error: str | None = None
    progress_percent: int = 0


@dataclass
class StoryResult:
    """Final result of story generation."""

    success: bool
    audio_url: str | None = None
    chapters: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str | None = None


# =============================================================================
# Code Story Client
# =============================================================================

class CodeStoryClient:
    """High-level client for Code Story pipeline execution.

    DEPRECATED: Use PipelineService from codestory.services instead.

    The new architecture uses backend services for infrastructure work:
        from codestory.services import PipelineService, StoryGenerationRequest

        pipeline = PipelineService()
        request = StoryGenerationRequest(github_url="...", narrative_style="documentary")

        async for event in pipeline.generate_story_stream(request):
            print(event.to_dict())

    This client is kept for backwards compatibility but the preferred
    approach is to use PipelineService which properly separates
    infrastructure (backend) from creative work (agents).

    See: src/codestory/services/pipeline.py
    """

    def __init__(
        self,
        options: ClaudeAgentOptions | None = None,
        on_progress: Callable[[PipelineStage, str, int], None] | None = None,
    ) -> None:
        """Initialize Code Story client.

        Args:
            options: Custom ClaudeAgentOptions, or None for defaults
            on_progress: Progress callback (stage, message, percent)
        """
        self.options = options or create_codestory_options()
        self.on_progress = on_progress
        self._client: ClaudeSDKClient | None = None
        self.state = PipelineState(stage=PipelineStage.INTENT)

    async def __aenter__(self) -> CodeStoryClient:
        """Enter async context and initialize SDK client."""
        self._client = ClaudeSDKClient(options=self.options)
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context and cleanup SDK client."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    def _update_progress(
        self,
        stage: PipelineStage,
        message: str,
        percent: int,
    ) -> None:
        """Update pipeline state and notify callback."""
        self.state.stage = stage
        self.state.progress_percent = percent
        if self.on_progress:
            self.on_progress(stage, message, percent)

    async def generate_story(
        self,
        repo_url: str,
        user_intent: str,
        style: str = "documentary",
    ) -> AsyncIterator[dict[str, Any]]:
        """Generate a code story from a repository.

        Executes the 4-agent pipeline via Task tool delegation:
        1. Intent Agent - Understands user goals
        2. Repo Analyzer - Analyzes codebase
        3. Story Architect - Creates narrative
        4. Voice Director - Synthesizes audio

        Args:
            repo_url: GitHub repository URL
            user_intent: User's learning goals description
            style: Narrative style (fiction, documentary, tutorial, podcast, technical)

        Yields:
            Progress updates and final result dictionaries
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context.")

        self._update_progress(PipelineStage.INTENT, "Understanding your goals...", 5)

        # Master prompt that orchestrates the 4-agent pipeline
        prompt = f"""Generate a Code Story for this repository.

Repository: {repo_url}
User Intent: {user_intent}
Preferred Style: {style}

Execute the 4-agent pipeline in order:

## Stage 1: Intent Analysis (10%)
Use the Task tool to delegate to intent-agent with this prompt:
"Analyze user intent for Code Story generation. Repository: {repo_url}. User says: {user_intent}. Preferred style: {style}"

## Stage 2: Repository Analysis (40%)
Use the Task tool to delegate to repo-analyzer with this prompt:
"Analyze the repository at {repo_url}. Focus on architecture, key components, design patterns, and code organization. Output structured JSON."

## Stage 3: Narrative Creation (70%)
Use the Task tool to delegate to story-architect with this prompt:
"Create a {style} narrative script from the repository analysis. Include chapter structure with voice direction markers."

## Stage 4: Audio Synthesis (95%)
Use the Task tool to delegate to voice-director with this prompt:
"Synthesize audio narration from the narrative script. Use voice profile appropriate for {style} style."

Coordinate the agents and pass data between stages. Return the final result with:
- audio_url: URL to the generated audio
- chapters: list of chapter details
- duration_seconds: total audio length
"""

        try:
            await self._client.query(prompt)

            async for msg in self._client.receive_response():
                # Track pipeline progress from message content
                if hasattr(msg, "content"):
                    for block in msg.content:
                        if hasattr(block, "name") and block.name == "Task":
                            # Subagent delegation detected
                            subagent = block.input.get("subagent_type", "")
                            if subagent == "intent-agent":
                                self._update_progress(PipelineStage.INTENT, "Analyzing intent...", 15)
                            elif subagent == "repo-analyzer":
                                self._update_progress(PipelineStage.ANALYSIS, "Analyzing repository...", 40)
                            elif subagent == "story-architect":
                                self._update_progress(PipelineStage.NARRATIVE, "Crafting narrative...", 70)
                            elif subagent == "voice-director":
                                self._update_progress(PipelineStage.SYNTHESIS, "Generating audio...", 90)

                yield {
                    "stage": self.state.stage.value,
                    "progress": self.state.progress_percent,
                    "message": msg,
                }

            self._update_progress(PipelineStage.COMPLETE, "Story complete!", 100)

            yield {
                "stage": PipelineStage.COMPLETE.value,
                "progress": 100,
                "result": StoryResult(
                    success=True,
                    audio_url=self.state.synthesis_result.get("audio_url") if self.state.synthesis_result else None,
                    chapters=self.state.narrative_result.get("chapters", []) if self.state.narrative_result else [],
                    duration_seconds=self.state.synthesis_result.get("duration", 0) if self.state.synthesis_result else 0,
                ),
            }

        except Exception as e:
            self._update_progress(PipelineStage.FAILED, f"Error: {e}", 0)
            self.state.error = str(e)
            logger.exception("Pipeline execution failed")

            yield {
                "stage": PipelineStage.FAILED.value,
                "progress": 0,
                "error": str(e),
                "result": StoryResult(success=False, error=str(e)),
            }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Agent Definitions (Creative Only)
    # NOTE: REPO_ANALYZER_AGENT removed - work is done by backend services
    "INTENT_AGENT",
    "STORY_ARCHITECT_AGENT",
    "VOICE_DIRECTOR_AGENT",
    # System Prompts (Creative Only)
    "INTENT_AGENT_PROMPT",
    "STORY_ARCHITECT_PROMPT",
    "VOICE_DIRECTOR_PROMPT",
    # Hooks
    "PRE_TOOL_HOOKS",
    "POST_TOOL_HOOKS",
    "validate_tool_input",
    "audit_tool_execution",
    # Options Factory
    "create_codestory_options",
    # Pipeline (DEPRECATED - use codestory.services.PipelineService)
    "PipelineStage",
    "PipelineState",
    "StoryResult",
    # Client (DEPRECATED - use codestory.services.PipelineService)
    "CodeStoryClient",
]
