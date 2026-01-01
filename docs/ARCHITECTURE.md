# Code Story - System Architecture

## Overview

Code Story transforms GitHub repositories into audio narratives using a 4-agent Claude SDK pipeline. This document defines the complete system architecture, data contracts, and component interactions.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CODE STORY PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  │              │      │              │      │              │      │              │
│  │    INTENT    │──────│     REPO     │──────│    STORY     │──────│    VOICE     │
│  │    AGENT     │      │   ANALYZER   │      │  ARCHITECT   │      │  DIRECTOR    │
│  │              │      │              │      │              │      │              │
│  └──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
│        │                      │                     │                     │
│        ▼                      ▼                     ▼                     ▼
│   IntentResult          AnalysisResult         NarrativeResult       AudioResult
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Contracts

### 1. IntentResult (Phase 2 → Phase 3/4)

Produced by: Intent Agent
Consumed by: Repo Analyzer, Story Architect

```python
@dataclass
class IntentResult:
    """Output from Intent Agent."""

    # Repository to analyze
    repo_url: str

    # User's learning goals
    intent_category: Literal["onboarding", "architecture", "feature", "debugging", "review"]
    expertise_level: Literal["beginner", "intermediate", "expert"]
    focus_areas: list[str]  # ["authentication", "database layer", "API design"]

    # Narrative preferences
    recommended_style: Literal["fiction", "documentary", "tutorial", "podcast", "technical"]
    target_duration_minutes: int  # 5-30 minutes

    # Preliminary structure
    chapter_outline: list[ChapterOutline]

@dataclass
class ChapterOutline:
    """Preliminary chapter structure from intent analysis."""
    title: str
    focus: str
    estimated_minutes: int
```

### 2. AnalysisResult (Phase 3 → Phase 4)

Produced by: Repo Analyzer
Consumed by: Story Architect

```python
@dataclass
class AnalysisResult:
    """Output from Repo Analyzer Agent."""

    # Repository metadata
    repo_url: str
    primary_language: str
    total_files: int

    # Architecture analysis
    architecture_pattern: str  # "MVC", "microservices", "monolith", etc.
    key_components: list[ComponentInfo]
    design_patterns: list[str]  # ["Factory", "Singleton", "Observer"]

    # Dependencies
    frameworks: list[str]  # ["FastAPI", "React", "SQLAlchemy"]
    external_apis: list[str]  # ["ElevenLabs", "GitHub API"]

    # Code organization
    directory_structure: dict[str, int]  # {"src/": 45, "tests/": 12}
    entry_points: list[str]  # ["main.py", "app.py"]

    # Story components (from identify_story_components)
    story_components: StoryComponents

@dataclass
class ComponentInfo:
    """Key component identified in repository."""
    name: str
    type: Literal["class", "module", "function", "endpoint"]
    file_path: str
    purpose: str
    importance: Literal["core", "supporting", "utility"]

@dataclass
class StoryComponents:
    """Narrative-oriented view of repository."""
    chapters: list[ChapterSuggestion]
    characters: list[CodeCharacter]  # Classes/modules personified
    themes: list[str]  # ["data transformation", "user authentication"]
    narrative_arc: str  # "How this codebase solves X problem"

@dataclass
class ChapterSuggestion:
    """Suggested chapter from code analysis."""
    title: str
    description: str
    key_files: list[str]
    code_concepts: list[str]
```

### 3. NarrativeResult (Phase 4 → Phase 5)

Produced by: Story Architect
Consumed by: Voice Director

```python
@dataclass
class NarrativeResult:
    """Output from Story Architect Agent."""

    # Story metadata
    title: str
    style: Literal["fiction", "documentary", "tutorial", "podcast", "technical"]

    # Complete narrative
    chapters: list[ChapterScript]

    # Synthesis guidance
    estimated_duration_seconds: int
    voice_profile_recommendation: str

@dataclass
class ChapterScript:
    """Individual chapter script for narration."""

    # Metadata
    chapter_number: int
    title: str

    # Content
    script: str  # The actual narration text

    # Voice direction markers embedded in script:
    # [PAUSE] - Brief pause
    # [EMPHASIS] - Stress this phrase
    # [SLOW] - Reduce pace for complex content
    # [CODE: snippet] - Read as code (technical pronunciation)
    # [CONVERSATIONAL] - Casual, lighter tone

    # Timing
    estimated_seconds: int

    # For audio assembly
    transition_out: str  # "fade", "silence", "music"
```

### 4. AudioResult (Phase 5 → API/Frontend)

Produced by: Voice Director
Consumed by: API, Frontend

```python
@dataclass
class AudioResult:
    """Output from Voice Director Agent."""

    # Overall result
    success: bool

    # Audio files
    audio_url: str  # S3 URL to combined audio

    # Chapter breakdown
    chapters: list[ChapterAudio]

    # Metadata
    total_duration_seconds: float
    voice_profile: VoiceProfile

    # Error handling
    error: str | None = None
    partial_chapters: list[ChapterAudio] | None = None  # If some failed

@dataclass
class ChapterAudio:
    """Audio for individual chapter."""
    chapter_number: int
    title: str
    audio_url: str
    duration_seconds: float
    start_offset_seconds: float  # Position in combined audio

@dataclass
class VoiceProfile:
    """ElevenLabs voice configuration used."""
    voice_id: str
    voice_name: str
    style: str
    stability: float
    similarity_boost: float
```

## Tool Registry

### Current Tools (19 total)

| Tool | Module | Agent | Input | Output |
|------|--------|-------|-------|--------|
| **Intent Tools** | | | | |
| `analyze_user_intent` | intent.py | Intent | user_message, repo_url | IntentCategory |
| `extract_learning_goals` | intent.py | Intent | user_message | LearningGoals |
| `parse_preferences` | intent.py | Intent | user_message | NarrativePreferences |
| **Repomix Tools** | | | | |
| `package_repository` | repomix.py | Analyzer | github_url, filters | PackagedRepository |
| `analyze_packaged_repository` | repomix.py | Analyzer | github_url | RepositoryAnalysis |
| `identify_story_components` | repomix.py | Analyzer | github_url | StoryComponents |
| `generate_analysis_summary` | repomix.py | Analyzer | github_url | AnalysisSummary |
| **Artifact Tools** | | | | |
| `get_repository_artifact` | repomix.py | Architect/Voice | github_url, type | ArtifactContent |
| `explore_file_in_package` | repomix.py | Architect/Voice | github_url, path | FileContent |
| `list_available_artifacts` | repomix.py | Architect/Voice | github_url | ArtifactList |
| **Analysis Tools** | | | | |
| `analyze_code_structure` | analysis.py | Analyzer | code_content | CodeStructure |
| `analyze_dependencies` | analysis.py | Analyzer | code_content | Dependencies |
| `extract_patterns` | analysis.py | Analyzer | code_content | Patterns |
| **Narrative Tools** | | | | |
| `create_narrative` | narrative.py | Architect | analysis, intent | NarrativeArc |
| `generate_chapters` | narrative.py | Architect | narrative, style | ChapterScripts |
| `apply_style` | narrative.py | Architect | content, style | StyledContent |
| **Voice Tools** | | | | |
| `select_voice_profile` | voice.py | Voice | style | VoiceProfile |
| `generate_audio_segment` | voice.py | Voice | text, voice | AudioSegment |
| `synthesize_narration` | voice.py | Voice | chapters, voice | CombinedAudio |

## Agent Definitions (Corrected)

### Intent Agent

```python
INTENT_AGENT = AgentDefinition(
    description="Understands user intent through conversational onboarding",
    prompt=INTENT_AGENT_PROMPT,
    tools=[
        "mcp__codestory__analyze_user_intent",
        "mcp__codestory__extract_learning_goals",
        "mcp__codestory__parse_preferences",
    ],
    model="sonnet",
)
```

### Repo Analyzer Agent (CORRECTED)

```python
REPO_ANALYZER_AGENT = AgentDefinition(
    description="Analyzes repository using Repomix packaging",
    prompt=REPO_ANALYZER_PROMPT,
    tools=[
        # Repomix tools (PRIMARY)
        "mcp__codestory__package_repository",
        "mcp__codestory__analyze_packaged_repository",
        "mcp__codestory__identify_story_components",
        "mcp__codestory__generate_analysis_summary",
        # Analysis tools (SECONDARY)
        "mcp__codestory__analyze_code_structure",
        "mcp__codestory__analyze_dependencies",
        "mcp__codestory__extract_patterns",
    ],
    model="opus",
)
```

### Story Architect Agent

```python
STORY_ARCHITECT_AGENT = AgentDefinition(
    description="Creates narrative structure from repository analysis",
    prompt=STORY_ARCHITECT_PROMPT,
    tools=[
        # Narrative tools
        "mcp__codestory__create_narrative",
        "mcp__codestory__generate_chapters",
        "mcp__codestory__apply_style",
        # Artifact access (for code exploration)
        "mcp__codestory__get_repository_artifact",
        "mcp__codestory__explore_file_in_package",
    ],
    model="opus",
)
```

### Voice Director Agent

```python
VOICE_DIRECTOR_AGENT = AgentDefinition(
    description="Synthesizes audio narration using ElevenLabs",
    prompt=VOICE_DIRECTOR_PROMPT,
    tools=[
        "mcp__codestory__select_voice_profile",
        "mcp__codestory__generate_audio_segment",
        "mcp__codestory__synthesize_narration",
    ],
    model="sonnet",
)
```

## Artifact Persistence

All Repomix outputs are persisted for cross-agent access:

```
/tmp/codestory_artifacts/
└── {owner}_{repo}/
    ├── packaged_repository.md      # Full repo content
    ├── analysis.json               # Structure analysis
    ├── story_components.json       # Narrative components
    └── analysis_summary.json       # Summary for handoff
```

### Artifact Size Management

| Artifact | Max Size | Strategy |
|----------|----------|----------|
| packaged_repository.md | 2MB | Aggressive exclusions, remove-comments |
| analysis.json | 50KB | Top 10 files per directory |
| story_components.json | 20KB | Key characters only |
| analysis_summary.json | 10KB | Summary for next agent |

## Pipeline Orchestration

### Execution Flow

```python
async def run_pipeline(repo_url: str, user_intent: str, style: str) -> AudioResult:
    """
    Complete pipeline orchestration.

    1. Intent Agent receives user input
    2. Repo Analyzer packages and analyzes repository
    3. Story Architect creates narrative from analysis
    4. Voice Director synthesizes audio from narrative
    """

    # Phase 1: Intent Analysis
    intent_result = await delegate_to_agent(
        agent="intent-agent",
        input={
            "repo_url": repo_url,
            "user_message": user_intent,
        }
    )

    # Phase 2: Repository Analysis (via Repomix)
    analysis_result = await delegate_to_agent(
        agent="repo-analyzer",
        input={
            "github_url": repo_url,
            "intent": intent_result,
            # Pass filters to exclude noise
            "exclude_patterns": ["**/node_modules/**", "**/*.test.*", "**/zh-CN/**"],
        }
    )

    # Phase 3: Narrative Creation
    narrative_result = await delegate_to_agent(
        agent="story-architect",
        input={
            "analysis": analysis_result,
            "intent": intent_result,
            "style": style,
        }
    )

    # Phase 4: Audio Synthesis
    audio_result = await delegate_to_agent(
        agent="voice-director",
        input={
            "narrative": narrative_result,
            "voice_profile": narrative_result.voice_profile_recommendation,
        }
    )

    return audio_result
```

## Validation Gates

### Phase 3 Validation (Repo Analyzer → Story Architect)

```python
def validate_analysis_result(result: AnalysisResult) -> bool:
    """Ensure analysis is sufficient for narrative generation."""
    return (
        result.primary_language is not None and
        result.total_files > 0 and
        len(result.key_components) > 0 and
        len(result.story_components.chapters) > 0
    )
```

### Phase 4 Validation (Story Architect → Voice Director)

```python
def validate_narrative_result(result: NarrativeResult) -> bool:
    """Ensure narrative is sufficient for synthesis."""
    return (
        len(result.chapters) > 0 and
        all(ch.script and len(ch.script) > 100 for ch in result.chapters) and
        result.estimated_duration_seconds > 60
    )
```

## Error Handling

### Graceful Degradation

| Stage | Failure Mode | Recovery |
|-------|--------------|----------|
| Repomix | CLI not installed | Return helpful error message |
| Repomix | Repo too large | Apply aggressive filters, retry |
| Analysis | 0 files detected | Check regex patterns, retry with fallback |
| Narrative | Style not supported | Default to "documentary" |
| Voice | ElevenLabs quota exceeded | Return partial audio with warning |
| Voice | Chunk too long | Split into smaller segments |

## File Structure

```
src/codestory/
├── agents/
│   ├── __init__.py           # Agent exports
│   └── base.py               # AgentDefinitions, CodeStoryClient
├── tools/
│   ├── __init__.py           # Tool registry, create_codestory_server()
│   ├── intent.py             # Intent analysis tools
│   ├── repomix.py            # Repomix integration (REPLACES github.py)
│   ├── analysis.py           # Code structure analysis
│   ├── narrative.py          # Story generation
│   └── voice.py              # ElevenLabs synthesis
├── models/
│   ├── contracts.py          # Data contracts (IntentResult, etc.)
│   ├── story.py              # Database models
│   └── user.py               # User models
├── api/
│   ├── main.py               # FastAPI app
│   └── routers/              # API endpoints
└── pipeline/
    └── orchestrator.py       # Pipeline coordination
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2025-12-31 | Initial architecture with GitHub API |
| 0.2.0 | 2025-12-31 | Replaced GitHub API with Repomix CLI |
| 0.3.0 | 2025-12-31 | Added artifact persistence for cross-agent access |
