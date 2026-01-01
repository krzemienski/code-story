"""User management tools for admin operations.

Provides tools for admin user management:
- Search and list users
- View user details
- Update user profiles and quotas
- Suspend/unsuspend accounts
- Create impersonation tokens
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codestory.models.user import APIKey, User

if TYPE_CHECKING:
    from codestory.models.admin import AdminUser


class UserManagementService:
    """Service for admin user management operations."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    async def search_users(
        self,
        search: str | None = None,
        status: str | None = None,
        plan: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """Search and filter users with pagination.

        Args:
            search: Search term for email
            status: Filter by active/inactive
            plan: Filter by subscription tier
            page: Page number (1-indexed)
            per_page: Results per page

        Returns:
            Dict with users, total count, and pagination info
        """
        query = select(User)

        # Apply filters
        if search:
            query = query.where(User.email.ilike(f"%{search}%"))

        if status:
            is_active = status.lower() == "active"
            query = query.where(User.is_active == is_active)

        if plan:
            query = query.where(User.subscription_tier == plan)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        query = query.order_by(User.created_at.desc())

        result = await self.db.execute(query)
        users = result.scalars().all()

        return {
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "is_active": u.is_active,
                    "subscription_tier": u.subscription_tier,
                    "usage_quota": u.usage_quota,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        }

    async def get_user_details(self, user_id: int) -> dict[str, Any] | None:
        """Get comprehensive user details.

        Args:
            user_id: User ID

        Returns:
            User details dict or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Count stories
        story_count = len(user.stories) if user.stories else 0

        # Count API keys
        api_key_count = len(user.api_keys) if user.api_keys else 0
        active_api_keys = sum(1 for k in user.api_keys if k.is_active) if user.api_keys else 0

        return {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "subscription_tier": user.subscription_tier,
            "usage_quota": user.usage_quota,
            "preferences": user.preferences,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "is_admin": user.is_admin,
            "stats": {
                "story_count": story_count,
                "api_key_count": api_key_count,
                "active_api_keys": active_api_keys,
            },
        }

    async def update_user(
        self,
        user_id: int,
        email: str | None = None,
        subscription_tier: str | None = None,
        usage_quota: int | None = None,
        preferences: dict | None = None,
    ) -> dict[str, Any] | None:
        """Update user profile fields.

        Args:
            user_id: User ID
            email: New email (optional)
            subscription_tier: New subscription tier (optional)
            usage_quota: New usage quota (optional)
            preferences: Updated preferences (optional)

        Returns:
            Updated user details or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        changes = {}
        if email is not None and email != user.email:
            changes["email"] = {"old": user.email, "new": email}
            user.email = email

        if subscription_tier is not None and subscription_tier != user.subscription_tier:
            changes["subscription_tier"] = {
                "old": user.subscription_tier,
                "new": subscription_tier,
            }
            user.subscription_tier = subscription_tier

        if usage_quota is not None and usage_quota != user.usage_quota:
            changes["usage_quota"] = {"old": user.usage_quota, "new": usage_quota}
            user.usage_quota = usage_quota

        if preferences is not None:
            changes["preferences"] = {"old": user.preferences, "new": preferences}
            user.preferences = preferences

        await self.db.commit()

        return {
            "user_id": user_id,
            "changes": changes,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }

    async def suspend_user(
        self,
        user_id: int,
        reason: str,
    ) -> dict[str, Any] | None:
        """Suspend a user account.

        Args:
            user_id: User ID
            reason: Suspension reason

        Returns:
            Suspension details or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        was_active = user.is_active
        user.is_active = False

        # Store suspension reason in preferences
        if user.preferences is None:
            user.preferences = {}
        user.preferences["suspension_reason"] = reason
        user.preferences["suspended_at"] = datetime.utcnow().isoformat()

        await self.db.commit()

        return {
            "user_id": user_id,
            "was_active": was_active,
            "is_active": False,
            "reason": reason,
        }

    async def unsuspend_user(self, user_id: int) -> dict[str, Any] | None:
        """Remove suspension from user account.

        Args:
            user_id: User ID

        Returns:
            Unsuspension details or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        user.is_active = True

        # Clear suspension info from preferences
        if user.preferences:
            user.preferences.pop("suspension_reason", None)
            user.preferences.pop("suspended_at", None)

        await self.db.commit()

        return {
            "user_id": user_id,
            "is_active": True,
        }

    async def delete_user(
        self,
        user_id: int,
        hard_delete: bool = False,
    ) -> dict[str, Any] | None:
        """Delete user account.

        Args:
            user_id: User ID
            hard_delete: If True, permanently delete; if False, soft delete

        Returns:
            Deletion details or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        if hard_delete:
            # Permanent deletion
            await self.db.delete(user)
            await self.db.commit()
            return {
                "user_id": user_id,
                "deleted": True,
                "type": "hard",
            }
        else:
            # Soft delete - deactivate and mark
            user.is_active = False
            if user.preferences is None:
                user.preferences = {}
            user.preferences["deleted_at"] = datetime.utcnow().isoformat()
            user.preferences["deletion_type"] = "soft"
            await self.db.commit()
            return {
                "user_id": user_id,
                "deleted": True,
                "type": "soft",
            }

    async def create_impersonation_token(
        self,
        user_id: int,
        admin: AdminUser,
        expires_minutes: int = 15,
    ) -> dict[str, Any] | None:
        """Create temporary token to impersonate user.

        Args:
            user_id: User ID to impersonate
            admin: Admin performing impersonation
            expires_minutes: Token expiration in minutes

        Returns:
            Impersonation token details or None if user not found
        """
        from codestory.core.security import create_access_token

        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Create impersonation token with extra metadata
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "type": "impersonation",
            "impersonated_by": admin.id,
            "original_admin_email": admin.user.email,
        }

        token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=expires_minutes),
        )

        return {
            "token": token,
            "user_id": user_id,
            "user_email": user.email,
            "expires_in": expires_minutes * 60,
            "impersonated_by": admin.user.email,
        }

    async def get_user_api_keys(self, user_id: int) -> list[dict[str, Any]]:
        """Get all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of API key details
        """
        result = await self.db.execute(
            select(APIKey).where(APIKey.user_id == user_id)
        )
        keys = result.scalars().all()

        return [
            {
                "id": k.id,
                "name": k.name,
                "is_active": k.is_active,
                "rate_limit": k.rate_limit,
                "permissions": k.permissions,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
            for k in keys
        ]

    async def revoke_user_api_key(
        self,
        user_id: int,
        key_id: int,
    ) -> dict[str, Any] | None:
        """Revoke a specific API key.

        Args:
            user_id: User ID
            key_id: API key ID

        Returns:
            Revocation details or None if not found
        """
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.id == key_id,
                APIKey.user_id == user_id,
            )
        )
        key = result.scalar_one_or_none()

        if not key:
            return None

        key.is_active = False
        await self.db.commit()

        return {
            "key_id": key_id,
            "user_id": user_id,
            "revoked": True,
        }
