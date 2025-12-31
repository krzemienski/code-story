"""Intent Agent Tools.

Tools for understanding user intent from repository URLs and preferences.
Uses Claude Agent SDK @tool decorator pattern with intelligent text analysis.
"""

import json
import re
from typing import Any

from claude_agent_sdk import tool


# =============================================================================
# Intent Analysis Patterns
# =============================================================================

# Experience level indicators
BEGINNER_INDICATORS = [
    "new to", "just started", "learning", "beginner", "basics", "simple",
    "introduction", "intro", "what is", "how does", "explain", "unfamiliar",
    "first time", "never used", "don't know", "confused about",
]

ADVANCED_INDICATORS = [
    "deep dive", "internals", "architecture", "advanced", "expert",
    "implementation details", "performance", "optimization", "under the hood",
    "edge cases", "trade-offs", "scalability", "production", "enterprise",
]

# Learning goal patterns
GOAL_PATTERNS = {
    "architecture": [
        r"architect\w*", r"structur\w*", r"design\w*", r"pattern\w*",
        r"how.*built", r"how.*organized", r"layout", r"overview",
    ],
    "functionality": [
        r"how.*work\w*", r"what.*do\w*", r"feature\w*", r"capabilit\w*",
        r"function\w*", r"purpose", r"usage",
    ],
    "integration": [
        r"integrat\w*", r"connect\w*", r"api\w*", r"interface\w*",
        r"use.*with", r"work.*with", r"compatible",
    ],
    "testing": [
        r"test\w*", r"spec\w*", r"coverage", r"quality", r"ci/cd",
        r"validate", r"verification",
    ],
    "security": [
        r"secur\w*", r"auth\w*", r"permission\w*", r"access control",
        r"vulnerabil\w*", r"safe\w*",
    ],
    "performance": [
        r"perform\w*", r"optimi\w*", r"fast\w*", r"speed", r"efficien\w*",
        r"benchmark", r"scale",
    ],
    "deployment": [
        r"deploy\w*", r"docker", r"kubernetes", r"k8s", r"container\w*",
        r"cloud", r"aws", r"gcp", r"azure", r"infrastructure",
    ],
    "database": [
        r"databas\w*", r"sql", r"query", r"schema", r"model\w*",
        r"postgres", r"mysql", r"mongo", r"redis",
    ],
}

# Depth preference indicators
DEPTH_INDICATORS = {
    "overview": [
        "overview", "summary", "high-level", "brief", "quick", "general",
        "understand", "grasp", "main", "key",
    ],
    "detailed": [
        "detailed", "thorough", "comprehensive", "complete", "in-depth",
        "everything", "all", "full",
    ],
    "deep-dive": [
        "deep", "internals", "source code", "implementation", "line by line",
        "every detail", "exhaustive",
    ],
}

# Focus area extraction patterns
FOCUS_AREA_PATTERNS = {
    "frontend": [r"frontend", r"front-end", r"ui", r"react", r"vue", r"angular", r"svelte", r"css", r"html"],
    "backend": [r"backend", r"back-end", r"server", r"api", r"rest", r"graphql", r"grpc"],
    "database": [r"database", r"db", r"sql", r"nosql", r"orm", r"migration", r"schema"],
    "testing": [r"test", r"spec", r"coverage", r"unit", r"integration", r"e2e"],
    "devops": [r"devops", r"ci", r"cd", r"docker", r"kubernetes", r"deploy", r"infrastructure"],
    "authentication": [r"auth", r"login", r"session", r"jwt", r"oauth", r"permission"],
    "api": [r"api", r"endpoint", r"route", r"controller", r"handler"],
    "data-flow": [r"data flow", r"state", r"redux", r"store", r"context"],
    "error-handling": [r"error", r"exception", r"handling", r"logging"],
    "configuration": [r"config", r"setting", r"environment", r"env"],
}


def _detect_experience_level(text: str) -> str:
    """Detect user's experience level from text."""
    text_lower = text.lower()

    beginner_score = sum(1 for indicator in BEGINNER_INDICATORS if indicator in text_lower)
    advanced_score = sum(1 for indicator in ADVANCED_INDICATORS if indicator in text_lower)

    if beginner_score > advanced_score:
        return "beginner"
    elif advanced_score > beginner_score:
        return "advanced"
    return "intermediate"


def _detect_preferred_depth(text: str) -> str:
    """Detect user's preferred depth from text."""
    text_lower = text.lower()

    for depth, indicators in DEPTH_INDICATORS.items():
        if any(indicator in text_lower for indicator in indicators):
            return depth
    return "overview"  # Default


def _extract_goals(text: str) -> list[str]:
    """Extract learning goals from text using pattern matching."""
    text_lower = text.lower()
    detected_goals = []

    for goal, patterns in GOAL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                detected_goals.append(goal)
                break  # Only add each goal once

    return detected_goals if detected_goals else ["architecture", "functionality"]


def _extract_focus_areas(text: str) -> list[str]:
    """Extract specific focus areas from text."""
    text_lower = text.lower()
    focus_areas = []

    for area, patterns in FOCUS_AREA_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                focus_areas.append(area)
                break

    return focus_areas


def _estimate_duration(goals: list[str], depth: str) -> str:
    """Estimate story duration based on goals and depth."""
    base_minutes = len(goals) * 5

    depth_multiplier = {
        "overview": 1.0,
        "detailed": 1.5,
        "deep-dive": 2.0,
    }

    total_minutes = int(base_minutes * depth_multiplier.get(depth, 1.0))
    total_minutes = max(10, min(60, total_minutes))  # Clamp to 10-60 minutes

    if total_minutes <= 15:
        return "10-15 minutes"
    elif total_minutes <= 25:
        return "15-25 minutes"
    elif total_minutes <= 40:
        return "25-40 minutes"
    else:
        return "40-60 minutes"


# =============================================================================
# Tool Functions
# =============================================================================


@tool(
    name="analyze_user_intent",
    description="Analyze user's intent from their message about a repository. "
    "Identifies what the user wants to learn, their experience level, and preferred depth.",
    input_schema={
        "message": "User's natural language message about the repository",
        "repo_url": "GitHub repository URL if provided",
    },
)
async def analyze_user_intent(args: dict) -> dict:
    """Analyze user intent from message and optional repo URL.

    Performs intelligent text analysis to understand:
    - User's learning goals (architecture, functionality, etc.)
    - Experience level (beginner, intermediate, advanced)
    - Preferred depth (overview, detailed, deep-dive)
    - Specific focus areas (frontend, backend, testing, etc.)
    """
    message = args.get("message", "")
    repo_url = args.get("repo_url", "")

    # Analyze the message
    experience_level = _detect_experience_level(message)
    preferred_depth = _detect_preferred_depth(message)
    detected_goals = _extract_goals(message)
    focus_areas = _extract_focus_areas(message)

    # Build structured intent
    intent = {
        "message": message,
        "repo_url": repo_url,
        "detected_goals": detected_goals,
        "experience_level": experience_level,
        "preferred_depth": preferred_depth,
        "focus_areas": focus_areas,
        "analysis_confidence": "high" if len(detected_goals) > 1 else "medium",
    }

    return {"content": [{"type": "text", "text": json.dumps(intent, indent=2)}]}


@tool(
    name="extract_learning_goals",
    description="Extract specific learning goals from user intent analysis. "
    "Identifies what concepts, patterns, or skills the user wants to understand.",
    input_schema={
        "intent_data": "Structured intent data from analyze_user_intent",
        "repo_context": "Optional context about the repository",
    },
)
async def extract_learning_goals(args: dict) -> dict:
    """Extract learning goals from intent data.

    Takes the structured intent from analyze_user_intent and enriches it
    with specific learning objectives based on repository context.
    """
    intent_data = args.get("intent_data", {})
    repo_context = args.get("repo_context", {})

    # Parse intent_data if string
    if isinstance(intent_data, str):
        try:
            intent_data = json.loads(intent_data)
        except json.JSONDecodeError:
            intent_data = {}

    # Parse repo_context if string
    if isinstance(repo_context, str):
        try:
            repo_context = json.loads(repo_context)
        except json.JSONDecodeError:
            repo_context = {}

    detected_goals = intent_data.get("detected_goals", [])
    focus_areas = intent_data.get("focus_areas", [])
    experience_level = intent_data.get("experience_level", "intermediate")
    preferred_depth = intent_data.get("preferred_depth", "overview")

    # Map detected goals to specific learning objectives
    goal_objectives = {
        "architecture": [
            "Understand the overall system architecture",
            "Learn how components are organized and connected",
            "Identify design patterns used in the codebase",
        ],
        "functionality": [
            "Learn what the project does and its main features",
            "Understand the core workflows and data flows",
            "See how different features interact",
        ],
        "integration": [
            "Learn how external services are integrated",
            "Understand API contracts and interfaces",
            "See how data flows between systems",
        ],
        "testing": [
            "Understand the testing strategy and coverage",
            "Learn about test organization and patterns",
            "See examples of different test types",
        ],
        "security": [
            "Learn about authentication and authorization",
            "Understand security best practices in the code",
            "Identify security patterns and configurations",
        ],
        "performance": [
            "Understand performance optimization techniques",
            "Learn about caching strategies",
            "See how scalability is addressed",
        ],
        "deployment": [
            "Learn the deployment and DevOps workflow",
            "Understand infrastructure configuration",
            "See CI/CD pipelines and automation",
        ],
        "database": [
            "Understand data models and schema design",
            "Learn about database access patterns",
            "See migration and data management strategies",
        ],
    }

    # Build primary goals from detected goals
    primary_goals = []
    secondary_goals = []

    for i, goal in enumerate(detected_goals[:3]):  # Top 3 as primary
        objectives = goal_objectives.get(goal, [f"Learn about {goal}"])
        if i == 0:
            primary_goals.extend(objectives[:2])  # First 2 objectives of top goal
        else:
            primary_goals.append(objectives[0])  # First objective of other goals

    # Secondary goals from remaining and focus areas
    for goal in detected_goals[3:]:
        objectives = goal_objectives.get(goal, [f"Explore {goal}"])
        secondary_goals.append(objectives[0])

    for area in focus_areas:
        secondary_goals.append(f"Focus on {area.replace('-', ' ')} aspects")

    # Suggest topics based on repo context
    suggested_topics = []
    repo_languages = repo_context.get("languages", [])
    repo_frameworks = repo_context.get("frameworks", [])

    if repo_languages:
        suggested_topics.append(f"Language-specific patterns for {', '.join(repo_languages[:2])}")
    if repo_frameworks:
        suggested_topics.append(f"Framework patterns for {', '.join(repo_frameworks[:2])}")

    # Add experience-appropriate suggestions
    if experience_level == "beginner":
        suggested_topics.append("Basic concepts and getting started guide")
    elif experience_level == "advanced":
        suggested_topics.append("Advanced implementation details and trade-offs")

    # Estimate duration
    estimated_duration = _estimate_duration(detected_goals, preferred_depth)

    goals = {
        "primary_goals": primary_goals if primary_goals else ["Understand the project architecture"],
        "secondary_goals": secondary_goals[:5],  # Limit to 5 secondary goals
        "suggested_topics": suggested_topics[:3],  # Limit to 3 suggestions
        "estimated_duration": estimated_duration,
        "recommended_chapters": min(3 + len(detected_goals), 8),  # 3-8 chapters
    }

    return {"content": [{"type": "text", "text": json.dumps(goals, indent=2)}]}


@tool(
    name="parse_preferences",
    description="Parse user preferences for story generation. "
    "Includes voice style, pacing, technical depth, and narrative style.",
    input_schema={
        "user_input": "User's preference specifications",
        "defaults": "Default preferences to use if not specified",
    },
)
async def parse_preferences(args: dict) -> dict:
    """Parse user preferences for story generation.

    Analyzes user input to extract story generation preferences:
    - Voice style (professional, casual, academic, enthusiastic)
    - Pacing (slow, moderate, fast)
    - Technical depth (light, balanced, heavy)
    - Narrative style (documentary, tutorial, podcast, technical, fiction)
    - Duration preference (short, medium, long)
    """
    user_input = args.get("user_input", "")
    defaults = args.get("defaults", {})

    # Parse defaults if string
    if isinstance(defaults, str):
        try:
            defaults = json.loads(defaults)
        except json.JSONDecodeError:
            defaults = {}

    user_lower = user_input.lower() if user_input else ""

    # Voice style detection
    voice_styles = {
        "professional": ["professional", "formal", "business", "corporate"],
        "casual": ["casual", "relaxed", "friendly", "conversational", "informal"],
        "academic": ["academic", "scholarly", "educational", "lecture"],
        "enthusiastic": ["enthusiastic", "excited", "energetic", "dynamic"],
    }
    voice_style = defaults.get("voice_style", "professional")
    for style, keywords in voice_styles.items():
        if any(kw in user_lower for kw in keywords):
            voice_style = style
            break

    # Pacing detection
    pacing_keywords = {
        "slow": ["slow", "detailed", "thorough", "take time", "in-depth"],
        "fast": ["fast", "quick", "brief", "concise", "rapid"],
        "moderate": ["moderate", "balanced", "normal", "standard"],
    }
    pacing = defaults.get("pacing", "moderate")
    for pace, keywords in pacing_keywords.items():
        if any(kw in user_lower for kw in keywords):
            pacing = pace
            break

    # Technical depth detection
    depth_keywords = {
        "light": ["simple", "easy", "beginner", "light", "basic", "introductory"],
        "heavy": ["technical", "deep", "advanced", "expert", "detailed code", "implementation"],
        "balanced": ["balanced", "moderate", "medium", "standard"],
    }
    technical_depth = defaults.get("technical_depth", "balanced")
    for depth, keywords in depth_keywords.items():
        if any(kw in user_lower for kw in keywords):
            technical_depth = depth
            break

    # Narrative style detection
    narrative_keywords = {
        "documentary": ["documentary", "story", "narrative", "journey"],
        "tutorial": ["tutorial", "how-to", "guide", "step by step", "learn"],
        "podcast": ["podcast", "discussion", "conversation", "talk"],
        "technical": ["technical", "reference", "documentation", "specs"],
        "fiction": ["fiction", "creative", "imaginative", "story-like"],
    }
    narrative_style = defaults.get("narrative_style", "documentary")
    for style, keywords in narrative_keywords.items():
        if any(kw in user_lower for kw in keywords):
            narrative_style = style
            break

    # Duration preference detection
    duration_keywords = {
        "short": ["short", "brief", "quick", "5 min", "10 min", "under 15"],
        "long": ["long", "comprehensive", "full", "complete", "45 min", "hour"],
        "medium": ["medium", "moderate", "standard", "20 min", "30 min"],
    }
    duration_preference = defaults.get("duration_preference", "medium")
    for duration, keywords in duration_keywords.items():
        if any(kw in user_lower for kw in keywords):
            duration_preference = duration
            break

    # Code snippets preference
    include_code_snippets = defaults.get("include_code_snippets", True)
    if "no code" in user_lower or "without code" in user_lower:
        include_code_snippets = False
    elif "with code" in user_lower or "show code" in user_lower or "include code" in user_lower:
        include_code_snippets = True

    preferences = {
        "voice_style": voice_style,
        "pacing": pacing,
        "technical_depth": technical_depth,
        "narrative_style": narrative_style,
        "include_code_snippets": include_code_snippets,
        "duration_preference": duration_preference,
        "parsed_from_input": bool(user_input),
    }

    return {"content": [{"type": "text", "text": json.dumps(preferences, indent=2)}]}
