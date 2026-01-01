"""Team collaboration features.

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-01

Adds:
- team_id column to stories table
- story_collaborators table for sharing
- story_comments table for feedback
- story_activities table for audit trail
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE collaboratorrole AS ENUM ('owner', 'editor', 'commenter', 'viewer');
    """)
    op.execute("""
        CREATE TYPE commentstatus AS ENUM ('active', 'resolved', 'deleted');
    """)
    op.execute("""
        CREATE TYPE activitytype AS ENUM (
            'story_created', 'story_updated', 'story_completed', 'story_failed',
            'story_deleted', 'story_shared', 'story_unshared',
            'collaborator_added', 'collaborator_removed', 'collaborator_role_changed',
            'comment_added', 'comment_updated', 'comment_deleted', 'comment_resolved',
            'transferred_to_team', 'removed_from_team'
        );
    """)

    # Add team_id to stories table
    op.add_column(
        "stories",
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_stories_team_id", "stories", ["team_id"])

    # Create story_collaborators table
    op.create_table(
        "story_collaborators",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "story_id",
            sa.Integer,
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum("owner", "editor", "commenter", "viewer", name="collaboratorrole"),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("invited_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("invited_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("accepted", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("accepted_at", sa.DateTime, nullable=True),
        sa.Column("last_accessed_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("story_id", "user_id", name="uq_story_collaborator"),
    )
    op.create_index("ix_story_collaborators_story_id", "story_collaborators", ["story_id"])
    op.create_index("ix_story_collaborators_user_id", "story_collaborators", ["user_id"])

    # Create story_comments table
    op.create_table(
        "story_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "story_id",
            sa.Integer,
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("story_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "chapter_id",
            sa.Integer,
            sa.ForeignKey("story_chapters.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("timestamp_seconds", sa.Integer, nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "resolved", "deleted", name="commentstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("resolved_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_story_comments_story_id", "story_comments", ["story_id"])
    op.create_index("ix_story_comments_parent_id", "story_comments", ["parent_id"])

    # Create story_activities table
    op.create_table(
        "story_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "story_id",
            sa.Integer,
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "activity_type",
            sa.Enum(
                "story_created", "story_updated", "story_completed", "story_failed",
                "story_deleted", "story_shared", "story_unshared",
                "collaborator_added", "collaborator_removed", "collaborator_role_changed",
                "comment_added", "comment_updated", "comment_deleted", "comment_resolved",
                "transferred_to_team", "removed_from_team",
                name="activitytype",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("activity_metadata", sa.Text, nullable=True),
        sa.Column("target_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_story_activities_story_id", "story_activities", ["story_id"])
    op.create_index("ix_story_activities_activity_type", "story_activities", ["activity_type"])
    op.create_index("ix_story_activities_created_at", "story_activities", ["created_at"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("story_activities")
    op.drop_table("story_comments")
    op.drop_table("story_collaborators")

    # Remove team_id from stories
    op.drop_index("ix_stories_team_id", table_name="stories")
    op.drop_column("stories", "team_id")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS activitytype;")
    op.execute("DROP TYPE IF EXISTS commentstatus;")
    op.execute("DROP TYPE IF EXISTS collaboratorrole;")
