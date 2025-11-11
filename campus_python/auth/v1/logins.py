"""campus.python.auth.v1.logins

Campus Auth logins resource (v1).

Provides a `Logins` collection for creating new login sessions and
accessing existing sessions by ID.
"""

from campus.common import env
import campus.model
import flask

from ...interface import JsonDict, Resource, ResourceCollection


class LoginSessions(ResourceCollection):
    """Campus Auth Logins resource."""
    path = "logins"

    @property
    def _session_key(self) -> str:
        provider = self.path.split("/")[-1]
        return f"{provider}_login_id"

    def __getitem__(
            self,
            session_id: str | None = None
    ) -> "LoginSessions.Login":
        """Get a login session resource by ID."""
        session_id = session_id or flask.session[self._session_key]
        assert session_id is not None, "No login session ID found"
        return LoginSessions.Login(session_id, parent=self)

    def from_session(self) -> campus.model.LoginSession:
        """Get a login session using the client-side session ID."""
        session_id = flask.session[self._session_key]
        return LoginSessions.Login(session_id, parent=self).get()

    def has_session(self) -> bool:
        """Check if there is a session ID stored in the flask session."""
        return self._session_key in flask.session

    def new(
            self,
            *,
            expiry_seconds: int,
            user_id: str,
            device_id: str | None = None,
            agent_string: str,
    ) -> campus.model.LoginSession:
        """Create a new login session.

        Mirrors the payload expected by the logins routes.
        """
        client_id = env.CLIENT_ID
        json_data: JsonDict = {
            "expiry_seconds": expiry_seconds,
            "client_id": str(client_id),
            "user_id": str(user_id),
            "agent_string": agent_string,
        }
        if device_id is not None:
            json_data["device_id"] = device_id

        resp = self.client.post(self.make_path(), json=json_data)
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        loginsession = campus.model.LoginSession.from_resource(resp.json())
        flask.session[self._session_key] = loginsession.id
        return campus.model.LoginSession.from_resource(resp.json())

    class Login(Resource):
        """A single login session resource."""

        @property
        def session_id(self) -> str:
            return self.path.split("/")[-1]

        def revoke(self) -> None:
            resp = self.client.delete(self.make_path())
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            del flask.session[self.session_id]

        def get(self) -> campus.model.LoginSession:
            resp = self.client.get(self.make_path())
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.LoginSession.from_resource(resp.json())

        def update(self, *, expiry_seconds: int) -> campus.model.LoginSession:
            resp = self.client.patch(
                self.make_path(),
                json={"expiry_seconds": expiry_seconds}
            )
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.LoginSession.from_resource(resp.json())
