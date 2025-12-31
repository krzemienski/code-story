"""GitHub API Tools.

Tools for interacting with GitHub repositories.
Uses Claude Agent SDK @tool decorator pattern.
"""

import os
from urllib.parse import urlparse

import httpx
from claude_agent_sdk import tool


@tool(
    name="get_repo_info",
    description="Get repository metadata from GitHub API. "
    "Returns repo name, description, stars, language, topics, and contributor info.",
    input_schema={
        "repo_url": "GitHub repository URL (e.g., https://github.com/owner/repo)",
    },
)
async def get_repo_info(args: dict) -> dict:
    """Fetch repository information from GitHub API."""
    repo_url = args.get("repo_url", "")

    # Parse owner/repo from URL
    parsed = urlparse(repo_url)
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 2:
        return {
            "content": [{"type": "text", "text": "Error: Invalid GitHub URL"}],
            "isError": True,
        }

    owner, repo = path_parts[0], path_parts[1]

    # GitHub API request
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json"}

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

        repo_info = {
            "name": data.get("name"),
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "language": data.get("language"),
            "topics": data.get("topics", []),
            "default_branch": data.get("default_branch"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "open_issues": data.get("open_issues_count"),
            "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
        }

        return {"content": [{"type": "text", "text": str(repo_info)}]}

    except httpx.HTTPStatusError as e:
        return {
            "content": [{"type": "text", "text": f"GitHub API error: {e.response.status_code}"}],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e!s}"}],
            "isError": True,
        }


@tool(
    name="clone_repository",
    description="Clone a GitHub repository to a temporary directory for analysis. "
    "Returns the path to the cloned repository.",
    input_schema={
        "repo_url": "GitHub repository URL",
        "branch": "Branch to clone (optional, defaults to default branch)",
        "depth": "Clone depth for shallow clone (optional, defaults to 1)",
    },
)
async def clone_repository(args: dict) -> dict:
    """Clone repository for local analysis."""
    import subprocess
    import tempfile

    repo_url = args.get("repo_url", "")
    branch = args.get("branch")
    depth = args.get("depth", 1)

    try:
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="codestory_")

        # Build git clone command
        cmd = ["git", "clone", "--depth", str(depth)]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([repo_url, temp_dir])

        # Execute clone
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            return {
                "content": [{"type": "text", "text": f"Clone failed: {result.stderr}"}],
                "isError": True,
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": str({"clone_path": temp_dir, "success": True}),
                }
            ]
        }

    except subprocess.TimeoutExpired:
        return {
            "content": [{"type": "text", "text": "Clone timed out after 120 seconds"}],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e!s}"}],
            "isError": True,
        }


@tool(
    name="list_repo_files",
    description="List files in a repository directory, optionally filtered by pattern. "
    "Returns file paths with basic metadata.",
    input_schema={
        "repo_path": "Path to the cloned repository",
        "pattern": "Optional glob pattern to filter files (e.g., '*.py', 'src/**/*.ts')",
        "max_files": "Maximum number of files to return (default 100)",
    },
)
async def list_repo_files(args: dict) -> dict:
    """List files in repository with optional filtering."""
    import glob
    from pathlib import Path

    repo_path = args.get("repo_path", "")
    pattern = args.get("pattern", "**/*")
    max_files = args.get("max_files", 100)

    try:
        base_path = Path(repo_path)
        if not base_path.exists():
            return {
                "content": [{"type": "text", "text": f"Path not found: {repo_path}"}],
                "isError": True,
            }

        # Find matching files
        files = []
        for file_path in base_path.glob(pattern):
            if file_path.is_file() and not any(
                part.startswith(".") for part in file_path.parts
            ):
                files.append(
                    {
                        "path": str(file_path.relative_to(base_path)),
                        "size": file_path.stat().st_size,
                        "extension": file_path.suffix,
                    }
                )
                if len(files) >= max_files:
                    break

        return {
            "content": [
                {
                    "type": "text",
                    "text": str({"files": files, "total": len(files)}),
                }
            ]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e!s}"}],
            "isError": True,
        }
