"""Team workspaces for enterprise features.

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-01

Creates team, team_members, and team_invites tables for enterprise
workspace functionality with role-based access control.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE teamplan AS ENUM ('free', 'starter', 'professional', 'enterprise');
    """)
    op.execute("""
        CREATE TYPE memberrole AS ENUM ('owner', 'admin', 'member', 'viewer');
    """)
    op.execute("""
        CREATE TYPE invitestatus AS ENUM ('pending', 'accepted', 'declined', 'expired', 'revoked');
    """)

    # Create teams table
    op.create_table(
        "teams",
        sa.Column("id", sa.String(36), primary_key=True),
        # Identity
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text, nullable=True),
        # Branding
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        # Subscription
        sa.Column(
            "plan",
            sa.Enum("free", "starter", "professional", "enterprise", name="teamplan"),
            nullable=False,
            server_default="free",
        ),
        sa.Column("plan_started_at", sa.DateTime, nullable=True),
        sa.Column("plan_expires_at", sa.DateTime, nullable=True),
        # Quotas
        sa.Column("max_members", sa.Integer, nullable=False, server_default="5"),
        sa.Column("max_stories_per_month", sa.Integer, nullable=False, server_default="10"),
        sa.Column("max_storage_gb", sa.Integer, nullable=False, server_default="5"),
        # Usage tracking
        sa.Column("stories_this_month", sa.Integer, nullable=False, server_default="0"),
        sa.Column("storage_used_bytes", sa.Integer, nullable=False, server_default="0"),
        # Settings
        sa.Column("settings", sa.Text, nullable=True),
        # SSO (Phase 13-03)
        sa.Column("sso_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sso_provider", sa.String(50), nullable=True),
        sa.Column("sso_config", sa.Text, nullable=True),
        # Lifecycle
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("suspended_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    )

    # Create team_members table
    op.create_table(
        "team_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Role
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "member", "viewer", name="memberrole"),
            nullable=False,
            server_default="member",
        ),
        # Metadata
        sa.Column("joined_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "invited_by_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        # Activity
        sa.Column("last_active_at", sa.DateTime, nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("deactivated_at", sa.DateTime, nullable=True),
        # Unique constraint
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )

    # Create team_invites table
    op.create_table(
        "team_invites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Invite details
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "member", "viewer", name="memberrole"),
            nullable=False,
            server_default="member",
        ),
        sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
        # Tracking
        sa.Column(
            "invited_by_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "declined", "expired", "revoked", name="invitestatus"),
            nullable=False,
            server_default="pending",
        ),
        # Lifecycle
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("accepted_at", sa.DateTime, nullable=True),
    )

    # Create indexes for common queries
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_invites_team_id", "team_invites", ["team_id"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("team_invites")
    op.drop_table("team_members")
    op.drop_table("teams")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS invitestatus;")
    op.execute("DROP TYPE IF EXISTS memberrole;")
    op.execute("DROP TYPE IF EXISTS teamplan;")
