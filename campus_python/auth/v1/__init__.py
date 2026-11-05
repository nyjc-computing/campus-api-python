"""campus.python.auth

Campus Auth resource.
"""

from typing import Literal

from campus.common import env
import campus.model

from ... import errors
from ...interface import ResourceRoot
from ...json_client.interface import JsonClient
from . import (
    broker,
    clients,
    connections,
    credentials,
    grants,
    logins,
    oauth,
    root,
    sessionstore,
    sessions,
    users,
    vaults,
)
from .sessionstore import set_session_id_provider

class AuthRoot(ResourceRoot):
    """Campus Auth resource."""
    url_prefix: str = "/auth/v1"

    def __init__(self, json_client: JsonClient):
        super().__init__(json_client=json_client)
        self._broker = None
        self._clients = None
        self._connections = None
        self._credentials = None
        self._grants = None
        self._logins = None
        self._oauth = None
        self._root = None
        self._sessions = None
        self._users = None
        self._vaults = None

    @property
    def broker(self) -> broker.Broker:
        """Get the token broker resource."""
        if not self._broker:
            self._broker = broker.Broker(root=self)
        return self._broker

    @property
    def clients(self) -> clients.Clients:
        """Get the clients resource."""
        if not self._clients:
            self._clients = clients.Clients(root=self)
        return self._clients

    @property
    def connections(self) -> connections.Connections:
        """Get the connections resource."""
        if not self._connections:
            self._connections = connections.Connections(root=self)
        return self._connections

    @property
    def credentials(self) -> credentials.Credentials:
        """Get the credentials resource."""
        if not self._credentials:
            self._credentials = credentials.Credentials(root=self)
        return self._credentials

    @property
    def logins(self) -> logins.LoginSessions:
        """Get the logins resource."""
        if not self._logins:
            self._logins = logins.LoginSessions(root=self)
        return self._logins

    @property
    def oauth(self) -> oauth.OAuth:
        """Get the OAuth resource for device authorization flow."""
        if not self._oauth:
            self._oauth = oauth.OAuth(root=self)
        return self._oauth

    @property
    def root(self) -> root.Root:
        """Get the root resource."""
        if not self._root:
            self._root = root.Root(root=self)
        return self._root

    @property
    def sessions(self) -> sessions.CampusSessions:
        """Get the sessions resource."""
        if not self._sessions:
            self._sessions = sessions.CampusSessions(root=self)
        return self._sessions

    @property
    def users(self) -> users.Users:
        """Get the users resource."""
        if not self._users:
            self._users = users.Users(root=self)
        return self._users

    @property
    def grants(self) -> grants.Grants:
        """Get the access-grant store resource."""
        if not self._grants:
            self._grants = grants.Grants(root=self)
        return self._grants

    @property
    def vaults(self) -> vaults.Vaults:
        """Get the vaults resource."""
        if not self._vaults:
            self._vaults = vaults.Vaults(root=self)
        return self._vaults

    def exchange_code_for_token(
            self,
            code: str,
            redirect_uri: str
    ) -> campus.model.OAuthToken:
        """Exchange authorization code for access token.

        Makes POST request to /auth/v1/token which atomically:
        - Validates the authorization code
        - Gets or creates credentials for the user
        - Issues a new token or reuses existing valid token
        - Stores the token in credentials
        - Returns the token

        Note: Credential storage is handled automatically by the token endpoint.

        Args:
            code: The authorization code from OAuth callback
            redirect_uri: The redirect URI used in the auth session

        Returns:
            OAuthToken containing access token and metadata

        Raises:
            AuthenticationError: If code is invalid or token exchange fails
        """
        json_body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": env.CLIENT_ID,
            "client_secret": env.CLIENT_SECRET,
        }
        token_path = self.url_prefix + "/token"
        return campus.model.OAuthToken.from_resource(
            self._post_json(token_path, json=json_body)
        )

    def get_token(self) -> campus.model.OAuthToken:
        """Convenience method to get access token for a user.

        Re-acquires the login session user's campus bearer via
        POST /logins/<session_id>/token (campus#963/#964, invariant
        A10): one Basic-authenticated endpoint call in the
        session-bound lane — never the operator-gated credentials
        routes (#854). An expired grant token is rotated server-side,
        so the returned token is always live; the response carries no
        refresh token.

        Args:
            None

        Returns:
            OAuthToken for the user

        Raises:
            AuthenticationError: If no login session is present
            APIError: invalid_grant if the login session or the
                user's campus grant is gone — re-login required

        Example:
            # In a protected view that needs the user's token
            token = campus.auth.get_token()
            headers = {"Authorization": f"Bearer {token.id}"}
            response = requests.get("https://api.example.com/data", headers=headers)
        """
        return self.logins.token()

    def token(
            self,
            grant_type: Literal[
                "client_credentials",
                "refresh_token"
            ],
            *,
            refresh_token: str | None = None,
            client_id: str | None = None,
    ) -> campus.model.OAuthToken:
        """Get OAuth token from the token endpoint.

        Targets the RFC 6749 token endpoint (/auth/v1/oauth/token,
        campus/auth/routes/oauth.py), which serves the device_code,
        refresh_token, and client_credentials grants — NOT the
        authorization-code session endpoint at /auth/v1/token
        (campus/auth/provider.py), whose contract requires code and
        redirect_uri and rejects every other grant type (#60).

        The path passed to the client is relative (like every other
        resource method): CampusRequest._build_url() prepends the
        client's base_url itself, so an absolute URL here would be
        double-prefixed into `https://host/https://host/...` and 404
        against real deployments.

        Args:
            grant_type: "client_credentials" or "refresh_token".
            refresh_token: The refresh token to present (refresh_token
                grant).
            client_id: The OAuth client the grant is made as. The token
                endpoint requires client_id for every grant (campus
                auth/routes/oauth.py token()), including refresh_token;
                defaults to CLIENT_ID from the environment (server
                mode). Public clients without CLIENT_ID configured must
                pass it explicitly (issue #87).
        """
        json_body: dict[str, str] = {
            "grant_type": grant_type,
        }
        match grant_type:
            case "client_credentials":
                json_body["client_id"] = env.CLIENT_ID
                json_body["client_secret"] = env.CLIENT_SECRET
            case "refresh_token":
                if not refresh_token:
                    raise errors.AuthenticationError(
                        error_description="Refresh token required for "
                                          "refresh_token grant type."
                    )
                resolved_client_id = client_id or env.get("CLIENT_ID")
                if not resolved_client_id:
                    raise errors.AuthenticationError(
                        error_description="client_id is required for the "
                                          "refresh_token grant; pass it "
                                          "explicitly or set CLIENT_ID."
                    )
                json_body["client_id"] = resolved_client_id
                json_body["refresh_token"] = refresh_token

        token_path = self.url_prefix + "/oauth/token"
        return campus.model.OAuthToken.from_resource(
            self._post_json(token_path, json=json_body)
        )

    def refresh(
            self,
            stored: campus.model.OAuthToken,
            *,
            client_id: str | None = None,
    ) -> campus.model.OAuthToken:
        """Refresh an OAuth token pair (RFC 6749 section 6).

        Takes a stored token and returns the rotated pair issued by the
        server: a new access token with a new refresh token. The
        presented refresh token is single-use — refresh-token grants
        rotate server-side (campus/auth/routes/oauth.py
        _handle_refresh_token_grant) — so the returned token must be
        persisted before the stale one is presented again.

        This is the public-client entry point (issue #87): it needs no
        client secret, only the client_id the stored token was issued
        to. Error responses (invalid_grant, invalid_client, ...) raise
        APIError subclasses carrying the OAuth error code in details,
        readable via APIError.oauth_error.

        Args:
            stored: The stored OAuthToken whose refresh token is
                presented to the server.
            client_id: The OAuth client the token was issued to;
                defaults to CLIENT_ID from the environment (server
                mode).

        Returns:
            The refreshed OAuthToken (new access + refresh tokens).
        """
        if not stored.refresh_token:
            raise errors.AuthenticationError(
                error_description="Stored token has no refresh token; "
                                  "re-authentication is required."
            )
        return self.token(
            grant_type="refresh_token",
            refresh_token=stored.refresh_token,
            client_id=client_id,
        )
