"""Code Story Pipeline Module.

Provides high-level orchestration for the 4-agent story generation pipeline
using Claude Agent SDK. The pipeline coordinates:

1. Intent Agent → User goal analysis
2. Repo Analyzer → Repository deep dive
3. Story Architect → Narrative creation
4. Voice Director → Audio synthesis

Usage:
    from codestory.pipeline import StoryPipeline, PipelineConfig

    pipeline = StoryPipeline(config=PipelineConfig(max_retries=3))
    result = await pipeline.run(
        repo_url="https://github.com/owner/repo",
        user_message="Explain how authentication works",
    )
"""

from .orchestrator import (
    PipelineConfig,
    StoryPipeline,
    PipelineEvent,
    PipelineEventType,
    run_story_pipeline,
)

__all__ = [
    "PipelineConfig",
    "StoryPipeline",
    "PipelineEvent",
    "PipelineEventType",
    "run_story_pipeline",
]
