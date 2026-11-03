"""campus.python.auth.v1.logins

Campus Auth logins resource (v1).

Provides a `Logins` collection for creating new login sessions and
accessing existing sessions by ID.
"""

from campus.common import env
import campus.model

from ... import errors
from ...interface import JsonDict, Resource, ResourceCollection
from . import sessionstore

# Client-side storage key for this resource's login-session id. The SDK
# does not touch any web-framework session store; hosts that keep the
# id in their own request state (flask_campus) use this key, and
# install a session-id provider (set_session_id_provider) so the
# resources below resolve ids without an explicit argument.
LOGIN_STORAGE_KEY = "logins_login_id"


class LoginSessions(ResourceCollection):
    """Campus Auth Logins resource."""
    path = "logins/"

    def __getitem__(
            self,
            session_id: str | None = None
    ) -> "LoginSessions.Login":
        """Get a login session resource by ID.

        Without an explicit ID, the id resolves from the installed
        session-id provider. There is no framework fallback: hosts
        without a provider must pass the id explicitly.
        """
        session_id = session_id or sessionstore.resolve_session_id(
            sessionstore.LANE_LOGIN
        )
        if not session_id:
            raise errors.AuthenticationError(
                error_description=(
                    "No login session ID available: pass session_id or "
                    "install a session-id provider "
                    "(campus_python.auth.v1.set_session_id_provider)."
                )
            )
        return LoginSessions.Login(session_id, parent=self)

    def from_session(
            self,
            session_id: str | None = None,
    ) -> campus.model.LoginSession:
        """Get a login session using a client-side session ID.

        Resolution order: explicit session_id > the installed
        session-id provider. There is no framework fallback.
        """
        return self[session_id].get()

    def has_session(self) -> bool:
        """True when the installed session-id provider supplies a login
        id for this lane."""
        return bool(sessionstore.resolve_session_id(sessionstore.LANE_LOGIN))

    def token(self, session_id: str | None = None) -> campus.model.OAuthToken:
        """Re-acquire the current login session's campus bearer (#117).

        One endpoint call (campus#964, invariant A10):
        POST /logins/<session_id>/token, authenticated by the client's
        Basic credentials plus the session id — user bearers are denied
        outright, so the caller must not present one (revoke_session()
        first mid-rotation). An expired grant token is rotated
        server-side; the response omits the refresh token.

        The session id resolves explicitly > installed provider.

        Raises:
            AuthenticationError: If no login session is present.
            APIError: invalid_grant when the session or the user's
                campus grant is gone — the cue to require re-login.
        """
        return self[session_id].token()

    def new(
            self,
            *,
            user_id: str,
            device_id: str | None = None,
            agent_string: str,
    ) -> campus.model.LoginSession:
        """Create a new login session.

        Mirrors the payload expected by the logins routes. Storing the
        returned session's id client-side is the host's business
        (flask_campus context owns its flask.session storage).
        """
        client_id = env.CLIENT_ID
        json_data: JsonDict = {
            "client_id": str(client_id),
            "user_id": str(user_id),
            "agent_string": agent_string,
        }
        if device_id is not None:
            json_data["device_id"] = device_id

        resp = self.client.post(self.make_path(), json=json_data)
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return campus.model.LoginSession.from_resource(resp.json())

    class Login(Resource):
        """A single login session resource."""

        @property
        def session_id(self) -> str:
            return self.path.rstrip("/").split("/")[-1]

        def revoke(self) -> None:
            resp = self.client.delete(
                self.make_path(end_slash=True)
            )
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()

        def get(self) -> campus.model.LoginSession:
            resp = self.client.get(
                self.make_path(end_slash=True)
            )
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.LoginSession.from_resource(resp.json())

        def update(self, *, expiry_seconds: int) -> campus.model.LoginSession:
            resp = self.client.patch(
                self.make_path(end_slash=True),
                json={"expiry_seconds": expiry_seconds}
            )
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.LoginSession.from_resource(resp.json())

        def token(self) -> campus.model.OAuthToken:
            """Re-acquire the session user's campus bearer (#117).

            POST /logins/<session_id>/token — the session-bound
            re-acquisition lane (campus#964, invariant A10): the login
            session plays the authorization code's role, authenticated
            with the client's Basic credentials. Issuance mirrors the
            code exchange: an unexpired grant token is reused, an
            expired one is minted fresh (rotated server-side), and a
            missing grant is an invalid_grant, never minted from
            nothing (C5). The response omits the refresh token —
            campus refresh material never leaves the auth service in
            this lane.

            The call presents Basic client credentials, never the
            ambient bearer: the route denies user principals outright
            (#963/A10), and with_user_session() nested inside another
            with_user_session() (e.g. an auth-broker release reached
            from a route that already holds the user session) would
            otherwise present the outer session's user token and be
            refused with 403. Any prior Authorization header is
            restored afterwards, so an enclosing session keeps its
            authorization until it re-runs use_token() with the fresh
            bearer.
            """
            # Canonical path has no trailing slash (route rule is
            # /<session_id>/token, unlike the CRUD subresources).
            prior_authorization = self.client.authorization
            self.client.reset_authorization()
            try:
                resp = self.client.post(
                    self.make_path("token")
                )
            finally:
                if prior_authorization is not None and prior_authorization.startswith(
                        "Bearer "):
                    self.client.set_bearer_authorization(
                        prior_authorization[len("Bearer "):]
                    )
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.OAuthToken.from_resource(resp.json())
