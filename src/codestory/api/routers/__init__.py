"""API routers for different endpoint groups.

Routers:
- auth: Authentication and token management
- health: Health check and monitoring endpoints
- sse: Server-Sent Events for real-time progress
- stories: Story generation and management
- users: User profile, API keys, and admin management
"""

from .auth import router as auth_router
from .health import router as health_router
from .sse import router as sse_router
from .stories import router as stories_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "health_router",
    "sse_router",
    "stories_router",
    "users_router",
]
