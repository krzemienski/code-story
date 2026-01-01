"""Analytics service for usage tracking and cost monitoring.

Provides:
- Daily metrics aggregation and retrieval
- Per-story usage tracking
- API call logging with cost calculation
- User quota management
- Cost breakdowns by service
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.models import (
    APICallLog,
    DailyMetrics,
    Story,
    StoryUsage,
    User,
    UsageQuotaTracker,
)


# Cost rates (in cents per unit)
COST_RATES = {
    "anthropic_input": Decimal("0.003"),    # $0.003 per 1K input tokens
    "anthropic_output": Decimal("0.015"),   # $0.015 per 1K output tokens
    "elevenlabs_character": Decimal("0.00018"),  # ~$0.18 per 1K chars
    "s3_storage_gb": Decimal("2.3"),        # $0.023 per GB per month
    "s3_request": Decimal("0.0004"),        # $0.0004 per request
}


class AnalyticsService:
    """Service for analytics data aggregation and cost tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Daily Metrics
    # -------------------------------------------------------------------------

    async def get_daily_metrics(
        self,
        start_date: date,
        end_date: date,
    ) -> list[DailyMetrics]:
        """Get daily metrics for a date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of DailyMetrics records
        """
        result = await self.session.execute(
            select(DailyMetrics)
            .where(
                and_(
                    DailyMetrics.date >= start_date,
                    DailyMetrics.date <= end_date,
                )
            )
            .order_by(DailyMetrics.date)
        )
        return list(result.scalars().all())

    async def get_or_create_daily_metrics(self, target_date: date) -> DailyMetrics:
        """Get or create daily metrics for a specific date.

        Args:
            target_date: The date to get/create metrics for

        Returns:
            DailyMetrics record
        """
        result = await self.session.execute(
            select(DailyMetrics).where(DailyMetrics.date == target_date)
        )
        metrics = result.scalar_one_or_none()

        if not metrics:
            metrics = DailyMetrics(date=target_date)
            self.session.add(metrics)
            await self.session.flush()

        return metrics

    async def aggregate_daily_metrics(self, target_date: date) -> DailyMetrics:
        """Aggregate metrics for a specific date from raw data.

        Calculates:
        - User metrics (new, active, churned)
        - Story metrics (created, completed, failed)
        - API costs by service
        - Token usage

        Args:
            target_date: Date to aggregate metrics for

        Returns:
            Updated DailyMetrics record
        """
        metrics = await self.get_or_create_daily_metrics(target_date)
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        # Count new users
        new_users_result = await self.session.execute(
            select(func.count(User.id)).where(
                and_(
                    User.created_at >= start_of_day,
                    User.created_at <= end_of_day,
                )
            )
        )
        metrics.new_users = new_users_result.scalar() or 0

        # Count stories created today
        stories_result = await self.session.execute(
            select(func.count(Story.id)).where(
                and_(
                    Story.created_at >= start_of_day,
                    Story.created_at <= end_of_day,
                )
            )
        )
        metrics.stories_created = stories_result.scalar() or 0

        # Aggregate API call costs
        api_costs = await self.session.execute(
            select(
                APICallLog.service,
                func.sum(APICallLog.cost_cents).label("total_cost"),
                func.sum(APICallLog.input_tokens).label("total_input"),
                func.sum(APICallLog.output_tokens).label("total_output"),
                func.count(APICallLog.id).label("request_count"),
            )
            .where(
                and_(
                    APICallLog.created_at >= start_of_day,
                    APICallLog.created_at <= end_of_day,
                )
            )
            .group_by(APICallLog.service)
        )

        for row in api_costs:
            if row.service == "anthropic":
                metrics.anthropic_cost = row.total_cost or 0
                metrics.anthropic_input_tokens = row.total_input or 0
                metrics.anthropic_output_tokens = row.total_output or 0
            elif row.service == "elevenlabs":
                metrics.elevenlabs_cost = row.total_cost or 0
            elif row.service == "s3":
                metrics.s3_cost = row.total_cost or 0
            metrics.api_requests += row.request_count or 0

        metrics.total_cost = (
            metrics.anthropic_cost + metrics.elevenlabs_cost + metrics.s3_cost
        )

        await self.session.flush()
        return metrics

    async def get_metrics_summary(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Get aggregated summary of metrics for a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Summary dict with totals and averages
        """
        metrics = await self.get_daily_metrics(start_date, end_date)

        if not metrics:
            return {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "days": 0,
                "users": {"new": 0, "active": 0, "churned": 0},
                "stories": {"created": 0, "completed": 0, "failed": 0},
                "costs": {"total": 0, "anthropic": 0, "elevenlabs": 0, "s3": 0},
                "tokens": {"input": 0, "output": 0},
                "revenue": {"total": 0, "profit_margin": 0},
            }

        total_new_users = sum(m.new_users for m in metrics)
        total_active_users = sum(m.active_users for m in metrics)
        total_stories = sum(m.stories_created for m in metrics)
        total_completed = sum(m.stories_completed for m in metrics)
        total_failed = sum(m.stories_failed for m in metrics)
        total_anthropic = sum(m.anthropic_cost for m in metrics)
        total_elevenlabs = sum(m.elevenlabs_cost for m in metrics)
        total_s3 = sum(m.s3_cost for m in metrics)
        total_cost = sum(m.total_cost for m in metrics)
        total_revenue = sum(m.revenue for m in metrics)
        total_input_tokens = sum(m.anthropic_input_tokens for m in metrics)
        total_output_tokens = sum(m.anthropic_output_tokens for m in metrics)

        profit_margin = (
            ((total_revenue - total_cost) / total_revenue * 100)
            if total_revenue > 0
            else 0
        )

        return {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "days": len(metrics),
            "users": {
                "new": total_new_users,
                "active": total_active_users,
                "churned": sum(m.churned_users for m in metrics),
            },
            "stories": {
                "created": total_stories,
                "completed": total_completed,
                "failed": total_failed,
                "completion_rate": (
                    round(total_completed / total_stories * 100, 1)
                    if total_stories > 0
                    else 0
                ),
            },
            "costs": {
                "total_cents": total_cost,
                "total_dollars": round(total_cost / 100, 2),
                "anthropic_cents": total_anthropic,
                "elevenlabs_cents": total_elevenlabs,
                "s3_cents": total_s3,
            },
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens,
            },
            "revenue": {
                "total_cents": total_revenue,
                "total_dollars": round(total_revenue / 100, 2),
                "profit_margin_percent": round(profit_margin, 1),
            },
        }

    # -------------------------------------------------------------------------
    # Story Usage
    # -------------------------------------------------------------------------

    async def track_story_usage(
        self,
        story_id: int,
        user_id: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        audio_characters: int = 0,
        audio_duration_seconds: int = 0,
        storage_bytes: int = 0,
        generation_time_seconds: int = 0,
    ) -> StoryUsage:
        """Track usage for a story generation.

        Args:
            story_id: Story ID
            user_id: User ID
            input_tokens: Claude input tokens used
            output_tokens: Claude output tokens used
            audio_characters: Characters synthesized to audio
            audio_duration_seconds: Duration of generated audio
            storage_bytes: S3 storage used
            generation_time_seconds: Total generation time

        Returns:
            StoryUsage record
        """
        # Calculate costs
        anthropic_cost = int(
            (input_tokens / 1000 * COST_RATES["anthropic_input"] +
             output_tokens / 1000 * COST_RATES["anthropic_output"]) * 100
        )
        elevenlabs_cost = int(
            audio_characters * COST_RATES["elevenlabs_character"] * 100
        )
        s3_cost = int(
            (storage_bytes / (1024 ** 3)) * COST_RATES["s3_storage_gb"] * 100
        )
        total_cost = anthropic_cost + elevenlabs_cost + s3_cost

        usage = StoryUsage(
            story_id=story_id,
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            anthropic_cost_cents=anthropic_cost,
            audio_characters=audio_characters,
            audio_duration_seconds=audio_duration_seconds,
            elevenlabs_cost_cents=elevenlabs_cost,
            storage_bytes=storage_bytes,
            s3_cost_cents=s3_cost,
            total_cost_cents=total_cost,
            generation_time_seconds=generation_time_seconds,
        )
        self.session.add(usage)
        await self.session.flush()
        return usage

    async def get_story_usage(self, story_id: int) -> StoryUsage | None:
        """Get usage data for a specific story.

        Args:
            story_id: Story ID

        Returns:
            StoryUsage record or None
        """
        result = await self.session.execute(
            select(StoryUsage).where(StoryUsage.story_id == story_id)
        )
        return result.scalar_one_or_none()

    async def get_user_usage_summary(
        self,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Get usage summary for a user.

        Args:
            user_id: User ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Usage summary dict
        """
        query = select(
            func.count(StoryUsage.id).label("story_count"),
            func.sum(StoryUsage.input_tokens).label("total_input_tokens"),
            func.sum(StoryUsage.output_tokens).label("total_output_tokens"),
            func.sum(StoryUsage.audio_duration_seconds).label("total_audio_seconds"),
            func.sum(StoryUsage.total_cost_cents).label("total_cost"),
            func.sum(StoryUsage.storage_bytes).label("total_storage"),
        ).where(StoryUsage.user_id == user_id)

        if start_date:
            query = query.where(StoryUsage.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.where(StoryUsage.created_at <= datetime.combine(end_date, datetime.max.time()))

        result = await self.session.execute(query)
        row = result.one()

        return {
            "user_id": user_id,
            "story_count": row.story_count or 0,
            "tokens": {
                "input": row.total_input_tokens or 0,
                "output": row.total_output_tokens or 0,
            },
            "audio_minutes": round((row.total_audio_seconds or 0) / 60, 2),
            "storage_mb": round((row.total_storage or 0) / (1024 * 1024), 2),
            "total_cost_cents": row.total_cost or 0,
            "total_cost_dollars": round((row.total_cost or 0) / 100, 2),
        }

    # -------------------------------------------------------------------------
    # API Call Logging
    # -------------------------------------------------------------------------

    async def log_api_call(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: int,
        story_id: int | None = None,
        user_id: int | None = None,
        request_size_bytes: int = 0,
        response_size_bytes: int = 0,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_cents: int = 0,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> APICallLog:
        """Log an external API call.

        Args:
            service: Service name (anthropic, elevenlabs, s3)
            endpoint: API endpoint called
            method: HTTP method
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            story_id: Optional associated story ID
            user_id: Optional associated user ID
            request_size_bytes: Request body size
            response_size_bytes: Response body size
            input_tokens: Anthropic input tokens (if applicable)
            output_tokens: Anthropic output tokens (if applicable)
            cost_cents: Calculated cost in cents
            error_message: Error message if failed
            metadata: Additional metadata

        Returns:
            APICallLog record
        """
        log = APICallLog(
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            story_id=story_id,
            user_id=user_id,
            request_size_bytes=request_size_bytes,
            response_size_bytes=response_size_bytes,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_cents=cost_cents,
            error_message=error_message,
            call_metadata=metadata or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_api_call_stats(
        self,
        start_date: date,
        end_date: date,
        service: str | None = None,
    ) -> dict[str, Any]:
        """Get API call statistics for a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            service: Optional service filter

        Returns:
            Statistics dict
        """
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query = select(
            APICallLog.service,
            func.count(APICallLog.id).label("total_calls"),
            func.sum(APICallLog.cost_cents).label("total_cost"),
            func.avg(APICallLog.duration_ms).label("avg_duration"),
            func.count(APICallLog.id).filter(APICallLog.status_code >= 400).label("error_count"),
        ).where(
            and_(
                APICallLog.created_at >= start_dt,
                APICallLog.created_at <= end_dt,
            )
        ).group_by(APICallLog.service)

        if service:
            query = query.where(APICallLog.service == service)

        result = await self.session.execute(query)

        stats = {}
        for row in result:
            stats[row.service] = {
                "total_calls": row.total_calls or 0,
                "total_cost_cents": row.total_cost or 0,
                "avg_duration_ms": round(row.avg_duration or 0, 2),
                "error_count": row.error_count or 0,
                "error_rate": (
                    round((row.error_count or 0) / (row.total_calls or 1) * 100, 2)
                ),
            }

        return {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "by_service": stats,
            "totals": {
                "calls": sum(s["total_calls"] for s in stats.values()),
                "cost_cents": sum(s["total_cost_cents"] for s in stats.values()),
                "errors": sum(s["error_count"] for s in stats.values()),
            },
        }

    # -------------------------------------------------------------------------
    # Quota Management
    # -------------------------------------------------------------------------

    async def get_or_create_quota_tracker(
        self,
        user_id: int,
        period_type: str = "monthly",
    ) -> UsageQuotaTracker:
        """Get or create quota tracker for current period.

        Args:
            user_id: User ID
            period_type: 'daily' or 'monthly'

        Returns:
            UsageQuotaTracker record
        """
        today = date.today()

        if period_type == "daily":
            period_start = today
            period_end = today
        else:  # monthly
            period_start = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            period_end = next_month.replace(day=1) - timedelta(days=1)

        result = await self.session.execute(
            select(UsageQuotaTracker).where(
                and_(
                    UsageQuotaTracker.user_id == user_id,
                    UsageQuotaTracker.period_type == period_type,
                    UsageQuotaTracker.period_start == period_start,
                )
            )
        )
        tracker = result.scalar_one_or_none()

        if not tracker:
            tracker = UsageQuotaTracker(
                user_id=user_id,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
            )
            self.session.add(tracker)
            await self.session.flush()

        return tracker

    async def increment_quota_usage(
        self,
        user_id: int,
        stories: int = 0,
        api_requests: int = 0,
        storage_bytes: int = 0,
    ) -> UsageQuotaTracker:
        """Increment quota usage for a user.

        Args:
            user_id: User ID
            stories: Stories to add
            api_requests: API requests to add
            storage_bytes: Storage bytes to add

        Returns:
            Updated tracker
        """
        tracker = await self.get_or_create_quota_tracker(user_id, "monthly")
        tracker.stories_used += stories
        tracker.api_requests_used += api_requests
        tracker.storage_bytes_used += storage_bytes
        await self.session.flush()
        return tracker

    async def check_quota(
        self,
        user_id: int,
        resource: str,
    ) -> dict[str, Any]:
        """Check quota status for a user resource.

        Args:
            user_id: User ID
            resource: 'stories', 'api_requests', or 'storage'

        Returns:
            Quota status dict
        """
        tracker = await self.get_or_create_quota_tracker(user_id, "monthly")

        if resource == "stories":
            used = tracker.stories_used
            limit = tracker.stories_limit
        elif resource == "api_requests":
            used = tracker.api_requests_used
            limit = tracker.api_requests_limit
        elif resource == "storage":
            used = tracker.storage_bytes_used
            limit = tracker.storage_bytes_limit
        else:
            raise ValueError(f"Unknown resource: {resource}")

        remaining = max(0, limit - used)
        percentage = round(used / limit * 100, 1) if limit > 0 else 100

        return {
            "resource": resource,
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percentage_used": percentage,
            "exceeded": used >= limit,
            "period": {
                "start": tracker.period_start.isoformat(),
                "end": tracker.period_end.isoformat(),
            },
        }

    async def get_user_quotas(self, user_id: int) -> dict[str, Any]:
        """Get all quota statuses for a user.

        Args:
            user_id: User ID

        Returns:
            All quota statuses
        """
        stories = await self.check_quota(user_id, "stories")
        api_requests = await self.check_quota(user_id, "api_requests")
        storage = await self.check_quota(user_id, "storage")

        return {
            "user_id": user_id,
            "stories": stories,
            "api_requests": api_requests,
            "storage": storage,
            "any_exceeded": (
                stories["exceeded"] or
                api_requests["exceeded"] or
                storage["exceeded"]
            ),
        }
