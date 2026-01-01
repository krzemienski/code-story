"""Admin analytics router for usage tracking and cost monitoring.

Provides endpoints for:
- Dashboard overview metrics
- Daily metrics retrieval and aggregation
- API call statistics
- User usage and quota management
- Cost breakdowns by service

All endpoints require admin authentication with analytics permissions.
"""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.api.deps import get_session
from codestory.api.routers.admin_auth import get_current_admin, require_permission
from codestory.models import AdminUser, Permission
from codestory.services import AnalyticsService

router = APIRouter()


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class DateRangeParams(BaseModel):
    """Date range query parameters."""

    start_date: date = Field(
        default_factory=lambda: date.today() - timedelta(days=30),
        description="Start date (inclusive)",
    )
    end_date: date = Field(
        default_factory=date.today,
        description="End date (inclusive)",
    )


class DashboardResponse(BaseModel):
    """Dashboard overview response."""

    period: dict[str, str]
    users: dict[str, int]
    stories: dict[str, Any]
    costs: dict[str, Any]
    tokens: dict[str, int]
    revenue: dict[str, Any]


class DailyMetricsResponse(BaseModel):
    """Daily metrics response."""

    date: date
    new_users: int
    active_users: int
    stories_created: int
    stories_completed: int
    api_requests: int
    anthropic_cost_cents: int
    elevenlabs_cost_cents: int
    s3_cost_cents: int
    total_cost_cents: int
    revenue_cents: int


class UserUsageResponse(BaseModel):
    """User usage summary response."""

    user_id: int
    story_count: int
    tokens: dict[str, int]
    audio_minutes: float
    storage_mb: float
    total_cost_cents: int
    total_cost_dollars: float


class QuotaStatusResponse(BaseModel):
    """Quota status response."""

    resource: str
    used: int
    limit: int
    remaining: int
    percentage_used: float
    exceeded: bool
    period: dict[str, str]


class UserQuotasResponse(BaseModel):
    """All user quotas response."""

    user_id: int
    stories: QuotaStatusResponse
    api_requests: QuotaStatusResponse
    storage: QuotaStatusResponse
    any_exceeded: bool


class APIStatsResponse(BaseModel):
    """API statistics response."""

    period: dict[str, str]
    by_service: dict[str, Any]
    totals: dict[str, int]


class CostBreakdownResponse(BaseModel):
    """Cost breakdown response."""

    period: dict[str, str]
    by_service: dict[str, dict[str, Any]]
    total_cents: int
    total_dollars: float
    daily_average_cents: float


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------


def get_analytics_service(session: AsyncSession) -> AnalyticsService:
    """Create analytics service instance."""
    return AnalyticsService(session)


# -------------------------------------------------------------------------
# Dashboard & Overview
# -------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get analytics dashboard",
    description="Get overview dashboard with key metrics for the last 30 days.",
)
async def get_dashboard(
    admin: AdminUser = Depends(require_permission(Permission.VIEW_ANALYTICS)),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Get analytics dashboard overview."""
    service = get_analytics_service(session)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    summary = await service.get_metrics_summary(start_date, end_date)
    return DashboardResponse(**summary)


@router.get(
    "/summary",
    response_model=DashboardResponse,
    summary="Get metrics summary",
    description="Get aggregated metrics summary for a custom date range.",
)
async def get_metrics_summary(
    start_date: date = Query(
        default_factory=lambda: date.today() - timedelta(days=30),
        description="Start date (inclusive)",
    ),
    end_date: date = Query(
        default_factory=date.today,
        description="End date (inclusive)",
    ),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_ANALYTICS)),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Get metrics summary for date range."""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    service = get_analytics_service(session)
    summary = await service.get_metrics_summary(start_date, end_date)
    return DashboardResponse(**summary)


# -------------------------------------------------------------------------
# Daily Metrics
# -------------------------------------------------------------------------


@router.get(
    "/daily-metrics",
    response_model=list[DailyMetricsResponse],
    summary="Get daily metrics",
    description="Get daily metrics for a date range.",
)
async def get_daily_metrics(
    start_date: date = Query(
        default_factory=lambda: date.today() - timedelta(days=7),
        description="Start date (inclusive)",
    ),
    end_date: date = Query(
        default_factory=date.today,
        description="End date (inclusive)",
    ),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_ANALYTICS)),
    session: AsyncSession = Depends(get_session),
) -> list[DailyMetricsResponse]:
    """Get daily metrics for date range."""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    service = get_analytics_service(session)
    metrics = await service.get_daily_metrics(start_date, end_date)

    return [
        DailyMetricsResponse(
            date=m.date,
            new_users=m.new_users,
            active_users=m.active_users,
            stories_created=m.stories_created,
            stories_completed=m.stories_completed,
            api_requests=m.api_requests,
            anthropic_cost_cents=m.anthropic_cost,
            elevenlabs_cost_cents=m.elevenlabs_cost,
            s3_cost_cents=m.s3_cost,
            total_cost_cents=m.total_cost,
            revenue_cents=m.revenue,
        )
        for m in metrics
    ]


@router.post(
    "/aggregate/{target_date}",
    response_model=DailyMetricsResponse,
    summary="Aggregate daily metrics",
    description="Trigger aggregation of metrics for a specific date.",
)
async def aggregate_daily_metrics(
    target_date: date,
    admin: AdminUser = Depends(require_permission(Permission.EXPORT_DATA)),
    session: AsyncSession = Depends(get_session),
) -> DailyMetricsResponse:
    """Aggregate metrics for a specific date."""
    if target_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot aggregate metrics for future dates",
        )

    service = get_analytics_service(session)
    metrics = await service.aggregate_daily_metrics(target_date)
    await session.commit()

    return DailyMetricsResponse(
        date=metrics.date,
        new_users=metrics.new_users,
        active_users=metrics.active_users,
        stories_created=metrics.stories_created,
        stories_completed=metrics.stories_completed,
        api_requests=metrics.api_requests,
        anthropic_cost_cents=metrics.anthropic_cost,
        elevenlabs_cost_cents=metrics.elevenlabs_cost,
        s3_cost_cents=metrics.s3_cost,
        total_cost_cents=metrics.total_cost,
        revenue_cents=metrics.revenue,
    )


# -------------------------------------------------------------------------
# API Statistics
# -------------------------------------------------------------------------


@router.get(
    "/api-stats",
    response_model=APIStatsResponse,
    summary="Get API call statistics",
    description="Get statistics for external API calls by service.",
)
async def get_api_stats(
    start_date: date = Query(
        default_factory=lambda: date.today() - timedelta(days=7),
        description="Start date (inclusive)",
    ),
    end_date: date = Query(
        default_factory=date.today,
        description="End date (inclusive)",
    ),
    service_filter: str | None = Query(
        None,
        alias="service",
        description="Filter by service (anthropic, elevenlabs, s3)",
    ),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_ANALYTICS)),
    session: AsyncSession = Depends(get_session),
) -> APIStatsResponse:
    """Get API call statistics."""
    analytics = get_analytics_service(session)
    stats = await analytics.get_api_call_stats(start_date, end_date, service_filter)
    return APIStatsResponse(**stats)


# -------------------------------------------------------------------------
# Cost Analysis
# -------------------------------------------------------------------------


@router.get(
    "/costs/breakdown",
    response_model=CostBreakdownResponse,
    summary="Get cost breakdown",
    description="Get detailed cost breakdown by service for a date range.",
)
async def get_cost_breakdown(
    start_date: date = Query(
        default_factory=lambda: date.today() - timedelta(days=30),
        description="Start date (inclusive)",
    ),
    end_date: date = Query(
        default_factory=date.today,
        description="End date (inclusive)",
    ),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_ANALYTICS)),
    session: AsyncSession = Depends(get_session),
) -> CostBreakdownResponse:
    """Get cost breakdown by service."""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    analytics = get_analytics_service(session)
    metrics = await analytics.get_daily_metrics(start_date, end_date)

    # Aggregate by service
    anthropic_total = sum(m.anthropic_cost for m in metrics)
    elevenlabs_total = sum(m.elevenlabs_cost for m in metrics)
    s3_total = sum(m.s3_cost for m in metrics)
    total = anthropic_total + elevenlabs_total + s3_total

    days = len(metrics) or 1

    return CostBreakdownResponse(
        period={"start": start_date.isoformat(), "end": end_date.isoformat()},
        by_service={
            "anthropic": {
                "total_cents": anthropic_total,
                "total_dollars": round(anthropic_total / 100, 2),
                "percentage": round(anthropic_total / total * 100, 1) if total else 0,
                "daily_average_cents": round(anthropic_total / days, 2),
            },
            "elevenlabs": {
                "total_cents": elevenlabs_total,
                "total_dollars": round(elevenlabs_total / 100, 2),
                "percentage": round(elevenlabs_total / total * 100, 1) if total else 0,
                "daily_average_cents": round(elevenlabs_total / days, 2),
            },
            "s3": {
                "total_cents": s3_total,
                "total_dollars": round(s3_total / 100, 2),
                "percentage": round(s3_total / total * 100, 1) if total else 0,
                "daily_average_cents": round(s3_total / days, 2),
            },
        },
        total_cents=total,
        total_dollars=round(total / 100, 2),
        daily_average_cents=round(total / days, 2),
    )


# -------------------------------------------------------------------------
# User Analytics
# -------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/usage",
    response_model=UserUsageResponse,
    summary="Get user usage",
    description="Get usage summary for a specific user.",
)
async def get_user_usage(
    user_id: int,
    start_date: date | None = Query(None, description="Optional start date filter"),
    end_date: date | None = Query(None, description="Optional end date filter"),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_ANALYTICS)),
    session: AsyncSession = Depends(get_session),
) -> UserUsageResponse:
    """Get user usage summary."""
    analytics = get_analytics_service(session)
    usage = await analytics.get_user_usage_summary(user_id, start_date, end_date)
    return UserUsageResponse(**usage)


@router.get(
    "/users/{user_id}/quotas",
    response_model=UserQuotasResponse,
    summary="Get user quotas",
    description="Get quota status for a specific user.",
)
async def get_user_quotas(
    user_id: int,
    admin: AdminUser = Depends(require_permission(Permission.VIEW_ANALYTICS)),
    session: AsyncSession = Depends(get_session),
) -> UserQuotasResponse:
    """Get user quota status."""
    analytics = get_analytics_service(session)
    quotas = await analytics.get_user_quotas(user_id)

    return UserQuotasResponse(
        user_id=quotas["user_id"],
        stories=QuotaStatusResponse(**quotas["stories"]),
        api_requests=QuotaStatusResponse(**quotas["api_requests"]),
        storage=QuotaStatusResponse(**quotas["storage"]),
        any_exceeded=quotas["any_exceeded"],
    )


@router.post(
    "/users/{user_id}/quotas/reset",
    response_model=dict[str, str],
    summary="Reset user quotas",
    description="Reset quota usage for a user (admin override).",
)
async def reset_user_quotas(
    user_id: int,
    admin: AdminUser = Depends(require_permission(Permission.EDIT_USERS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Reset user quota usage."""
    analytics = get_analytics_service(session)
    tracker = await analytics.get_or_create_quota_tracker(user_id, "monthly")
    tracker.stories_used = 0
    tracker.api_requests_used = 0
    tracker.storage_bytes_used = 0
    await session.commit()

    return {"status": "success", "message": f"Quotas reset for user {user_id}"}
