"""SSO configuration and authentication endpoints.

Provides endpoints for:
- SAML/OIDC configuration management (team admins)
- SAML authentication flow (SP metadata, login, ACS)
- OIDC authentication flow (login, callback)
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Form, Response, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from codestory.api.deps import DBSession, SupabaseUser
from codestory.models import (
    SSOProvider, SSOStatus, Team, TeamMember, MemberRole
)
from codestory.services import (
    SSOService,
    SSOError,
    SSOConfigExistsError,
    SSOSessionInvalidError,
    TeamService,
)
from codestory.core.config import get_settings

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class SAMLConfigCreate(BaseModel):
    """SAML SSO configuration input."""
    display_name: str = Field(..., min_length=1, max_length=100)

    # Identity Provider settings
    idp_entity_id: str = Field(..., description="IdP Entity ID / Issuer")
    idp_sso_url: str = Field(..., description="IdP Single Sign-On URL")
    idp_slo_url: Optional[str] = Field(None, description="IdP Single Logout URL")
    idp_certificate: str = Field(..., description="IdP X.509 Certificate (PEM format)")

    # Attribute mapping
    attribute_email: str = Field(default="email", description="Attribute name for email")
    attribute_first_name: str = Field(default="firstName")
    attribute_last_name: str = Field(default="lastName")

    # Optional settings
    allowed_domains: Optional[List[str]] = Field(None, description="Allowed email domains")
    auto_provision: bool = Field(default=True, description="Auto-create users on first login")
    default_role: str = Field(default="member")

    @field_validator("idp_certificate")
    @classmethod
    def validate_certificate(cls, v: str) -> str:
        """Validate certificate format."""
        if "BEGIN CERTIFICATE" not in v:
            raise ValueError("Certificate must be in PEM format")
        return v


class OIDCConfigCreate(BaseModel):
    """OIDC SSO configuration input."""
    display_name: str = Field(..., min_length=1, max_length=100)

    # Provider settings
    issuer: str = Field(..., description="OIDC Issuer URL")
    client_id: str = Field(..., description="OAuth Client ID")
    client_secret: str = Field(..., description="OAuth Client Secret")

    # Optional: manual endpoint configuration
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None

    # Scopes
    scopes: List[str] = Field(default=["openid", "email", "profile"])

    # Claim mapping
    claim_email: str = Field(default="email")
    claim_name: str = Field(default="name")
    claim_given_name: str = Field(default="given_name")
    claim_family_name: str = Field(default="family_name")

    # Optional settings
    allowed_domains: Optional[List[str]] = None
    auto_provision: bool = True
    default_role: str = Field(default="member")


class SSOConfigResponse(BaseModel):
    """SSO configuration response."""
    id: str
    team_id: str
    provider: SSOProvider
    status: SSOStatus
    display_name: Optional[str]
    connection_id: str
    allowed_domains: Optional[List[str]]
    auto_provision: bool
    default_role: str
    created_at: datetime
    updated_at: datetime
    last_tested_at: Optional[datetime]
    last_login_at: Optional[datetime]

    # Service Provider metadata (for SAML)
    sp_entity_id: Optional[str] = None
    sp_acs_url: Optional[str] = None
    sp_slo_url: Optional[str] = None
    sp_metadata_url: Optional[str] = None
    callback_url: Optional[str] = None

    model_config = {"from_attributes": True}


class SSOStatusUpdate(BaseModel):
    """SSO status update request."""
    status: SSOStatus


# =============================================================================
# Helper Functions
# =============================================================================

def _build_config_response(config, sso_service: SSOService) -> SSOConfigResponse:
    """Build SSO config response with SP metadata."""
    sp_urls = sso_service.get_sp_urls(config)

    return SSOConfigResponse(
        id=config.id,
        team_id=config.team_id,
        provider=config.provider,
        status=config.status,
        display_name=config.display_name,
        connection_id=config.connection_id,
        allowed_domains=config.allowed_domains.split(",") if config.allowed_domains else None,
        auto_provision=config.auto_provision,
        default_role=config.default_role,
        created_at=config.created_at,
        updated_at=config.updated_at,
        last_tested_at=config.last_tested_at,
        last_login_at=config.last_login_at,
        sp_entity_id=sp_urls.get("sp_entity_id"),
        sp_acs_url=sp_urls.get("sp_acs_url"),
        sp_slo_url=sp_urls.get("sp_slo_url"),
        sp_metadata_url=sp_urls.get("sp_metadata_url"),
        callback_url=sp_urls.get("callback_url"),
    )


async def _require_team_owner(
    team_id: str,
    user_id: str,
    db: DBSession,
) -> Team:
    """Require team owner access.

    Args:
        team_id: Team to check.
        user_id: User requesting access.
        db: Database session.

    Returns:
        Team if access granted.

    Raises:
        HTTPException: If team not found or user not owner.
    """
    from sqlalchemy import select

    # Get team
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check membership
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.is_active == True,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership or membership.role != MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required"
        )

    return team


async def _require_team_admin(
    team_id: str,
    user_id: str,
    db: DBSession,
) -> Team:
    """Require team admin access.

    Args:
        team_id: Team to check.
        user_id: User requesting access.
        db: Database session.

    Returns:
        Team if access granted.

    Raises:
        HTTPException: If team not found or user not admin.
    """
    from sqlalchemy import select

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.is_active == True,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership or membership.role not in (MemberRole.OWNER, MemberRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return team


# =============================================================================
# Configuration Management Endpoints (Authenticated)
# =============================================================================

@router.post(
    "/teams/{team_id}/sso/saml",
    response_model=SSOConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SAML SSO configuration",
)
async def create_saml_config(
    team_id: str,
    data: SAMLConfigCreate,
    db: DBSession,
    current_user: SupabaseUser,
):
    """Create SAML SSO configuration for a team.

    Requires team owner access. Only one SSO configuration per team.
    """
    user_id = current_user["id"]
    team = await _require_team_owner(team_id, user_id, db)

    sso_service = SSOService(db)

    try:
        config = await sso_service.create_saml_config(
            team=team,
            display_name=data.display_name,
            idp_entity_id=data.idp_entity_id,
            idp_sso_url=data.idp_sso_url,
            idp_certificate=data.idp_certificate,
            idp_slo_url=data.idp_slo_url,
            attribute_email=data.attribute_email,
            attribute_first_name=data.attribute_first_name,
            attribute_last_name=data.attribute_last_name,
            allowed_domains=data.allowed_domains,
            auto_provision=data.auto_provision,
            default_role=data.default_role,
            created_by_id=user_id,
        )
    except SSOConfigExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    return _build_config_response(config, sso_service)


@router.post(
    "/teams/{team_id}/sso/oidc",
    response_model=SSOConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create OIDC SSO configuration",
)
async def create_oidc_config(
    team_id: str,
    data: OIDCConfigCreate,
    db: DBSession,
    current_user: SupabaseUser,
):
    """Create OIDC SSO configuration for a team.

    Requires team owner access. Only one SSO configuration per team.
    """
    user_id = current_user["id"]
    team = await _require_team_owner(team_id, user_id, db)

    sso_service = SSOService(db)

    try:
        config = await sso_service.create_oidc_config(
            team=team,
            display_name=data.display_name,
            issuer=data.issuer,
            client_id=data.client_id,
            client_secret=data.client_secret,
            authorization_endpoint=data.authorization_endpoint,
            token_endpoint=data.token_endpoint,
            userinfo_endpoint=data.userinfo_endpoint,
            jwks_uri=data.jwks_uri,
            scopes=data.scopes,
            claim_email=data.claim_email,
            claim_name=data.claim_name,
            claim_given_name=data.claim_given_name,
            claim_family_name=data.claim_family_name,
            allowed_domains=data.allowed_domains,
            auto_provision=data.auto_provision,
            default_role=data.default_role,
            created_by_id=user_id,
        )
    except SSOConfigExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    return _build_config_response(config, sso_service)


@router.get(
    "/teams/{team_id}/sso",
    response_model=SSOConfigResponse,
    summary="Get SSO configuration",
)
async def get_sso_config(
    team_id: str,
    db: DBSession,
    current_user: SupabaseUser,
):
    """Get SSO configuration for a team.

    Requires team admin access.
    """
    user_id = current_user["id"]
    await _require_team_admin(team_id, user_id, db)

    sso_service = SSOService(db)
    config = await sso_service.get_config(team_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SSO configuration found"
        )

    return _build_config_response(config, sso_service)


@router.patch(
    "/teams/{team_id}/sso/status",
    response_model=SSOConfigResponse,
    summary="Update SSO status",
)
async def update_sso_status(
    team_id: str,
    data: SSOStatusUpdate,
    db: DBSession,
    current_user: SupabaseUser,
):
    """Update SSO configuration status.

    Requires team owner access. Valid transitions:
    - DRAFT -> TESTING (after initial test)
    - TESTING -> ACTIVE (after successful test)
    - ACTIVE -> DISABLED (temporarily disable)
    - DISABLED -> ACTIVE (re-enable)
    """
    user_id = current_user["id"]
    await _require_team_owner(team_id, user_id, db)

    sso_service = SSOService(db)
    config = await sso_service.get_config(team_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SSO configuration found"
        )

    # Validate status transitions
    if data.status == SSOStatus.ACTIVE and config.status == SSOStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO must be tested before activation"
        )

    config = await sso_service.update_status(config, data.status)
    return _build_config_response(config, sso_service)


@router.delete(
    "/teams/{team_id}/sso",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete SSO configuration",
)
async def delete_sso_config(
    team_id: str,
    db: DBSession,
    current_user: SupabaseUser,
):
    """Delete SSO configuration.

    Requires team owner access.
    """
    user_id = current_user["id"]
    await _require_team_owner(team_id, user_id, db)

    sso_service = SSOService(db)
    config = await sso_service.get_config(team_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SSO configuration found"
        )

    await sso_service.delete_config(config)


# =============================================================================
# SAML Endpoints (Unauthenticated)
# =============================================================================

@router.get(
    "/sso/saml/{connection_id}/metadata",
    response_class=Response,
    summary="SAML SP Metadata",
)
async def saml_metadata(
    connection_id: str,
    db: DBSession,
):
    """Get SAML Service Provider metadata.

    This endpoint is used by Identity Providers to configure trust.
    Returns XML metadata with SP entity ID, ACS URL, and SLO URL.
    """
    sso_service = SSOService(db)
    config = await sso_service.get_config_by_connection(connection_id)

    if not config or config.provider != SSOProvider.SAML:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found"
        )

    metadata = sso_service.generate_sp_metadata(config)
    return Response(content=metadata, media_type="application/xml")


@router.get(
    "/sso/saml/{connection_id}/login",
    response_class=RedirectResponse,
    summary="Initiate SAML login",
)
async def saml_login(
    connection_id: str,
    db: DBSession,
    relay_state: Optional[str] = Query(None, description="URL to redirect after auth"),
):
    """Initiate SAML authentication.

    Redirects user to Identity Provider for authentication.
    """
    sso_service = SSOService(db)
    config = await sso_service.get_config_by_connection(connection_id)

    if not config or config.provider != SSOProvider.SAML:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found"
        )

    try:
        redirect_url, state = await sso_service.initiate_saml_login(config, relay_state)
    except SSOError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.post(
    "/sso/saml/{connection_id}/acs",
    response_class=RedirectResponse,
    summary="SAML Assertion Consumer Service",
)
async def saml_acs(
    connection_id: str,
    db: DBSession,
    SAMLResponse: str = Form(...),
    RelayState: str = Form(...),
):
    """SAML Assertion Consumer Service - process IdP response.

    This endpoint receives the SAML response from the Identity Provider
    after successful authentication. It validates the response, creates
    or retrieves the user, and issues an application JWT token.
    """
    sso_service = SSOService(db)
    config = await sso_service.get_config_by_connection(connection_id)

    if not config or config.provider != SSOProvider.SAML:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found"
        )

    try:
        # Validate session
        session = await sso_service.validate_saml_session(config, RelayState)

        # Parse SAML response (simplified - use python3-saml in production)
        saml_config = config.get_config()
        attributes = sso_service.parse_saml_response(SAMLResponse, saml_config)

        # Extract user info from attributes
        attr_mapping = saml_config.get("attribute_mapping", {})
        email = attributes.get(attr_mapping.get("email", "email"))
        first_name = attributes.get(attr_mapping.get("first_name", "firstName"), "")
        last_name = attributes.get(attr_mapping.get("last_name", "lastName"), "")

        if not email:
            raise SSOError("Email attribute not found in SAML response")

        # Validate domain
        if not config.is_domain_allowed(email):
            raise SSOError(f"Email domain not allowed for this SSO connection")

        # Record login and complete session
        await sso_service.record_login(config)
        # Note: In full implementation, would create/get user and issue JWT here
        # For now, redirect to frontend SSO callback with connection info
        settings = get_settings()
        redirect_url = f"{settings.base_url}/auth/sso-callback?connection={connection_id}&email={email}"

        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    except SSOSessionInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SSOError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# OIDC Endpoints (Unauthenticated)
# =============================================================================

@router.get(
    "/sso/oidc/{connection_id}/login",
    response_class=RedirectResponse,
    summary="Initiate OIDC login",
)
async def oidc_login(
    connection_id: str,
    db: DBSession,
    relay_state: Optional[str] = Query(None, description="URL to redirect after auth"),
):
    """Initiate OIDC authentication.

    Redirects user to Identity Provider's authorization endpoint.
    """
    sso_service = SSOService(db)
    config = await sso_service.get_config_by_connection(connection_id)

    if not config or config.provider != SSOProvider.OIDC:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found"
        )

    try:
        redirect_url, state = await sso_service.initiate_oidc_login(config, relay_state)
    except SSOError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/sso/oidc/{connection_id}/callback",
    response_class=RedirectResponse,
    summary="OIDC callback",
)
async def oidc_callback(
    connection_id: str,
    db: DBSession,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    error: Optional[str] = Query(None, description="Error code"),
    error_description: Optional[str] = Query(None, description="Error description"),
):
    """OIDC callback - process IdP response.

    This endpoint receives the authorization code from the Identity Provider.
    It exchanges the code for tokens, validates the ID token, and issues
    an application JWT token.
    """
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error
        )

    sso_service = SSOService(db)
    config = await sso_service.get_config_by_connection(connection_id)

    if not config or config.provider != SSOProvider.OIDC:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found"
        )

    try:
        # Validate session
        session = await sso_service.validate_oidc_session(config, state)

        # Exchange code for tokens
        tokens = await sso_service.exchange_oidc_code(config, code)

        # Validate ID token
        id_token = tokens.get("id_token")
        if not id_token:
            raise SSOError("No ID token in response")

        claims = await sso_service.validate_oidc_token(config, id_token, session.nonce)

        # Get additional user info
        userinfo = await sso_service.get_oidc_userinfo(config, tokens.get("access_token", ""))
        claims.update(userinfo)

        # Extract user info
        oidc_config = config.get_config()
        claim_mapping = oidc_config.get("claim_mapping", {})
        email = claims.get(claim_mapping.get("email", "email"))
        name = claims.get(claim_mapping.get("name", "name"))

        if not name:
            given = claims.get(claim_mapping.get("given_name", "given_name"), "")
            family = claims.get(claim_mapping.get("family_name", "family_name"), "")
            name = f"{given} {family}".strip()

        if not email:
            raise SSOError("Email claim not found in ID token")

        # Validate domain
        if not config.is_domain_allowed(email):
            raise SSOError(f"Email domain not allowed for this SSO connection")

        # Record login
        await sso_service.record_login(config)

        # Note: In full implementation, would create/get user and issue JWT here
        settings = get_settings()
        redirect_url = f"{settings.base_url}/auth/sso-callback?connection={connection_id}&email={email}"

        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    except SSOSessionInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SSOError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Testing Endpoints
# =============================================================================

@router.post(
    "/teams/{team_id}/sso/test",
    summary="Test SSO configuration",
)
async def test_sso_config(
    team_id: str,
    db: DBSession,
    current_user: SupabaseUser,
):
    """Mark SSO configuration as tested and ready.

    Requires team owner access. Updates status to TESTING if in DRAFT.
    Returns login URL for manual testing.
    """
    user_id = current_user["id"]
    await _require_team_owner(team_id, user_id, db)

    sso_service = SSOService(db)
    config = await sso_service.get_config(team_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SSO configuration found"
        )

    await sso_service.record_test(config)

    # Generate test login URL
    prefix = "saml" if config.provider == SSOProvider.SAML else "oidc"
    settings = get_settings()
    login_url = f"{settings.base_url}/sso/{prefix}/{config.connection_id}/login"

    return {
        "status": config.status.value,
        "login_url": login_url,
        "message": "SSO configuration marked as tested. Use login_url to test.",
    }
