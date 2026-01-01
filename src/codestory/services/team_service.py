"""Team management service for enterprise workspaces.

Provides business logic for team operations:
- Team CRUD with quota management
- Member management with role hierarchy
- Invitation flow with token-based acceptance
- Usage tracking and quota enforcement
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from codestory.models.team import (
    Team,
    TeamMember,
    TeamInvite,
    TeamPlan,
    MemberRole,
    InviteStatus,
)


class TeamServiceError(Exception):
    """Base exception for team service errors."""
    pass


class TeamNotFoundError(TeamServiceError):
    """Team not found."""
    pass


class MemberNotFoundError(TeamServiceError):
    """Team member not found."""
    pass


class InviteNotFoundError(TeamServiceError):
    """Invitation not found."""
    pass


class QuotaExceededError(TeamServiceError):
    """Team quota exceeded."""
    pass


class PermissionDeniedError(TeamServiceError):
    """User lacks required permission."""
    pass


class InviteExpiredError(TeamServiceError):
    """Invitation has expired or is invalid."""
    pass


class TeamService:
    """Service for managing team workspaces."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Team CRUD
    # =========================================================================

    async def create_team(
        self,
        name: str,
        slug: str,
        owner_user_id: str,
        description: Optional[str] = None,
        plan: TeamPlan = TeamPlan.FREE,
    ) -> Team:
        """Create a new team with the given user as owner.

        Args:
            name: Team display name
            slug: URL-safe unique identifier
            owner_user_id: User ID who will be the team owner
            description: Optional team description
            plan: Subscription plan (default FREE)

        Returns:
            Created team with owner membership

        Raises:
            ValueError: If slug is already taken
        """
        # Check slug uniqueness
        existing = await self.db.execute(
            select(Team).where(Team.slug == slug)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Team slug '{slug}' is already taken")

        # Set plan-based quotas
        quota_map = {
            TeamPlan.FREE: {"members": 5, "stories": 10, "storage": 5},
            TeamPlan.STARTER: {"members": 15, "stories": 50, "storage": 25},
            TeamPlan.PROFESSIONAL: {"members": 50, "stories": 200, "storage": 100},
            TeamPlan.ENTERPRISE: {"members": 500, "stories": 1000, "storage": 1000},
        }
        quotas = quota_map.get(plan, quota_map[TeamPlan.FREE])

        # Create team
        team = Team(
            id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            description=description,
            plan=plan,
            plan_started_at=datetime.utcnow(),
            max_members=quotas["members"],
            max_stories_per_month=quotas["stories"],
            max_storage_gb=quotas["storage"],
        )
        self.db.add(team)

        # Add owner as first member
        owner_member = TeamMember(
            id=str(uuid.uuid4()),
            team_id=team.id,
            user_id=owner_user_id,
            role=MemberRole.OWNER,
            joined_at=datetime.utcnow(),
        )
        self.db.add(owner_member)

        await self.db.commit()
        await self.db.refresh(team)

        return team

    async def get_team(self, team_id: str) -> Team:
        """Get team by ID with members loaded.

        Args:
            team_id: Team UUID

        Returns:
            Team with relationships

        Raises:
            TeamNotFoundError: If team doesn't exist
        """
        result = await self.db.execute(
            select(Team)
            .options(selectinload(Team.members))
            .where(Team.id == team_id, Team.deleted_at.is_(None))
        )
        team = result.scalar_one_or_none()
        if not team:
            raise TeamNotFoundError(f"Team {team_id} not found")
        return team

    async def get_team_by_slug(self, slug: str) -> Team:
        """Get team by slug.

        Args:
            slug: Team slug

        Returns:
            Team with relationships

        Raises:
            TeamNotFoundError: If team doesn't exist
        """
        result = await self.db.execute(
            select(Team)
            .options(selectinload(Team.members))
            .where(Team.slug == slug, Team.deleted_at.is_(None))
        )
        team = result.scalar_one_or_none()
        if not team:
            raise TeamNotFoundError(f"Team with slug '{slug}' not found")
        return team

    async def update_team(
        self,
        team_id: str,
        user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        primary_color: Optional[str] = None,
    ) -> Team:
        """Update team details.

        Args:
            team_id: Team UUID
            user_id: User making the update (must be admin or owner)
            name: New team name
            description: New description
            logo_url: New logo URL
            primary_color: New primary color (hex)

        Returns:
            Updated team

        Raises:
            TeamNotFoundError: If team doesn't exist
            PermissionDeniedError: If user lacks admin role
        """
        team = await self.get_team(team_id)
        await self._require_role(team_id, user_id, MemberRole.ADMIN)

        if name is not None:
            team.name = name
        if description is not None:
            team.description = description
        if logo_url is not None:
            team.logo_url = logo_url
        if primary_color is not None:
            team.primary_color = primary_color

        team.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(team)

        return team

    async def delete_team(self, team_id: str, user_id: str) -> None:
        """Soft-delete a team (owner only).

        Args:
            team_id: Team UUID
            user_id: User requesting deletion (must be owner)

        Raises:
            TeamNotFoundError: If team doesn't exist
            PermissionDeniedError: If user is not owner
        """
        team = await self.get_team(team_id)
        await self._require_role(team_id, user_id, MemberRole.OWNER)

        team.deleted_at = datetime.utcnow()
        await self.db.commit()

    async def list_user_teams(
        self,
        user_id: str,
        include_inactive: bool = False,
    ) -> list[Team]:
        """List all teams a user belongs to.

        Args:
            user_id: User UUID
            include_inactive: Include suspended/deleted teams

        Returns:
            List of teams with user's membership
        """
        query = (
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user_id, TeamMember.is_active == True)
        )

        if not include_inactive:
            query = query.where(
                Team.deleted_at.is_(None),
                Team.suspended_at.is_(None),
            )

        result = await self.db.execute(query.order_by(Team.name))
        return list(result.scalars().all())

    # =========================================================================
    # Member Management
    # =========================================================================

    async def add_member(
        self,
        team_id: str,
        user_id: str,
        role: MemberRole = MemberRole.MEMBER,
        invited_by_id: Optional[str] = None,
    ) -> TeamMember:
        """Add a user to a team.

        Args:
            team_id: Team UUID
            user_id: User to add
            role: Role to assign (default MEMBER)
            invited_by_id: User who invited this member

        Returns:
            Created team membership

        Raises:
            TeamNotFoundError: If team doesn't exist
            QuotaExceededError: If team is at member limit
        """
        team = await self.get_team(team_id)

        if not team.can_add_member():
            raise QuotaExceededError(
                f"Team has reached member limit ({team.max_members})"
            )

        # Check if already a member
        existing = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        existing_member = existing.scalar_one_or_none()
        if existing_member:
            if existing_member.is_active:
                raise ValueError("User is already a team member")
            # Reactivate if previously deactivated
            existing_member.is_active = True
            existing_member.deactivated_at = None
            existing_member.role = role
            await self.db.commit()
            return existing_member

        member = TeamMember(
            id=str(uuid.uuid4()),
            team_id=team_id,
            user_id=user_id,
            role=role,
            invited_by_id=invited_by_id,
            joined_at=datetime.utcnow(),
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)

        return member

    async def update_member_role(
        self,
        team_id: str,
        member_user_id: str,
        new_role: MemberRole,
        updated_by_id: str,
    ) -> TeamMember:
        """Update a team member's role.

        Args:
            team_id: Team UUID
            member_user_id: User whose role to update
            new_role: New role to assign
            updated_by_id: User making the change (must have higher role)

        Returns:
            Updated membership

        Raises:
            MemberNotFoundError: If member doesn't exist
            PermissionDeniedError: If updater lacks permission
        """
        # Get both memberships
        updater_member = await self._get_member(team_id, updated_by_id)
        target_member = await self._get_member(team_id, member_user_id)

        # Cannot demote owner or change to owner unless owner
        if target_member.role == MemberRole.OWNER:
            raise PermissionDeniedError("Cannot change owner's role")
        if new_role == MemberRole.OWNER and updater_member.role != MemberRole.OWNER:
            raise PermissionDeniedError("Only owner can transfer ownership")

        # Must have higher role than target
        if not updater_member.has_permission(MemberRole.ADMIN):
            raise PermissionDeniedError("Only admins can change roles")

        # Transfer ownership if assigning owner role
        if new_role == MemberRole.OWNER:
            updater_member.role = MemberRole.ADMIN
            target_member.role = MemberRole.OWNER
        else:
            target_member.role = new_role

        await self.db.commit()
        await self.db.refresh(target_member)

        return target_member

    async def remove_member(
        self,
        team_id: str,
        member_user_id: str,
        removed_by_id: str,
    ) -> None:
        """Remove a member from the team.

        Args:
            team_id: Team UUID
            member_user_id: User to remove
            removed_by_id: User performing removal

        Raises:
            MemberNotFoundError: If member doesn't exist
            PermissionDeniedError: If remover lacks permission
        """
        remover = await self._get_member(team_id, removed_by_id)
        target = await self._get_member(team_id, member_user_id)

        # Cannot remove owner
        if target.role == MemberRole.OWNER:
            raise PermissionDeniedError("Cannot remove team owner")

        # Must be admin+ or self-removal
        if member_user_id != removed_by_id:
            if not remover.has_permission(MemberRole.ADMIN):
                raise PermissionDeniedError("Only admins can remove members")

        target.is_active = False
        target.deactivated_at = datetime.utcnow()
        await self.db.commit()

    async def get_team_members(
        self,
        team_id: str,
        include_inactive: bool = False,
    ) -> list[TeamMember]:
        """Get all members of a team.

        Args:
            team_id: Team UUID
            include_inactive: Include deactivated members

        Returns:
            List of team members
        """
        query = (
            select(TeamMember)
            .where(TeamMember.team_id == team_id)
        )

        if not include_inactive:
            query = query.where(TeamMember.is_active == True)

        result = await self.db.execute(query.order_by(TeamMember.joined_at))
        return list(result.scalars().all())

    # =========================================================================
    # Invitation Flow
    # =========================================================================

    async def create_invite(
        self,
        team_id: str,
        email: str,
        role: MemberRole,
        invited_by_id: str,
        expires_days: int = 7,
    ) -> TeamInvite:
        """Create an invitation to join a team.

        Args:
            team_id: Team UUID
            email: Email address to invite
            role: Role to assign on acceptance
            invited_by_id: User creating the invite
            expires_days: Days until invite expires

        Returns:
            Created invitation with token

        Raises:
            TeamNotFoundError: If team doesn't exist
            PermissionDeniedError: If inviter lacks admin role
        """
        team = await self.get_team(team_id)
        await self._require_role(team_id, invited_by_id, MemberRole.ADMIN)

        if not team.can_add_member():
            raise QuotaExceededError(
                f"Team has reached member limit ({team.max_members})"
            )

        # Check for existing pending invite
        existing = await self.db.execute(
            select(TeamInvite).where(
                TeamInvite.team_id == team_id,
                TeamInvite.email == email.lower(),
                TeamInvite.status == InviteStatus.PENDING,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Pending invitation already exists for {email}")

        invite = TeamInvite(
            id=str(uuid.uuid4()),
            team_id=team_id,
            email=email.lower(),
            role=role,
            token=secrets.token_urlsafe(48),
            invited_by_id=invited_by_id,
            expires_at=datetime.utcnow() + timedelta(days=expires_days),
        )
        self.db.add(invite)
        await self.db.commit()
        await self.db.refresh(invite)

        return invite

    async def accept_invite(
        self,
        token: str,
        user_id: str,
    ) -> TeamMember:
        """Accept a team invitation.

        Args:
            token: Invitation token
            user_id: User accepting the invite

        Returns:
            Created team membership

        Raises:
            InviteNotFoundError: If token is invalid
            InviteExpiredError: If invite has expired
        """
        result = await self.db.execute(
            select(TeamInvite)
            .options(selectinload(TeamInvite.team))
            .where(TeamInvite.token == token)
        )
        invite = result.scalar_one_or_none()

        if not invite:
            raise InviteNotFoundError("Invalid invitation token")

        if not invite.is_valid():
            if datetime.utcnow() > invite.expires_at:
                invite.status = InviteStatus.EXPIRED
                await self.db.commit()
                raise InviteExpiredError("Invitation has expired")
            raise InviteExpiredError("Invitation is no longer valid")

        # Mark invite as accepted
        invite.status = InviteStatus.ACCEPTED
        invite.accepted_at = datetime.utcnow()

        # Add user to team
        member = await self.add_member(
            team_id=invite.team_id,
            user_id=user_id,
            role=invite.role,
            invited_by_id=invite.invited_by_id,
        )

        await self.db.commit()

        return member

    async def revoke_invite(
        self,
        invite_id: str,
        revoked_by_id: str,
    ) -> None:
        """Revoke a pending invitation.

        Args:
            invite_id: Invitation UUID
            revoked_by_id: User revoking the invite

        Raises:
            InviteNotFoundError: If invite doesn't exist
            PermissionDeniedError: If user lacks admin role
        """
        result = await self.db.execute(
            select(TeamInvite).where(TeamInvite.id == invite_id)
        )
        invite = result.scalar_one_or_none()

        if not invite:
            raise InviteNotFoundError(f"Invitation {invite_id} not found")

        await self._require_role(invite.team_id, revoked_by_id, MemberRole.ADMIN)

        invite.status = InviteStatus.REVOKED
        await self.db.commit()

    async def get_team_invites(
        self,
        team_id: str,
        status_filter: Optional[InviteStatus] = None,
    ) -> list[TeamInvite]:
        """Get invitations for a team.

        Args:
            team_id: Team UUID
            status_filter: Filter by status (default: PENDING only)

        Returns:
            List of invitations
        """
        query = select(TeamInvite).where(TeamInvite.team_id == team_id)

        if status_filter:
            query = query.where(TeamInvite.status == status_filter)
        else:
            query = query.where(TeamInvite.status == InviteStatus.PENDING)

        result = await self.db.execute(query.order_by(TeamInvite.created_at.desc()))
        return list(result.scalars().all())

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _get_member(self, team_id: str, user_id: str) -> TeamMember:
        """Get a team member or raise error."""
        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
                TeamMember.is_active == True,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise MemberNotFoundError(f"User {user_id} is not a member of team {team_id}")
        return member

    async def _require_role(
        self,
        team_id: str,
        user_id: str,
        required_role: MemberRole,
    ) -> TeamMember:
        """Ensure user has at least the required role."""
        member = await self._get_member(team_id, user_id)
        if not member.has_permission(required_role):
            raise PermissionDeniedError(
                f"Requires {required_role.value} role or higher"
            )
        return member

    async def get_user_role_in_team(
        self,
        team_id: str,
        user_id: str,
    ) -> Optional[MemberRole]:
        """Get a user's role in a team, or None if not a member."""
        try:
            member = await self._get_member(team_id, user_id)
            return member.role
        except MemberNotFoundError:
            return None


__all__ = [
    "TeamService",
    "TeamServiceError",
    "TeamNotFoundError",
    "MemberNotFoundError",
    "InviteNotFoundError",
    "QuotaExceededError",
    "PermissionDeniedError",
    "InviteExpiredError",
]
