"""Analysis Service - Code Structure and Pattern Detection.

This is a BACKEND SERVICE, not an agent tool.
It runs BEFORE agents are spawned to prepare context.

Architecture:
    Frontend → FastAPI → RepositoryService → AnalysisService (this) → spawn Agent

The service:
1. Parses packaged repository content
2. Identifies structure, frameworks, patterns
3. Transforms technical analysis into story components
4. Returns AnalysisResult ready for Story Architect agent

No Claude Agent SDK, no MCP - just pure Python infrastructure.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models.contracts import (
    AnalysisResult,
    ChapterSuggestion,
    CodeCharacter,
    ComponentInfo,
    StoryComponents,
)


class AnalysisService:
    """Service for analyzing packaged repository content.

    This is infrastructure code that runs BEFORE agents are spawned.
    It transforms raw code into structured analysis for agents.

    Usage:
        repo_service = RepositoryService()
        analysis_service = AnalysisService()

        # Package repository
        package_result = await repo_service.package("https://github.com/owner/repo")

        # Analyze packaged content
        analysis = analysis_service.analyze(
            packaged_content=package_result.packaged_content,
            github_url="https://github.com/owner/repo"
        )

        # analysis is now ready to pass to Story Architect agent
    """

    # Framework detection patterns
    FRAMEWORK_INDICATORS = {
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
        "ElevenLabs": [r"elevenlabs", r"ElevenLabsClient"],
        "Claude": [r"anthropic", r"claude", r"Agent\("],
    }

    # Entry point patterns
    ENTRY_POINT_PATTERNS = [
        r"main\.py",
        r"app\.py",
        r"server\.py",
        r"index\.ts",
        r"index\.js",
        r"manage\.py",
        r"run\.py",
        r"wsgi\.py",
        r"asgi\.py",
        r"src/main\.",
        r"src/index\.",
        r"src/app\.",
    ]

    # Language mapping
    LANGUAGE_MAP = {
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
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".swift": "Swift",
        ".kt": "Kotlin",
    }

    def analyze(
        self,
        packaged_content: str,
        github_url: str,
        focus_areas: list[str] | None = None,
    ) -> AnalysisResult:
        """Analyze packaged repository content.

        This is the main entry point for analysis.
        Called by backend AFTER repository is packaged, BEFORE spawning agents.

        Args:
            packaged_content: Content from RepositoryService.package()
            github_url: Original repository URL
            focus_areas: Optional areas to focus on

        Returns:
            AnalysisResult ready for Story Architect agent
        """
        if not packaged_content:
            return AnalysisResult(
                repo_url=github_url,
                primary_language=None,
                total_files=0,
            )

        # Extract file paths
        file_paths = self._extract_file_paths(packaged_content)

        # Build directory structure
        directories = self._build_directory_structure(file_paths)

        # Detect primary language
        primary_language = self._detect_primary_language(file_paths)

        # Identify entry points
        entry_points = self._identify_entry_points(file_paths, packaged_content)

        # Detect frameworks
        frameworks = self._detect_frameworks(packaged_content)

        # Detect architectural patterns
        patterns = self._detect_architectural_patterns(directories)

        # Detect external APIs
        external_apis = self._detect_external_apis(packaged_content)

        # Identify key components
        key_components = self._identify_key_components(
            file_paths, entry_points, directories
        )

        # Build story components (the narrative-ready transformation)
        story_components = self._build_story_components(
            entry_points=entry_points,
            frameworks=frameworks,
            patterns=patterns,
            directories=directories,
            primary_language=primary_language,
        )

        return AnalysisResult(
            repo_url=github_url,
            primary_language=primary_language,
            total_files=len(file_paths),
            architecture_pattern=patterns[0] if patterns else "",
            key_components=key_components,
            design_patterns=patterns,
            frameworks=frameworks,
            external_apis=external_apis,
            directory_structure=self._count_files_per_directory(file_paths),
            entry_points=entry_points,
            story_components=story_components,
        )

    def _extract_file_paths(self, content: str) -> list[str]:
        """Extract all file paths from packaged content."""
        file_paths = []

        # Markdown format (Repomix uses ## File:)
        file_paths.extend(re.findall(r"^## File: (.+)$", content, re.MULTILINE))
        file_paths.extend(re.findall(r"^# File: (.+)$", content, re.MULTILINE))

        # XML format
        file_paths.extend(re.findall(r'<file path="([^"]+)">', content))

        return list(set(file_paths))

    def _build_directory_structure(self, file_paths: list[str]) -> set[str]:
        """Build set of directories from file paths."""
        directories = set()
        for path in file_paths:
            parts = Path(path).parts
            for i in range(1, len(parts)):
                directories.add("/".join(parts[:i]))
        return directories

    def _count_files_per_directory(self, file_paths: list[str]) -> dict[str, int]:
        """Count files per top-level directory."""
        counts: dict[str, int] = {}
        for path in file_paths:
            parts = path.split("/")
            if len(parts) > 1:
                top_dir = parts[0] + "/"
                counts[top_dir] = counts.get(top_dir, 0) + 1
            else:
                counts["root"] = counts.get("root", 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1])[:20])

    def _detect_primary_language(self, file_paths: list[str]) -> str | None:
        """Detect the primary programming language."""
        extensions = [Path(p).suffix for p in file_paths if Path(p).suffix]
        if not extensions:
            return None

        ext_counts: dict[str, int] = {}
        for ext in extensions:
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        top_ext = max(ext_counts, key=ext_counts.get)  # type: ignore[arg-type]
        return self.LANGUAGE_MAP.get(top_ext, top_ext)

    def _identify_entry_points(
        self, file_paths: list[str], content: str
    ) -> list[str]:
        """Identify application entry points."""
        entry_points = []

        for path in file_paths:
            for pattern in self.ENTRY_POINT_PATTERNS:
                if re.search(pattern, path, re.IGNORECASE):
                    entry_points.append(path)
                    break

        # Check for __main__
        if "__main__" in content:
            main_matches = re.findall(
                r"# File: ([^\n]+)\n[^#]*if __name__", content
            )
            entry_points.extend(main_matches)

        return list(set(entry_points))[:10]

    def _detect_frameworks(self, content: str) -> list[str]:
        """Detect frameworks and libraries used."""
        detected = []
        for framework, patterns in self.FRAMEWORK_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    detected.append(framework)
                    break
        return detected

    def _detect_external_apis(self, content: str) -> list[str]:
        """Detect external API integrations."""
        apis = []
        api_patterns = {
            "GitHub API": r"api\.github\.com|octokit|@octokit",
            "ElevenLabs": r"eleven-labs|elevenlabs",
            "OpenAI": r"openai\.com|openai\.api|OpenAI\(",
            "Anthropic": r"anthropic\.com|anthropic\.api|Anthropic\(",
            "Stripe": r"stripe\.com|stripe\.api|Stripe\(",
            "AWS": r"aws-sdk|boto3|@aws-sdk",
            "Google Cloud": r"googleapis|google-cloud",
            "Supabase": r"supabase\.co|@supabase",
        }

        for api, pattern in api_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                apis.append(api)

        return apis

    def _detect_architectural_patterns(self, directories: set[str]) -> list[str]:
        """Detect architectural patterns from directory structure."""
        patterns = []

        # MVC
        if any(d in directories for d in ["models", "views", "controllers"]) or any(
            d in directories for d in ["model", "view", "controller"]
        ):
            patterns.append("MVC")

        # Clean Architecture
        if any(d in directories for d in ["domain", "application", "infrastructure"]):
            patterns.append("Clean Architecture")
        elif any(d in directories for d in ["services", "repositories", "entities"]):
            patterns.append("Layered Architecture")

        # API-centric
        if any(d in directories for d in ["routes", "routers", "api", "endpoints"]):
            patterns.append("REST API")

        # Component-based
        if any(d in directories for d in ["components", "pages", "layouts"]):
            patterns.append("Component-Based")

        # Monorepo
        if any(d in directories for d in ["packages", "apps", "libs"]):
            patterns.append("Monorepo")

        # Agent-based
        if any(d in directories for d in ["agents", "tools"]):
            patterns.append("Agent Architecture")

        return patterns

    def _identify_key_components(
        self,
        file_paths: list[str],
        entry_points: list[str],
        directories: set[str],
    ) -> list[ComponentInfo]:
        """Identify key components in the codebase."""
        components = []

        # Entry points are core
        for ep in entry_points[:3]:
            components.append(
                ComponentInfo(
                    name=Path(ep).stem,
                    type="module",
                    file_path=ep,
                    purpose="Application entry point",
                    importance="core",
                )
            )

        # Key directories
        important_dirs = ["src", "lib", "core", "app", "api", "services", "models"]
        for dir_name in important_dirs:
            if dir_name in directories:
                # Find representative file
                rep_file = next(
                    (f for f in file_paths if f.startswith(f"{dir_name}/")), None
                )
                if rep_file:
                    components.append(
                        ComponentInfo(
                            name=dir_name,
                            type="module",
                            file_path=rep_file,
                            purpose=f"Core {dir_name} module",
                            importance="core",
                        )
                    )

        return components[:10]

    def _build_story_components(
        self,
        entry_points: list[str],
        frameworks: list[str],
        patterns: list[str],
        directories: set[str],
        primary_language: str | None,
    ) -> StoryComponents:
        """Transform technical analysis into narrative story components.

        This is the key transformation that prepares context for the Story Architect.
        """
        chapters = []
        characters = []
        themes = []

        # Chapter 1: The Beginning
        if entry_points:
            main_entry = entry_points[0]
            chapters.append(
                ChapterSuggestion(
                    title="Where It All Begins",
                    description="How the application comes to life",
                    key_files=entry_points[:3],
                    code_concepts=["initialization", "entry point", "bootstrap"],
                )
            )
            characters.append(
                CodeCharacter(
                    name=Path(main_entry).stem,
                    role="protagonist",
                    description=f"The application awakens in {main_entry}",
                    file_path=main_entry,
                )
            )

        # Chapter 2: The Architecture
        if patterns:
            chapters.append(
                ChapterSuggestion(
                    title="The Architecture",
                    description=f"Built on {' and '.join(patterns[:2])}",
                    key_files=[],
                    code_concepts=patterns,
                )
            )
            themes.extend(patterns)

        # Chapter 3: The Tools
        if frameworks:
            chapters.append(
                ChapterSuggestion(
                    title="The Tools of the Trade",
                    description=f"Powered by {frameworks[0]}",
                    key_files=[],
                    code_concepts=[f"{f} integration" for f in frameworks[:3]],
                )
            )
            for fw in frameworks[:2]:
                characters.append(
                    CodeCharacter(
                        name=fw,
                        role="supporting",
                        description=f"{fw} provides core capabilities",
                        file_path="",
                    )
                )

        # Chapter 4: The Core
        core_dirs = [d for d in directories if d in ["src", "lib", "core", "app"]]
        if core_dirs:
            chapters.append(
                ChapterSuggestion(
                    title="The Heart of the System",
                    description="Core modules working in harmony",
                    key_files=[],
                    code_concepts=["modules", "organization", "structure"],
                )
            )

        # Chapter 5: Synthesis
        chapters.append(
            ChapterSuggestion(
                title="Bringing It Together",
                description=f"A {primary_language or 'code'} story of craftsmanship",
                key_files=[],
                code_concepts=["design decisions", "big picture"],
            )
        )

        # Build narrative arc
        if frameworks and patterns:
            narrative_arc = (
                f"A {primary_language} application built with {frameworks[0]}, "
                f"following {patterns[0]} principles"
            )
        elif frameworks:
            narrative_arc = f"A {primary_language} application powered by {frameworks[0]}"
        elif patterns:
            narrative_arc = f"A {primary_language} codebase following {patterns[0]}"
        else:
            narrative_arc = f"Exploring a {primary_language or 'code'} project"

        return StoryComponents(
            chapters=chapters,
            characters=characters,
            themes=themes,
            narrative_arc=narrative_arc,
        )

    def generate_summary(self, analysis: AnalysisResult) -> str:
        """Generate a human-readable summary of the analysis.

        This creates a markdown summary that can be included in agent context
        or displayed to users.

        Args:
            analysis: The AnalysisResult to summarize

        Returns:
            Markdown-formatted summary string
        """
        parts = []

        # Overview
        parts.append("## Repository Overview\n")
        parts.append(f"- **Primary Language**: {analysis.primary_language or 'Unknown'}")
        parts.append(f"- **Total Files**: {analysis.total_files}")
        if analysis.frameworks:
            parts.append(f"- **Frameworks**: {', '.join(analysis.frameworks)}")
        if analysis.design_patterns:
            parts.append(f"- **Architecture**: {', '.join(analysis.design_patterns)}")

        # Key Findings
        parts.append("\n## Key Findings\n")
        if analysis.entry_points:
            parts.append(f"- Entry point: `{analysis.entry_points[0]}`")
        if analysis.frameworks:
            parts.append(f"- Built with: {analysis.frameworks[0]}")
        if analysis.design_patterns:
            parts.append(f"- Follows: {analysis.design_patterns[0]} pattern")

        # Story Structure
        if analysis.story_components.chapters:
            parts.append("\n## Recommended Story Structure\n")
            for chapter in analysis.story_components.chapters:
                parts.append(f"- **{chapter.title}**: {chapter.description}")

        # Themes
        if analysis.story_components.themes:
            parts.append("\n## Themes\n")
            for theme in analysis.story_components.themes[:5]:
                parts.append(f"- {theme}")

        return "\n".join(parts)
