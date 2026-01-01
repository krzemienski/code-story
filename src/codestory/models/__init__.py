"""Database models and data contracts for Code Story.

SQLAlchemy models for:
- Users and API keys
- Repositories
- Stories and chapters
- Story intents

Data contracts for pipeline handoffs:
- IntentResult: Intent Agent → Repo Analyzer
- AnalysisResult: Repo Analyzer → Story Architect
- NarrativeResult: Story Architect → Voice Director
- AudioResult: Voice Director → API/Frontend

All models use async SQLAlchemy with asyncpg for PostgreSQL.
"""

from .contracts import (
    AnalysisResult,
    AudioResult,
    ChapterAudio,
    ChapterOutline,
    ChapterScript,
    ChapterSuggestion,
    CodeCharacter,
    ComponentInfo,
    IntentResult,
    NarrativeResult,
    StoryComponents,
    VoiceProfile,
    validate_analysis_result,
    validate_audio_result,
    validate_intent_result,
    validate_narrative_result,
)
from .database import Base, close_db, get_engine, get_session, init_db
from .intent import StoryIntent
from .story import NarrativeStyle, Repository, Story, StoryChapter, StoryStatus
from .user import APIKey, User
from .admin import (
    AdminRole,
    AdminSession,
    AdminUser,
    AuditLog,
    Permission,
    ROLE_PERMISSIONS,
)
from .analytics import (
    APICallLog,
    DailyMetrics,
    StoryUsage,
    UsageQuotaTracker,
)
from .team import (
    Team,
    TeamMember,
    TeamInvite,
    TeamPlan,
    MemberRole,
    InviteStatus,
)
from .collaboration import (
    CollaboratorRole,
    ActivityType,
    CommentStatus,
    StoryCollaborator,
    StoryComment,
    StoryActivity,
)
from .sso import (
    SSOProvider,
    SSOStatus,
    SSOConfiguration,
    SSOSession,
)

__all__ = [
    # Database
    "Base",
    "init_db",
    "get_session",
    "get_engine",
    "close_db",
    # User models
    "User",
    "APIKey",
    # Admin models
    "AdminUser",
    "AdminSession",
    "AdminRole",
    "Permission",
    "ROLE_PERMISSIONS",
    "AuditLog",
    # Analytics models
    "DailyMetrics",
    "StoryUsage",
    "APICallLog",
    "UsageQuotaTracker",
    # Team models
    "Team",
    "TeamMember",
    "TeamInvite",
    "TeamPlan",
    "MemberRole",
    "InviteStatus",
    # Collaboration models
    "CollaboratorRole",
    "ActivityType",
    "CommentStatus",
    "StoryCollaborator",
    "StoryComment",
    "StoryActivity",
    # SSO models
    "SSOProvider",
    "SSOStatus",
    "SSOConfiguration",
    "SSOSession",
    # Story models
    "Repository",
    "Story",
    "StoryChapter",
    "StoryStatus",
    "NarrativeStyle",
    # Intent
    "StoryIntent",
    # Data Contracts (pipeline handoffs)
    "ChapterOutline",
    "IntentResult",
    "ComponentInfo",
    "CodeCharacter",
    "ChapterSuggestion",
    "StoryComponents",
    "AnalysisResult",
    "ChapterScript",
    "NarrativeResult",
    "VoiceProfile",
    "ChapterAudio",
    "AudioResult",
    # Validation functions
    "validate_intent_result",
    "validate_analysis_result",
    "validate_narrative_result",
    "validate_audio_result",
]
