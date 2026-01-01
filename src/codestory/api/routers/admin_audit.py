"""Admin audit log endpoints.

Provides endpoints for:
- Query audit logs with comprehensive filtering
- Get audit activity summary
- Get available audit categories and actions

All endpoints require admin authentication with VIEW_AUDIT_LOGS permission.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.api.deps import get_session
from codestory.api.routers.admin_auth import require_permission
from codestory.models import AdminUser, AuditLog, Permission

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class AuditLogItem(BaseModel):
    """Audit log item response."""

    id: int
    action: str
    category: str
    actor_email: str
    target_type: str | None
    target_id: str | None
    details: dict[str, Any]
    status: str
    error_message: str | None
    ip_address: str | None
    created_at: datetime


class AuditLogsResponse(BaseModel):
    """Audit logs list response."""

    logs: list[AuditLogItem]
    total: int
    page: int
    per_page: int


class AuditSummaryResponse(BaseModel):
    """Audit activity summary response."""

    total_events: int
    by_category: dict[str, int]
    by_action: dict[str, int]
    by_status: dict[str, int]
    period_days: int


class AuditCategoriesResponse(BaseModel):
    """Available audit categories and actions."""

    categories: list[str]
    actions: dict[str, list[str]]


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------


AUDIT_CATEGORIES = ["auth", "user", "api_key", "story", "analytics", "system"]

AUDIT_ACTIONS = {
    "auth": [
        "admin_login",
        "admin_logout",
        "admin_login_failed",
        "admin_2fa_enabled",
        "admin_2fa_disabled",
        "admin_session_revoked",
    ],
    "user": [
        "user_created",
        "user_updated",
        "user_suspended",
        "user_unsuspended",
        "user_deleted",
        "user_quota_updated",
        "user_impersonated",
    ],
    "api_key": [
        "api_key_created",
        "api_key_revoked",
        "api_key_admin_revoked",
        "api_key_reactivated",
        "api_keys_listed",
    ],
    "story": [
        "story_created",
        "story_deleted",
        "story_updated",
    ],
    "analytics": [
        "analytics_dashboard_viewed",
        "analytics_exported",
        "quota_reset",
    ],
    "system": [
        "system_setting_changed",
        "export_initiated",
    ],
}


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get(
    "/logs",
    response_model=AuditLogsResponse,
    summary="Query audit logs",
    description="Query audit logs with comprehensive filtering and pagination.",
)
async def query_audit_logs(
    category: str | None = Query(None, description="Filter by category"),
    action: str | None = Query(None, description="Filter by action"),
    actor_email: str | None = Query(None, description="Filter by actor email"),
    target_type: str | None = Query(None, description="Filter by target type"),
    target_id: str | None = Query(None, description="Filter by target ID"),
    start_date: datetime | None = Query(None, description="Start date filter"),
    end_date: datetime | None = Query(None, description="End date filter"),
    status: str | None = Query(None, description="Filter by status (success, failure, warning)"),
    search: str | None = Query(None, description="Search in actor email, action, or target"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    session: AsyncSession = Depends(get_session),
) -> AuditLogsResponse:
    """Query audit logs with filters."""
    query = select(AuditLog)

    # Apply filters
    if category:
        query = query.where(AuditLog.category == category)
    if action:
        query = query.where(AuditLog.action == action)
    if actor_email:
        query = query.where(AuditLog.actor_email.ilike(f"%{actor_email}%"))
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    if target_id:
        query = query.where(AuditLog.target_id == target_id)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
    if status:
        query = query.where(AuditLog.status == status)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                AuditLog.actor_email.ilike(search_term),
                AuditLog.action.ilike(search_term),
                AuditLog.target_id.ilike(search_term),
            )
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(per_page)

    result = await session.execute(query)
    logs = result.scalars().all()

    return AuditLogsResponse(
        logs=[
            AuditLogItem(
                id=log.id,
                action=log.action,
                category=log.category,
                actor_email=log.actor_email,
                target_type=log.target_type,
                target_id=log.target_id,
                details=log.details or {},
                status=log.status,
                error_message=log.error_message,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/summary",
    response_model=AuditSummaryResponse,
    summary="Get audit summary",
    description="Get summary of audit activity for a time period.",
)
async def get_audit_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to summarize"),
    admin: AdminUser = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    session: AsyncSession = Depends(get_session),
) -> AuditSummaryResponse:
    """Get audit activity summary."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get all logs in period
    result = await session.execute(
        select(AuditLog).where(
            and_(
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
            )
        )
    )
    logs = result.scalars().all()

    # Aggregate by category, action, and status
    by_category: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_status: dict[str, int] = {"success": 0, "failure": 0, "warning": 0}

    for log in logs:
        by_category[log.category] = by_category.get(log.category, 0) + 1
        by_action[log.action] = by_action.get(log.action, 0) + 1
        if log.status in by_status:
            by_status[log.status] += 1

    return AuditSummaryResponse(
        total_events=len(logs),
        by_category=by_category,
        by_action=by_action,
        by_status=by_status,
        period_days=days,
    )


@router.get(
    "/categories",
    response_model=AuditCategoriesResponse,
    summary="Get audit categories",
    description="Get available audit categories and their actions for filtering.",
)
async def get_audit_categories(
    admin: AdminUser = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
) -> AuditCategoriesResponse:
    """Get available audit categories and actions."""
    return AuditCategoriesResponse(
        categories=AUDIT_CATEGORIES,
        actions=AUDIT_ACTIONS,
    )


@router.get(
    "/logs/{log_id}",
    response_model=AuditLogItem,
    summary="Get audit log details",
    description="Get detailed information about a specific audit log entry.",
)
async def get_audit_log_details(
    log_id: int,
    admin: AdminUser = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    session: AsyncSession = Depends(get_session),
) -> AuditLogItem:
    """Get details of a specific audit log entry."""
    result = await session.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    return AuditLogItem(
        id=log.id,
        action=log.action,
        category=log.category,
        actor_email=log.actor_email,
        target_type=log.target_type,
        target_id=log.target_id,
        details=log.details or {},
        status=log.status,
        error_message=log.error_message,
        ip_address=log.ip_address,
        created_at=log.created_at,
    )
