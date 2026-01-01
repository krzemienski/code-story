"""Repomix-based Repository Analysis Tools.

Tools for packaging and analyzing GitHub repositories using Repomix CLI.
Replaces GitHub API-based tools with a single-invocation approach.

Uses Claude Agent SDK @tool decorator pattern.

ARTIFACT PERSISTENCE:
All Repomix outputs are saved as artifacts that subsequent agents
(Story Architect, Voice Director) can access for:
- Re-reading packaged code if they need more context
- Exploring specific files mentioned in analysis
- Triple-checking their understanding before generating content
"""

import asyncio
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from claude_agent_sdk import tool

# Artifact storage directory (relative to project root or configurable)
ARTIFACT_DIR = os.environ.get("CODESTORY_ARTIFACT_DIR", "/tmp/codestory_artifacts")


def _ensure_artifact_dir():
    """Ensure artifact directory exists."""
    Path(ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)
    return ARTIFACT_DIR


def _hash_url(url: str) -> str:
    """Create a short hash of a URL for caching keys."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract owner/repo from GitHub URL."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) >= 2:
        return path_parts[0], path_parts[1].replace(".git", "")
    return None


def _get_artifact_path(github_url: str, artifact_type: str, ext: str = "json") -> str:
    """Generate consistent artifact path for a repository.

    Artifacts are stored as:
    {ARTIFACT_DIR}/{owner}_{repo}/{artifact_type}.{ext}
    """
    parsed = _parse_github_url(github_url)
    if not parsed:
        return os.path.join(ARTIFACT_DIR, f"unknown_{_hash_url(github_url)}", f"{artifact_type}.{ext}")

    owner, repo = parsed
    repo_dir = os.path.join(ARTIFACT_DIR, f"{owner}_{repo}")
    Path(repo_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(repo_dir, f"{artifact_type}.{ext}")


def _save_artifact(github_url: str, artifact_type: str, content: str | dict, ext: str = "json") -> str:
    """Save an artifact and return its path.

    This enables later agents to:
    - Load packaged repository content
    - Access analysis results
    - Explore code for additional context
    """
    _ensure_artifact_dir()
    path = _get_artifact_path(github_url, artifact_type, ext)

    if isinstance(content, dict):
        content = json.dumps(content, indent=2)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


@tool(
    name="package_repository",
    description="Package a GitHub repository using Repomix CLI into an AI-friendly format. "
    "Returns the packaged content with token count and file statistics. "
    "This is the primary tool for repository analysis - use it FIRST before any analysis.",
    input_schema={
        "github_url": "GitHub repository URL (e.g., https://github.com/owner/repo)",
        "output_format": "Output format: 'markdown' (default), 'xml', or 'json'",
        "include_patterns": "Optional list of glob patterns to include (e.g., ['src/**', '*.py'])",
        "exclude_patterns": "Optional list of patterns to exclude (e.g., ['*.test.*', 'node_modules/**'])",
        "remove_comments": "Whether to remove code comments for smaller output (default: false)",
    },
)
async def package_repository(args: dict) -> dict:
    """Package a repository using Repomix CLI.

    This tool invokes the Repomix CLI to package an entire GitHub repository
    into a single AI-friendly file. The packaged output contains all file
    contents with clear separators, making it ideal for LLM analysis.
    """
    github_url = args.get("github_url", "")
    output_format = args.get("output_format", "markdown")
    include_patterns = args.get("include_patterns", [])
    exclude_patterns = args.get("exclude_patterns", [])
    remove_comments = args.get("remove_comments", False)

    # Validate GitHub URL
    parsed = _parse_github_url(github_url)
    if not parsed:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "Invalid GitHub URL. Expected format: https://github.com/owner/repo",
                "url": github_url
            })}],
            "isError": True,
        }

    owner, repo = parsed

    # Create temp file for output
    ext_map = {"markdown": "md", "xml": "xml", "json": "json"}
    ext = ext_map.get(output_format, "md")
    temp_output = tempfile.mktemp(suffix=f".{ext}", prefix=f"repomix_{_hash_url(github_url)}_")

    # Build repomix command
    cmd = [
        "npx", "repomix",
        "--remote", f"{owner}/{repo}",
        "--style", output_format,
        "-o", temp_output,
    ]

    # Add include patterns
    if include_patterns:
        cmd.extend(["--include", ",".join(include_patterns)])

    # Add exclude patterns
    if exclude_patterns:
        cmd.extend(["-i", ",".join(exclude_patterns)])

    # Add comment removal flag
    if remove_comments:
        cmd.append("--remove-comments")

    try:
        # Execute repomix
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=300  # 5 minute timeout for large repos
        )

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": f"Repomix failed: {error_msg}",
                    "command": " ".join(cmd),
                    "return_code": process.returncode
                })}],
                "isError": True,
            }

        # Read packaged content
        if not os.path.exists(temp_output):
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": "Repomix did not produce output file",
                    "expected_path": temp_output
                })}],
                "isError": True,
            }

        with open(temp_output, "r", encoding="utf-8") as f:
            packaged_content = f.read()

        # Extract statistics from repomix output (Repomix uses ## File: format)
        file_count = len(re.findall(r"^## File:|^# File:|^<file path=", packaged_content, re.MULTILINE))

        # Estimate token count (rough: ~4 chars per token)
        estimated_tokens = len(packaged_content) // 4

        # Parse stdout for actual stats if available
        stdout_text = stdout.decode() if stdout else ""

        # SAVE ARTIFACT for later agents (Story Architect, Voice Director)
        # This enables them to re-read code if they need more context
        artifact_path = _save_artifact(
            github_url,
            "packaged_repository",
            packaged_content,
            ext=ext
        )

        result = {
            "success": True,
            "repository": f"{owner}/{repo}",
            "github_url": github_url,
            "output_format": output_format,
            "artifact_path": artifact_path,  # Persistent artifact for later agents
            "packaged_content": packaged_content,
            "statistics": {
                "file_count": file_count,
                "character_count": len(packaged_content),
                "estimated_tokens": estimated_tokens,
                "within_context_limit": estimated_tokens < 150000,  # Claude's context limit
            },
            "repomix_output": stdout_text[:1000] if stdout_text else None,
            "artifact_info": {
                "path": artifact_path,
                "note": "Later agents can use get_repository_artifact to re-read this content",
            }
        }

        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    except asyncio.TimeoutError:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "Repomix timed out after 5 minutes",
                "repository": f"{owner}/{repo}"
            })}],
            "isError": True,
        }
    except FileNotFoundError:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "Repomix CLI not found. Install with: npm install -g repomix",
                "install_command": "npm install -g repomix"
            })}],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": f"Unexpected error: {str(e)}",
                "type": type(e).__name__
            })}],
            "isError": True,
        }
    finally:
        # Clean up temp file (artifact is saved separately)
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass


@tool(
    name="analyze_packaged_repository",
    description="Extract structured analysis from Repomix-packaged repository content. "
    "Identifies directory structure, entry points, frameworks, and architectural patterns. "
    "Use this AFTER package_repository to analyze the codebase.",
    input_schema={
        "packaged_content": "The packaged repository content from package_repository",
        "focus_areas": "Optional list of areas to focus on (e.g., ['architecture', 'api', 'data'])",
    },
)
async def analyze_packaged_repository(args: dict) -> dict:
    """Analyze packaged repository content to extract structure and patterns.

    This tool parses the Repomix output to identify:
    - Directory structure
    - Entry points (main files, app initialization)
    - Frameworks and libraries
    - Architectural patterns (MVC, layered, microservices, etc.)
    """
    packaged_content = args.get("packaged_content", "")
    focus_areas = args.get("focus_areas", [])

    if not packaged_content:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "No packaged content provided. Run package_repository first."
            })}],
            "isError": True,
        }

    try:
        # Extract file paths from packaged content
        # Supports both markdown (## File: path) and XML (<file path="path">) formats
        file_paths = []

        # Markdown format (Repomix uses ## File: not # File:)
        md_files = re.findall(r"^## File: (.+)$", packaged_content, re.MULTILINE)
        file_paths.extend(md_files)

        # Also try single # for backwards compatibility
        if not md_files:
            md_files = re.findall(r"^# File: (.+)$", packaged_content, re.MULTILINE)
            file_paths.extend(md_files)

        # XML format
        xml_files = re.findall(r'<file path="([^"]+)">', packaged_content)
        file_paths.extend(xml_files)

        # Build directory structure
        directories = set()
        for path in file_paths:
            parts = Path(path).parts
            for i in range(1, len(parts)):
                directories.add("/".join(parts[:i]))

        # Identify entry points
        entry_point_patterns = [
            r"main\.py", r"app\.py", r"server\.py", r"index\.ts", r"index\.js",
            r"manage\.py", r"run\.py", r"wsgi\.py", r"asgi\.py",
            r"src/main\.", r"src/index\.", r"src/app\.",
        ]
        entry_points = []
        for path in file_paths:
            for pattern in entry_point_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    entry_points.append(path)
                    break

        # Also check for __main__ in content
        if "__main__" in packaged_content:
            main_matches = re.findall(r"# File: ([^\n]+)\n[^#]*if __name__", packaged_content)
            entry_points.extend(main_matches)

        entry_points = list(set(entry_points))

        # Detect frameworks
        framework_indicators = {
            "FastAPI": [r"from fastapi import", r"FastAPI\(\)"],
            "Django": [r"from django", r"django\.conf", r"manage\.py.*django"],
            "Flask": [r"from flask import", r"Flask\(__name__\)"],
            "Express": [r"require\(['\"]express['\"]", r"import express"],
            "React": [r"from ['\"]react['\"]", r"import React", r"useState", r"useEffect"],
            "Next.js": [r"from ['\"]next", r"getServerSideProps", r"getStaticProps"],
            "Vue": [r"from ['\"]vue['\"]", r"createApp", r"defineComponent"],
            "NestJS": [r"@nestjs/", r"@Module\(", r"@Controller\("],
            "SQLAlchemy": [r"from sqlalchemy", r"declarative_base", r"Column\("],
            "Prisma": [r"@prisma/client", r"PrismaClient"],
            "pytest": [r"import pytest", r"@pytest\."],
            "Jest": [r"describe\(", r"it\(", r"expect\("],
        }

        detected_frameworks = []
        for framework, patterns in framework_indicators.items():
            for pattern in patterns:
                if re.search(pattern, packaged_content):
                    detected_frameworks.append(framework)
                    break

        # Detect primary language
        extensions = [Path(p).suffix for p in file_paths if Path(p).suffix]
        ext_counts = {}
        for ext in extensions:
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        language_map = {
            ".py": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript (React)",
            ".js": "JavaScript",
            ".jsx": "JavaScript (React)",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".rb": "Ruby",
            ".php": "PHP",
        }

        primary_language = None
        if ext_counts:
            top_ext = max(ext_counts, key=ext_counts.get)
            primary_language = language_map.get(top_ext, top_ext)

        # Detect architectural patterns
        architectural_patterns = []

        # MVC pattern
        if any(d in directories for d in ["models", "views", "controllers"]) or \
           any(d in directories for d in ["model", "view", "controller"]):
            architectural_patterns.append("MVC")

        # Layered architecture
        if any(d in directories for d in ["domain", "application", "infrastructure"]):
            architectural_patterns.append("Clean Architecture")
        elif any(d in directories for d in ["services", "repositories", "entities"]):
            architectural_patterns.append("Layered Architecture")

        # API-centric
        if any(d in directories for d in ["routes", "routers", "api", "endpoints"]):
            architectural_patterns.append("REST API")

        # Component-based (frontend)
        if any(d in directories for d in ["components", "pages", "layouts"]):
            architectural_patterns.append("Component-Based")

        # Monorepo
        if any(d in directories for d in ["packages", "apps", "libs"]):
            architectural_patterns.append("Monorepo")

        # Identify core modules
        core_modules = []
        core_patterns = ["src/", "lib/", "core/", "app/", "pkg/"]
        for path in file_paths:
            for pattern in core_patterns:
                if path.startswith(pattern):
                    module = path.split("/")[1] if "/" in path else path
                    if module not in core_modules and not module.startswith("."):
                        core_modules.append(module)
                    break

        core_modules = core_modules[:20]  # Limit to top 20

        result = {
            "success": True,
            "structure": {
                "total_files": len(file_paths),
                "directories": sorted(directories)[:50],  # Top 50 dirs
                "file_extensions": dict(sorted(ext_counts.items(), key=lambda x: -x[1])[:10]),
            },
            "entry_points": entry_points[:10],
            "frameworks": detected_frameworks,
            "primary_language": primary_language,
            "architectural_patterns": architectural_patterns,
            "core_modules": core_modules,
            "analysis_metadata": {
                "content_length": len(packaged_content),
                "focus_areas": focus_areas,
            }
        }

        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": f"Analysis failed: {str(e)}",
                "type": type(e).__name__
            })}],
            "isError": True,
        }


@tool(
    name="identify_story_components",
    description="Transform repository analysis into narrative story components. "
    "Maps technical structures to chapters and narrative hooks for the Story Architect. "
    "Use this AFTER analyze_packaged_repository.",
    input_schema={
        "analysis": "The analysis result from analyze_packaged_repository",
        "intent": "Optional user intent from Intent Agent (category, focus_areas, style)",
        "narrative_style": "Preferred narrative style: 'educational', 'dramatic', 'technical', 'casual'",
    },
)
async def identify_story_components(args: dict) -> dict:
    """Transform technical analysis into narrative story components.

    This tool maps repository structures to narrative elements:
    - Entry points -> "The Beginning" / "Where It All Starts"
    - Core modules -> "The Heart of the System"
    - External dependencies -> "The Allies" / "Standing on Shoulders"
    - Error handling -> "Handling the Unexpected"
    - Tests -> "Ensuring Quality"
    """
    analysis = args.get("analysis", {})
    intent = args.get("intent", {})
    narrative_style = args.get("narrative_style", "educational")

    if not analysis:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "No analysis provided. Run analyze_packaged_repository first."
            })}],
            "isError": True,
        }

    try:
        # Extract analysis components
        entry_points = analysis.get("entry_points", [])
        frameworks = analysis.get("frameworks", [])
        patterns = analysis.get("architectural_patterns", [])
        core_modules = analysis.get("core_modules", [])
        primary_language = analysis.get("primary_language", "Unknown")

        # Build chapters based on what's present
        chapters = []
        narrative_hooks = []

        # Chapter 1: The Beginning (Entry Points)
        if entry_points:
            main_entry = entry_points[0]
            chapters.append({
                "number": 1,
                "title": "Where It All Begins",
                "focus": "entry_points",
                "key_files": entry_points[:3],
                "narrative_hook": f"Our journey starts at {main_entry}, where the application comes to life.",
                "learning_goals": ["Understand how the application initializes", "Trace the startup flow"],
            })
            narrative_hooks.append(f"The application awakens in {main_entry}")

        # Chapter 2: The Architecture (Patterns)
        if patterns:
            pattern_desc = " and ".join(patterns[:2])
            chapters.append({
                "number": 2,
                "title": "The Architecture",
                "focus": "patterns",
                "patterns": patterns,
                "narrative_hook": f"Built on {pattern_desc}, the codebase reveals its structure.",
                "learning_goals": [f"Understand the {p} pattern" for p in patterns[:3]],
            })
            narrative_hooks.append(f"A {pattern_desc} architecture emerges")

        # Chapter 3: The Tools of Trade (Frameworks)
        if frameworks:
            main_framework = frameworks[0]
            chapters.append({
                "number": 3,
                "title": "The Tools of the Trade",
                "focus": "frameworks",
                "frameworks": frameworks,
                "narrative_hook": f"Powered by {main_framework}, the developers chose their weapons wisely.",
                "learning_goals": [f"Learn how {f} is used" for f in frameworks[:3]],
            })
            narrative_hooks.append(f"{main_framework} powers the application")

        # Chapter 4: The Core (Main Modules)
        if core_modules:
            chapters.append({
                "number": 4,
                "title": "The Heart of the System",
                "focus": "core_modules",
                "modules": core_modules[:5],
                "narrative_hook": "At the core, these modules work in harmony.",
                "learning_goals": ["Understand the main components", "See how modules interact"],
            })
            narrative_hooks.append(f"Core modules: {', '.join(core_modules[:3])}")

        # Chapter 5: Bringing It Together
        chapters.append({
            "number": len(chapters) + 1,
            "title": "Bringing It Together",
            "focus": "synthesis",
            "narrative_hook": f"Written in {primary_language}, this codebase tells a story of craftsmanship.",
            "learning_goals": ["See the big picture", "Understand the design decisions"],
        })

        # Apply narrative style adjustments
        style_modifiers = {
            "educational": {"tone": "instructive", "pace": "measured", "detail_level": "high"},
            "dramatic": {"tone": "engaging", "pace": "dynamic", "detail_level": "medium"},
            "technical": {"tone": "precise", "pace": "steady", "detail_level": "very_high"},
            "casual": {"tone": "friendly", "pace": "relaxed", "detail_level": "medium"},
        }
        style_config = style_modifiers.get(narrative_style, style_modifiers["educational"])

        # Key concepts to cover
        key_concepts = []
        if frameworks:
            key_concepts.extend([f"{f} framework" for f in frameworks[:3]])
        if patterns:
            key_concepts.extend([f"{p} pattern" for p in patterns[:2]])
        key_concepts.append(f"{primary_language} programming")

        result = {
            "success": True,
            "story_components": {
                "chapters": chapters,
                "narrative_hooks": narrative_hooks,
                "key_concepts": key_concepts[:10],
                "total_chapters": len(chapters),
            },
            "style_config": style_config,
            "metadata": {
                "narrative_style": narrative_style,
                "primary_language": primary_language,
                "intent_category": intent.get("category", "exploration"),
            }
        }

        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": f"Story component identification failed: {str(e)}",
                "type": type(e).__name__
            })}],
            "isError": True,
        }


@tool(
    name="generate_analysis_summary",
    description="Generate a human-readable summary of repository analysis for the Story Architect. "
    "Combines all analysis into a narrative-ready format. "
    "Use this as the FINAL step before passing to Story Architect.",
    input_schema={
        "github_url": "GitHub repository URL (for artifact persistence)",
        "analysis": "The analysis result from analyze_packaged_repository",
        "story_components": "The story components from identify_story_components",
        "include_recommendations": "Whether to include recommendations (default: true)",
    },
)
async def generate_analysis_summary(args: dict) -> dict:
    """Generate a comprehensive summary for the Story Architect agent.

    This tool creates a narrative-ready summary that includes:
    - Repository overview
    - Key findings
    - Story structure recommendations
    - Technical highlights worth emphasizing
    """
    github_url = args.get("github_url", "")
    analysis = args.get("analysis", {})
    story_components = args.get("story_components", {})
    include_recommendations = args.get("include_recommendations", True)

    if not analysis:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "No analysis provided."
            })}],
            "isError": True,
        }

    try:
        # Extract key info
        structure = analysis.get("structure", {})
        frameworks = analysis.get("frameworks", [])
        patterns = analysis.get("architectural_patterns", [])
        primary_language = analysis.get("primary_language", "Unknown")
        entry_points = analysis.get("entry_points", [])

        chapters = story_components.get("story_components", {}).get("chapters", [])
        narrative_hooks = story_components.get("story_components", {}).get("narrative_hooks", [])

        # Build summary text
        summary_parts = []

        # Overview
        summary_parts.append(f"## Repository Overview\n")
        summary_parts.append(f"- **Primary Language**: {primary_language}")
        summary_parts.append(f"- **Total Files**: {structure.get('total_files', 'Unknown')}")
        if frameworks:
            summary_parts.append(f"- **Frameworks**: {', '.join(frameworks)}")
        if patterns:
            summary_parts.append(f"- **Architecture**: {', '.join(patterns)}")

        # Key Findings
        summary_parts.append(f"\n## Key Findings\n")
        if entry_points:
            summary_parts.append(f"- Entry point: `{entry_points[0]}`")
        if frameworks:
            summary_parts.append(f"- Built with: {frameworks[0]}")
        if patterns:
            summary_parts.append(f"- Follows: {patterns[0]} pattern")

        # Story Structure
        if chapters:
            summary_parts.append(f"\n## Recommended Story Structure\n")
            for chapter in chapters:
                summary_parts.append(f"- **Chapter {chapter['number']}: {chapter['title']}** - {chapter.get('narrative_hook', '')}")

        # Narrative Hooks
        if narrative_hooks:
            summary_parts.append(f"\n## Narrative Hooks\n")
            for hook in narrative_hooks[:5]:
                summary_parts.append(f"- {hook}")

        # Recommendations
        recommendations = []
        if include_recommendations:
            if len(frameworks) > 1:
                recommendations.append("Multiple frameworks detected - consider covering integration points")
            if "Clean Architecture" in patterns or "Layered Architecture" in patterns:
                recommendations.append("Well-structured codebase - highlight separation of concerns")
            if primary_language == "Python":
                recommendations.append("Python codebase - emphasize readability and Pythonic patterns")
            if primary_language in ["TypeScript", "TypeScript (React)"]:
                recommendations.append("TypeScript used - highlight type safety benefits")
            if not patterns:
                recommendations.append("No clear architecture detected - focus on individual components")

        summary_text = "\n".join(summary_parts)

        result = {
            "success": True,
            "summary": summary_text,
            "summary_data": {
                "primary_language": primary_language,
                "frameworks": frameworks,
                "patterns": patterns,
                "total_files": structure.get("total_files", 0),
                "chapter_count": len(chapters),
            },
            "recommendations": recommendations if include_recommendations else [],
            "ready_for_story_architect": True,
        }

        # Save summary as artifact for later reference
        artifact_path = _save_artifact(
            github_url if github_url else "unknown",
            "analysis_summary",
            result,
        )
        result["artifact_path"] = artifact_path

        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": f"Summary generation failed: {str(e)}",
                "type": type(e).__name__
            })}],
            "isError": True,
        }


# =============================================================================
# ARTIFACT RETRIEVAL TOOLS
# These enable later agents (Story Architect, Voice Director) to:
# - Re-read the packaged repository if they need more context
# - Access analysis results
# - Explore specific files from the packaged content
# - Use sequential thinking to understand code deeply
# =============================================================================


@tool(
    name="get_repository_artifact",
    description="Retrieve a previously saved repository artifact (packaged content, analysis, or summary). "
    "Use this when you need to re-read the repository code for additional context. "
    "Story Architect and Voice Director agents can use this to explore code further if "
    "they don't have enough information to complete their task.",
    input_schema={
        "github_url": "GitHub repository URL that was previously analyzed",
        "artifact_type": "Type of artifact: 'packaged_repository', 'analysis', 'story_components', 'analysis_summary'",
    },
)
async def get_repository_artifact(args: dict) -> dict:
    """Retrieve a saved artifact for re-reading.

    This enables Story Architect and Voice Director agents to:
    - Re-read the full packaged repository content
    - Access stored analysis results
    - Triple-check their understanding before generating content
    """
    github_url = args.get("github_url", "")
    artifact_type = args.get("artifact_type", "packaged_repository")

    if not github_url:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "github_url is required"
            })}],
            "isError": True,
        }

    try:
        # Determine file extension based on type
        ext_map = {
            "packaged_repository": "md",  # Default format
            "analysis": "json",
            "story_components": "json",
            "analysis_summary": "json",
        }
        ext = ext_map.get(artifact_type, "json")

        # Try common formats for packaged_repository
        artifact_path = _get_artifact_path(github_url, artifact_type, ext)

        if not os.path.exists(artifact_path):
            # Try other extensions for packaged_repository
            if artifact_type == "packaged_repository":
                for try_ext in ["md", "xml", "json"]:
                    alt_path = _get_artifact_path(github_url, artifact_type, try_ext)
                    if os.path.exists(alt_path):
                        artifact_path = alt_path
                        break

        if not os.path.exists(artifact_path):
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": f"Artifact not found: {artifact_type}",
                    "github_url": github_url,
                    "searched_path": artifact_path,
                    "hint": "Run package_repository first to create artifacts"
                })}],
                "isError": True,
            }

        with open(artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse JSON if applicable
        if ext == "json":
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass  # Return as string if not valid JSON

        result = {
            "success": True,
            "artifact_type": artifact_type,
            "artifact_path": artifact_path,
            "github_url": github_url,
            "content": content,
            "content_length": len(str(content)),
        }

        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": f"Failed to retrieve artifact: {str(e)}",
                "type": type(e).__name__
            })}],
            "isError": True,
        }


@tool(
    name="explore_file_in_package",
    description="Extract and return a specific file's content from the packaged repository. "
    "Use this when you need to look at a specific file more closely. "
    "Useful for Story Architect to understand specific code patterns or for "
    "Voice Director to verify technical accuracy before narration.",
    input_schema={
        "github_url": "GitHub repository URL that was previously analyzed",
        "file_path": "Path to the file within the repository (e.g., 'src/main.py', 'lib/utils.ts')",
    },
)
async def explore_file_in_package(args: dict) -> dict:
    """Extract a specific file from the packaged repository.

    This allows agents to:
    - Look at specific files mentioned in analysis
    - Verify their understanding of specific code
    - Get more detail before generating content
    """
    github_url = args.get("github_url", "")
    file_path = args.get("file_path", "")

    if not github_url or not file_path:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "Both github_url and file_path are required"
            })}],
            "isError": True,
        }

    try:
        # Get the packaged repository artifact
        packaged_path = None
        for ext in ["md", "xml", "json"]:
            path = _get_artifact_path(github_url, "packaged_repository", ext)
            if os.path.exists(path):
                packaged_path = path
                break

        if not packaged_path:
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": "Packaged repository not found",
                    "github_url": github_url,
                    "hint": "Run package_repository first"
                })}],
                "isError": True,
            }

        with open(packaged_path, "r", encoding="utf-8") as f:
            packaged_content = f.read()

        # Extract the specific file based on format
        file_content = None

        # Try markdown format: ## File: path\n````lang\ncontent\n```` (Repomix uses 4 backticks)
        md_pattern = rf"## File: {re.escape(file_path)}\n````[^\n]*\n(.*?)````"
        md_match = re.search(md_pattern, packaged_content, re.DOTALL)
        if md_match:
            file_content = md_match.group(1)

        # Try with 3 backticks as fallback
        if not file_content:
            md_pattern = rf"## File: {re.escape(file_path)}\n```[^\n]*\n(.*?)```"
            md_match = re.search(md_pattern, packaged_content, re.DOTALL)
            if md_match:
                file_content = md_match.group(1)

        # Try single # File: format
        if not file_content:
            md_pattern = rf"# File: {re.escape(file_path)}\n```[^\n]*\n(.*?)```"
            md_match = re.search(md_pattern, packaged_content, re.DOTALL)
            if md_match:
                file_content = md_match.group(1)

        # Try XML format: <file path="path"><content>...</content></file>
        if not file_content:
            xml_pattern = rf'<file path="{re.escape(file_path)}"[^>]*>\s*<content>(.*?)</content>'
            xml_match = re.search(xml_pattern, packaged_content, re.DOTALL)
            if xml_match:
                file_content = xml_match.group(1)

        # Try simpler markdown format without fences
        if not file_content:
            simple_pattern = rf"## File: {re.escape(file_path)}\n(.*?)(?=\n## File:|$)"
            simple_match = re.search(simple_pattern, packaged_content, re.DOTALL)
            if simple_match:
                file_content = simple_match.group(1).strip()

        if not file_content:
            # List available files for debugging
            available_files = re.findall(r"## File: ([^\n]+)", packaged_content)[:20]
            if not available_files:
                available_files = re.findall(r"# File: ([^\n]+)", packaged_content)[:20]
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": f"File not found in package: {file_path}",
                    "available_files_sample": available_files,
                    "hint": "Check file path spelling or use analyze_packaged_repository to see structure"
                })}],
                "isError": True,
            }

        result = {
            "success": True,
            "file_path": file_path,
            "github_url": github_url,
            "content": file_content,
            "content_length": len(file_content),
            "lines": file_content.count("\n") + 1,
        }

        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": f"Failed to explore file: {str(e)}",
                "type": type(e).__name__
            })}],
            "isError": True,
        }


@tool(
    name="list_available_artifacts",
    description="List all available artifacts for a repository. "
    "Use this to see what analysis results are available for re-reading. "
    "Helpful when an agent needs to check what context is available before "
    "deciding to explore further.",
    input_schema={
        "github_url": "GitHub repository URL that was previously analyzed",
    },
)
async def list_available_artifacts(args: dict) -> dict:
    """List all artifacts available for a repository.

    Returns a list of what artifacts exist, enabling agents to:
    - Know what context is available
    - Decide which artifacts to re-read
    - Understand what analysis has been done
    """
    github_url = args.get("github_url", "")

    if not github_url:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": "github_url is required"
            })}],
            "isError": True,
        }

    try:
        parsed = _parse_github_url(github_url)
        if not parsed:
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": "Invalid GitHub URL"
                })}],
                "isError": True,
            }

        owner, repo = parsed
        repo_dir = os.path.join(ARTIFACT_DIR, f"{owner}_{repo}")

        if not os.path.exists(repo_dir):
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "error": "No artifacts found for this repository",
                    "github_url": github_url,
                    "hint": "Run package_repository first to create artifacts"
                })}],
                "isError": True,
            }

        artifacts = []
        for file in os.listdir(repo_dir):
            file_path = os.path.join(repo_dir, file)
            stat = os.stat(file_path)
            artifacts.append({
                "name": file,
                "path": file_path,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        result = {
            "success": True,
            "github_url": github_url,
            "repository": f"{owner}/{repo}",
            "artifact_directory": repo_dir,
            "artifacts": artifacts,
            "total_artifacts": len(artifacts),
        }

        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": json.dumps({
                "error": f"Failed to list artifacts: {str(e)}",
                "type": type(e).__name__
            })}],
            "isError": True,
        }
