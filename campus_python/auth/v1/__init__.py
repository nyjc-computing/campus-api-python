"""campus.python.auth

Campus Auth resource.
"""

from typing import Literal

import flask
import werkzeug

from campus.common import env
from campus.common.utils import uid
import campus.model

from ... import errors
from ...interface import ResourceRoot
from ...json_client.interface import JsonClient
from . import (
    clients,
    credentials,
    logins,
    oauth,
    root,
    sessions,
    users,
    vaults,
)


class AuthRoot(ResourceRoot):
    """Campus Auth resource."""
    url_prefix: str = "/auth/v1"

    def __init__(self, json_client: JsonClient):
        super().__init__(json_client=json_client)
        self._clients = None
        self._credentials = None
        self._logins = None
        self._oauth = None
        self._root = None
        self._sessions = None
        self._users = None
        self._vaults = None

    @property
    def clients(self) -> clients.Clients:
        """Get the clients resource."""
        if not self._clients:
            self._clients = clients.Clients(root=self)
        return self._clients

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
    def vaults(self) -> vaults.Vaults:
        """Get the vaults resource."""
        if not self._vaults:
            self._vaults = vaults.Vaults(root=self)
        return self._vaults

    def authorize(
            self,
            target: str,  # app URL
    ) -> werkzeug.Response:
        """Begin an authorization flow.

        Returns a redirect response to the authorization endpoint.

        IMPORTANT: This must return a redirect response directly (not use
        requests.get) to preserve the browser's user agent and cookies.
        If we use requests, Google detects a server user agent and switches
        to OAuth Lite flow which breaks in browsers (500 error).
        """
        from urllib.parse import urlencode

        # Use the app's own callback URL instead of going through campus proxy
        redirect_uri = target

        auth_session = self.sessions.new(
            redirect_uri=redirect_uri,
            scopes=["campus.profile"],
            target=target,
        )

        # Construct Campus OAuth Provider URL (using provider directly, not proxy)
        authorize_url = self.base_url + self.make_path("authorize")
        params = {
            "client_id": env.CLIENT_ID,
            "response_type": "code",  # OAuth2 authorization code flow
            "redirect_uri": redirect_uri,  # Callback URL after auth
            "state": auth_session.id,
        }
        full_url = f"{authorize_url}?{urlencode(params)}"

        # Return redirect to preserve browser user agent and cookies
        return flask.redirect(full_url)

    def finalize(
            self,
            state: str,
            code: str,
            scope: str,
    ) -> werkzeug.Response:
        """Finalize an authorization flow.

        Returns a redirect response to the target.
        """
        # 1. Validate auth session
        auth_session = self.sessions.from_code(code=code)
        if auth_session.id != state:
            raise errors.AuthenticationError(
                error_description="State parameter does not match session ID."
            )
        if auth_session.user_id is None:
            raise errors.AuthenticationError(
                error_description="Unidentified user from auth session"
            )

        # 2. Exchange authorization code for access token
        # This call to the token endpoint automatically stores credentials
        token = self._exchange_code_for_token(
            code=code,
            redirect_uri=auth_session.redirect_uri
        )

        # 3. Finalize session and get target
        target = self.sessions[auth_session.id].finalize()

        # 4. Ensure user exists
        self.users[auth_session.user_id]

        # 5. Create login session
        ls = self.logins.new(
            user_id=auth_session.user_id,
            device_id=uid.generate_category_uid("device", length=16),
            agent_string=flask.request.headers.get("User-Agent", ""),
        )

        # 6. Redirect to target
        return flask.redirect(target)

    def _exchange_code_for_token(
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
        resp = self.client.post(token_path, json=json_body)
        resp.raise_for_status()
        return campus.model.OAuthToken.from_resource(resp.json())

    def logout(self) -> None:
        """Logout the current user by revoking their login session."""
        flask.g.pop("user")
        flask.g.pop("device")
        if self.logins.has_session():
            login_session = self.logins.from_session()
            self.logins[login_session.id].revoke()

    def get_token(
            self,
            provider: str = "campus",
            user_id: str | None = None,
    ) -> campus.model.OAuthToken:
        """Get access token for a user.

        If user_id is not provided, uses the current logged-in user from
        the login session.

        This retrieves the user's credentials which includes their access token.
        Allows apps to get a fresh token without re-authenticating via OAuth
        if the user has a valid login session.

        Args:
            provider: Provider name (default: "campus")
            user_id: User ID (default: current logged-in user)

        Returns:
            OAuthToken for the user

        Raises:
            AuthenticationError: If no login session or no credentials found

        Example:
            # In a protected view that needs the user's token
            token = campus.auth.get_token()
            headers = {"Authorization": f"Bearer {token.id}"}
            response = requests.get("https://api.example.com/data", headers=headers)
        """
        # Get user_id from login session if not provided
        if user_id is None:
            if not self.logins.has_session():
                raise errors.AuthenticationError(
                    error_description="No login session found. User must log in first."
                )
            login_session = self.logins.from_session()
            user_id = login_session.user_id

        # Retrieve credentials for the user
        credentials = self.credentials[provider][user_id].get()

        if not credentials.token:
            raise errors.AuthenticationError(
                error_description=f"No token found for user {user_id} with provider {provider}"
            )

        # TODO: Auto-refresh if token is expired and refresh_token is available
        # For now, return the token as-is

        return credentials.token

    def push_context(self) -> None:
        """Push auth/login context to flask g."""
        flask.g.user = None
        flask.g.device = None

        # Try to load auth session if one exists
        if self.sessions.has_session():
            try:
                auth_session = self.sessions.from_session()
                if auth_session.user_id:
                    flask.g.user = self.users[auth_session.user_id].get()
            except errors.NotFoundError:
                # Session no longer exists on server (expired, restart, etc.)
                # Clear the stale session reference from Flask session
                if self.sessions._session_key in flask.session:
                    del flask.session[self.sessions._session_key]

        # Try to load login session if one exists
        elif self.logins.has_session():
            try:
                login_session = self.logins.from_session()
                flask.g.user = self.users[login_session.user_id].get()
                flask.g.device = login_session.device_id
            except errors.NotFoundError:
                # Login session no longer exists on server
                # Clear the stale session reference from Flask session
                if self.logins._session_key in flask.session:
                    del flask.session[self.logins._session_key]

    def token(
            self,
            grant_type: Literal[
                "client_credentials",
                "refresh_token"
            ],
            *,
            refresh_token: str | None = None,
    ) -> campus.model.OAuthToken:
        """Get OAuth token from the token endpoint."""
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
                json_body["refresh_token"] = refresh_token

        base_url = self.base_url + self.url_prefix + "/token"
        resp = self.client.post(base_url, json=json_body)
        resp.raise_for_status()
        return campus.model.OAuthToken.from_resource(resp.json())
