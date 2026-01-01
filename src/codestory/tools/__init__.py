"""Code Story Tool Handlers.

All tools use the Claude Agent SDK @tool decorator pattern.

Usage:
    from codestory.tools import create_codestory_server

    server = create_codestory_server()
    options = ClaudeAgentOptions(
        mcp_servers={"codestory": server},
        allowed_tools=["mcp__codestory__*"]
    )
"""

from claude_agent_sdk import create_sdk_mcp_server

from .analysis import analyze_code_structure, analyze_dependencies, extract_patterns
from .intent import analyze_user_intent, extract_learning_goals, parse_preferences
from .narrative import apply_style, create_narrative, generate_chapters
from .repomix import (
    analyze_packaged_repository,
    explore_file_in_package,
    generate_analysis_summary,
    get_repository_artifact,
    identify_story_components,
    list_available_artifacts,
    package_repository,
)
from .voice import generate_audio_segment, synthesize_narration, select_voice_profile

# ALL_TOOLS list for validation and programmatic access
ALL_TOOLS = [
    # Intent tools
    analyze_user_intent,
    extract_learning_goals,
    parse_preferences,
    # Repomix tools (repository analysis via Repomix CLI)
    package_repository,
    analyze_packaged_repository,
    identify_story_components,
    generate_analysis_summary,
    # Artifact retrieval tools (for Story Architect, Voice Director to re-read code)
    get_repository_artifact,
    explore_file_in_package,
    list_available_artifacts,
    # Analysis tools (code structure analysis)
    analyze_code_structure,
    analyze_dependencies,
    extract_patterns,
    # Narrative tools
    create_narrative,
    generate_chapters,
    apply_style,
    # Voice tools
    generate_audio_segment,
    synthesize_narration,
    select_voice_profile,
]


def create_codestory_server():
    """Create the Code Story MCP server with all tools."""
    return create_sdk_mcp_server(
        name="codestory",
        version="1.0.0",
        tools=[
            # Intent tools
            analyze_user_intent,
            extract_learning_goals,
            parse_preferences,
            # Repomix tools (repository analysis via Repomix CLI)
            package_repository,
            analyze_packaged_repository,
            identify_story_components,
            generate_analysis_summary,
            # Artifact retrieval tools (for Story Architect, Voice Director to re-read code)
            get_repository_artifact,
            explore_file_in_package,
            list_available_artifacts,
            # Analysis tools (code structure analysis)
            analyze_code_structure,
            analyze_dependencies,
            extract_patterns,
            # Narrative tools
            create_narrative,
            generate_chapters,
            apply_style,
            # Voice tools
            generate_audio_segment,
            synthesize_narration,
            select_voice_profile,
        ],
    )


__all__ = [
    "ALL_TOOLS",
    "create_codestory_server",
    # Intent
    "analyze_user_intent",
    "extract_learning_goals",
    "parse_preferences",
    # Repomix
    "package_repository",
    "analyze_packaged_repository",
    "identify_story_components",
    "generate_analysis_summary",
    # Artifact retrieval
    "get_repository_artifact",
    "explore_file_in_package",
    "list_available_artifacts",
    # Analysis
    "analyze_code_structure",
    "analyze_dependencies",
    "extract_patterns",
    # Narrative
    "create_narrative",
    "generate_chapters",
    "apply_style",
    # Voice
    "generate_audio_segment",
    "synthesize_narration",
    "select_voice_profile",
]
