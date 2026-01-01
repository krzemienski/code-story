"""SSO Integration for enterprise authentication.

Revision ID: 0005
Revises: 0004
Create Date: 2026-01-01

Adds:
- sso_configurations table for SAML/OIDC config storage
- sso_sessions table for authentication state management
- Enum types for provider and status
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE ssoprovider AS ENUM ('saml', 'oidc');
    """)
    op.execute("""
        CREATE TYPE ssostatus AS ENUM ('draft', 'testing', 'active', 'disabled');
    """)

    # Create sso_configurations table
    op.create_table(
        "sso_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "team_id",
            sa.String(36),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "provider",
            sa.Enum("saml", "oidc", name="ssoprovider"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "testing", "active", "disabled", name="ssostatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("connection_id", sa.String(100), nullable=False, unique=True),
        sa.Column("config_encrypted", sa.Text, nullable=False),
        sa.Column("allowed_domains", sa.Text, nullable=True),
        sa.Column("auto_provision", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("default_role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("last_tested_at", sa.DateTime, nullable=True),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_sso_configurations_team_id", "sso_configurations", ["team_id"])
    op.create_index("ix_sso_configurations_connection_id", "sso_configurations", ["connection_id"])

    # Create sso_sessions table
    op.create_table(
        "sso_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "sso_config_id",
            sa.String(36),
            sa.ForeignKey("sso_configurations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(64), nullable=False, unique=True),
        sa.Column("nonce", sa.String(64), nullable=True),
        sa.Column("relay_state", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_sso_sessions_sso_config_id", "sso_sessions", ["sso_config_id"])
    op.create_index("ix_sso_sessions_state", "sso_sessions", ["state"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("sso_sessions")
    op.drop_table("sso_configurations")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS ssostatus;")
    op.execute("DROP TYPE IF EXISTS ssoprovider;")
