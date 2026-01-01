"""Repository Service - Repomix CLI Integration.

This is a BACKEND SERVICE, not an agent tool.
It runs BEFORE agents are spawned to prepare context.

Architecture:
    Frontend → FastAPI → RepositoryService (this) → prepare context → spawn Agent

The service:
1. Validates GitHub URLs
2. Calls Repomix CLI via subprocess
3. Stores artifacts for later reference
4. Returns packaged content ready for analysis

No Claude Agent SDK, no MCP - just pure Python infrastructure.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Configuration
ARTIFACT_DIR = os.environ.get("CODESTORY_ARTIFACT_DIR", "/tmp/codestory_artifacts")
REPOMIX_TIMEOUT = int(os.environ.get("REPOMIX_TIMEOUT", "300"))  # 5 minutes


@dataclass
class PackageResult:
    """Result from packaging a repository."""

    success: bool
    repository: str  # owner/repo
    github_url: str
    output_format: str
    artifact_path: str
    packaged_content: str
    file_count: int
    character_count: int
    estimated_tokens: int
    within_context_limit: bool
    error: str | None = None


@dataclass
class RepositoryStats:
    """Statistics about a packaged repository."""

    total_files: int = 0
    directories: list[str] = field(default_factory=list)
    file_extensions: dict[str, int] = field(default_factory=dict)
    estimated_tokens: int = 0
    within_context_limit: bool = True


class RepositoryService:
    """Service for packaging GitHub repositories using Repomix.

    This is infrastructure code that runs BEFORE agents are spawned.
    It prepares the context that agents will use for creative work.

    Usage:
        service = RepositoryService()
        result = await service.package("https://github.com/owner/repo")

        # Result contains packaged_content ready for analysis
        if result.success:
            # Pass to AnalysisService or directly to agent context
            analysis = await analysis_service.analyze(result.packaged_content)
    """

    def __init__(self, artifact_dir: str | None = None):
        """Initialize the repository service.

        Args:
            artifact_dir: Directory to store artifacts. Defaults to ARTIFACT_DIR env var.
        """
        self.artifact_dir = artifact_dir or ARTIFACT_DIR
        self._ensure_artifact_dir()

    def _ensure_artifact_dir(self) -> str:
        """Ensure artifact directory exists."""
        Path(self.artifact_dir).mkdir(parents=True, exist_ok=True)
        return self.artifact_dir

    @staticmethod
    def _hash_url(url: str) -> str:
        """Create a short hash of a URL for caching keys."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    @staticmethod
    def parse_github_url(url: str) -> tuple[str, str] | None:
        """Extract owner/repo from GitHub URL.

        Args:
            url: GitHub URL like https://github.com/owner/repo

        Returns:
            Tuple of (owner, repo) or None if invalid
        """
        parsed = urlparse(url)
        if parsed.netloc not in ("github.com", "www.github.com"):
            return None
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            return path_parts[0], path_parts[1].replace(".git", "")
        return None

    def _get_artifact_path(self, github_url: str, artifact_type: str, ext: str = "json") -> str:
        """Generate consistent artifact path for a repository.

        Artifacts are stored as:
        {artifact_dir}/{owner}_{repo}/{artifact_type}.{ext}
        """
        parsed = self.parse_github_url(github_url)
        if not parsed:
            return os.path.join(
                self.artifact_dir,
                f"unknown_{self._hash_url(github_url)}",
                f"{artifact_type}.{ext}",
            )

        owner, repo = parsed
        repo_dir = os.path.join(self.artifact_dir, f"{owner}_{repo}")
        Path(repo_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(repo_dir, f"{artifact_type}.{ext}")

    def save_artifact(
        self, github_url: str, artifact_type: str, content: str | dict, ext: str = "json"
    ) -> str:
        """Save an artifact and return its path.

        Args:
            github_url: Repository URL for organizing artifacts
            artifact_type: Type of artifact (e.g., "packaged_repository", "analysis")
            content: Content to save (string or dict)
            ext: File extension

        Returns:
            Path to saved artifact
        """
        self._ensure_artifact_dir()
        path = self._get_artifact_path(github_url, artifact_type, ext)

        if isinstance(content, dict):
            content = json.dumps(content, indent=2)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return path

    def get_artifact(self, github_url: str, artifact_type: str) -> str | dict | None:
        """Retrieve a previously saved artifact.

        Args:
            github_url: Repository URL
            artifact_type: Type of artifact to retrieve

        Returns:
            Artifact content or None if not found
        """
        # Try common extensions
        ext_map = {
            "packaged_repository": ["md", "xml", "json"],
            "analysis": ["json"],
            "story_components": ["json"],
            "analysis_summary": ["json"],
        }
        extensions = ext_map.get(artifact_type, ["json"])

        for ext in extensions:
            path = self._get_artifact_path(github_url, artifact_type, ext)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                if ext == "json":
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        return content
                return content

        return None

    def list_artifacts(self, github_url: str) -> list[dict]:
        """List all artifacts for a repository.

        Args:
            github_url: Repository URL

        Returns:
            List of artifact info dicts
        """
        parsed = self.parse_github_url(github_url)
        if not parsed:
            return []

        owner, repo = parsed
        repo_dir = os.path.join(self.artifact_dir, f"{owner}_{repo}")

        if not os.path.exists(repo_dir):
            return []

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

        return artifacts

    async def package(
        self,
        github_url: str,
        output_format: str = "markdown",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        remove_comments: bool = False,
    ) -> PackageResult:
        """Package a GitHub repository using Repomix CLI.

        This is the main entry point for repository packaging.
        Called by FastAPI backend BEFORE spawning any agents.

        Args:
            github_url: GitHub repository URL
            output_format: Output format (markdown, xml, json)
            include_patterns: Glob patterns to include
            exclude_patterns: Glob patterns to exclude
            remove_comments: Whether to strip code comments

        Returns:
            PackageResult with packaged content and metadata
        """
        # Validate GitHub URL
        parsed = self.parse_github_url(github_url)
        if not parsed:
            return PackageResult(
                success=False,
                repository="",
                github_url=github_url,
                output_format=output_format,
                artifact_path="",
                packaged_content="",
                file_count=0,
                character_count=0,
                estimated_tokens=0,
                within_context_limit=False,
                error=f"Invalid GitHub URL: {github_url}. Expected format: https://github.com/owner/repo",
            )

        owner, repo = parsed

        # Create temp file for output
        ext_map = {"markdown": "md", "xml": "xml", "json": "json"}
        ext = ext_map.get(output_format, "md")
        temp_output = tempfile.mktemp(
            suffix=f".{ext}", prefix=f"repomix_{self._hash_url(github_url)}_"
        )

        # Build repomix command
        cmd = [
            "npx",
            "repomix",
            "--remote",
            f"{owner}/{repo}",
            "--style",
            output_format,
            "-o",
            temp_output,
        ]

        if include_patterns:
            cmd.extend(["--include", ",".join(include_patterns)])

        if exclude_patterns:
            cmd.extend(["-i", ",".join(exclude_patterns)])

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
                process.communicate(), timeout=REPOMIX_TIMEOUT
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return PackageResult(
                    success=False,
                    repository=f"{owner}/{repo}",
                    github_url=github_url,
                    output_format=output_format,
                    artifact_path="",
                    packaged_content="",
                    file_count=0,
                    character_count=0,
                    estimated_tokens=0,
                    within_context_limit=False,
                    error=f"Repomix failed: {error_msg}",
                )

            # Read packaged content
            if not os.path.exists(temp_output):
                return PackageResult(
                    success=False,
                    repository=f"{owner}/{repo}",
                    github_url=github_url,
                    output_format=output_format,
                    artifact_path="",
                    packaged_content="",
                    file_count=0,
                    character_count=0,
                    estimated_tokens=0,
                    within_context_limit=False,
                    error="Repomix did not produce output file",
                )

            with open(temp_output, "r", encoding="utf-8") as f:
                packaged_content = f.read()

            # Extract statistics
            file_count = len(
                re.findall(r"^## File:|^# File:|^<file path=", packaged_content, re.MULTILINE)
            )
            estimated_tokens = len(packaged_content) // 4
            within_context_limit = estimated_tokens < 150000

            # Save artifact for later reference
            artifact_path = self.save_artifact(
                github_url, "packaged_repository", packaged_content, ext=ext
            )

            return PackageResult(
                success=True,
                repository=f"{owner}/{repo}",
                github_url=github_url,
                output_format=output_format,
                artifact_path=artifact_path,
                packaged_content=packaged_content,
                file_count=file_count,
                character_count=len(packaged_content),
                estimated_tokens=estimated_tokens,
                within_context_limit=within_context_limit,
            )

        except asyncio.TimeoutError:
            return PackageResult(
                success=False,
                repository=f"{owner}/{repo}",
                github_url=github_url,
                output_format=output_format,
                artifact_path="",
                packaged_content="",
                file_count=0,
                character_count=0,
                estimated_tokens=0,
                within_context_limit=False,
                error=f"Repomix timed out after {REPOMIX_TIMEOUT} seconds",
            )

        except FileNotFoundError:
            return PackageResult(
                success=False,
                repository=f"{owner}/{repo}",
                github_url=github_url,
                output_format=output_format,
                artifact_path="",
                packaged_content="",
                file_count=0,
                character_count=0,
                estimated_tokens=0,
                within_context_limit=False,
                error="Repomix CLI not found. Install with: npm install -g repomix",
            )

        except Exception as e:
            return PackageResult(
                success=False,
                repository=f"{owner}/{repo}" if parsed else "",
                github_url=github_url,
                output_format=output_format,
                artifact_path="",
                packaged_content="",
                file_count=0,
                character_count=0,
                estimated_tokens=0,
                within_context_limit=False,
                error=f"Unexpected error: {type(e).__name__}: {str(e)}",
            )

        finally:
            # Clean up temp file (artifact is saved separately)
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except OSError:
                    pass

    def extract_file(self, github_url: str, file_path: str) -> str | None:
        """Extract a specific file from the packaged repository.

        Args:
            github_url: Repository URL
            file_path: Path to file within repository

        Returns:
            File content or None if not found
        """
        packaged = self.get_artifact(github_url, "packaged_repository")
        if not packaged or not isinstance(packaged, str):
            return None

        # Try markdown format: ## File: path\n````lang\ncontent\n````
        patterns = [
            rf"## File: {re.escape(file_path)}\n````[^\n]*\n(.*?)````",
            rf"## File: {re.escape(file_path)}\n```[^\n]*\n(.*?)```",
            rf"# File: {re.escape(file_path)}\n```[^\n]*\n(.*?)```",
            rf"## File: {re.escape(file_path)}\n(.*?)(?=\n## File:|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, packaged, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Try XML format
        xml_pattern = rf'<file path="{re.escape(file_path)}"[^>]*>\s*<content>(.*?)</content>'
        xml_match = re.search(xml_pattern, packaged, re.DOTALL)
        if xml_match:
            return xml_match.group(1)

        return None

    def list_files(self, github_url: str) -> list[str]:
        """List all files in the packaged repository.

        Args:
            github_url: Repository URL

        Returns:
            List of file paths
        """
        packaged = self.get_artifact(github_url, "packaged_repository")
        if not packaged or not isinstance(packaged, str):
            return []

        # Find all file markers
        files = []
        files.extend(re.findall(r"^## File: (.+)$", packaged, re.MULTILINE))
        files.extend(re.findall(r"^# File: (.+)$", packaged, re.MULTILINE))
        files.extend(re.findall(r'<file path="([^"]+)">', packaged))

        return list(set(files))
