"""Team and organization data models for enterprise features."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, ForeignKey,
    Text, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped

from codestory.models.database import Base

if TYPE_CHECKING:
    from codestory.models.user import User
    from codestory.models.story import Story


class TeamPlan(str, Enum):
    """Subscription plans for teams."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class MemberRole(str, Enum):
    """Roles within a team."""
    OWNER = "owner"         # Full control, billing, can delete team
    ADMIN = "admin"         # Manage members, settings, all stories
    MEMBER = "member"       # Create/edit own stories, view team stories
    VIEWER = "viewer"       # View-only access to team stories


class InviteStatus(str, Enum):
    """Status of team invitations."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Team(Base):
    """Organization/team workspace."""
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Identity
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # Branding
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), nullable=True)  # Hex color

    # Subscription
    plan = Column(SQLEnum(TeamPlan), default=TeamPlan.FREE, nullable=False)
    plan_started_at = Column(DateTime, nullable=True)
    plan_expires_at = Column(DateTime, nullable=True)

    # Quotas (overridable per plan)
    max_members = Column(Integer, default=5)
    max_stories_per_month = Column(Integer, default=10)
    max_storage_gb = Column(Integer, default=5)

    # Usage tracking
    stories_this_month = Column(Integer, default=0)
    storage_used_bytes = Column(Integer, default=0)

    # Settings
    settings = Column(Text, nullable=True)  # JSON blob for team settings

    # SSO (Phase 13-03)
    sso_enabled = Column(Boolean, default=False)
    sso_provider = Column(String(50), nullable=True)  # saml, oidc
    sso_config = Column(Text, nullable=True)  # Encrypted JSON

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    suspended_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    members: Mapped[List["TeamMember"]] = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan"
    )
    invites: Mapped[List["TeamInvite"]] = relationship(
        "TeamInvite",
        back_populates="team",
        cascade="all, delete-orphan"
    )
    stories: Mapped[List["Story"]] = relationship(
        "Story",
        back_populates="team",
        foreign_keys="Story.team_id"
    )

    @property
    def is_active(self) -> bool:
        """Check if team is active (not suspended or deleted)."""
        return self.suspended_at is None and self.deleted_at is None

    @property
    def member_count(self) -> int:
        """Count active team members."""
        return len([m for m in self.members if m.is_active])

    def can_add_member(self) -> bool:
        """Check if team can add more members."""
        return self.member_count < self.max_members

    def can_create_story(self) -> bool:
        """Check if team can create more stories this month."""
        return self.stories_this_month < self.max_stories_per_month


class TeamMember(Base):
    """Team membership junction table."""
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', name='uq_team_member'),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Role
    role = Column(SQLEnum(MemberRole), default=MemberRole.MEMBER, nullable=False)

    # Metadata
    joined_at = Column(DateTime, default=datetime.utcnow)
    invited_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Activity
    last_active_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    deactivated_at = Column(DateTime, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="members")
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="team_memberships"
    )
    invited_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[invited_by_id]
    )

    def has_permission(self, required_role: MemberRole) -> bool:
        """Check if member has required role or higher."""
        role_hierarchy = {
            MemberRole.VIEWER: 0,
            MemberRole.MEMBER: 1,
            MemberRole.ADMIN: 2,
            MemberRole.OWNER: 3
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 0)


class TeamInvite(Base):
    """Pending team invitations."""
    __tablename__ = "team_invites"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)

    # Invite details
    email = Column(String(255), nullable=False, index=True)
    role = Column(SQLEnum(MemberRole), default=MemberRole.MEMBER, nullable=False)
    token = Column(String(64), nullable=False, unique=True, index=True)

    # Tracking
    invited_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(SQLEnum(InviteStatus), default=InviteStatus.PENDING, nullable=False)

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="invites")
    invited_by: Mapped["User"] = relationship("User")

    def is_valid(self) -> bool:
        """Check if invite is still valid."""
        if self.status != InviteStatus.PENDING:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True
