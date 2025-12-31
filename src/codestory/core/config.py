"""Application configuration using pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Code Story"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/codestory"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Redis (for Celery and cache)
    redis_url: str = "redis://localhost:6379/0"

    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-5-20251101"
    claude_max_tokens: int = 8192
    claude_effort: str = "high"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_default_voice: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    elevenlabs_model: str = "eleven_multilingual_v2"

    # GitHub
    github_token: str = ""
    github_api_base: str = "https://api.github.com"

    # JWT Authentication
    secret_key: str = "change-me-in-production"
    jwt_secret_key: str = ""  # Falls back to secret_key if not set
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    refresh_token_expire_days: int = 30

    # Aliases for backward compatibility
    algorithm: str = "HS256"

    # S3 Storage
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = "codestory-audio"
    s3_bucket_name: str = ""  # Alias for s3_bucket
    s3_endpoint_url: str = ""

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 3600

    # Feature Flags
    enable_voice_synthesis: bool = True
    enable_github_private_repos: bool = False
    enable_analytics: bool = True
    max_story_duration_minutes: int = 30
    max_repo_size_mb: int = 100

    @property
    def async_database_url(self) -> str:
        """Ensure database URL uses asyncpg."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def effective_jwt_secret(self) -> str:
        """Get the effective JWT secret key (prefers jwt_secret_key, falls back to secret_key)."""
        return self.jwt_secret_key or self.secret_key

    @property
    def effective_jwt_algorithm(self) -> str:
        """Get the effective JWT algorithm."""
        return self.jwt_algorithm or self.algorithm

    @property
    def effective_s3_bucket(self) -> str:
        """Get the effective S3 bucket name."""
        return self.s3_bucket_name or self.s3_bucket

    def has_github_token(self) -> bool:
        """Check if GitHub token is configured."""
        return bool(self.github_token)

    def has_elevenlabs_key(self) -> bool:
        """Check if ElevenLabs API key is configured."""
        return bool(self.elevenlabs_api_key)

    def has_anthropic_key(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(self.anthropic_api_key)

    def has_aws_credentials(self) -> bool:
        """Check if AWS credentials are configured."""
        return bool(self.aws_access_key_id and self.aws_secret_access_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
