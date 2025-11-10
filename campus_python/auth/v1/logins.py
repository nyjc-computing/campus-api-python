"""campus.python.auth.v1.logins

Campus Auth logins resource (v1).

Provides a `Logins` collection for creating new login sessions and
accessing existing sessions by ID.
"""

from campus.common import env
import campus.model

from ...interface import JsonDict, Resource, ResourceCollection


class Logins(ResourceCollection):
    """Campus Auth Logins resource."""
    path = "logins"

    def __getitem__(self, session_id: str) -> "Logins.Login":
        """Get a login session resource by ID."""
        return Logins.Login(session_id, parent=self)

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

        resp = self.client.post(self.make_url(), json=json_data)
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return campus.model.LoginSession.from_resource(resp.json())

    class Login(Resource):
        """A single login session resource."""

        def delete(self) -> None:
            resp = self.client.delete(self.make_url())
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()

        def get(self) -> campus.model.LoginSession:
            resp = self.client.get(self.make_url())
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.LoginSession.from_resource(resp.json())

        def update(self, *, expiry_seconds: int) -> campus.model.LoginSession:
            resp = self.client.patch(
                self.make_url(),
                json={"expiry_seconds": expiry_seconds}
            )
            # Raise error if status code is not 2XX or 3XX
            resp.raise_for_status()
            return campus.model.LoginSession.from_resource(resp.json())
