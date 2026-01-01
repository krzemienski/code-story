"""Analytics models for usage tracking and cost monitoring.

Tracks:
- Daily aggregated metrics
- Per-story usage statistics
- API call logs with costs
"""

from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .database import Base


class DailyMetrics(Base):
    """Daily aggregated platform metrics.

    Stores daily rollups of:
    - User activity (new, active, churned)
    - Story generation stats
    - API costs by service
    - Revenue data
    """

    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)

    # User metrics
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    churned_users: Mapped[int] = mapped_column(Integer, default=0)
    total_users: Mapped[int] = mapped_column(Integer, default=0)

    # Story metrics
    stories_created: Mapped[int] = mapped_column(Integer, default=0)
    stories_completed: Mapped[int] = mapped_column(Integer, default=0)
    stories_failed: Mapped[int] = mapped_column(Integer, default=0)
    total_audio_minutes: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00")
    )

    # API request metrics
    api_requests: Mapped[int] = mapped_column(Integer, default=0)
    api_errors: Mapped[int] = mapped_column(Integer, default=0)

    # Cost tracking (in cents for precision)
    anthropic_cost: Mapped[int] = mapped_column(Integer, default=0)
    elevenlabs_cost: Mapped[int] = mapped_column(Integer, default=0)
    s3_cost: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[int] = mapped_column(Integer, default=0)

    # Token usage
    anthropic_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    anthropic_output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Revenue (in cents)
    revenue: Mapped[int] = mapped_column(Integer, default=0)
    subscriptions_started: Mapped[int] = mapped_column(Integer, default=0)
    subscriptions_cancelled: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<DailyMetrics(date={self.date})>"


class StoryUsage(Base):
    """Per-story usage and cost tracking.

    Tracks resource consumption for each story:
    - Claude API tokens and cost
    - ElevenLabs audio cost
    - S3 storage cost
    - Generation time
    """

    __tablename__ = "story_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Claude API usage
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    anthropic_cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # ElevenLabs usage
    audio_characters: Mapped[int] = mapped_column(Integer, default=0)
    audio_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    elevenlabs_cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # S3 storage
    storage_bytes: Mapped[int] = mapped_column(Integer, default=0)
    s3_cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # Total cost
    total_cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    generation_time_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<StoryUsage(story_id={self.story_id})>"


class APICallLog(Base):
    """Individual API call log for detailed tracking.

    Logs each external API call:
    - Anthropic Claude API
    - ElevenLabs TTS
    - S3 operations
    """

    __tablename__ = "api_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Request context
    story_id: Mapped[int | None] = mapped_column(
        ForeignKey("stories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # API identification
    service: Mapped[str] = mapped_column(String(50), index=True)  # anthropic, elevenlabs, s3
    endpoint: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10))  # GET, POST, etc.

    # Request details
    request_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    response_size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    # Token usage (Anthropic)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cost (in cents)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    # Response
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extra metadata (using 'call_metadata' to avoid SQLAlchemy reserved name)
    call_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<APICallLog(id={self.id}, service='{self.service}')>"


class UsageQuotaTracker(Base):
    """Track user quota usage for rate limiting.

    Tracks usage against quota limits:
    - Stories per month
    - API requests per day
    - Storage bytes
    """

    __tablename__ = "usage_quota_trackers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Period tracking
    period_type: Mapped[str] = mapped_column(String(20))  # daily, monthly
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    # Usage counts
    stories_used: Mapped[int] = mapped_column(Integer, default=0)
    api_requests_used: Mapped[int] = mapped_column(Integer, default=0)
    storage_bytes_used: Mapped[int] = mapped_column(Integer, default=0)

    # Quota limits (snapshot from user at period start)
    stories_limit: Mapped[int] = mapped_column(Integer, default=10)
    api_requests_limit: Mapped[int] = mapped_column(Integer, default=1000)
    storage_bytes_limit: Mapped[int] = mapped_column(Integer, default=104857600)  # 100MB

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<UsageQuotaTracker(user_id={self.user_id}, period={self.period_type})>"
