"""SSO authentication service for SAML and OIDC.

Provides complete SSO lifecycle management:
- Configuration creation and management
- SAML AuthnRequest generation and response processing
- OIDC authorization code flow
- User auto-provisioning
- Service Provider metadata generation
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from codestory.core.config import get_settings
from codestory.models.sso import (
    SSOConfiguration, SSOSession, SSOProvider, SSOStatus
)
from codestory.models.team import Team, TeamMember, MemberRole


class SSOError(Exception):
    """Base exception for SSO operations."""
    pass


class SSOConfigNotFoundError(SSOError):
    """Raised when SSO configuration is not found."""
    pass


class SSOConfigExistsError(SSOError):
    """Raised when team already has SSO configured."""
    pass


class SSOSessionInvalidError(SSOError):
    """Raised when SSO session is invalid or expired."""
    pass


class SSODomainNotAllowedError(SSOError):
    """Raised when email domain is not allowed."""
    pass


class SSOProvisioningDisabledError(SSOError):
    """Raised when auto-provisioning is disabled and user doesn't exist."""
    pass


class SSOService:
    """Service for SSO authentication and configuration management."""

    def __init__(self, db: AsyncSession):
        """Initialize SSO service.

        Args:
            db: Async database session.
        """
        self.db = db
        self._settings = get_settings()
        self.base_url = self._settings.base_url

    # -------------------------------------------------------------------------
    # Configuration Management
    # -------------------------------------------------------------------------

    async def create_saml_config(
        self,
        team: Team,
        display_name: str,
        idp_entity_id: str,
        idp_sso_url: str,
        idp_certificate: str,
        idp_slo_url: Optional[str] = None,
        attribute_email: str = "email",
        attribute_first_name: str = "firstName",
        attribute_last_name: str = "lastName",
        allowed_domains: Optional[list[str]] = None,
        auto_provision: bool = True,
        default_role: str = "member",
        created_by_id: Optional[str] = None,
    ) -> SSOConfiguration:
        """Create SAML SSO configuration for a team.

        Args:
            team: Team to configure SSO for.
            display_name: Display name for login button.
            idp_entity_id: Identity Provider Entity ID.
            idp_sso_url: IdP Single Sign-On URL.
            idp_certificate: IdP X.509 certificate in PEM format.
            idp_slo_url: Optional IdP Single Logout URL.
            attribute_*: SAML attribute names for user info.
            allowed_domains: List of allowed email domains.
            auto_provision: Whether to create users on first login.
            default_role: Role for auto-provisioned users.
            created_by_id: ID of admin creating config.

        Returns:
            Created SSOConfiguration.

        Raises:
            SSOConfigExistsError: If team already has SSO configured.
        """
        # Check for existing configuration
        existing = await self.get_config(team.id)
        if existing:
            raise SSOConfigExistsError("Team already has an SSO configuration")

        # Generate unique connection ID
        connection_id = f"saml-{team.slug}-{secrets.token_hex(4)}"

        # Build encrypted config
        config = {
            "idp_entity_id": idp_entity_id,
            "idp_sso_url": idp_sso_url,
            "idp_slo_url": idp_slo_url,
            "idp_certificate": idp_certificate,
            "attribute_mapping": {
                "email": attribute_email,
                "first_name": attribute_first_name,
                "last_name": attribute_last_name,
            }
        }

        sso_config = SSOConfiguration(
            id=str(uuid.uuid4()),
            team_id=team.id,
            provider=SSOProvider.SAML,
            display_name=display_name,
            connection_id=connection_id,
            allowed_domains=",".join(allowed_domains) if allowed_domains else None,
            auto_provision=auto_provision,
            default_role=default_role,
            created_by_id=created_by_id,
        )
        sso_config.set_config(config)

        self.db.add(sso_config)
        await self.db.commit()
        await self.db.refresh(sso_config)

        return sso_config

    async def create_oidc_config(
        self,
        team: Team,
        display_name: str,
        issuer: str,
        client_id: str,
        client_secret: str,
        authorization_endpoint: Optional[str] = None,
        token_endpoint: Optional[str] = None,
        userinfo_endpoint: Optional[str] = None,
        jwks_uri: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        claim_email: str = "email",
        claim_name: str = "name",
        claim_given_name: str = "given_name",
        claim_family_name: str = "family_name",
        allowed_domains: Optional[list[str]] = None,
        auto_provision: bool = True,
        default_role: str = "member",
        created_by_id: Optional[str] = None,
    ) -> SSOConfiguration:
        """Create OIDC SSO configuration for a team.

        Args:
            team: Team to configure SSO for.
            display_name: Display name for login button.
            issuer: OIDC issuer URL.
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            *_endpoint: Optional manual endpoint URLs.
            scopes: OAuth scopes to request.
            claim_*: OIDC claim names for user info.
            allowed_domains: List of allowed email domains.
            auto_provision: Whether to create users on first login.
            default_role: Role for auto-provisioned users.
            created_by_id: ID of admin creating config.

        Returns:
            Created SSOConfiguration.

        Raises:
            SSOConfigExistsError: If team already has SSO configured.
        """
        existing = await self.get_config(team.id)
        if existing:
            raise SSOConfigExistsError("Team already has an SSO configuration")

        connection_id = f"oidc-{team.slug}-{secrets.token_hex(4)}"

        config = {
            "issuer": issuer,
            "client_id": client_id,
            "client_secret": client_secret,
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
            "userinfo_endpoint": userinfo_endpoint,
            "jwks_uri": jwks_uri,
            "scopes": scopes or ["openid", "email", "profile"],
            "claim_mapping": {
                "email": claim_email,
                "name": claim_name,
                "given_name": claim_given_name,
                "family_name": claim_family_name,
            }
        }

        sso_config = SSOConfiguration(
            id=str(uuid.uuid4()),
            team_id=team.id,
            provider=SSOProvider.OIDC,
            display_name=display_name,
            connection_id=connection_id,
            allowed_domains=",".join(allowed_domains) if allowed_domains else None,
            auto_provision=auto_provision,
            default_role=default_role,
            created_by_id=created_by_id,
        )
        sso_config.set_config(config)

        self.db.add(sso_config)
        await self.db.commit()
        await self.db.refresh(sso_config)

        return sso_config

    async def get_config(self, team_id: str) -> Optional[SSOConfiguration]:
        """Get SSO configuration for a team.

        Args:
            team_id: Team ID to look up.

        Returns:
            SSOConfiguration if found, None otherwise.
        """
        result = await self.db.execute(
            select(SSOConfiguration).where(SSOConfiguration.team_id == team_id)
        )
        return result.scalar_one_or_none()

    async def get_config_by_connection(
        self, connection_id: str
    ) -> Optional[SSOConfiguration]:
        """Get SSO configuration by connection ID.

        Args:
            connection_id: Connection identifier for routing.

        Returns:
            SSOConfiguration if found, None otherwise.
        """
        result = await self.db.execute(
            select(SSOConfiguration).where(
                SSOConfiguration.connection_id == connection_id
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, config: SSOConfiguration, status: SSOStatus
    ) -> SSOConfiguration:
        """Update SSO configuration status.

        Args:
            config: Configuration to update.
            status: New status.

        Returns:
            Updated SSOConfiguration.
        """
        config.status = status
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def delete_config(self, config: SSOConfiguration) -> None:
        """Delete SSO configuration.

        Args:
            config: Configuration to delete.
        """
        await self.db.delete(config)
        await self.db.commit()

    async def record_test(self, config: SSOConfiguration) -> None:
        """Record that SSO was tested.

        Args:
            config: Configuration that was tested.
        """
        config.last_tested_at = datetime.utcnow()
        if config.status == SSOStatus.DRAFT:
            config.status = SSOStatus.TESTING
        await self.db.commit()

    async def record_login(self, config: SSOConfiguration) -> None:
        """Record successful SSO login.

        Args:
            config: Configuration used for login.
        """
        config.last_login_at = datetime.utcnow()
        await self.db.commit()

    # -------------------------------------------------------------------------
    # SAML Authentication
    # -------------------------------------------------------------------------

    async def initiate_saml_login(
        self,
        config: SSOConfiguration,
        relay_state: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Initiate SAML authentication flow.

        Creates an SSOSession and generates redirect URL to IdP.

        Args:
            config: SAML configuration.
            relay_state: Optional URL to redirect to after auth.

        Returns:
            Tuple of (redirect_url, state).

        Raises:
            SSOError: If configuration is not SAML or not active.
        """
        if config.provider != SSOProvider.SAML:
            raise SSOError("Configuration is not SAML")

        if not config.is_active:
            raise SSOError("SSO is not active")

        # Create session for state management
        state = secrets.token_urlsafe(32)
        session = SSOSession(
            id=str(uuid.uuid4()),
            sso_config_id=config.id,
            state=state,
            relay_state=relay_state,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        self.db.add(session)
        await self.db.commit()

        # Build SAML AuthnRequest
        saml_config = config.get_config()
        saml_request = self._build_saml_authn_request(config, state)

        # Build redirect URL
        params = {
            "SAMLRequest": saml_request,
            "RelayState": state,
        }
        redirect_url = f"{saml_config['idp_sso_url']}?{urlencode(params)}"

        return redirect_url, state

    def _build_saml_authn_request(
        self, config: SSOConfiguration, state: str
    ) -> str:
        """Build SAML AuthnRequest.

        Note: In production, use python3-saml library for proper
        request generation with cryptographic signatures.

        Args:
            config: SAML configuration.
            state: Session state for request ID.

        Returns:
            Base64-encoded, deflate-compressed AuthnRequest.
        """
        import base64
        import zlib

        sp_entity_id = f"{self.base_url}/sso/saml/{config.connection_id}/metadata"
        sp_acs_url = f"{self.base_url}/sso/saml/{config.connection_id}/acs"

        saml_config = config.get_config()

        # Simplified AuthnRequest XML
        authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest
    xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="_{state}"
    Version="2.0"
    IssueInstant="{datetime.utcnow().isoformat()}Z"
    Destination="{saml_config['idp_sso_url']}"
    AssertionConsumerServiceURL="{sp_acs_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
</samlp:AuthnRequest>"""

        # Compress and encode (remove zlib header/checksum for DEFLATE)
        compressed = zlib.compress(authn_request.encode())[2:-4]
        encoded = base64.b64encode(compressed).decode()

        return encoded

    async def validate_saml_session(
        self, config: SSOConfiguration, state: str
    ) -> SSOSession:
        """Validate SAML session state.

        Args:
            config: SAML configuration.
            state: Session state from RelayState.

        Returns:
            Valid SSOSession.

        Raises:
            SSOSessionInvalidError: If session is invalid or expired.
        """
        result = await self.db.execute(
            select(SSOSession).where(
                SSOSession.state == state,
                SSOSession.sso_config_id == config.id,
            )
        )
        session = result.scalar_one_or_none()

        if not session or not session.is_valid():
            raise SSOSessionInvalidError("Invalid or expired SSO session")

        return session

    def parse_saml_response(
        self, saml_response: str, config: dict
    ) -> Dict[str, Any]:
        """Parse SAML response and extract attributes.

        Note: In production, use python3-saml for proper signature
        validation and security checks.

        Args:
            saml_response: Base64-encoded SAML response.
            config: Decrypted SAML configuration.

        Returns:
            Dict of user attributes.
        """
        import base64
        import xml.etree.ElementTree as ET

        # Decode response
        decoded = base64.b64decode(saml_response)
        root = ET.fromstring(decoded)

        # SAML namespaces
        ns = {
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        }

        attributes = {}

        # Extract AttributeStatement
        for attr in root.findall(".//saml:Attribute", ns):
            name = attr.get("Name")
            value_elem = attr.find("saml:AttributeValue", ns)
            if value_elem is not None and value_elem.text:
                attributes[name] = value_elem.text

        return attributes

    # -------------------------------------------------------------------------
    # OIDC Authentication
    # -------------------------------------------------------------------------

    async def initiate_oidc_login(
        self,
        config: SSOConfiguration,
        relay_state: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Initiate OIDC authentication flow.

        Creates an SSOSession and generates authorization URL.

        Args:
            config: OIDC configuration.
            relay_state: Optional URL to redirect to after auth.

        Returns:
            Tuple of (redirect_url, state).

        Raises:
            SSOError: If configuration is not OIDC or not active.
        """
        if config.provider != SSOProvider.OIDC:
            raise SSOError("Configuration is not OIDC")

        if not config.is_active:
            raise SSOError("SSO is not active")

        oidc_config = config.get_config()

        # Generate state and nonce for security
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        # Create session
        session = SSOSession(
            id=str(uuid.uuid4()),
            sso_config_id=config.id,
            state=state,
            nonce=nonce,
            relay_state=relay_state,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        self.db.add(session)
        await self.db.commit()

        # Get authorization endpoint
        auth_endpoint = oidc_config.get("authorization_endpoint")
        if not auth_endpoint:
            auth_endpoint = await self._discover_oidc_endpoint(
                oidc_config["issuer"], "authorization_endpoint"
            )

        # Build authorization URL
        redirect_uri = f"{self.base_url}/sso/oidc/{config.connection_id}/callback"

        params = {
            "response_type": "code",
            "client_id": oidc_config["client_id"],
            "redirect_uri": redirect_uri,
            "scope": " ".join(oidc_config.get("scopes", ["openid", "email", "profile"])),
            "state": state,
            "nonce": nonce,
        }

        redirect_url = f"{auth_endpoint}?{urlencode(params)}"

        return redirect_url, state

    async def validate_oidc_session(
        self, config: SSOConfiguration, state: str
    ) -> SSOSession:
        """Validate OIDC session state.

        Args:
            config: OIDC configuration.
            state: Session state from callback.

        Returns:
            Valid SSOSession with nonce.

        Raises:
            SSOSessionInvalidError: If session is invalid or expired.
        """
        result = await self.db.execute(
            select(SSOSession).where(
                SSOSession.state == state,
                SSOSession.sso_config_id == config.id,
            )
        )
        session = result.scalar_one_or_none()

        if not session or not session.is_valid():
            raise SSOSessionInvalidError("Invalid or expired SSO session")

        return session

    async def exchange_oidc_code(
        self, config: SSOConfiguration, code: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens.

        Args:
            config: OIDC configuration.
            code: Authorization code from callback.

        Returns:
            Token response dict with access_token, id_token, etc.

        Raises:
            SSOError: If token exchange fails.
        """
        import httpx

        oidc_config = config.get_config()

        token_endpoint = oidc_config.get("token_endpoint")
        if not token_endpoint:
            token_endpoint = await self._discover_oidc_endpoint(
                oidc_config["issuer"], "token_endpoint"
            )

        redirect_uri = f"{self.base_url}/sso/oidc/{config.connection_id}/callback"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": oidc_config["client_id"],
                    "client_secret": oidc_config["client_secret"],
                },
            )

        if response.status_code != 200:
            raise SSOError(f"Token exchange failed: {response.text}")

        return response.json()

    async def validate_oidc_token(
        self,
        config: SSOConfiguration,
        id_token: str,
        expected_nonce: str,
    ) -> Dict[str, Any]:
        """Validate and decode OIDC ID token.

        Args:
            config: OIDC configuration.
            id_token: JWT ID token.
            expected_nonce: Nonce from session.

        Returns:
            Decoded token claims.

        Raises:
            SSOError: If token validation fails.
        """
        import jwt
        from jwt import PyJWKClient

        oidc_config = config.get_config()

        # Get JWKS URI for key validation
        jwks_uri = oidc_config.get("jwks_uri")
        if not jwks_uri:
            jwks_uri = await self._discover_oidc_endpoint(
                oidc_config["issuer"], "jwks_uri"
            )

        # Get signing key from JWKS
        jwks_client = PyJWKClient(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        # Decode and validate token
        try:
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=oidc_config["client_id"],
                issuer=oidc_config["issuer"],
            )
        except jwt.InvalidTokenError as e:
            raise SSOError(f"Invalid ID token: {e}")

        # Validate nonce for replay attack prevention
        if claims.get("nonce") != expected_nonce:
            raise SSOError("Invalid nonce in ID token")

        return claims

    async def get_oidc_userinfo(
        self, config: SSOConfiguration, access_token: str
    ) -> Dict[str, Any]:
        """Get additional user info from userinfo endpoint.

        Args:
            config: OIDC configuration.
            access_token: OAuth access token.

        Returns:
            User info claims (may be empty if endpoint unavailable).
        """
        import httpx

        oidc_config = config.get_config()

        userinfo_endpoint = oidc_config.get("userinfo_endpoint")
        if not userinfo_endpoint:
            userinfo_endpoint = await self._discover_oidc_endpoint(
                oidc_config["issuer"], "userinfo_endpoint"
            )

        if not userinfo_endpoint:
            return {}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.status_code != 200:
            return {}

        return response.json()

    async def _discover_oidc_endpoint(
        self, issuer: str, endpoint: str
    ) -> Optional[str]:
        """Discover OIDC endpoint from well-known configuration.

        Args:
            issuer: OIDC issuer URL.
            endpoint: Endpoint key to retrieve.

        Returns:
            Endpoint URL if found, None otherwise.
        """
        import httpx

        discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(discovery_url)

            if response.status_code != 200:
                return None

            config = response.json()
            return config.get(endpoint)
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    async def complete_session(
        self,
        session: SSOSession,
        user_id: str,
        error: Optional[str] = None,
    ) -> None:
        """Mark SSO session as completed.

        Args:
            session: Session to complete.
            user_id: ID of authenticated user (or None if error).
            error: Optional error message.
        """
        session.completed_at = datetime.utcnow()
        session.user_id = user_id
        session.error_message = error
        await self.db.commit()

    # -------------------------------------------------------------------------
    # Service Provider Metadata
    # -------------------------------------------------------------------------

    def generate_sp_metadata(self, config: SSOConfiguration) -> str:
        """Generate SAML Service Provider metadata XML.

        Args:
            config: SAML configuration.

        Returns:
            SP metadata XML string.

        Raises:
            SSOError: If configuration is not SAML.
        """
        if config.provider != SSOProvider.SAML:
            raise SSOError("Not a SAML configuration")

        sp_entity_id = f"{self.base_url}/sso/saml/{config.connection_id}/metadata"
        sp_acs_url = f"{self.base_url}/sso/saml/{config.connection_id}/acs"
        sp_slo_url = f"{self.base_url}/sso/saml/{config.connection_id}/slo"

        metadata = f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{sp_entity_id}">
    <md:SPSSODescriptor
        AuthnRequestsSigned="false"
        WantAssertionsSigned="true"
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
        <md:AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{sp_acs_url}"
            index="0"
            isDefault="true"/>
        <md:SingleLogoutService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            Location="{sp_slo_url}"/>
    </md:SPSSODescriptor>
</md:EntityDescriptor>"""

        return metadata

    def get_sp_urls(self, config: SSOConfiguration) -> Dict[str, str]:
        """Get Service Provider URLs for SSO configuration.

        Args:
            config: SSO configuration.

        Returns:
            Dict with sp_entity_id, sp_acs_url, sp_slo_url, sp_metadata_url.
        """
        prefix = "saml" if config.provider == SSOProvider.SAML else "oidc"

        return {
            "sp_entity_id": f"{self.base_url}/sso/{prefix}/{config.connection_id}/metadata",
            "sp_acs_url": f"{self.base_url}/sso/saml/{config.connection_id}/acs",
            "sp_slo_url": f"{self.base_url}/sso/saml/{config.connection_id}/slo",
            "sp_metadata_url": f"{self.base_url}/sso/saml/{config.connection_id}/metadata",
            "callback_url": f"{self.base_url}/sso/oidc/{config.connection_id}/callback",
        }


# Export all service classes and exceptions
__all__ = [
    "SSOService",
    "SSOError",
    "SSOConfigNotFoundError",
    "SSOConfigExistsError",
    "SSOSessionInvalidError",
    "SSODomainNotAllowedError",
    "SSOProvisioningDisabledError",
]
