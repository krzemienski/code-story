"""SSO configuration models for enterprise SAML/OIDC authentication.

Provides models for:
- SSOConfiguration: Team-level SSO settings with encrypted credentials
- SSOSession: State management for SSO authentication flows
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, ForeignKey,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped

from codestory.models.database import Base

if TYPE_CHECKING:
    from codestory.models.user import User
    from codestory.models.team import Team


class SSOProvider(str, Enum):
    """Supported SSO providers."""
    SAML = "saml"
    OIDC = "oidc"


class SSOStatus(str, Enum):
    """SSO configuration status."""
    DRAFT = "draft"           # Being configured
    TESTING = "testing"       # Ready for test login
    ACTIVE = "active"         # Production ready
    DISABLED = "disabled"     # Temporarily disabled


class SSOConfiguration(Base):
    """SSO configuration for a team.

    Stores encrypted SAML or OIDC configuration with provider-specific
    settings like IdP certificates, client secrets, and attribute mappings.
    """
    __tablename__ = "sso_configurations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(
        String(36),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Provider type
    provider = Column(SQLEnum(SSOProvider), nullable=False)
    status = Column(SQLEnum(SSOStatus), default=SSOStatus.DRAFT, nullable=False)

    # Display name for login button (e.g., "Sign in with Acme Corp")
    display_name = Column(String(100), nullable=True)

    # Connection identifier for routing (e.g., "saml-acme-corp-a1b2c3")
    connection_id = Column(String(100), nullable=False, unique=True, index=True)

    # Encrypted configuration (provider-specific JSON)
    # Contains IdP URLs, certificates, client secrets, attribute mappings
    config_encrypted = Column(Text, nullable=False)

    # Domain restrictions (comma-separated email domains)
    allowed_domains = Column(Text, nullable=True)

    # Behavior settings
    auto_provision = Column(Boolean, default=True)  # Auto-create users on first login
    default_role = Column(String(20), default="member")  # Role for auto-provisioned users

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    last_tested_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship(
        "Team",
        backref="sso_config",
        foreign_keys=[team_id],
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
    )

    @staticmethod
    def get_cipher():
        """Get Fernet cipher for encryption/decryption.

        Uses SSO_ENCRYPTION_KEY from settings. Key must be a valid
        Fernet key (32 url-safe base64-encoded bytes).
        """
        from cryptography.fernet import Fernet
        from codestory.core.config import get_settings

        settings = get_settings()
        key = settings.sso_encryption_key.encode()
        return Fernet(key)

    def set_config(self, config: dict) -> None:
        """Encrypt and store configuration.

        Args:
            config: Provider-specific configuration dict containing
                    IdP URLs, certificates, client secrets, etc.
        """
        import json
        cipher = self.get_cipher()
        plaintext = json.dumps(config).encode()
        self.config_encrypted = cipher.encrypt(plaintext).decode()

    def get_config(self) -> dict:
        """Decrypt and return configuration.

        Returns:
            Provider-specific configuration dict.
        """
        import json
        cipher = self.get_cipher()
        plaintext = cipher.decrypt(self.config_encrypted.encode())
        return json.loads(plaintext)

    def is_domain_allowed(self, email: str) -> bool:
        """Check if email domain is allowed for this SSO connection.

        Args:
            email: User's email address to check.

        Returns:
            True if domain is allowed or no restrictions set.
        """
        if not self.allowed_domains:
            return True

        domain = email.split("@")[-1].lower()
        allowed = [d.strip().lower() for d in self.allowed_domains.split(",")]
        return domain in allowed

    @property
    def is_active(self) -> bool:
        """Check if SSO is active for logins."""
        return self.status in (SSOStatus.TESTING, SSOStatus.ACTIVE)


class SSOSession(Base):
    """SSO authentication session tracking.

    Manages state for SSO authentication flows to prevent CSRF
    and replay attacks. Sessions are short-lived (10 minutes).
    """
    __tablename__ = "sso_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sso_config_id = Column(
        String(36),
        ForeignKey("sso_configurations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # State management (CSRF protection)
    state = Column(String(64), nullable=False, unique=True, index=True)
    nonce = Column(String(64), nullable=True)  # For OIDC replay prevention

    # Relay state (where to redirect after auth)
    relay_state = Column(String(500), nullable=True)

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Result (populated after successful auth)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    sso_config: Mapped["SSOConfiguration"] = relationship(
        "SSOConfiguration",
        backref="sessions",
        foreign_keys=[sso_config_id],
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[user_id],
    )

    def is_valid(self) -> bool:
        """Check if session is still valid for authentication.

        Returns:
            False if already completed or expired.
        """
        if self.completed_at:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True


__all__ = [
    "SSOProvider",
    "SSOStatus",
    "SSOConfiguration",
    "SSOSession",
]
