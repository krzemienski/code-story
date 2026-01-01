"""API routers for different endpoint groups.

Routers:
- admin_auth: Admin authentication with 2FA and session management
- admin_users: Admin user management (search, update, suspend, impersonate)
- api_keys: API key generation and management
- auth: Authentication and token management
- auth_supabase: Supabase-based authentication (primary)
- health: Health check and monitoring endpoints
- sse: Server-Sent Events for real-time progress
- stories: Story generation and management
- users: User profile and admin management
"""

from .admin_analytics import router as admin_analytics_router
from .admin_api_keys import router as admin_api_keys_router
from .admin_audit import router as admin_audit_router
from .admin_auth import router as admin_auth_router
from .admin_users import router as admin_users_router
from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .auth_supabase import router as auth_supabase_router
from .health import router as health_router
from .sse import router as sse_router
from .stories import router as stories_router
from .users import router as users_router
from .teams import router as teams_router
from .collaboration import router as collaboration_router
from .sso import router as sso_router

__all__ = [
    "admin_analytics_router",
    "admin_api_keys_router",
    "admin_audit_router",
    "admin_auth_router",
    "admin_users_router",
    "api_keys_router",
    "auth_router",
    "auth_supabase_router",
    "health_router",
    "sse_router",
    "stories_router",
    "users_router",
    "teams_router",
    "collaboration_router",
    "sso_router",
]
