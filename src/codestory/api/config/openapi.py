"""OpenAPI configuration and customization for Code Story API.

Provides comprehensive API documentation with enhanced descriptions,
authentication flows, and custom examples.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# API metadata
API_TITLE = "Code Story API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
# Code Story API

Transform your repositories into engaging audio narratives.

## Overview

Code Story analyzes your codebase and generates professional audio stories
that explain your code's architecture, design patterns, and implementation details.

## Authentication

The API supports two authentication methods:

### JWT Bearer Token
For web and mobile applications. Obtain a token via `/api/auth/login`.

```
Authorization: Bearer <your-jwt-token>
```

### API Key
For server-to-server integrations. Generate keys at `/api/api-keys`.

```
X-API-Key: cs_<your-api-key>
```

## Rate Limits

| Tier | Requests/hour | Stories/day | Audio mins/month |
|------|--------------|-------------|------------------|
| Free | 100 | 2 | 30 |
| Pro | 1000 | 10 | 300 |
| Team | 5000 | 50 | 1000 |
| Enterprise | Unlimited | 500 | 10000 |

## Errors

The API uses standard HTTP status codes:

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid auth |
| 402 | Payment Required - Quota exceeded |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Error - Server issue |

## Narrative Styles

| Style | Description |
|-------|-------------|
| documentary | Professional, PBS-style narration |
| storytelling | Engaging narrative with characters |
| educational | Tutorial-focused learning |
| casual | Friendly podcast format |
| executive | High-level business summary |

## Webhooks (Coming Soon)

Subscribe to events like `story.created`, `story.completed`, `story.failed`.
"""

TAGS_METADATA = [
    {
        "name": "health",
        "description": "Health check and system status endpoints",
    },
    {
        "name": "auth",
        "description": "User authentication via Supabase Auth service",
    },
    {
        "name": "auth-legacy",
        "description": "Legacy JWT authentication (deprecated, use Supabase auth)",
    },
    {
        "name": "stories",
        "description": "Create and manage audio stories from repositories",
    },
    {
        "name": "api-keys",
        "description": "Manage API keys for programmatic access",
    },
    {
        "name": "users",
        "description": "User profile and settings management",
    },
    {
        "name": "sse",
        "description": "Server-Sent Events for real-time story generation updates",
    },
]

CONTACT_INFO = {
    "name": "Code Story Support",
    "url": "https://codestory.dev/support",
    "email": "api-support@codestory.dev",
}

LICENSE_INFO = {
    "name": "MIT",
    "url": "https://opensource.org/licenses/MIT",
}


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced documentation.

    Args:
        app: FastAPI application instance

    Returns:
        OpenAPI schema dictionary
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=TAGS_METADATA,
        contact=CONTACT_INFO,
        license_info=LICENSE_INFO,
    )

    # Initialize components if not present
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token from /api/auth/login or Supabase Auth",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key from /api/api-keys (format: cs_<hex>)",
        },
    }

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Local development",
        },
        {
            "url": "https://api.codestory.dev",
            "description": "Production server",
        },
        {
            "url": "https://api-staging.codestory.dev",
            "description": "Staging server",
        },
    ]

    # Add examples to common schemas
    _add_schema_examples(openapi_schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def _add_schema_examples(schema: dict[str, Any]) -> None:
    """Add examples to schema definitions.

    Args:
        schema: OpenAPI schema dictionary to modify in place
    """
    schemas = schema.get("components", {}).get("schemas", {})

    # Story examples
    if "StoryResponse" in schemas:
        schemas["StoryResponse"]["example"] = {
            "id": "story_abc123",
            "title": "Understanding FastAPI Architecture",
            "status": "completed",
            "repo_url": "https://github.com/tiangolo/fastapi",
            "narrative_style": "documentary",
            "total_duration_seconds": 1847,
            "chapter_count": 5,
            "created_at": "2025-01-15T10:30:00Z",
        }

    # API Key examples
    if "APIKeyResponse" in schemas:
        schemas["APIKeyResponse"]["example"] = {
            "id": 1,
            "name": "CI/CD Pipeline Key",
            "permissions": ["read", "write"],
            "rate_limit": 1000,
            "is_active": True,
            "created_at": "2025-01-15T10:30:00Z",
            "expires_at": None,
            "last_used_at": "2025-01-15T12:45:00Z",
        }

    if "APIKeyCreated" in schemas:
        schemas["APIKeyCreated"]["example"] = {
            "id": 1,
            "name": "CI/CD Pipeline Key",
            "key": "cs_a1b2c3d4e5f6...",
            "permissions": ["read", "write"],
            "rate_limit": 1000,
            "is_active": True,
            "created_at": "2025-01-15T10:30:00Z",
            "expires_at": None,
            "last_used_at": None,
        }


# Story creation request examples for documentation
STORY_CREATE_EXAMPLES = {
    "basic": {
        "summary": "Basic story creation",
        "description": "Create a story with default settings",
        "value": {"repo_url": "https://github.com/user/my-app"},
    },
    "documentary_style": {
        "summary": "Documentary narrative",
        "description": "Create a documentary-style narration",
        "value": {
            "repo_url": "https://github.com/user/my-app",
            "narrative_style": "documentary",
            "voice_id": "EXAVITQu4vr4xnSDxMaL",
        },
    },
    "tutorial_focused": {
        "summary": "Tutorial for beginners",
        "description": "Educational tutorial focusing on specific areas",
        "value": {
            "repo_url": "https://github.com/user/my-app",
            "narrative_style": "educational",
            "focus_areas": ["getting_started", "configuration"],
        },
    },
    "technical_deep_dive": {
        "summary": "Technical analysis",
        "description": "In-depth technical architecture review",
        "value": {
            "repo_url": "https://github.com/user/my-app",
            "narrative_style": "storytelling",
            "focus_areas": ["architecture", "patterns", "performance"],
        },
    },
}

# Error response examples for documentation
ERROR_EXAMPLES = {
    "validation_error": {
        "detail": [
            {
                "loc": ["body", "repo_url"],
                "msg": "Invalid GitHub URL format",
                "type": "value_error",
            }
        ]
    },
    "authentication_error": {"detail": "Invalid or expired authentication token"},
    "rate_limit_error": {"error": "Rate limit exceeded", "limit": 1000, "retry_after": 45},
    "quota_exceeded": {
        "detail": {
            "error": "Daily quota exceeded",
            "quota_info": {"daily": {"used": 2, "limit": 2, "remaining": 0}},
            "upgrade_url": "/settings/billing",
        }
    },
}
