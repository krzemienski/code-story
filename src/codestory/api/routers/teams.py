"""Teams router for enterprise workspace management.

Endpoints for creating and managing team workspaces:
- Team CRUD operations
- Member management with role hierarchy
- Invitation flow (create, accept, revoke)
- Team settings and quotas
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, EmailStr

from codestory.api.deps import DBSession, SupabaseUser
from codestory.api.exceptions import NotFoundError
from codestory.models.team import (
    Team,
    TeamMember,
    TeamInvite,
    TeamPlan,
    MemberRole,
    InviteStatus,
)
from codestory.services.team_service import (
    TeamService,
    TeamNotFoundError,
    MemberNotFoundError,
    InviteNotFoundError,
    QuotaExceededError,
    PermissionDeniedError,
    InviteExpiredError,
)

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================


class TeamCreate(BaseModel):
    """Request to create a new team."""

    name: str = Field(..., min_length=2, max_length=100, description="Team display name")
    slug: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe identifier (lowercase, hyphens allowed)",
    )
    description: Optional[str] = Field(None, max_length=500, description="Team description")


class TeamUpdate(BaseModel):
    """Request to update team details."""

    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color code (e.g., #FF5733)",
    )


class TeamResponse(BaseModel):
    """Team information response."""

    id: str
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    primary_color: Optional[str]
    plan: TeamPlan
    max_members: int
    max_stories_per_month: int
    member_count: int
    stories_this_month: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    """List of teams."""

    items: list[TeamResponse]
    total: int


class MemberResponse(BaseModel):
    """Team member information."""

    id: str
    user_id: str
    role: MemberRole
    joined_at: datetime
    last_active_at: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class MemberListResponse(BaseModel):
    """List of team members."""

    items: list[MemberResponse]
    total: int


class MemberRoleUpdate(BaseModel):
    """Request to update a member's role."""

    role: MemberRole = Field(..., description="New role to assign")


class InviteCreate(BaseModel):
    """Request to create a team invitation."""

    email: EmailStr = Field(..., description="Email address to invite")
    role: MemberRole = Field(
        default=MemberRole.MEMBER,
        description="Role to assign on acceptance",
    )


class InviteResponse(BaseModel):
    """Team invitation information."""

    id: str
    email: str
    role: MemberRole
    status: InviteStatus
    invited_by_id: str
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime]

    class Config:
        from_attributes = True


class InviteListResponse(BaseModel):
    """List of team invitations."""

    items: list[InviteResponse]
    total: int


class AcceptInviteRequest(BaseModel):
    """Request to accept an invitation."""

    token: str = Field(..., min_length=32, description="Invitation token")


class AcceptInviteResponse(BaseModel):
    """Response after accepting invitation."""

    team_id: str
    team_name: str
    role: MemberRole
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def _team_to_response(team: Team) -> TeamResponse:
    """Convert Team model to response schema."""
    return TeamResponse(
        id=team.id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        logo_url=team.logo_url,
        primary_color=team.primary_color,
        plan=team.plan,
        max_members=team.max_members,
        max_stories_per_month=team.max_stories_per_month,
        member_count=team.member_count,
        stories_this_month=team.stories_this_month,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


def _handle_service_error(e: Exception) -> None:
    """Convert service exceptions to HTTP exceptions."""
    if isinstance(e, TeamNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, MemberNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, InviteNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, QuotaExceededError):
        raise HTTPException(status_code=402, detail=str(e))
    if isinstance(e, PermissionDeniedError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, InviteExpiredError):
        raise HTTPException(status_code=410, detail=str(e))
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    raise e


# =============================================================================
# Team Endpoints
# =============================================================================


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new team",
    description="""
    Create a new team workspace with the authenticated user as owner.

    The team slug must be unique and URL-safe (lowercase alphanumeric with hyphens).
    Teams start on the FREE plan with default quotas.
    """,
)
async def create_team(
    request: TeamCreate,
    user: SupabaseUser,
    db: DBSession,
) -> TeamResponse:
    """Create a new team with current user as owner."""
    try:
        service = TeamService(db)
        team = await service.create_team(
            name=request.name,
            slug=request.slug,
            owner_user_id=user["id"],
            description=request.description,
        )
        return _team_to_response(team)
    except Exception as e:
        _handle_service_error(e)


@router.get(
    "",
    response_model=TeamListResponse,
    summary="List user's teams",
    description="List all teams the authenticated user is a member of.",
)
async def list_teams(
    user: SupabaseUser,
    db: DBSession,
) -> TeamListResponse:
    """List teams for the current user."""
    service = TeamService(db)
    teams = await service.list_user_teams(user["id"])
    return TeamListResponse(
        items=[_team_to_response(t) for t in teams],
        total=len(teams),
    )


@router.get(
    "/{team_id}",
    response_model=TeamResponse,
    summary="Get team details",
    description="Get detailed information about a specific team.",
)
async def get_team(
    team_id: Annotated[str, Path(description="Team UUID")],
    user: SupabaseUser,
    db: DBSession,
) -> TeamResponse:
    """Get team by ID."""
    try:
        service = TeamService(db)
        # Verify user is member
        role = await service.get_user_role_in_team(team_id, user["id"])
        if role is None:
            raise HTTPException(
                status_code=403,
                detail="You are not a member of this team",
            )
        team = await service.get_team(team_id)
        return _team_to_response(team)
    except Exception as e:
        _handle_service_error(e)


@router.patch(
    "/{team_id}",
    response_model=TeamResponse,
    summary="Update team",
    description="Update team details. Requires ADMIN or OWNER role.",
)
async def update_team(
    team_id: Annotated[str, Path(description="Team UUID")],
    request: TeamUpdate,
    user: SupabaseUser,
    db: DBSession,
) -> TeamResponse:
    """Update team details."""
    try:
        service = TeamService(db)
        team = await service.update_team(
            team_id=team_id,
            user_id=user["id"],
            name=request.name,
            description=request.description,
            logo_url=request.logo_url,
            primary_color=request.primary_color,
        )
        return _team_to_response(team)
    except Exception as e:
        _handle_service_error(e)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete team",
    description="Soft-delete a team. Requires OWNER role.",
)
async def delete_team(
    team_id: Annotated[str, Path(description="Team UUID")],
    user: SupabaseUser,
    db: DBSession,
) -> None:
    """Delete a team (soft-delete)."""
    try:
        service = TeamService(db)
        await service.delete_team(team_id, user["id"])
    except Exception as e:
        _handle_service_error(e)


# =============================================================================
# Member Endpoints
# =============================================================================


@router.get(
    "/{team_id}/members",
    response_model=MemberListResponse,
    summary="List team members",
    description="List all members of a team.",
)
async def list_members(
    team_id: Annotated[str, Path(description="Team UUID")],
    user: SupabaseUser,
    db: DBSession,
    include_inactive: Annotated[bool, Query(description="Include deactivated members")] = False,
) -> MemberListResponse:
    """List team members."""
    try:
        service = TeamService(db)
        # Verify user is member
        role = await service.get_user_role_in_team(team_id, user["id"])
        if role is None:
            raise HTTPException(
                status_code=403,
                detail="You are not a member of this team",
            )
        members = await service.get_team_members(team_id, include_inactive)
        return MemberListResponse(
            items=[MemberResponse.model_validate(m) for m in members],
            total=len(members),
        )
    except Exception as e:
        _handle_service_error(e)


@router.patch(
    "/{team_id}/members/{user_id}/role",
    response_model=MemberResponse,
    summary="Update member role",
    description="Change a team member's role. Requires ADMIN or OWNER role.",
)
async def update_member_role(
    team_id: Annotated[str, Path(description="Team UUID")],
    user_id: Annotated[str, Path(description="Member's user UUID")],
    request: MemberRoleUpdate,
    current_user: SupabaseUser,
    db: DBSession,
) -> MemberResponse:
    """Update a member's role."""
    try:
        service = TeamService(db)
        member = await service.update_member_role(
            team_id=team_id,
            member_user_id=user_id,
            new_role=request.role,
            updated_by_id=current_user["id"],
        )
        return MemberResponse.model_validate(member)
    except Exception as e:
        _handle_service_error(e)


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member",
    description="Remove a member from the team. Requires ADMIN role, or self-removal.",
)
async def remove_member(
    team_id: Annotated[str, Path(description="Team UUID")],
    user_id: Annotated[str, Path(description="Member's user UUID")],
    current_user: SupabaseUser,
    db: DBSession,
) -> None:
    """Remove a member from the team."""
    try:
        service = TeamService(db)
        await service.remove_member(
            team_id=team_id,
            member_user_id=user_id,
            removed_by_id=current_user["id"],
        )
    except Exception as e:
        _handle_service_error(e)


# =============================================================================
# Invitation Endpoints
# =============================================================================


@router.post(
    "/{team_id}/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invitation",
    description="Create an invitation to join the team. Requires ADMIN role.",
)
async def create_invite(
    team_id: Annotated[str, Path(description="Team UUID")],
    request: InviteCreate,
    user: SupabaseUser,
    db: DBSession,
) -> InviteResponse:
    """Create a team invitation."""
    try:
        service = TeamService(db)
        invite = await service.create_invite(
            team_id=team_id,
            email=request.email,
            role=request.role,
            invited_by_id=user["id"],
        )
        return InviteResponse.model_validate(invite)
    except Exception as e:
        _handle_service_error(e)


@router.get(
    "/{team_id}/invites",
    response_model=InviteListResponse,
    summary="List invitations",
    description="List pending invitations for a team. Requires ADMIN role.",
)
async def list_invites(
    team_id: Annotated[str, Path(description="Team UUID")],
    user: SupabaseUser,
    db: DBSession,
    status_filter: Annotated[Optional[InviteStatus], Query(description="Filter by status")] = None,
) -> InviteListResponse:
    """List team invitations."""
    try:
        service = TeamService(db)
        # Verify admin role
        await service._require_role(team_id, user["id"], MemberRole.ADMIN)
        invites = await service.get_team_invites(team_id, status_filter)
        return InviteListResponse(
            items=[InviteResponse.model_validate(i) for i in invites],
            total=len(invites),
        )
    except Exception as e:
        _handle_service_error(e)


@router.delete(
    "/{team_id}/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke invitation",
    description="Revoke a pending invitation. Requires ADMIN role.",
)
async def revoke_invite(
    team_id: Annotated[str, Path(description="Team UUID")],
    invite_id: Annotated[str, Path(description="Invitation UUID")],
    user: SupabaseUser,
    db: DBSession,
) -> None:
    """Revoke a team invitation."""
    try:
        service = TeamService(db)
        await service.revoke_invite(invite_id, user["id"])
    except Exception as e:
        _handle_service_error(e)


@router.post(
    "/accept-invite",
    response_model=AcceptInviteResponse,
    summary="Accept invitation",
    description="""
    Accept a team invitation using the token sent via email.

    The token is validated for expiration and status before creating membership.
    """,
)
async def accept_invite(
    request: AcceptInviteRequest,
    user: SupabaseUser,
    db: DBSession,
) -> AcceptInviteResponse:
    """Accept a team invitation."""
    try:
        service = TeamService(db)
        member = await service.accept_invite(
            token=request.token,
            user_id=user["id"],
        )
        # Get team name for response
        team = await service.get_team(member.team_id)
        return AcceptInviteResponse(
            team_id=team.id,
            team_name=team.name,
            role=member.role,
            message=f"Successfully joined team '{team.name}' as {member.role.value}",
        )
    except Exception as e:
        _handle_service_error(e)
