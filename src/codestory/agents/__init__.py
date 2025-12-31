"""Code Story Agent Framework.

This module provides the 4-agent pipeline architecture using Claude Agent SDK:
- Intent Agent: Conversational onboarding to understand user goals
- Repo Analyzer Agent: Deep repository analysis with pattern detection
- Story Architect Agent: Narrative script generation with voice direction
- Voice Director Agent: ElevenLabs audio synthesis

Architecture:
    ClaudeSDKClient
      └── ClaudeAgentOptions
            ├── MCP Server (codestory) - 12 @tool functions
            ├── AgentDefinitions (4 agents via Task tool)
            └── HookMatchers (validation + audit logging)

Usage:
    from codestory.agents import CodeStoryClient, create_codestory_options

    async with CodeStoryClient() as client:
        async for update in client.generate_story(
            repo_url="https://github.com/owner/repo",
            user_intent="Understand the architecture",
            style="documentary"
        ):
            print(update)
"""

from .base import (
    # Agent Definitions (for Task tool delegation)
    INTENT_AGENT,
    REPO_ANALYZER_AGENT,
    STORY_ARCHITECT_AGENT,
    VOICE_DIRECTOR_AGENT,
    # System Prompts (for customization)
    INTENT_AGENT_PROMPT,
    REPO_ANALYZER_PROMPT,
    STORY_ARCHITECT_PROMPT,
    VOICE_DIRECTOR_PROMPT,
    # Hooks (for extension)
    PRE_TOOL_HOOKS,
    POST_TOOL_HOOKS,
    validate_tool_input,
    audit_tool_execution,
    # Options Factory
    create_codestory_options,
    # Pipeline State
    PipelineStage,
    PipelineState,
    StoryResult,
    # Client
    CodeStoryClient,
)

__all__ = [
    # Agent Definitions
    "INTENT_AGENT",
    "REPO_ANALYZER_AGENT",
    "STORY_ARCHITECT_AGENT",
    "VOICE_DIRECTOR_AGENT",
    # System Prompts
    "INTENT_AGENT_PROMPT",
    "REPO_ANALYZER_PROMPT",
    "STORY_ARCHITECT_PROMPT",
    "VOICE_DIRECTOR_PROMPT",
    # Hooks
    "PRE_TOOL_HOOKS",
    "POST_TOOL_HOOKS",
    "validate_tool_input",
    "audit_tool_execution",
    # Options Factory
    "create_codestory_options",
    # Pipeline
    "PipelineStage",
    "PipelineState",
    "StoryResult",
    # Client
    "CodeStoryClient",
]
