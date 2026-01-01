"""Backend Services for Code Story.

These are deterministic, infrastructure-level services that prepare context
for Claude Agents. They are NOT agent tools - they run BEFORE agents are spawned.

Architecture:
    Frontend → FastAPI → Services (prepare context) → Agent (creative work)

Services:
- repository: Repomix CLI integration, repo packaging
- analysis: Code structure analysis, pattern detection
- pipeline: Orchestrates the full story generation flow

Usage:
    from codestory.services import PipelineService, StoryGenerationRequest

    # In FastAPI endpoint
    pipeline = PipelineService()
    request = StoryGenerationRequest(
        github_url="https://github.com/owner/repo",
        narrative_style="documentary",
    )

    # Stream progress (for SSE/WebSocket)
    async for event in pipeline.generate_story_stream(request):
        yield event.to_dict()

    # Or get final result
    result = await pipeline.generate_story(request)
"""

from .admin_auth import AdminAuthService
from .analysis import AnalysisService
from .analytics import AnalyticsService
from .pipeline import (
    PipelineConfig,
    PipelineEvent,
    PipelineService,
    PipelineStage,
    StoryGenerationRequest,
    StoryGenerationResult,
)
from .repository import PackageResult, RepositoryService, RepositoryStats
from .team_service import (
    TeamService,
    TeamServiceError,
    TeamNotFoundError,
    MemberNotFoundError,
    InviteNotFoundError,
    QuotaExceededError,
    PermissionDeniedError,
    InviteExpiredError,
)
from .collaboration_service import (
    CollaborationService,
    CollaborationError,
    StoryNotFoundError,
    CollaboratorNotFoundError,
    CommentNotFoundError,
)
from .sso_service import (
    SSOService,
    SSOError,
    SSOConfigNotFoundError,
    SSOConfigExistsError,
    SSOSessionInvalidError,
    SSODomainNotAllowedError,
    SSOProvisioningDisabledError,
)

__all__ = [
    # Admin Auth Service
    "AdminAuthService",
    # Analytics Service
    "AnalyticsService",
    # Repository Service
    "RepositoryService",
    "PackageResult",
    "RepositoryStats",
    # Analysis Service
    "AnalysisService",
    # Pipeline Service
    "PipelineService",
    "PipelineConfig",
    "PipelineEvent",
    "PipelineStage",
    "StoryGenerationRequest",
    "StoryGenerationResult",
    # Team Service
    "TeamService",
    "TeamServiceError",
    "TeamNotFoundError",
    "MemberNotFoundError",
    "InviteNotFoundError",
    "QuotaExceededError",
    "PermissionDeniedError",
    "InviteExpiredError",
    # Collaboration Service
    "CollaborationService",
    "CollaborationError",
    "StoryNotFoundError",
    "CollaboratorNotFoundError",
    "CommentNotFoundError",
    # SSO Service
    "SSOService",
    "SSOError",
    "SSOConfigNotFoundError",
    "SSOConfigExistsError",
    "SSOSessionInvalidError",
    "SSODomainNotAllowedError",
    "SSOProvisioningDisabledError",
]
