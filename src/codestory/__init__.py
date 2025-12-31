"""Code Story - Transform code repositories into audio narratives.

An open-source, developer-first platform that transforms code repositories
into tailored audio narratives using Claude Agent SDK multi-agent architecture.

Quick Start:
    from codestory import StoryPipeline, run_story_pipeline

    # Simple usage
    result = await run_story_pipeline(
        repo_url="https://github.com/owner/repo",
        user_message="Explain the architecture",
    )

    # Advanced usage with events
    pipeline = StoryPipeline()
    async for event in pipeline.run(repo_url, user_message):
        print(f"{event.stage}: {event.progress_percent}%")

Architecture:
    The pipeline uses 4 specialized agents coordinated via Task tool:
    1. Intent Agent (Sonnet) - User goal analysis
    2. Repo Analyzer (Opus) - Deep code analysis
    3. Story Architect (Opus) - Narrative creation
    4. Voice Director (Sonnet) - Audio synthesis
"""

__version__ = "0.1.0"

# High-level pipeline API
from codestory.pipeline import (
    PipelineConfig,
    PipelineEvent,
    PipelineEventType,
    StoryPipeline,
    run_story_pipeline,
)

# Agent framework
from codestory.agents import (
    CodeStoryClient,
    PipelineStage,
    PipelineState,
    StoryResult,
    create_codestory_options,
)

# Tool server factory
from codestory.tools import create_codestory_server

__all__ = [
    # Version
    "__version__",
    # Pipeline
    "StoryPipeline",
    "PipelineConfig",
    "PipelineEvent",
    "PipelineEventType",
    "run_story_pipeline",
    # Agents
    "CodeStoryClient",
    "PipelineStage",
    "PipelineState",
    "StoryResult",
    "create_codestory_options",
    # Tools
    "create_codestory_server",
]
