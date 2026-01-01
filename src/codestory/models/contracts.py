"""Data Contracts for Code Story Pipeline.

These dataclasses define the formal contracts between agents in the 4-stage pipeline:
1. IntentResult: Intent Agent → Repo Analyzer, Story Architect
2. AnalysisResult: Repo Analyzer → Story Architect
3. NarrativeResult: Story Architect → Voice Director
4. AudioResult: Voice Director → API/Frontend

Each contract ensures type-safe handoffs between pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# =============================================================================
# Phase 1 → Phase 2/3: Intent Result
# =============================================================================

@dataclass
class ChapterOutline:
    """Preliminary chapter structure from intent analysis."""

    title: str
    focus: str
    estimated_minutes: int


@dataclass
class IntentResult:
    """Output from Intent Agent.

    Consumed by: Repo Analyzer, Story Architect
    """

    # Repository to analyze
    repo_url: str

    # User's learning goals
    intent_category: Literal["onboarding", "architecture", "feature", "debugging", "review"]
    expertise_level: Literal["beginner", "intermediate", "expert"]
    focus_areas: list[str] = field(default_factory=list)  # ["authentication", "database layer"]

    # Narrative preferences
    recommended_style: Literal["fiction", "documentary", "tutorial", "podcast", "technical"] = "documentary"
    target_duration_minutes: int = 10  # 5-30 minutes

    # Preliminary structure
    chapter_outline: list[ChapterOutline] = field(default_factory=list)


# =============================================================================
# Phase 2 → Phase 3: Analysis Result
# =============================================================================

@dataclass
class ComponentInfo:
    """Key component identified in repository."""

    name: str
    type: Literal["class", "module", "function", "endpoint"]
    file_path: str
    purpose: str
    importance: Literal["core", "supporting", "utility"]


@dataclass
class CodeCharacter:
    """Code entity personified for narrative."""

    name: str  # Class/module name
    role: str  # "protagonist", "supporting", "antagonist"
    description: str  # Narrative description
    file_path: str


@dataclass
class ChapterSuggestion:
    """Suggested chapter from code analysis."""

    title: str
    description: str
    key_files: list[str] = field(default_factory=list)
    code_concepts: list[str] = field(default_factory=list)


@dataclass
class StoryComponents:
    """Narrative-oriented view of repository."""

    chapters: list[ChapterSuggestion] = field(default_factory=list)
    characters: list[CodeCharacter] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)  # ["data transformation", "authentication"]
    narrative_arc: str = ""  # "How this codebase solves X problem"


@dataclass
class AnalysisResult:
    """Output from Repo Analyzer Agent.

    Consumed by: Story Architect
    """

    # Repository metadata
    repo_url: str
    primary_language: str | None = None
    total_files: int = 0

    # Architecture analysis
    architecture_pattern: str = ""  # "MVC", "microservices", "monolith"
    key_components: list[ComponentInfo] = field(default_factory=list)
    design_patterns: list[str] = field(default_factory=list)  # ["Factory", "Singleton"]

    # Dependencies
    frameworks: list[str] = field(default_factory=list)  # ["FastAPI", "React"]
    external_apis: list[str] = field(default_factory=list)  # ["ElevenLabs", "GitHub API"]

    # Code organization
    directory_structure: dict[str, int] = field(default_factory=dict)  # {"src/": 45}
    entry_points: list[str] = field(default_factory=list)  # ["main.py", "app.py"]

    # Story components (from identify_story_components)
    story_components: StoryComponents = field(default_factory=StoryComponents)


# =============================================================================
# Phase 3 → Phase 4: Narrative Result
# =============================================================================

@dataclass
class ChapterScript:
    """Individual chapter script for narration."""

    # Metadata
    chapter_number: int
    title: str

    # Content - the actual narration text
    # Voice direction markers embedded in script:
    # [PAUSE] - Brief pause
    # [EMPHASIS] - Stress this phrase
    # [SLOW] - Reduce pace for complex content
    # [CODE: snippet] - Read as code (technical pronunciation)
    # [CONVERSATIONAL] - Casual, lighter tone
    script: str

    # Timing
    estimated_seconds: int = 0

    # For audio assembly
    transition_out: Literal["fade", "silence", "music"] = "silence"


@dataclass
class NarrativeResult:
    """Output from Story Architect Agent.

    Consumed by: Voice Director
    """

    # Story metadata
    title: str
    style: Literal["fiction", "documentary", "tutorial", "podcast", "technical"]

    # Complete narrative
    chapters: list[ChapterScript] = field(default_factory=list)

    # Synthesis guidance
    estimated_duration_seconds: int = 0
    voice_profile_recommendation: str = ""  # ElevenLabs voice ID suggestion


# =============================================================================
# Phase 4 → API/Frontend: Audio Result
# =============================================================================

@dataclass
class VoiceProfile:
    """ElevenLabs voice configuration used."""

    voice_id: str
    voice_name: str
    style: str
    stability: float = 0.5
    similarity_boost: float = 0.75


@dataclass
class ChapterAudio:
    """Audio for individual chapter."""

    chapter_number: int
    title: str
    audio_url: str
    duration_seconds: float
    start_offset_seconds: float = 0.0  # Position in combined audio


@dataclass
class AudioResult:
    """Output from Voice Director Agent.

    Consumed by: API, Frontend
    """

    # Overall result
    success: bool

    # Audio files
    audio_url: str = ""  # S3 URL to combined audio

    # Chapter breakdown
    chapters: list[ChapterAudio] = field(default_factory=list)

    # Metadata
    total_duration_seconds: float = 0.0
    voice_profile: VoiceProfile | None = None

    # Error handling
    error: str | None = None
    partial_chapters: list[ChapterAudio] | None = None  # If some failed


# =============================================================================
# Validation Functions
# =============================================================================

def validate_intent_result(result: IntentResult) -> tuple[bool, str]:
    """Validate IntentResult is sufficient for pipeline continuation.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not result.repo_url:
        return False, "repo_url is required"
    if not result.repo_url.startswith("https://github.com/"):
        return False, "Only GitHub URLs are supported"
    if not result.intent_category:
        return False, "intent_category is required"
    if not result.expertise_level:
        return False, "expertise_level is required"
    return True, ""


def validate_analysis_result(result: AnalysisResult) -> tuple[bool, str]:
    """Validate AnalysisResult is sufficient for narrative generation.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not result.repo_url:
        return False, "repo_url is required"
    if result.total_files == 0:
        return False, "No files detected in repository"
    if not result.primary_language:
        return False, "primary_language is required"
    if not result.story_components.chapters:
        return False, "At least one chapter suggestion is required"
    return True, ""


def validate_narrative_result(result: NarrativeResult) -> tuple[bool, str]:
    """Validate NarrativeResult is sufficient for audio synthesis.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not result.title:
        return False, "Story title is required"
    if not result.chapters:
        return False, "At least one chapter is required"
    for chapter in result.chapters:
        if not chapter.script or len(chapter.script) < 100:
            return False, f"Chapter {chapter.chapter_number} script is too short"
    if result.estimated_duration_seconds < 60:
        return False, "Estimated duration must be at least 60 seconds"
    return True, ""


def validate_audio_result(result: AudioResult) -> tuple[bool, str]:
    """Validate AudioResult is complete and usable.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not result.success:
        return False, result.error or "Audio generation failed"
    if not result.audio_url:
        return False, "audio_url is required"
    if result.total_duration_seconds <= 0:
        return False, "total_duration_seconds must be positive"
    return True, ""


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Intent types
    "ChapterOutline",
    "IntentResult",
    # Analysis types
    "ComponentInfo",
    "CodeCharacter",
    "ChapterSuggestion",
    "StoryComponents",
    "AnalysisResult",
    # Narrative types
    "ChapterScript",
    "NarrativeResult",
    # Audio types
    "VoiceProfile",
    "ChapterAudio",
    "AudioResult",
    # Validation functions
    "validate_intent_result",
    "validate_analysis_result",
    "validate_narrative_result",
    "validate_audio_result",
]
