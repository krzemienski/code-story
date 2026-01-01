"""Code Analysis Tools.

Tools for analyzing repository code structure, patterns, and dependencies.
Uses Claude Agent SDK @tool decorator pattern.
"""

import ast
import json
from pathlib import Path

from claude_agent_sdk import tool


@tool(
    name="analyze_code_structure",
    description="Analyze the structure of code. "
    "Identifies modules, classes, functions, and their relationships. "
    "Can analyze either a repository path or a direct code string.",
    input_schema={
        "repo_path": "Path to the repository root (optional if code is provided)",
        "code": "Direct code string to analyze (optional if repo_path is provided)",
        "language": "Programming language (python, javascript, typescript, etc.)",
        "focus_paths": "Optional list of paths to focus analysis on (for repo_path)",
    },
)
async def analyze_code_structure(args: dict) -> dict:
    """Analyze codebase or code snippet structure and organization."""
    repo_path = args.get("repo_path", "")
    code = args.get("code", "")
    language = args.get("language", "python")
    focus_paths = args.get("focus_paths", [])

    try:
        structure = {
            "modules": [],
            "classes": [],
            "functions": [],
            "entry_points": [],
            "architecture_pattern": None,
        }

        # Direct code analysis mode
        if code:
            if language == "python":
                structure = _analyze_python_code(code)
            else:
                structure["note"] = f"Direct code analysis for {language} not yet supported"
            return {"content": [{"type": "text", "text": json.dumps(structure, indent=2)}]}

        # Repository path mode
        if repo_path:
            base_path = Path(repo_path)
            if not base_path.exists():
                return {
                    "content": [{"type": "text", "text": f"Path not found: {repo_path}"}],
                    "isError": True,
                }

            # Language-specific analysis
            if language == "python":
                structure = _analyze_python_structure(base_path, focus_paths)
            elif language in ("javascript", "typescript"):
                structure = _analyze_js_structure(base_path, focus_paths)
            else:
                structure["note"] = f"Basic analysis for {language}"

            return {"content": [{"type": "text", "text": json.dumps(structure, indent=2)}]}

        return {
            "content": [{"type": "text", "text": "Error: Either repo_path or code must be provided"}],
            "isError": True,
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Analysis error: {e!s}"}],
            "isError": True,
        }


def _analyze_python_code(code: str) -> dict:
    """Analyze a Python code string directly."""
    structure = {
        "modules": [],
        "classes": [],
        "functions": [],
        "entry_points": [],
        "architecture_pattern": None,
    }

    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                structure["classes"].append(
                    {
                        "name": node.name,
                        "module": "<snippet>",
                        "methods": [
                            n.name
                            for n in node.body
                            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                        ],
                    }
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.col_offset == 0:
                structure["functions"].append(
                    {"name": node.name, "module": "<snippet>"}
                )

    except SyntaxError as e:
        structure["error"] = f"Syntax error: {e}"

    return structure


def _analyze_python_structure(base_path: Path, focus_paths: list) -> dict:
    """Analyze Python project structure."""
    structure = {
        "modules": [],
        "classes": [],
        "functions": [],
        "entry_points": [],
        "architecture_pattern": None,
    }

    py_files = list(base_path.glob("**/*.py"))
    if focus_paths:
        py_files = [f for f in py_files if any(fp in str(f) for fp in focus_paths)]

    for py_file in py_files[:50]:  # Limit for performance
        try:
            content = py_file.read_text()
            tree = ast.parse(content)

            module_name = str(py_file.relative_to(base_path))
            structure["modules"].append(module_name)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    structure["classes"].append(
                        {
                            "name": node.name,
                            "module": module_name,
                            "methods": [
                                n.name
                                for n in node.body
                                if isinstance(n, ast.FunctionDef)
                            ],
                        }
                    )
                elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                    structure["functions"].append(
                        {"name": node.name, "module": module_name}
                    )

        except (SyntaxError, UnicodeDecodeError):
            continue

    # Detect architecture patterns
    if any("fastapi" in str(m).lower() for m in structure["modules"]):
        structure["architecture_pattern"] = "FastAPI REST API"
    elif any("django" in str(m).lower() for m in structure["modules"]):
        structure["architecture_pattern"] = "Django MVC"
    elif any("flask" in str(m).lower() for m in structure["modules"]):
        structure["architecture_pattern"] = "Flask Microframework"

    return structure


def _analyze_js_structure(base_path: Path, focus_paths: list) -> dict:
    """Analyze JavaScript/TypeScript project structure."""
    structure = {
        "modules": [],
        "components": [],
        "functions": [],
        "entry_points": [],
        "architecture_pattern": None,
    }

    # Check for framework indicators
    package_json = base_path / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "next" in deps:
                structure["architecture_pattern"] = "Next.js"
            elif "react" in deps:
                structure["architecture_pattern"] = "React SPA"
            elif "vue" in deps:
                structure["architecture_pattern"] = "Vue.js"
            elif "express" in deps:
                structure["architecture_pattern"] = "Express.js API"
        except json.JSONDecodeError:
            pass

    # Find JS/TS files
    for pattern in ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"]:
        for file in list(base_path.glob(pattern))[:30]:
            if "node_modules" in str(file):
                continue
            structure["modules"].append(str(file.relative_to(base_path)))

    return structure


@tool(
    name="analyze_dependencies",
    description="Analyze project dependencies and their relationships. "
    "Identifies direct and transitive dependencies, versions, and potential issues.",
    input_schema={
        "repo_path": "Path to the repository root",
        "include_dev": "Whether to include development dependencies (default true)",
    },
)
async def analyze_dependencies(args: dict) -> dict:
    """Analyze project dependencies."""
    repo_path = args.get("repo_path", "")
    include_dev = args.get("include_dev", True)

    try:
        base_path = Path(repo_path)
        dependencies = {"runtime": [], "development": [], "outdated": [], "security": []}

        # Python dependencies
        requirements = base_path / "requirements.txt"
        pyproject = base_path / "pyproject.toml"

        if requirements.exists():
            lines = requirements.read_text().splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    dependencies["runtime"].append({"name": line, "source": "requirements.txt"})

        if pyproject.exists():
            content = pyproject.read_text()
            if "dependencies" in content:
                dependencies["runtime"].append({"source": "pyproject.toml", "note": "See pyproject.toml for details"})

        # JavaScript dependencies
        package_json = base_path / "package.json"
        if package_json.exists():
            try:
                pkg = json.loads(package_json.read_text())
                for name, version in pkg.get("dependencies", {}).items():
                    dependencies["runtime"].append({"name": name, "version": version})
                if include_dev:
                    for name, version in pkg.get("devDependencies", {}).items():
                        dependencies["development"].append({"name": name, "version": version})
            except json.JSONDecodeError:
                pass

        return {"content": [{"type": "text", "text": json.dumps(dependencies, indent=2)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e!s}"}],
            "isError": True,
        }


@tool(
    name="extract_patterns",
    description="Extract design patterns and architectural decisions from code. "
    "Identifies common patterns like Factory, Singleton, Observer, etc.",
    input_schema={
        "repo_path": "Path to the repository root",
        "code_samples": "Optional list of specific code samples to analyze",
    },
)
async def extract_patterns(args: dict) -> dict:
    """Extract design patterns from codebase."""
    repo_path = args.get("repo_path", "")
    code_samples = args.get("code_samples", [])

    patterns = {
        "detected": [],
        "architecture": None,
        "conventions": [],
        "suggestions": [],
    }

    try:
        base_path = Path(repo_path)

        # Check for common patterns
        if (base_path / "src" / "components").exists():
            patterns["detected"].append("Component-based architecture")
        if (base_path / "src" / "services").exists():
            patterns["detected"].append("Service layer pattern")
        if (base_path / "src" / "models").exists():
            patterns["detected"].append("MVC/Model pattern")
        if (base_path / "src" / "hooks").exists():
            patterns["detected"].append("React Hooks pattern")
        if (base_path / "tests").exists() or (base_path / "test").exists():
            patterns["conventions"].append("Test-driven development")

        # Check for DI/IoC
        for py_file in list(base_path.glob("**/*.py"))[:20]:
            try:
                content = py_file.read_text()
                if "@inject" in content or "Depends(" in content:
                    patterns["detected"].append("Dependency Injection")
                    break
            except UnicodeDecodeError:
                continue

        return {"content": [{"type": "text", "text": json.dumps(patterns, indent=2)}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e!s}"}],
            "isError": True,
        }
