"""Story Architect Narrative Tools.

Tools for generating narrative scripts, chapters, and applying storytelling styles.
Uses Claude Agent SDK @tool decorator pattern for MCP integration.
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from claude_agent_sdk import tool


# =============================================================================
# Narrative Styles and Templates
# =============================================================================


class NarrativeStyle(str, Enum):
    """Supported narrative styles for story generation."""

    DOCUMENTARY = "documentary"
    TUTORIAL = "tutorial"
    PODCAST = "podcast"
    TECHNICAL = "technical"
    FICTION = "fiction"


# Style-specific opening templates
STYLE_OPENINGS = {
    NarrativeStyle.DOCUMENTARY: [
        "Welcome to an exploration of {repo_name}...",
        "In the vast landscape of software engineering, there exists a project that...",
        "Every great piece of software tells a story. Today, we explore {repo_name}...",
    ],
    NarrativeStyle.TUTORIAL: [
        "Today, we're going to learn how {repo_name} works step by step...",
        "Let's dive into {repo_name} and understand its architecture...",
        "In this guide, we'll walk through {repo_name} from the ground up...",
    ],
    NarrativeStyle.PODCAST: [
        "Hey everyone! Today we're talking about {repo_name}...",
        "Welcome back! Let's chat about this interesting project called {repo_name}...",
        "So I've been looking at {repo_name}, and let me tell you...",
    ],
    NarrativeStyle.TECHNICAL: [
        "Repository: {repo_name}. Architecture analysis follows...",
        "Technical overview of {repo_name}. Key components include...",
        "This is a detailed analysis of {repo_name}'s implementation...",
    ],
    NarrativeStyle.FICTION: [
        "Once upon a time, in a directory called {repo_name}...",
        "The code had been waiting. Waiting for someone to understand its story...",
        "In the kingdom of repositories, {repo_name} stood as a testament to...",
    ],
}

# Style-specific transition phrases
STYLE_TRANSITIONS = {
    NarrativeStyle.DOCUMENTARY: [
        "Moving on to the next crucial component...",
        "This brings us to another important aspect...",
        "Let's now turn our attention to...",
        "Building upon this foundation...",
    ],
    NarrativeStyle.TUTORIAL: [
        "Next, let's look at...",
        "Now that we understand that, let's move on to...",
        "The next step in our journey is...",
        "With that covered, let's explore...",
    ],
    NarrativeStyle.PODCAST: [
        "Okay, so here's where it gets interesting...",
        "Now, check this out...",
        "But wait, there's more...",
        "And speaking of which...",
    ],
    NarrativeStyle.TECHNICAL: [
        "Proceeding to...",
        "The following component is...",
        "Next section covers...",
        "Subsequently...",
    ],
    NarrativeStyle.FICTION: [
        "And so the journey continued to...",
        "But this was only the beginning...",
        "The tale then took a turn towards...",
        "Meanwhile, in another part of the codebase...",
    ],
}

# Style-specific closing templates
STYLE_CLOSINGS = {
    NarrativeStyle.DOCUMENTARY: [
        "And that concludes our exploration of {repo_name}.",
        "This has been a journey through the architecture of {repo_name}.",
        "We've seen how {repo_name} brings together these components into a cohesive whole.",
    ],
    NarrativeStyle.TUTORIAL: [
        "And that's everything you need to know to get started with {repo_name}!",
        "Now you have a solid understanding of how {repo_name} works.",
        "With this knowledge, you're ready to explore {repo_name} on your own.",
    ],
    NarrativeStyle.PODCAST: [
        "So that's {repo_name} in a nutshell! Pretty cool, right?",
        "Hope you enjoyed this deep dive into {repo_name}!",
        "That's a wrap on {repo_name}! Thanks for listening!",
    ],
    NarrativeStyle.TECHNICAL: [
        "End of {repo_name} technical analysis.",
        "This concludes the architectural overview of {repo_name}.",
        "Summary: {repo_name} implementation analysis complete.",
    ],
    NarrativeStyle.FICTION: [
        "And so, the story of {repo_name} reaches its conclusion... for now.",
        "The code lived on, its story now told.",
        "And they deployed happily ever after. The end.",
    ],
}

# Voice direction markers for different emotional tones
VOICE_MARKERS = {
    "emphasis": "[EMPHASIS]",
    "pause": "[PAUSE]",
    "slower": "[SLOWER]",
    "faster": "[FASTER]",
    "excited": "[EXCITED]",
    "thoughtful": "[THOUGHTFUL]",
    "questioning": "[QUESTIONING]",
    "conclusion": "[CONCLUSION]",
}


# =============================================================================
# Chapter Templates
# =============================================================================

CHAPTER_TEMPLATES = {
    "introduction": {
        "title_patterns": [
            "Introduction to {topic}",
            "Getting Started: {topic}",
            "Welcome to {topic}",
        ],
        "content_structure": [
            "overview",
            "key_concepts",
            "what_to_expect",
        ],
    },
    "architecture": {
        "title_patterns": [
            "The Architecture of {topic}",
            "Understanding the Structure: {topic}",
            "How {topic} is Organized",
        ],
        "content_structure": [
            "high_level_overview",
            "component_breakdown",
            "relationships",
        ],
    },
    "core_functionality": {
        "title_patterns": [
            "Core Functionality: {topic}",
            "The Heart of {topic}",
            "How {topic} Works",
        ],
        "content_structure": [
            "main_features",
            "key_workflows",
            "data_flow",
        ],
    },
    "deep_dive": {
        "title_patterns": [
            "Deep Dive: {topic}",
            "Under the Hood: {topic}",
            "A Closer Look at {topic}",
        ],
        "content_structure": [
            "implementation_details",
            "design_decisions",
            "trade_offs",
        ],
    },
    "conclusion": {
        "title_patterns": [
            "Wrapping Up: {topic}",
            "Conclusion: {topic}",
            "Final Thoughts on {topic}",
        ],
        "content_structure": [
            "summary",
            "key_takeaways",
            "next_steps",
        ],
    },
}


# =============================================================================
# Helper Functions
# =============================================================================


def _select_template(templates: list[str], index: int = 0) -> str:
    """Select a template from a list, cycling through options."""
    return templates[index % len(templates)]


def _apply_voice_markers(text: str, style: NarrativeStyle) -> str:
    """Apply voice direction markers based on content and style."""
    result = text

    # Add pauses after periods for dramatic effect
    if style in (NarrativeStyle.DOCUMENTARY, NarrativeStyle.FICTION):
        result = result.replace(". ", f". {VOICE_MARKERS['pause']} ")

    # Add emphasis markers for key technical terms
    tech_terms = ["architecture", "component", "module", "function", "class", "API"]
    for term in tech_terms:
        if term.lower() in result.lower():
            result = result.replace(term, f"{VOICE_MARKERS['emphasis']}{term}")
            break  # Only mark first occurrence

    return result


def _estimate_chapter_duration(script: str, pacing: str = "moderate") -> float:
    """Estimate chapter duration in seconds based on word count and pacing."""
    word_count = len(script.split())

    # Words per minute based on pacing
    wpm_map = {
        "slow": 120,
        "moderate": 150,
        "fast": 180,
    }
    wpm = wpm_map.get(pacing, 150)

    duration_seconds = (word_count / wpm) * 60
    return round(duration_seconds, 1)


def _generate_chapter_outline(
    goals: list[str],
    focus_areas: list[str],
    repo_context: dict[str, Any],
    num_chapters: int,
) -> list[dict[str, Any]]:
    """Generate a chapter outline based on goals and focus areas."""
    chapters = []

    # Always start with introduction
    chapters.append({
        "type": "introduction",
        "topic": repo_context.get("name", "the repository"),
        "goals": ["overview", "orientation"],
    })

    # Map goals to chapter types
    goal_to_chapter_type = {
        "architecture": "architecture",
        "functionality": "core_functionality",
        "integration": "deep_dive",
        "testing": "deep_dive",
        "security": "deep_dive",
        "performance": "deep_dive",
        "deployment": "deep_dive",
        "database": "deep_dive",
    }

    # Add chapters for each goal (up to num_chapters - 2 to leave room for intro/conclusion)
    for i, goal in enumerate(goals[: num_chapters - 2]):
        chapter_type = goal_to_chapter_type.get(goal, "deep_dive")
        chapters.append({
            "type": chapter_type,
            "topic": goal.replace("_", " ").title(),
            "goals": [goal] + focus_areas[:2],
        })

    # Always end with conclusion
    chapters.append({
        "type": "conclusion",
        "topic": repo_context.get("name", "the repository"),
        "goals": ["summary", "takeaways"],
    })

    return chapters


# =============================================================================
# Tool Functions
# =============================================================================


@tool(
    name="create_narrative",
    description="Create the overall narrative structure for a code story. "
    "Generates a story arc with chapters based on learning goals and repository analysis.",
    input_schema={
        "repo_analysis": "Repository analysis data from Repo Analyzer agent",
        "learning_goals": "Learning goals extracted from user intent",
        "preferences": "User preferences for story generation",
    },
)
async def create_narrative(args: dict) -> dict:
    """Create the overall narrative structure for a code story.

    Takes repository analysis, learning goals, and preferences to generate
    a complete narrative structure with chapter outline and story arc.
    """
    repo_analysis = args.get("repo_analysis", {})
    learning_goals = args.get("learning_goals", {})
    preferences = args.get("preferences", {})

    # Parse string inputs
    for key in ["repo_analysis", "learning_goals", "preferences"]:
        val = args.get(key, {})
        if isinstance(val, str):
            try:
                args[key] = json.loads(val)
            except json.JSONDecodeError:
                args[key] = {}

    repo_analysis = args.get("repo_analysis", {})
    learning_goals = args.get("learning_goals", {})
    preferences = args.get("preferences", {})

    # Extract key information
    repo_name = repo_analysis.get("name", repo_analysis.get("repo_name", "Repository"))
    primary_goals = learning_goals.get("primary_goals", ["Understand the architecture"])
    secondary_goals = learning_goals.get("secondary_goals", [])
    recommended_chapters = learning_goals.get("recommended_chapters", 5)

    # Determine style
    style_str = preferences.get("narrative_style", "documentary")
    try:
        style = NarrativeStyle(style_str)
    except ValueError:
        style = NarrativeStyle.DOCUMENTARY

    # Build chapter outline
    all_goals = []
    for goal in primary_goals:
        # Extract goal keywords
        for keyword in ["architecture", "functionality", "integration", "testing",
                       "security", "performance", "deployment", "database"]:
            if keyword in goal.lower():
                all_goals.append(keyword)
                break
        else:
            all_goals.append("functionality")

    focus_areas = learning_goals.get("focus_areas", [])
    if not focus_areas and "detected_goals" in learning_goals:
        focus_areas = learning_goals["detected_goals"]

    chapter_outline = _generate_chapter_outline(
        goals=all_goals,
        focus_areas=focus_areas,
        repo_context={"name": repo_name},
        num_chapters=recommended_chapters,
    )

    # Generate opening and closing
    opening = _select_template(STYLE_OPENINGS[style]).format(repo_name=repo_name)
    closing = _select_template(STYLE_CLOSINGS[style]).format(repo_name=repo_name)

    # Calculate estimated duration
    pacing = preferences.get("pacing", "moderate")
    base_duration_per_chapter = {"slow": 300, "moderate": 240, "fast": 180}
    estimated_duration = len(chapter_outline) * base_duration_per_chapter.get(pacing, 240)

    narrative = {
        "repo_name": repo_name,
        "style": style.value,
        "opening": opening,
        "closing": closing,
        "chapter_outline": chapter_outline,
        "chapter_count": len(chapter_outline),
        "estimated_duration_seconds": estimated_duration,
        "estimated_duration_formatted": f"{estimated_duration // 60}:{estimated_duration % 60:02d}",
        "transitions": STYLE_TRANSITIONS[style],
        "voice_tone": _get_voice_tone(style),
        "pacing": pacing,
        "goals_addressed": all_goals,
    }

    return {"content": [{"type": "text", "text": json.dumps(narrative, indent=2)}]}


def _get_voice_tone(style: NarrativeStyle) -> str:
    """Get the recommended voice tone for a style."""
    tone_map = {
        NarrativeStyle.DOCUMENTARY: "professional, authoritative, engaging",
        NarrativeStyle.TUTORIAL: "friendly, clear, instructive",
        NarrativeStyle.PODCAST: "casual, conversational, enthusiastic",
        NarrativeStyle.TECHNICAL: "precise, neutral, informative",
        NarrativeStyle.FICTION: "dramatic, narrative, immersive",
    }
    return tone_map.get(style, "professional")


@tool(
    name="generate_chapters",
    description="Generate chapter scripts with voice direction markers. "
    "Creates detailed scripts for each chapter with timing and pacing guidance.",
    input_schema={
        "narrative": "Narrative structure from create_narrative",
        "repo_analysis": "Repository analysis data for content generation",
        "preferences": "User preferences for technical depth and style",
    },
)
async def generate_chapters(args: dict) -> dict:
    """Generate chapter scripts with voice direction markers.

    Creates detailed scripts for each chapter based on the narrative structure
    and repository analysis. Includes voice direction markers for synthesis.
    """
    narrative = args.get("narrative", {})
    repo_analysis = args.get("repo_analysis", {})
    preferences = args.get("preferences", {})

    # Parse string inputs
    for key in ["narrative", "repo_analysis", "preferences"]:
        val = args.get(key, {})
        if isinstance(val, str):
            try:
                args[key] = json.loads(val)
            except json.JSONDecodeError:
                args[key] = {}

    narrative = args.get("narrative", {})
    repo_analysis = args.get("repo_analysis", {})
    preferences = args.get("preferences", {})

    style_str = narrative.get("style", "documentary")
    try:
        style = NarrativeStyle(style_str)
    except ValueError:
        style = NarrativeStyle.DOCUMENTARY

    chapter_outline = narrative.get("chapter_outline", [])
    repo_name = narrative.get("repo_name", "Repository")
    pacing = narrative.get("pacing", preferences.get("pacing", "moderate"))
    technical_depth = preferences.get("technical_depth", "balanced")
    include_code = preferences.get("include_code_snippets", True)

    # Repository content for script generation
    components = repo_analysis.get("components", repo_analysis.get("key_components", []))
    patterns = repo_analysis.get("patterns", repo_analysis.get("detected_patterns", []))
    dependencies = repo_analysis.get("dependencies", [])
    languages = repo_analysis.get("languages", repo_analysis.get("primary_languages", []))

    chapters = []
    transitions = narrative.get("transitions", STYLE_TRANSITIONS[style])
    running_time = 0.0

    for i, chapter_info in enumerate(chapter_outline):
        chapter_type = chapter_info.get("type", "deep_dive")
        topic = chapter_info.get("topic", f"Chapter {i + 1}")
        goals = chapter_info.get("goals", [])

        # Get title template
        templates = CHAPTER_TEMPLATES.get(chapter_type, CHAPTER_TEMPLATES["deep_dive"])
        title = _select_template(templates["title_patterns"], i).format(topic=topic)

        # Generate script content based on chapter type
        script = _generate_chapter_script(
            chapter_type=chapter_type,
            topic=topic,
            repo_name=repo_name,
            style=style,
            components=components,
            patterns=patterns,
            dependencies=dependencies,
            languages=languages,
            technical_depth=technical_depth,
            include_code=include_code,
            is_first=(i == 0),
            is_last=(i == len(chapter_outline) - 1),
            opening=narrative.get("opening", ""),
            closing=narrative.get("closing", ""),
        )

        # Apply voice markers
        script_with_markers = _apply_voice_markers(script, style)

        # Add transition if not last chapter
        if i < len(chapter_outline) - 1:
            transition = transitions[i % len(transitions)]
            script_with_markers += f"\n\n{VOICE_MARKERS['pause']} {transition}"

        # Calculate duration
        duration = _estimate_chapter_duration(script, pacing)
        start_time = running_time
        running_time += duration

        chapters.append({
            "order": i + 1,
            "title": title,
            "type": chapter_type,
            "script": script_with_markers,
            "goals_covered": goals,
            "start_time": start_time,
            "duration_seconds": duration,
            "word_count": len(script.split()),
            "voice_markers": _count_voice_markers(script_with_markers),
        })

    result = {
        "chapters": chapters,
        "total_chapters": len(chapters),
        "total_duration_seconds": running_time,
        "total_duration_formatted": f"{int(running_time // 60)}:{int(running_time % 60):02d}",
        "style": style.value,
        "pacing": pacing,
    }

    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


def _generate_chapter_script(
    chapter_type: str,
    topic: str,
    repo_name: str,
    style: NarrativeStyle,
    components: list,
    patterns: list,
    dependencies: list,
    languages: list,
    technical_depth: str,
    include_code: bool,
    is_first: bool,
    is_last: bool,
    opening: str,
    closing: str,
) -> str:
    """Generate a chapter script based on type and content."""
    lines = []

    if is_first:
        lines.append(opening)
        lines.append("")

    if chapter_type == "introduction":
        lines.extend(_generate_intro_script(repo_name, languages, style))
    elif chapter_type == "architecture":
        lines.extend(_generate_architecture_script(repo_name, components, style, technical_depth))
    elif chapter_type == "core_functionality":
        lines.extend(_generate_functionality_script(repo_name, patterns, style))
    elif chapter_type == "deep_dive":
        lines.extend(_generate_deep_dive_script(topic, components, dependencies, style, technical_depth))
    elif chapter_type == "conclusion":
        lines.extend(_generate_conclusion_script(repo_name, style))
        if is_last:
            lines.append("")
            lines.append(closing)
    else:
        lines.append(f"Exploring {topic} in {repo_name}.")

    return "\n".join(lines)


def _generate_intro_script(repo_name: str, languages: list, style: NarrativeStyle) -> list[str]:
    """Generate introduction chapter script."""
    lang_str = ", ".join(languages[:3]) if languages else "modern technologies"

    if style == NarrativeStyle.DOCUMENTARY:
        return [
            f"{repo_name} represents an interesting piece of software engineering.",
            f"Built using {lang_str}, it demonstrates thoughtful design choices.",
            "In this exploration, we'll uncover the patterns and principles that make it work.",
        ]
    elif style == NarrativeStyle.TUTORIAL:
        return [
            f"Let's start by understanding what {repo_name} is all about.",
            f"This project uses {lang_str}, and we'll see how these technologies work together.",
            "By the end, you'll have a solid understanding of its architecture.",
        ]
    elif style == NarrativeStyle.PODCAST:
        return [
            f"So {repo_name}, right? Let me tell you why this is interesting.",
            f"It's built with {lang_str}, which already tells us something about the approach.",
            "Let's break it down and see what makes it tick.",
        ]
    else:
        return [
            f"Repository: {repo_name}",
            f"Primary technologies: {lang_str}",
            "Analysis of architectural components follows.",
        ]


def _generate_architecture_script(
    repo_name: str, components: list, style: NarrativeStyle, depth: str
) -> list[str]:
    """Generate architecture chapter script."""
    comp_list = components[:5] if components else ["core modules", "utilities", "interfaces"]
    comp_str = ", ".join(str(c) if isinstance(c, str) else c.get("name", str(c)) for c in comp_list[:3])

    lines = [f"The architecture of {repo_name} is built around several key components."]

    if depth in ("balanced", "heavy"):
        lines.append(f"The main components include: {comp_str}.")
        lines.append("Each of these plays a specific role in the overall system.")

    if style == NarrativeStyle.DOCUMENTARY:
        lines.append("The design reflects deliberate choices that prioritize maintainability and clarity.")
    elif style == NarrativeStyle.TUTORIAL:
        lines.append("Understanding this structure will help you navigate the codebase effectively.")

    return lines


def _generate_functionality_script(repo_name: str, patterns: list, style: NarrativeStyle) -> list[str]:
    """Generate core functionality chapter script."""
    pattern_list = patterns[:3] if patterns else ["standard patterns"]
    pattern_str = ", ".join(str(p) if isinstance(p, str) else p.get("name", str(p)) for p in pattern_list)

    lines = [f"At its core, {repo_name} provides a set of well-defined capabilities."]
    lines.append(f"The codebase employs patterns such as: {pattern_str}.")

    if style == NarrativeStyle.PODCAST:
        lines.append("And honestly, that's pretty clever when you think about it.")
    else:
        lines.append("These patterns help maintain consistency across the codebase.")

    return lines


def _generate_deep_dive_script(
    topic: str, components: list, dependencies: list, style: NarrativeStyle, depth: str
) -> list[str]:
    """Generate deep dive chapter script."""
    lines = [f"Let's take a closer look at {topic}."]

    if components:
        comp = components[0] if components else "the main component"
        comp_name = comp if isinstance(comp, str) else comp.get("name", str(comp))
        lines.append(f"Starting with {comp_name}, we can see how it integrates with the rest of the system.")

    if depth == "heavy" and dependencies:
        dep_str = ", ".join(str(d)[:20] for d in dependencies[:3])
        lines.append(f"Key dependencies include: {dep_str}.")

    if style == NarrativeStyle.DOCUMENTARY:
        lines.append("The implementation reveals careful consideration of both performance and maintainability.")
    elif style == NarrativeStyle.TUTORIAL:
        lines.append("Understanding these details will help when you need to modify or extend this functionality.")

    return lines


def _generate_conclusion_script(repo_name: str, style: NarrativeStyle) -> list[str]:
    """Generate conclusion chapter script."""
    if style == NarrativeStyle.DOCUMENTARY:
        return [
            f"We've journeyed through the architecture and implementation of {repo_name}.",
            "The patterns we've seen reflect thoughtful software engineering.",
            "This codebase serves as an example of clean, maintainable design.",
        ]
    elif style == NarrativeStyle.TUTORIAL:
        return [
            f"That covers the key aspects of {repo_name}.",
            "You now have the knowledge to navigate and understand this codebase.",
            "Feel free to explore further and experiment with what you've learned.",
        ]
    elif style == NarrativeStyle.PODCAST:
        return [
            f"And that's {repo_name} in a nutshell!",
            "Pretty cool project, right? I hope you found this helpful.",
            "Until next time, happy coding!",
        ]
    else:
        return [
            f"Analysis of {repo_name} complete.",
            "Key findings have been documented.",
            "End of technical overview.",
        ]


def _count_voice_markers(script: str) -> dict[str, int]:
    """Count voice markers in a script."""
    counts = {}
    for name, marker in VOICE_MARKERS.items():
        count = script.count(marker)
        if count > 0:
            counts[name] = count
    return counts


@tool(
    name="apply_style",
    description="Apply a narrative style transformation to existing content. "
    "Transforms technical content into the appropriate storytelling style.",
    input_schema={
        "content": "Technical content to transform",
        "target_style": "Target narrative style (documentary, tutorial, podcast, technical, fiction)",
        "context": "Additional context for the transformation",
    },
)
async def apply_style(args: dict) -> dict:
    """Apply a narrative style transformation to content.

    Takes technical content and transforms it according to the specified
    narrative style while preserving the core information.
    """
    content = args.get("content", "")
    target_style_str = args.get("target_style", "documentary")
    context = args.get("context", {})

    # Parse context if string
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except json.JSONDecodeError:
            context = {}

    # Determine target style
    try:
        target_style = NarrativeStyle(target_style_str.lower())
    except ValueError:
        target_style = NarrativeStyle.DOCUMENTARY

    # Get style characteristics
    style_config = {
        "tone": _get_voice_tone(target_style),
        "transitions": STYLE_TRANSITIONS[target_style],
        "markers": VOICE_MARKERS,
    }

    # Apply style-specific transformations
    transformed = _transform_content(content, target_style, context)

    # Add voice markers
    transformed_with_markers = _apply_voice_markers(transformed, target_style)

    # Estimate duration
    duration = _estimate_chapter_duration(transformed_with_markers, context.get("pacing", "moderate"))

    result = {
        "original_content": content,
        "transformed_content": transformed_with_markers,
        "style_applied": target_style.value,
        "style_config": style_config,
        "word_count": len(transformed.split()),
        "estimated_duration_seconds": duration,
        "voice_markers_added": _count_voice_markers(transformed_with_markers),
    }

    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


def _transform_content(content: str, style: NarrativeStyle, context: dict) -> str:
    """Transform content according to the target style."""
    if not content:
        return ""

    # Style-specific sentence starters
    starters = {
        NarrativeStyle.DOCUMENTARY: "Interestingly, ",
        NarrativeStyle.TUTORIAL: "Here's an important point: ",
        NarrativeStyle.PODCAST: "So here's the thing - ",
        NarrativeStyle.TECHNICAL: "Note: ",
        NarrativeStyle.FICTION: "And then, ",
    }

    # Apply basic transformation
    lines = content.split(". ")
    transformed_lines = []

    for i, line in enumerate(lines):
        if not line.strip():
            continue

        # Add style-appropriate starter to some lines
        if i > 0 and i % 3 == 0:
            line = starters[style] + line[0].lower() + line[1:]

        transformed_lines.append(line)

    return ". ".join(transformed_lines)
