"""Code Story Agent Framework.

ARCHITECTURE (Services-First):
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
Use PipelineService from codestory.services for the correct architecture.

Usage (PREFERRED - Services-First):
    from codestory.services import PipelineService, StoryGenerationRequest

    pipeline = PipelineService()
    request = StoryGenerationRequest(
        github_url="https://github.com/owner/repo",
        narrative_style="documentary",
    )

    async for event in pipeline.generate_story_stream(request):
        print(event.to_dict())

Usage (DEPRECATED - Direct Agent Client):
    from codestory.agents import CodeStoryClient

    async with CodeStoryClient() as client:
        async for update in client.generate_story(...):
            print(update)
"""

from .base import (
    # Agent Definitions (Creative Only)
    # NOTE: REPO_ANALYZER_AGENT removed - work is done by backend services
    INTENT_AGENT,
    STORY_ARCHITECT_AGENT,
    VOICE_DIRECTOR_AGENT,
    # System Prompts (Creative Only)
    INTENT_AGENT_PROMPT,
    STORY_ARCHITECT_PROMPT,
    VOICE_DIRECTOR_PROMPT,
    # Hooks (for extension)
    PRE_TOOL_HOOKS,
    POST_TOOL_HOOKS,
    validate_tool_input,
    audit_tool_execution,
    # Options Factory
    create_codestory_options,
    # Pipeline State (DEPRECATED - use codestory.services.PipelineService)
    PipelineStage,
    PipelineState,
    StoryResult,
    # Client (DEPRECATED - use codestory.services.PipelineService)
    CodeStoryClient,
)

__all__ = [
    # Agent Definitions (Creative Only)
    "INTENT_AGENT",
    "STORY_ARCHITECT_AGENT",
    "VOICE_DIRECTOR_AGENT",
    # System Prompts
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
    # Pipeline (DEPRECATED)
    "PipelineStage",
    "PipelineState",
    "StoryResult",
    # Client (DEPRECATED)
    "CodeStoryClient",
]
