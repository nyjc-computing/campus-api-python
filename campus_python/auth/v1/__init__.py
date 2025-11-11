"""campus.python.auth

Campus Auth resource.
"""

import flask
import requests
import werkzeug

from campus.common.utils import uid

from ... import errors
from ...interface import ResourceRoot
from ...json_client.interface import JsonClient
from . import (
    clients,
    credentials,
    logins,
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
            redirect_uri: str,
            target: str,
    ) -> werkzeug.Response:
        """Begin an authorization flow.

        Returns a redirect response to the authorization endpoint.
        """
        auth_session = self.sessions.new(
            expiry_seconds=600,  # 10 minutes
            redirect_uri=redirect_uri,
            scopes=["campus.profile"],
            target=target,
        )
        base_url = self.base_url + "/auth/authorize"
        resp = requests.get(
            base_url,
            {
                "client_id": auth_session.client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": " ".join(auth_session.scopes),
                "state": auth_session.id,
                "hd": "nyjc.edu.sg",
            }
        )
        return flask.redirect(resp.url)

    def finalize(
            self,
            state: str,
            code: str,
            scope: str,
    ) -> werkzeug.Response:
        """Finalize an authorization flow.

        Returns a redirect response to the target.
        """
        auth_session = self.sessions.get(code=code)
        if auth_session.id != state:
            raise errors.AuthenticationError(
                error_description="State parameter does not match session ID."
            )
        if auth_session.user_id is None:
            raise errors.AuthenticationError(
                error_description="Unidentified user from auth session"
            )
        target = self.sessions[auth_session.id].finalize()
        self.users[auth_session.user_id]
        self.logins.new(
            expiry_seconds=86400 * 30,  # 30 days
            user_id=auth_session.user_id,
            device_id=uid.generate_category_uid("device", length=16),
            agent_string=flask.request.headers.get("User-Agent", ""),
        )
        return flask.redirect(target)

    def logout(self) -> None:
        """Logout the current user by revoking their login session."""
        flask.g.pop("user")
        flask.g.pop("device")
        if self.logins.has_session():
            login_session = self.logins[].get()
            self.logins[login_session.id].revoke()

    def push_context(self) -> None:
        """Push auth/login context to flask g."""
        if self.sessions.has_session():
            auth_session = self.sessions[].get()
            if auth_session.user_id:
                flask.g.user = self.users[auth_session.user_id].get()
        elif self.logins.has_session():
            login_session = self.logins[].get()
            flask.g.user = self.users[login_session.user_id].get()
            flask.g.device = login_session.device_id
