"""Create analytics tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-01

Tables:
- daily_metrics: Daily aggregated platform metrics
- story_usage: Per-story usage and cost tracking
- api_call_logs: Individual API call logging
- usage_quota_trackers: User quota tracking
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Daily aggregated metrics
    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        # User metrics
        sa.Column("new_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("churned_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_users", sa.Integer(), nullable=False, server_default="0"),
        # Story metrics
        sa.Column("stories_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stories_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stories_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_audio_minutes",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        # API request metrics
        sa.Column("api_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_errors", sa.Integer(), nullable=False, server_default="0"),
        # Cost tracking (in cents)
        sa.Column("anthropic_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("elevenlabs_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("s3_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Integer(), nullable=False, server_default="0"),
        # Token usage
        sa.Column("anthropic_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anthropic_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        # Revenue (in cents)
        sa.Column("revenue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subscriptions_started", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subscriptions_cancelled", sa.Integer(), nullable=False, server_default="0"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date"),
    )
    op.create_index("ix_daily_metrics_date", "daily_metrics", ["date"])

    # Per-story usage tracking
    op.create_table(
        "story_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Claude API usage
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anthropic_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        # ElevenLabs usage
        sa.Column("audio_characters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audio_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("elevenlabs_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        # S3 storage
        sa.Column("storage_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("s3_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        # Total cost
        sa.Column("total_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        # Timing
        sa.Column("generation_time_seconds", sa.Integer(), nullable=False, server_default="0"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_story_usage_story_id", "story_usage", ["story_id"])
    op.create_index("ix_story_usage_user_id", "story_usage", ["user_id"])

    # API call logs
    op.create_table(
        "api_call_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        # Request context
        sa.Column("story_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        # API identification
        sa.Column("service", sa.String(length=50), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        # Request details
        sa.Column("request_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        # Token usage (Anthropic)
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        # Cost (in cents)
        sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"),
        # Response
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Extra metadata
        sa.Column("call_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_call_logs_story_id", "api_call_logs", ["story_id"])
    op.create_index("ix_api_call_logs_user_id", "api_call_logs", ["user_id"])
    op.create_index("ix_api_call_logs_service", "api_call_logs", ["service"])
    op.create_index("ix_api_call_logs_created_at", "api_call_logs", ["created_at"])

    # Usage quota trackers
    op.create_table(
        "usage_quota_trackers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Period tracking
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        # Usage counts
        sa.Column("stories_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_requests_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_bytes_used", sa.Integer(), nullable=False, server_default="0"),
        # Quota limits
        sa.Column("stories_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("api_requests_limit", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column(
            "storage_bytes_limit",
            sa.Integer(),
            nullable=False,
            server_default="104857600",  # 100MB
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usage_quota_trackers_user_id", "usage_quota_trackers", ["user_id"])


def downgrade() -> None:
    op.drop_table("usage_quota_trackers")
    op.drop_table("api_call_logs")
    op.drop_table("story_usage")
    op.drop_table("daily_metrics")
