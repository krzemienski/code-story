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
from .github import clone_repository, get_repo_info, list_repo_files
from .intent import analyze_user_intent, extract_learning_goals, parse_preferences
from .narrative import apply_style, create_narrative, generate_chapters
from .voice import generate_audio_segment, synthesize_narration, select_voice_profile


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
            # GitHub tools
            get_repo_info,
            clone_repository,
            list_repo_files,
            # Analysis tools
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
    "create_codestory_server",
    # Intent
    "analyze_user_intent",
    "extract_learning_goals",
    "parse_preferences",
    # GitHub
    "get_repo_info",
    "clone_repository",
    "list_repo_files",
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
